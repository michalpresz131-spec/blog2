# AllManiac Django

## Approved project scope

Create a Python/Django recreation of the public Allotment and Gardening
AllManiac blog in this workspace, based on
https://github.com/michalpresz131-spec/blog.

The user approved:

- Retaining the source blog's public reading and visitor submission experience.
- Holding visitor-submitted posts and comments for staff moderation.
- Requiring a signed-in Django staff account for moderation.
- Supporting approval, rejection, and deletion of posts and comments.
- Connecting application data to Turso, with credentials supplied through
  environment variables and never committed.
- Importing existing content if it is accessible; otherwise starting with an
  empty database.
- Retaining visit tracking and email notifications.
- Using the existing blog assets and configurable media storage without
  requiring Azure Blob Storage.

## Implementation

- Use Django templates and the existing site's styling and background image
  for the server-rendered public site.
- Use Django ORM models and migrations with the Django libSQL backend to
  connect to Turso using `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`.
- Provide public post and comment submission, post/comment likes, visit
  counting, and a staff-protected Django administration interface.
- Provide JSON import/export support for posts. No post data export or Turso
  credentials were supplied with the repository; do not claim that existing
  database content has been imported.
- Configure media storage via Django settings, with local media as the
  development default and an optional storage backend selected by environment.
- Configure email via environment-backed Django email settings; do not embed
  credentials.
- Include dependency declarations, environment-variable examples, setup and
  run instructions, and focused tests.

## Out of scope

- Azure deployment or mandatory Azure services.
- Committing secrets, real database credentials, or SMTP credentials.
- Claiming production Turso connectivity or content import until valid
  credentials are supplied and the connection is verified.
