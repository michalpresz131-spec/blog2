from django.urls import path

from . import views

app_name = "blog"
urlpatterns = [
    path("", views.home, name="home"),
    path("submit/", views.submit_post, name="submit_post"),
    path("posts/<int:post_id>/comments/", views.submit_comment, name="submit_comment"),
    path("posts/<int:post_id>/like/", views.like_post, name="like_post"),
    path("comments/<int:comment_id>/like/", views.like_comment, name="like_comment"),
]
