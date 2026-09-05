# Nathaniel Johnson — Flask Developer Portfolio

A modern, responsive developer portfolio built with Python and Flask.

## Features

- Responsive developer portfolio
- Home, About, Projects and Contact pages
- Project showcase
- Skills and technology sections
- SQLite database for contact messages
- Flash messages for form feedback
- Simple Flask architecture that is easy to extend
- Health-check endpoint at `/health`

## 1. Create a virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Run the application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

The SQLite database is created automatically the first time the app starts.

## Customize

Edit the content in:

- `templates/index.html`
- `templates/about.html`
- `templates/projects.html`
- `templates/contact.html`

Change styling in:

- `static/css/style.css`

Change interactive behavior in:

- `static/js/script.js`

Replace the placeholder profile image with your own image:

```text
static/images/profile.jpg
```

## Production note

Before deploying publicly, change `SECRET_KEY`, turn off Flask debug mode, and use a production WSGI server.
