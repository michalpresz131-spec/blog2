import base64
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connection, transaction
from django.db.models import Count
from django.utils.dateparse import parse_datetime

from blog.models import Comment, ModerationStatus, Post


API_BASE_URL = "https://poigogvk4u5zj2eiq2zkgumy4a0pvqnk.lambda-url.us-east-1.on.aws"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _read_url(path):
    request = Request(
        f"{API_BASE_URL}{path}",
        headers={"Accept": "application/json, image/*", "User-Agent": "AllManiacBlogImporter/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            body = response.read(MAX_IMAGE_BYTES + 1)
            if len(body) > MAX_IMAGE_BYTES:
                raise CommandError(f"Source response exceeded the size limit: {path}")
            return content_type, body
    except (OSError, URLError, TimeoutError) as error:
        raise CommandError(f"Could not fetch source data from {path}: {error}") from error


def _read_json(path):
    content_type, body = _read_url(path)
    if content_type != "application/json":
        raise CommandError(f"Expected JSON from source endpoint: {path}")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommandError(f"Source endpoint returned invalid JSON: {path}") from error


def _parse_date(value, item):
    parsed = parse_datetime(str(value))
    if parsed is None or parsed.utcoffset() is None:
        raise CommandError(f"Source {item} has an invalid or timezone-free date.")
    return parsed


def _retry_on_database_lock(operation):
    for attempt in range(6):
        try:
            return operation()
        except OperationalError as error:
            if "database is locked" not in str(error).lower() or attempt == 5:
                raise
            connection.close()
            time.sleep(min(0.25 * (2**attempt), 4))


def _save_post(item):
    post, created = Post.objects.get_or_create(
        legacy_source_id=item["source_id"],
        defaults={
            "title": item["title"],
            "body": item["body"],
            "author_name": "AllManiac",
            "status": ModerationStatus.APPROVED,
            "created_at": item["created_at"],
            "image_data": item["image_data"],
            "image_content_type": item["image_content_type"],
        },
    )
    if created:
        Post.objects.filter(pk=post.pk).update(
            created_at=item["created_at"],
            updated_at=item["created_at"],
        )
    elif item["image_data"] and not post.image_data:
        post.image_data = item["image_data"]
        post.image_content_type = item["image_content_type"]
        post.save(update_fields=["image_data", "image_content_type"])

    imported_comments = 0
    for source_comment in item["comments"]:
        comment, comment_created = Comment.objects.get_or_create(
            legacy_source_id=source_comment["source_id"],
            defaults={
                "post": post,
                "author_name": source_comment["author_name"],
                "body": source_comment["body"],
                "status": ModerationStatus.APPROVED,
                "created_at": source_comment["created_at"],
            },
        )
        if comment_created:
            Comment.objects.filter(pk=comment.pk).update(
                created_at=source_comment["created_at"]
            )
            imported_comments += 1
    return int(created), imported_comments


def _sync_legacy_likes(source_posts, dry_run):
    source_ids = [str(item["id"]) for item in source_posts]
    posts_by_source_id = Post.objects.in_bulk(source_ids, field_name="legacy_source_id")
    missing_posts = set(source_ids) - set(posts_by_source_id)
    if missing_posts:
        raise CommandError(
            f"Cannot map likes for {len(missing_posts)} source post(s); import the posts first."
        )

    updated_posts = []
    updated_comments = []
    seen_comment_ids = set()
    for item in source_posts:
        likes = item.get("likes")
        if not isinstance(likes, int) or isinstance(likes, bool) or likes < 0:
            raise CommandError(f"Source post {item['id']} has an invalid like count.")
        post = posts_by_source_id[str(item["id"])]
        if post.legacy_likes != likes:
            post.legacy_likes = likes
            updated_posts.append(post)

        expected_count = item.get("comment_count", 0)
        if not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 0:
            raise CommandError(f"Source post {item['id']} has an invalid comment count.")
        source_comments = (
            _read_json(f"/api/posts/{item['id']}/comments") if expected_count else []
        )
        if not isinstance(source_comments, list) or len(source_comments) != expected_count:
            raise CommandError(
                f"Expected {expected_count} comment(s) for source post "
                f"{item['id']}, received {len(source_comments) if isinstance(source_comments, list) else 'invalid data'}."
            )
        comment_ids = []
        for comment in source_comments:
            if not isinstance(comment, dict) or comment.get("id") is None:
                raise CommandError(f"Source post {item['id']} has an invalid comment.")
            source_comment_id = str(comment["id"])
            likes = comment.get("likes")
            if (
                source_comment_id in seen_comment_ids
                or not isinstance(likes, int)
                or isinstance(likes, bool)
                or likes < 0
            ):
                raise CommandError(f"Source comment {source_comment_id} has invalid data.")
            seen_comment_ids.add(source_comment_id)
            comment_ids.append((source_comment_id, likes))

        comments_by_source_id = Comment.objects.in_bulk(
            [comment_id for comment_id, _ in comment_ids],
            field_name="legacy_source_id",
        )
        missing_comments = {
            comment_id for comment_id, _ in comment_ids
        } - set(comments_by_source_id)
        if missing_comments:
            raise CommandError(
                f"Cannot map likes for {len(missing_comments)} source comment(s); "
                "import the comments first."
            )
        for source_comment_id, likes in comment_ids:
            comment = comments_by_source_id[source_comment_id]
            if comment.legacy_likes != likes:
                comment.legacy_likes = likes
                updated_comments.append(comment)

    if not dry_run:
        with transaction.atomic():
            Post.objects.bulk_update(updated_posts, ["legacy_likes"])
            Comment.objects.bulk_update(updated_comments, ["legacy_likes"])
    return len(updated_posts), len(updated_comments)


class Command(BaseCommand):
    help = "Import approved posts, comments, and images from the original AllManiac blog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and validate source data without writing to the database.",
        )
        parser.add_argument(
            "--likes-only",
            action="store_true",
            help="Import historical like totals for already-imported posts and comments.",
        )

    def handle(self, *args, **options):
        source_posts = _read_json("/api/posts")
        if not isinstance(source_posts, list):
            raise CommandError("The source posts endpoint did not return a JSON array.")
        if options["likes_only"]:
            if any(
                not isinstance(item, dict) or item.get("id") is None
                for item in source_posts
            ):
                raise CommandError("The source posts endpoint returned an invalid post.")
            if len({str(item["id"]) for item in source_posts}) != len(source_posts):
                raise CommandError("The source posts endpoint returned duplicate IDs.")
            post_count, comment_count = _sync_legacy_likes(
                source_posts, options["dry_run"]
            )
            action = "Would update" if options["dry_run"] else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} historical likes for {post_count} post(s) "
                    f"and {comment_count} comment(s)."
                )
            )
            return

        source_ids = {
            str(item["id"])
            for item in source_posts
            if isinstance(item, dict) and item.get("id") is not None
        }
        if len(source_ids) != len(source_posts):
            raise CommandError("The source posts endpoint returned duplicate or invalid IDs.")
        existing_posts = dict(
            Post.objects.filter(legacy_source_id__in=source_ids).values_list(
                "legacy_source_id", "image_content_type"
            )
        )
        comment_counts = dict(
            Comment.objects.filter(post__legacy_source_id__in=source_ids)
            .values("post__legacy_source_id")
            .annotate(total=Count("id"))
            .values_list("post__legacy_source_id", "total")
        )
        if (
            set(existing_posts) == source_ids
            and all(
                not item.get("has_image") or existing_posts[str(item["id"])]
                for item in source_posts
            )
            and all(
                comment_counts.get(str(item["id"]), 0) == item.get("comment_count", 0)
                for item in source_posts
            )
        ):
            self.stdout.write(self.style.SUCCESS("The source blog data is already imported."))
            return

        posts = []
        total_image_bytes = 0
        for item in source_posts:
            if not isinstance(item, dict) or item.get("id") is None:
                raise CommandError("The source posts endpoint returned an invalid post.")
            title = str(item.get("title") or "").strip()
            body = str(item.get("content") or "").strip()
            if not title or not body:
                raise CommandError(f"Source post {item['id']} is missing its title or content.")
            if len(title) > 180:
                raise CommandError(f"Source post {item['id']} has a title longer than 180 characters.")

            post = {
                "source_id": str(item["id"]),
                "title": title,
                "body": body,
                "created_at": _parse_date(item.get("date"), f"post {item['id']}"),
                "image_data": "",
                "image_content_type": "",
                "comments": [],
            }
            if item.get("has_image"):
                image_type, image_bytes = _read_url(f"/api/posts/{item['id']}/image")
                if image_type not in IMAGE_CONTENT_TYPES:
                    raise CommandError(
                        f"Source post {item['id']} has an unsupported image type: {image_type}"
                    )
                if not image_bytes:
                    raise CommandError(f"Source post {item['id']} has an empty image.")
                post["image_data"] = base64.b64encode(image_bytes).decode("ascii")
                post["image_content_type"] = image_type
                total_image_bytes += len(image_bytes)

            if item.get("comment_count", 0):
                source_comments = _read_json(f"/api/posts/{item['id']}/comments")
                if not isinstance(source_comments, list):
                    raise CommandError(
                        f"Comments for source post {item['id']} were not a JSON array."
                    )
                if len(source_comments) != item["comment_count"]:
                    raise CommandError(
                        f"Expected {item['comment_count']} comment(s) for source post "
                        f"{item['id']}, received {len(source_comments)}."
                    )
                for comment in source_comments:
                    if not isinstance(comment, dict) or comment.get("id") is None:
                        raise CommandError(
                            f"Source post {item['id']} has an invalid comment."
                        )
                    comment_body = str(comment.get("content") or "").strip()
                    if not comment_body:
                        raise CommandError(
                            f"Source comment {comment['id']} is missing its content."
                        )
                    post["comments"].append(
                        {
                            "source_id": str(comment["id"]),
                            "author_name": str(comment.get("author") or "Garden visitor").strip()[:80],
                            "body": comment_body,
                            "created_at": _parse_date(
                                comment.get("date"), f"comment {comment['id']}"
                            ),
                        }
                    )
            posts.append(post)

        comment_count = sum(len(post["comments"]) for post in posts)
        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Validated {len(posts)} post(s), {comment_count} comment(s), "
                    f"and {total_image_bytes} image bytes; database unchanged."
                )
            )
            return

        imported_posts = 0
        imported_comments = 0
        for item in posts:
            post_count, comment_count = _retry_on_database_lock(lambda: _save_post(item))
            imported_posts += post_count
            imported_comments += comment_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported_posts} new post(s) and {imported_comments} new comment(s); "
                f"stored {total_image_bytes} image bytes."
            )
        )
