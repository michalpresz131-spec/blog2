# AllManiac Django integration hand-off

- Backend: workspace root; `python manage.py runserver 127.0.0.1:8000`; SQLite by default, Turso via `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`; health URL `/`; build/check: `python manage.py check`.
- Frontend: server-rendered Django templates in `templates/blog/home.html`; static styling `static/allmaniac/site.css`; dev command `python manage.py runserver`; no separate frontend build or API client.
- API seam / mock files: none; server-rendered frontend uses Django views directly. No mock data files.
- Routes: `GET /`; `POST /submit/`; `POST /posts/<post_id>/comments/`; `POST /posts/<post_id>/like/`; `POST /comments/<comment_id>/like/`; staff admin `/admin/`.
- Database: Turso/libSQL using verified `django-libsql==0.1.3`, or local SQLite without credentials. Migration tool: Django migrations in `blog/migrations/`; env vars `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. Schema only; **NO seed data**.
- Shared types: Django ORM models in `blog/models.py`; no separate shared package.
- Services: Django web application (Essential); S3-compatible media storage and SMTP email (optional Enhancements).
- Source content: no source JSON export or Turso credentials supplied; no import has been claimed. `import_posts` / `export_posts` management commands are provided for operator-supplied JSON.
