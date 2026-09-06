# Nathaniel Johnson Portfolio

A Flask portfolio site with résumé downloads and a contact form that stores messages in SQLite.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000`.

For local development, the database is created at `instance/portfolio.db`.

## Deploy to Render

1. Push this repository to GitHub.
2. In Render, select **New > Blueprint** and choose the repository. Render reads `render.yaml` and creates the web service.
3. Deploy. Render automatically generates `SECRET_KEY`, serves the application with Gunicorn, checks `/health`, and mounts a persistent disk at `/var/data` for the contact-form database.

The included disk is required for contact messages to survive deploys and restarts. Render persistent disks require a paid web service; if you use a service without a disk, the site works but contact-form messages are temporary. For a no-disk production deployment, use a managed PostgreSQL database instead.

### Render environment variables

The Blueprint configures these automatically:

- `SECRET_KEY`: securely generated for Flask sessions and flash messages.
- `SESSION_COOKIE_SECURE=true`: restricts session cookies to HTTPS.
- `RENDER_DISK_PATH=/var/data`: stores SQLite data on Render's persistent disk.

To use another writable database location, set `DATABASE_PATH` to the complete SQLite file path.

## Production details

- Gunicorn is used instead of Flask's development server.
- Debug mode is disabled.
- A one-megabyte request limit and basic contact-form length validation are enabled.
- Reverse-proxy headers are handled for Render HTTPS.
- `/health` is available as a health check.
