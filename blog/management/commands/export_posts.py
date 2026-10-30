import json

from django.core.management.base import BaseCommand, CommandError

from blog.models import ModerationStatus, Post


class Command(BaseCommand):
    help = "Export blog posts to JSON. Approved posts are exported by default."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Destination JSON file path.")
        parser.add_argument(
            "--include-unapproved",
            action="store_true",
            help="Include pending and rejected submissions in the export.",
        )

    def handle(self, *args, **options):
        try:
            posts = Post.objects.defer("image_data").all()
            if not options["include_unapproved"]:
                posts = posts.filter(status=ModerationStatus.APPROVED)
            payload = {
                "posts": [
                    {
                        "slug": post.slug,
                        "title": post.title,
                        "body": post.body,
                        "author_name": post.author_name,
                        "status": post.status,
                        "created_at": post.created_at.isoformat(),
                    }
                    for post in posts.order_by("id")
                ]
            }
            with open(options["file"], "w", encoding="utf-8") as destination:
                json.dump(payload, destination, ensure_ascii=False, indent=2)
                destination.write("\n")
        except OSError as error:
            raise CommandError(f"Could not write post JSON: {error}") from error
        self.stdout.write(self.style.SUCCESS(f"Exported {len(payload['posts'])} post(s)."))
