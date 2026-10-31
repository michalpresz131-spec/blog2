import secrets

from django.core.validators import MaxLengthValidator
from django.db import models
from django.utils.text import slugify


class ModerationStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Post(models.Model):
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=210, unique=True, blank=True)
    body = models.TextField(validators=[MaxLengthValidator(20000)])
    author_name = models.CharField(max_length=80, default="Garden visitor")
    author_email = models.EmailField(blank=True)
    image = models.ImageField(upload_to="posts/%Y/%m/", blank=True)
    image_data = models.TextField(blank=True)
    image_content_type = models.CharField(max_length=100, blank=True)
    legacy_source_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:190] or "garden-story"
            candidate = base
            while Post.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base[:180]}-{secrets.token_hex(4)}"
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def likes_count(self):
        if hasattr(self, "annotated_likes_count"):
            return self.annotated_likes_count
        return self.likes.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author_name = models.CharField(max_length=80)
    author_email = models.EmailField(blank=True)
    body = models.TextField(validators=[MaxLengthValidator(4000)])
    legacy_source_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    status = models.CharField(
        max_length=10, choices=ModerationStatus.choices, default=ModerationStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post}"

    @property
    def likes_count(self):
        if hasattr(self, "annotated_likes_count"):
            return self.annotated_likes_count
        return self.likes.count()


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    visitor_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "visitor_key"], name="unique_post_like_per_visitor")
        ]


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="likes")
    visitor_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "visitor_key"], name="unique_comment_like_per_visitor"
            )
        ]


class Visit(models.Model):
    """A daily unique browser visit; store only a hash of a random session token."""

    visitor_key = models.CharField(max_length=64)
    day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["visitor_key", "day"], name="unique_daily_visitor")
        ]
