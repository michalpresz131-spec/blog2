# Allotment and Gardening AllManiac

A server-rendered Django recreation of the public AllManiac gardening blog.
Visitors can read approved posts, submit posts and comments for staff review,
and like published posts and comments. Staff sign in to Django admin to approve,
reject, or delete submissions. The existing sunset background image is retained.

## Requirements

- Python 3.10 or later (the existing virtual environment is not modified)
- Turso credentials only when connecting to a hosted Turso database
- Optional S3-compatible media credentials when using remote media storage

## Local setup

From the project directory, activate the existing environment and install the
requirements:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The app loads settings from environment variables; Django does not read `.env`
automatically. Set the values in your terminal, or use your preferred local
environment loader. With both Turso variables blank, the app uses SQLite at
`db.sqlite3` for development and tests.

```powershell
$env:DJANGO_DEBUG = "true"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. The public site has no visitor sign-in. Staff
use `http://127.0.0.1:8000/admin/`; create staff credentials with
`createsuperuser`. Never expose the development server to the public internet.

## Turso/libSQL

`django-libsql` 0.1.3 is the available Django libSQL backend used by this
project. Set both variables to configure it:

```text
TURSO_DATABASE_URL=libsql://your-database-name.turso.io
TURSO_AUTH_TOKEN=your-token
```

Both settings are required together. If either is missing, startup fails with
an actionable configuration error; with neither set, local SQLite is selected.
The backend receives the URL and token from the environment, and credentials
are not committed. Run `python manage.py migrate` after configuring Turso.
This workspace did not include Turso credentials, so a live remote connection
or remote migration was not verified. The automated test suite runs against a
temporary SQLite database and does not need Turso.

## Submissions, moderation, and email

New posts and comments start in `pending` state and are never shown publicly
until approved. In Django admin, select one or more items and choose an
**Approve** or **Reject** action; the standard delete action removes them.
Email is sent to configured moderator addresses for new submissions and to
submitters after an approve/reject decision when they supplied an email.

Configure SMTP with `DJANGO_EMAIL_BACKEND`,
`DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`,
`DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, and
`DJANGO_DEFAULT_FROM_EMAIL`. Set `MODERATION_NOTIFICATION_EMAILS` to a
comma-separated list. Local development defaults to Django's console email
backend. Do not put real email credentials in source control.

The visit count tracks one visit per browser session per local calendar day.
Only a hash of a random session token is stored; client IP addresses are not
collected. Likes are likewise unique per browser session.

## Import and export

No posts JSON export or database credentials were present in the source
repository, so no existing posts were imported and no Turso data is claimed.
The commands support a JSON array or `{"posts": [...]}` using `title` and
`body` (or `content`) fields:

```powershell
python manage.py import_posts --file posts.json
python manage.py export_posts --file posts-export.json
```

Imports are approved by default (use `--status pending` to hold them for
review). Exports include approved posts by default; a staff operator should
only use `--include-unapproved` when intentionally exporting private pending or
rejected submissions. Uploaded image files are not embedded in JSON.

## Media storage

Uploads use local `MEDIA_ROOT` (default `media/`) unless
`MEDIA_STORAGE_BACKEND=s3` selects the optional S3-compatible Django storage
backend. Configure `AWS_STORAGE_BUCKET_NAME`, optionally `AWS_S3_REGION_NAME`
and `AWS_S3_ENDPOINT_URL`, and provide credentials through the standard AWS
environment variables. This does not require Azure Blob Storage.

For production, serve uploaded media via the configured storage and serve
static files with a production static-file server. Set `DJANGO_DEBUG=false`,
provide a strong `DJANGO_SECRET_KEY`, configure `DJANGO_ALLOWED_HOSTS`, and
use HTTPS and secure deployment settings before public hosting.

## Verification

```powershell
python manage.py check
python manage.py test
```
