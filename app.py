import logging
import os
import secrets
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

BASE_DIR = Path(__file__).resolve().parent
RESUME_DIRECTORY = BASE_DIR / "templates" / "resume"


def get_database_path() -> Path:
    """Choose a writable SQLite database location for local development.

    Change these environment-variable rules if messages move to another database service.
    """
    configured_path = os.getenv("DATABASE_PATH")
    if configured_path:
        return Path(configured_path)

    return BASE_DIR / "instance" / "portfolio.db"


DATABASE = get_database_path()
DATABASE_URL = os.getenv("DATABASE_URL")


def uses_postgres() -> bool:
    """Use PostgreSQL when a deployment supplies DATABASE_URL."""
    return bool(DATABASE_URL)


def get_db():
    # Import lazily so local SQLite development remains dependency-free.
    if uses_postgres():
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    # Keep both schemas aligned when adding persisted contact fields. PostgreSQL
    # uses BIGSERIAL, while SQLite uses its compatible AUTOINCREMENT syntax.
    create_messages_table = (
        """
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        if uses_postgres()
        else """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    with get_db() as conn:
        conn.execute(create_messages_table)


def create_app():
    # Keep all site-page routes together so new navigation pages are easy to register.
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_urlsafe(32),
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        # Store only a Werkzeug password hash in Render's ADMIN_PASSWORD_HASH variable.
        ADMIN_PASSWORD_HASH=os.getenv("ADMIN_PASSWORD_HASH"),
    )

    # Render terminates HTTPS at its proxy. This preserves the original request scheme.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    def csrf_token() -> str:
        """Return the session-bound token required by admin forms."""
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    def valid_csrf_token(submitted_token: str | None) -> bool:
        stored_token = session.get("csrf_token")
        return bool(stored_token and submitted_token and secrets.compare_digest(stored_token, submitted_token))

    def admin_required(view):
        """Require the short-lived authenticated session for private message views."""
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if not session.get("admin_authenticated"):
                flash("Please sign in to access messages.", "error")
                return redirect(url_for("admin_login"))
            return view(*args, **kwargs)

        return wrapped_view

    init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/projects")
    def projects():
        return render_template("projects.html")

    @app.route("/testimonials")
    def testimonials():
        return render_template("testimonials.html")

    @app.route("/faq")
    def faq():
        return render_template("faq.html")

    @app.route("/resume")
    def resume():
        return render_template("resume.html")

    @app.route("/resume/download")
    def download_resume():
        return send_from_directory(
            RESUME_DIRECTORY,
            "Nathaniel_Johnson_Resume.pdf",
            as_attachment=True,
        )

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        # The form field names must stay in sync with templates/contact.html.
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            subject = request.form.get("subject", "").strip()
            message = request.form.get("message", "").strip()

            # Update validation limits when the contact form fields or database schema changes.
            if not all([name, email, subject, message]):
                flash("Please complete all fields.", "error")
                return redirect(url_for("contact"))

            if "@" not in email or len(email) > 254:
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("contact"))

            if any(len(value) > limit for value, limit in ((name, 120), (subject, 200), (message, 5000))):
                flash("Your message is too long. Please shorten it and try again.", "error")
                return redirect(url_for("contact"))

            try:
                placeholders = "%s, %s, %s, %s" if uses_postgres() else "?, ?, ?, ?"
                with get_db() as conn:
                    conn.execute(
                        f"INSERT INTO messages (name, email, subject, message) VALUES ({placeholders})",
                        (name, email, subject, message),
                    )
            except Exception:
                app.logger.exception("Unable to save contact message")
                flash("Sorry, your message could not be saved. Please try again later.", "error")
                return redirect(url_for("contact"))

            flash("Thanks! Your message has been received.", "success")
            return redirect(url_for("contact"))

        return render_template("contact.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        """Authenticate the owner before exposing private contact submissions."""
        password_hash = app.config["ADMIN_PASSWORD_HASH"]
        if not password_hash:
            app.logger.error("ADMIN_PASSWORD_HASH is not configured")
            return render_template("admin_login.html", configured=False, csrf_token=csrf_token()), 503

        if request.method == "POST":
            if not valid_csrf_token(request.form.get("csrf_token")):
                flash("Your session expired. Please try again.", "error")
                return redirect(url_for("admin_login"))

            try:
                password_is_valid = check_password_hash(password_hash, request.form.get("password", ""))
            except ValueError:
                app.logger.error("ADMIN_PASSWORD_HASH has an invalid format")
                password_is_valid = False

            if password_is_valid:
                session.clear()
                session["admin_authenticated"] = True
                session.permanent = True
                csrf_token()
                return redirect(url_for("admin_messages"))

            flash("Invalid password.", "error")

        return render_template("admin_login.html", configured=True, csrf_token=csrf_token())

    @app.route("/admin/messages")
    @admin_required
    def admin_messages():
        """Display contact messages only after successful admin authentication."""
        try:
            with get_db() as conn:
                messages = conn.execute(
                    """SELECT id, name, email, subject, message, created_at
                       FROM messages ORDER BY created_at DESC"""
                ).fetchall()
        except Exception:
            app.logger.exception("Unable to retrieve contact messages")
            flash("Messages could not be loaded. Please try again later.", "error")
            messages = []

        return render_template("admin_messages.html", messages=messages, csrf_token=csrf_token())

    @app.route("/admin/logout", methods=["POST"])
    @admin_required
    def admin_logout():
        """End the private admin session; logout requires CSRF validation too."""
        if not valid_csrf_token(request.form.get("csrf_token")):
            flash("Your session expired. Please try again.", "error")
            return redirect(url_for("admin_messages"))

        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("admin_login"))

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    @app.errorhandler(413)
    def request_too_large(_error):
        # This response matches the MAX_CONTENT_LENGTH setting above.
        flash("Your submission is too large. Please try again with a shorter message.", "error")
        return redirect(url_for("contact"))

    @app.after_request
    def prevent_admin_caching(response):
        # Contact submissions must not be stored in browser or intermediary caches.
        if request.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
