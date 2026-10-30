import json
import tempfile
from base64 import b64encode
from email.message import Message
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.db.backends.turso.driver import TursoCursorWrapper
from .models import Comment, CommentLike, ModerationStatus, Post, PostLike, Visit


class TursoCursorWrapperTests(SimpleTestCase):
    def test_execute_translates_positional_parameters(self):
        connection = _FakeTursoConnection()
        cursor = TursoCursorWrapper(connection)

        cursor.execute("SELECT id FROM items WHERE id = %s", (7,))

        self.assertEqual(
            connection.statements,
            [("SELECT id FROM items WHERE id = ?", [7], None, True)],
        )
        self.assertEqual(cursor.fetchone(), (7,))

    def test_execute_translates_named_parameters(self):
        connection = _FakeTursoConnection()
        cursor = TursoCursorWrapper(connection)

        cursor.execute(
            "SELECT id FROM items WHERE id = %(item_id)s", {"item_id": 7}
        )

        self.assertEqual(
            connection.statements,
            [
                (
                    "SELECT id FROM items WHERE id = :item_id",
                    None,
                    [(":item_id", 7)],
                    True,
                )
            ],
        )


class _FakeTursoConnection:
    row_factory = None

    def __init__(self):
        self.statements = []
        self.transaction_checks = []

    def _maybe_implicit_begin(self, sql):
        self.transaction_checks.append(sql)
        return None

    def _execute_stmt(
        self, sql, params=None, named_params=None, want_rows=True
    ):
        self.statements.append((sql, params, named_params, want_rows))
        return SimpleNamespace(
            columns=["id"],
            rows=[(7,)],
            affected_rows=1,
            last_insert_rowid=None,
        )


class HealthCheckTests(SimpleTestCase):
    def test_health_check_returns_ok_without_database_access(self):
        response = self.client.get("/healthz/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")


class LegacyPostImageTests(TestCase):
    def test_imported_image_is_served_for_approved_post(self):
        image_bytes = b"image bytes"
        post = Post.objects.create(
            title="Imported garden",
            body="A garden story.",
            image_data=b64encode(image_bytes).decode("ascii"),
            image_content_type="image/jpeg",
            legacy_source_id="legacy-post-1",
            status=ModerationStatus.APPROVED,
        )

        response = self.client.get(reverse("blog:post_image", args=[post.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response.content, image_bytes)
        self.assertContains(
            self.client.get(reverse("blog:home")),
            reverse("blog:post_image", args=[post.slug]),
        )


@override_settings(
    MODERATION_NOTIFICATION_EMAILS=["staff@example.test"],
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class BlogPublicFlowTests(TestCase):
    def setUp(self):
        self.post = Post.objects.create(
            title="Spring seedlings",
            body="Tomatoes are growing.",
            author_name="A gardener",
            status=ModerationStatus.APPROVED,
        )

    def test_home_shows_approved_content_and_hides_unmoderated_submissions(self):
        pending = Post.objects.create(title="Not public", body="Hidden text")
        response = self.client.get(reverse("blog:home"))
        self.assertContains(response, "Spring seedlings")
        self.assertNotContains(response, "Not public")
        self.assertNotContains(response, "Hidden text")
        self.assertEqual(response.context["posts"].count(), 1)
        self.assertEqual(Visit.objects.count(), 1)
        self.assertEqual(pending.status, ModerationStatus.PENDING)

    def test_post_submission_waits_for_review_and_emails_staff(self):
        response = self.client.post(
            reverse("blog:submit_post"),
            {
                "title": "New visitor story",
                "body": "A useful gardening tip.",
                "author_name": "Guest",
                "author_email": "guest@example.test",
                "website": "",
            },
        )
        self.assertRedirects(response, reverse("blog:home"))
        post = Post.objects.get(title="New visitor story")
        self.assertEqual(post.status, ModerationStatus.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["staff@example.test"])

    def test_visitor_comments_are_pending_and_hidden_until_approved(self):
        response = self.client.post(
            reverse("blog:submit_comment", args=[self.post.pk]),
            {
                "author_name": "Reader",
                "author_email": "",
                "body": "Lovely garden!",
                "website": "",
            },
        )
        self.assertRedirects(response, reverse("blog:home"))
        comment = Comment.objects.get(post=self.post)
        self.assertEqual(comment.status, ModerationStatus.PENDING)
        self.assertNotContains(self.client.get(reverse("blog:home")), "Lovely garden!")
        comment.status = ModerationStatus.APPROVED
        comment.save()
        self.assertContains(self.client.get(reverse("blog:home")), "Lovely garden!")

    def test_likes_are_unique_per_browser(self):
        url = reverse("blog:like_post", args=[self.post.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(PostLike.objects.filter(post=self.post).count(), 1)
        comment = Comment.objects.create(
            post=self.post, author_name="Reader", body="Nice!", status=ModerationStatus.APPROVED
        )
        comment_url = reverse("blog:like_comment", args=[comment.pk])
        self.client.post(comment_url)
        self.client.post(comment_url)
        self.assertEqual(CommentLike.objects.filter(comment=comment).count(), 1)

    def test_staff_admin_moderation_actions_approve_and_notify(self):
        pending = Post.objects.create(
            title="Review me", body="Pending content", author_email="writer@example.test"
        )
        staff = get_user_model().objects.create_superuser("staff", "staff@example.test", "safe-test-password")
        self.client.force_login(staff)
        response = self.client.post(
            reverse("admin:blog_post_changelist"),
            {"action": "approve_posts", "_selected_action": [pending.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, ModerationStatus.APPROVED)
        self.assertTrue(any("writer@example.test" in message.to for message in mail.outbox))

    def test_staff_can_reject_comments_and_notify_submitters(self):
        comment = Comment.objects.create(
            post=self.post,
            author_name="Reader",
            author_email="reader@example.test",
            body="Please review this.",
        )
        staff = get_user_model().objects.create_superuser(
            "moderator", "moderator@example.test", "safe-test-password"
        )
        self.client.force_login(staff)
        self.client.post(
            reverse("admin:blog_comment_changelist"),
            {"action": "reject_comments", "_selected_action": [comment.pk]},
            follow=True,
        )
        comment.refresh_from_db()
        self.assertEqual(comment.status, ModerationStatus.REJECTED)
        self.assertTrue(any("reader@example.test" in message.to for message in mail.outbox))

    def test_admin_requires_staff_authentication(self):
        response = self.client.get(reverse("admin:blog_post_changelist"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_visit_counter_does_not_count_refreshes_again_same_day(self):
        self.client.get(reverse("blog:home"))
        self.client.get(reverse("blog:home"))
        self.assertEqual(Visit.objects.count(), 1)


class PostImportExportTests(TestCase):
    def test_import_and_export_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            destination = Path(directory) / "output.json"
            source.write_text(
                json.dumps({"posts": [{"title": "Imported", "content": "Imported text"}]}),
                encoding="utf-8",
            )
            call_command("import_posts", file=str(source))
            post = Post.objects.get(title="Imported")
            self.assertEqual(post.status, ModerationStatus.APPROVED)
            call_command("export_posts", file=str(destination))
            exported = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(exported["posts"][0]["title"], "Imported")

    @patch("blog.management.commands.import_legacy_blog.urlopen")
    def test_legacy_import_preserves_image_and_comment_without_duplicates(self, urlopen):
        from blog.management.commands.import_legacy_blog import API_BASE_URL

        post_data = [
            {
                "id": 10,
                "title": "Original post",
                "content": "Original content",
                "date": "2024-06-01T10:00:00Z",
                "has_image": True,
                "comment_count": 1,
            }
        ]
        comment_data = [
            {
                "id": 20,
                "post_id": 10,
                "author": "Reader",
                "content": "Lovely garden.",
                "date": "2024-06-02T10:00:00Z",
            }
        ]
        image_bytes = b"legacy image"
        responses = {
            f"{API_BASE_URL}/api/posts": (json.dumps(post_data).encode(), "application/json"),
            f"{API_BASE_URL}/api/posts/10/comments": (
                json.dumps(comment_data).encode(),
                "application/json",
            ),
            f"{API_BASE_URL}/api/posts/10/image": (image_bytes, "image/jpeg"),
        }

        class FakeResponse:
            status = 200

            def __init__(self, body, content_type):
                self.body = body
                self.headers = Message()
                self.headers["Content-Type"] = content_type

            def read(self, size=-1):
                return self.body if size < 0 else self.body[:size]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        def fake_urlopen(request, timeout):
            body, content_type = responses[request.full_url]
            return FakeResponse(body, content_type)

        urlopen.side_effect = fake_urlopen
        output = StringIO()
        call_command("import_legacy_blog", stdout=output)
        call_command("import_legacy_blog", stdout=output)

        self.assertEqual(urlopen.call_count, 4)
        post = Post.objects.get(legacy_source_id="10")
        comment = Comment.objects.get(legacy_source_id="20")
        self.assertEqual(Post.objects.filter(legacy_source_id="10").count(), 1)
        self.assertEqual(Comment.objects.filter(legacy_source_id="20").count(), 1)
        self.assertEqual(post.image_data, b64encode(image_bytes).decode("ascii"))
        self.assertEqual(post.created_at.isoformat(), "2024-06-01T10:00:00+00:00")
        self.assertEqual(comment.post_id, post.pk)
        self.assertEqual(comment.body, "Lovely garden.")
