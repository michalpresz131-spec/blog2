import json

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from blog.models import ModerationStatus, Post


class Command(BaseCommand):
    help = "Import posts from a JSON array or an object containing a 'posts' array."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the JSON export file.")
        parser.add_argument(
            "--status",
            choices=[ModerationStatus.APPROVED, ModerationStatus.PENDING],
            default=ModerationStatus.APPROVED,
            help="Moderation status for imported content (default: approved).",
        )

    def handle(self, *args, **options):
        try:
            with open(options["file"], encoding="utf-8") as source:
                data = json.load(source)
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Could not read post JSON: {error}") from error

        entries = data.get("posts") if isinstance(data, dict) else data
        if not isinstance(entries, list):
            raise CommandError("Expected a JSON array or an object with a 'posts' array.")

        imported = 0
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                raise CommandError(f"Post #{index} must be a JSON object.")
            title = str(entry.get("title", "")).strip()
            body = str(entry.get("body", entry.get("content", ""))).strip()
            if not title or not body:
                raise CommandError(f"Post #{index} requires non-empty title and body/content.")
            slug = str(entry.get("slug") or slugify(title)).strip()[:210]
            values = {
                "title": title[:180],
                "body": body[:20000],
                "author_name": str(entry.get("author_name") or entry.get("author") or "Garden visitor")[:80],
                "author_email": str(entry.get("author_email") or "")[:254],
                "status": options["status"],
            }
            post = Post.objects.filter(slug=slug).first() if slug else None
            if post:
                for field, value in values.items():
                    setattr(post, field, value)
                post.save()
            else:
                Post.objects.create(slug=slug or None, **values)
            imported += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {imported} post(s)."))
