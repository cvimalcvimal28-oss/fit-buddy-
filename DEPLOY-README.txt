FitBuddy - Render upload bundle

Upload the contents of this ZIP to the ROOT of your GitHub repository. Keep
the app, templates, and static folders intact beside requirements.txt.

Render setup (create a Web Service, not a Blueprint):
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

Set these in Render's Environment settings:
SESSION_SECRET = a long random secret
COOKIE_SECURE = true
GOOGLE_API_KEY = optional; set privately in Render, never in GitHub
COACH_EMAILS = optional comma-separated coach email addresses

SQLite on a free web service is temporary; account data may disappear on
restart or redeploy. Configure persistent storage before storing real data.
Do not upload .env, fitbuddy.db, venv, or __pycache__.
