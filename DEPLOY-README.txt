FitBuddy Render Web Service

Upload the ZIP contents to the GitHub repository root, preserving app/,
templates/, and static/ folders.
Build: pip install -r requirements.txt
Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT

In Render Environment, set SESSION_SECRET to a long random value and
COOKIE_SECURE=true. Set GOOGLE_API_KEY privately if using Gemini.
Password reset emails also require PUBLIC_BASE_URL (HTTPS), SMTP_HOST,
SMTP_PORT (usually 587), SMTP_USERNAME, SMTP_PASSWORD (app password), and
SMTP_FROM_EMAIL. Never commit those credentials.
SQLite on a free web service is temporary. Never upload .env, fitbuddy.db,
venv, or __pycache__.
