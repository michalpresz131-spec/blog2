from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Prefetch
from django.views.decorators.http import require_POST

from .forms import CommentSubmissionForm, PostSubmissionForm
from .models import Comment, CommentLike, ModerationStatus, Post, PostLike
from .notifications import notify_moderators
from .visitors import get_visitor_key, record_visit


def home(request, post_form=None):
    visit_count = record_visit(request)
    posts = (
        Post.objects.filter(status=ModerationStatus.APPROVED)
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=Comment.objects.filter(status=ModerationStatus.APPROVED).prefetch_related("likes"),
            )
        )
        .order_by("-created_at", "-id")
    )
    return render(
        request,
        "blog/home.html",
        {
            "posts": posts,
            "post_form": post_form or PostSubmissionForm(),
            "comment_form": CommentSubmissionForm(),
            "visit_count": visit_count,
        },
    )


@require_POST
def submit_post(request):
    form = PostSubmissionForm(request.POST, request.FILES)
    if not form.is_valid():
        return home(request, post_form=form)
    post = form.save(commit=False)
    post.status = ModerationStatus.PENDING
    post.save()
    notify_moderators("post", post)
    messages.success(request, "Thank you! Your post is awaiting staff review.")
    return redirect("blog:home")


@require_POST
def submit_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id, status=ModerationStatus.APPROVED)
    form = CommentSubmissionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please check the comment details and try again.")
        return redirect("blog:home")
    comment = form.save(commit=False)
    comment.post = post
    comment.status = ModerationStatus.PENDING
    comment.save()
    notify_moderators("comment", comment)
    messages.success(request, "Your comment is awaiting staff review.")
    return redirect("blog:home")


@require_POST
def like_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id, status=ModerationStatus.APPROVED)
    try:
        PostLike.objects.get_or_create(post=post, visitor_key=get_visitor_key(request))
    except IntegrityError:
        pass
    messages.info(request, "Thanks for showing this post some love.")
    return redirect("blog:home")


@require_POST
def like_comment(request, comment_id):
    comment = get_object_or_404(
        Comment.objects.select_related("post"),
        pk=comment_id,
        status=ModerationStatus.APPROVED,
        post__status=ModerationStatus.APPROVED,
    )
    try:
        CommentLike.objects.get_or_create(comment=comment, visitor_key=get_visitor_key(request))
    except IntegrityError:
        pass
    return redirect("blog:home")
