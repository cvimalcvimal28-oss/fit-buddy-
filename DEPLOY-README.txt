FitBuddy Render Web Service

Upload the ZIP contents to the GitHub repository root, preserving the app/,
templates/, and static/ folders.

Build command: pip install -r requirements.txt
Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check: /healthz

Set these privately in Render Environment before deploying:
- SESSION_SECRET: long random value; keep it stable between deploys
- COOKIE_SECURE=true
- REQUIRE_TURNSTILE=true
- REQUIRE_MOBILE_OTP=true
- TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY from Cloudflare
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID
- SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USERNAME, SMTP_PASSWORD,
  SMTP_FROM_EMAIL
- GOOGLE_API_KEY (optional, for Gemini features)

Use a Google App Password for SMTP, never your normal Gmail password.
Create a Twilio Verify service for SMS. Turnstile and Twilio are required by
the included Render Blueprint. Do not start serving sign-ins until all their
credentials are set. Existing accounts without a verified mobile number will
be asked to enroll one at their next sign-in.

The Blueprint uses persistent-disk SQLite. For multi-instance scaling, use
managed PostgreSQL and set DATABASE_URL to its private connection string.
Free web services may sleep and have temporary local files; they are for demos,
not a high-availability or unlimited-traffic promise.

Never upload .env, fitbuddy.db, venv, __pycache__, or credentials.
