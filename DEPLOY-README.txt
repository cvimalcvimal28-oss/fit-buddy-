FitBuddy - Render upload bundle

Upload the contents of this ZIP to the ROOT of your GitHub repository. Keep
the app, templates, and static folders intact beside requirements.txt.

Render Web Service:
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

Set SESSION_SECRET to a long random value and COOKIE_SECURE=true in Render.
Set GOOGLE_API_KEY privately in Render if using Gemini. Never commit secrets.
SQLite on a free web service is temporary and account data may disappear on
restart or redeploy. Do not upload .env, fitbuddy.db, venv, or __pycache__.
