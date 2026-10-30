import hashlib
import secrets

from django.utils import timezone

from .models import Visit


def get_visitor_key(request):
    token = request.session.get("blog_visitor_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["blog_visitor_token"] = token
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def record_visit(request):
    Visit.objects.get_or_create(visitor_key=get_visitor_key(request), day=timezone.localdate())
    return Visit.objects.count()
