import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Comment, CommentLike, ModerationStatus, Post, PostLike, Visit


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
