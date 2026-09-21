import logging
import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

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

        return psycopg.connect(DATABASE_URL)

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
    )

    # Render terminates HTTPS at its proxy. This preserves the original request scheme.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    @app.errorhandler(413)
    def request_too_large(_error):
        # This response matches the MAX_CONTENT_LENGTH setting above.
        flash("Your submission is too large. Please try again with a shorter message.", "error")
        return redirect(url_for("contact"))

    return app


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
