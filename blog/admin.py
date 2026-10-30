from django.contrib import admin, messages

from .models import Comment, CommentLike, ModerationStatus, Post, PostLike, Visit
from .notifications import notify_submitter


def _moderate(queryset, status):
    for item in queryset:
        if item.status == status:
            continue
        item.status = status
        item.save(update_fields=["status"])
        notify_submitter(item, status)


@admin.action(description="Approve selected posts and notify authors")
def approve_posts(modeladmin, request, queryset):
    _moderate(queryset, ModerationStatus.APPROVED)
    modeladmin.message_user(request, "Selected posts approved.", messages.SUCCESS)


@admin.action(description="Reject selected posts and notify authors")
def reject_posts(modeladmin, request, queryset):
    _moderate(queryset, ModerationStatus.REJECTED)
    modeladmin.message_user(request, "Selected posts rejected.", messages.WARNING)


@admin.action(description="Approve selected comments and notify authors")
def approve_comments(modeladmin, request, queryset):
    _moderate(queryset, ModerationStatus.APPROVED)
    modeladmin.message_user(request, "Selected comments approved.", messages.SUCCESS)


@admin.action(description="Reject selected comments and notify authors")
def reject_comments(modeladmin, request, queryset):
    _moderate(queryset, ModerationStatus.REJECTED)
    modeladmin.message_user(request, "Selected comments rejected.", messages.WARNING)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author_name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "body", "author_name", "author_email")
    readonly_fields = ("created_at", "updated_at")
    actions = (approve_posts, reject_posts)

    def get_queryset(self, request):
        return super().get_queryset(request).defer("image_data")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author_name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("body", "author_name", "author_email", "post__title")
    readonly_fields = ("created_at",)
    actions = (approve_comments, reject_comments)


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("day", "created_at")
    list_filter = ("day",)
    search_fields = ()
    ordering = ("-day",)


admin.site.site_header = "AllManiac blog moderation"
admin.site.site_title = "AllManiac administration"
admin.site.index_title = "Review visitor submissions"
