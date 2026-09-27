# FitBuddy — AI Fitness Plan Generator

FitBuddy generates a personalized 7-day workout plan using Google Gemini
models, adds a nutrition/recovery tip, and lets users submit feedback to get
an updated plan. Built with FastAPI, Jinja2, SQLite/SQLAlchemy, and the
Google Gemini API.

## Design

The responsive interface uses a deep charcoal and purple palette with
Bebas Neue display typography. The landing page guides members through a
personalized training card, while the plan view tracks completed sessions
in the browser on the current device. See `static/css/style.css` and
`static/js/app.js`.

When `GOOGLE_API_KEY` is configured, Gemini drafts the workout plan, nutrition
tip, and revisions based on member feedback. Built-in fallbacks keep the app
demonstrable when Gemini is unavailable; generated fitness guidance is a
starting point, not a substitute for professional medical advice.

Signed-in members can use `/diet-chat` for general balanced meal ideas. Chat
history is private to each account and can be cleared from the chat page. Gemini
replies require `GOOGLE_API_KEY`; without it, a clearly labeled general fallback
is shown. Avoid entering sensitive health details. The chat is not medical
advice, and individualized nutrition needs should be discussed with a qualified
clinician or registered dietitian.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your private settings:

```
GOOGLE_API_KEY=your_gemini_api_key_here
SESSION_SECRET=your_unique_random_secret
COOKIE_SECURE=false
```

Never commit the real `.env` file — it's already in `.gitignore`.
Generate a session secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
For production, use HTTPS and set `COOKIE_SECURE=true`.

### Email OTP, bot checks, and mobile verification

Password recovery sends a six-digit email OTP that expires after 30 minutes
and locks after five incorrect attempts. Gmail delivery uses SMTP; enable
2-Step Verification on the sender account and create a Google App Password.
Never use or share your regular Gmail password.

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
```

Cloudflare Turnstile protects login, registration, and reset-code requests.
Create a Turnstile site and add `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY`.
For production, set `REQUIRE_TURNSTILE=true`; missing keys then fail closed.
When `COOKIE_SECURE=true`, Turnstile and mobile OTP are required by default
unless their respective `REQUIRE_*` setting explicitly overrides that default.

To require a verified mobile number at new account registration and an SMS
second factor at each sign-in, configure a Twilio Verify service and set
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_VERIFY_SERVICE_SID`.
Set `REQUIRE_MOBILE_OTP=true` to require a phone number for new registrations
and every sign-in.
Existing members can sign in and enroll a number from the FitBuddy home page.
Numbers must be in international format (for example, `+14155552671`).

Add every setting as a private environment variable in Render; do not commit
real credentials. The Render Blueprint declares the required settings and
`REQUIRE_TURNSTILE=true`, so configure the real Turnstile keys, Twilio Verify,
and Gmail SMTP settings before deploying to production; without these, login
verification or code delivery will be blocked by design.

## Run

```bash
uvicorn app.main:app --reload
```

- App: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

The app runs without a Gemini key too — it falls back to a built-in sample
plan so the flow stays demonstrable offline.
Create an account at `/register` to begin; account passwords are stored
as salted PBKDF2 hashes, and workout pages require an active sign-in.

### Preview on a phone

`127.0.0.1` always means “this device,” so it will not open the computer's
website when entered on a phone. For a temporary design preview, connect both
devices to the same trusted Wi-Fi network, start the app so it listens on the
local network, and open `http://<computer-local-IP>:8000` on the phone:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find the computer's local IPv4 address with `ipconfig` on Windows. This local
HTTP preview is not encrypted; do not enter a real account password or expose
the port to the internet. For a shareable HTTPS preview, deploy the static
Netlify edition below. Use the Render blueprint if you need the FastAPI
account and database features.

## Publish on GitHub and deploy

### Netlify static edition

The repository includes a static Netlify edition in `netlify-site/`. To publish
it, push the repository to GitHub and in Netlify choose **Add new site → Import
an existing project**. Select the repository and let Netlify use `netlify.toml`;
it copies the shared CSS, JavaScript, and images into the publish directory.
The site is served from `netlify-site/`, not from the repository root, so the
FastAPI source and local SQLite database are not part of the published site.

This edition builds workout plans in the browser and saves plans, completion
marks, and feedback in that browser only. It does not provide accounts,
cross-device data, coach tools, shared feedback, or Gemini AI: those features
need a hosted backend and database. Do not add a Gemini key to the static site.
The existing FastAPI app remains available for local use and for a backend host
such as the Render configuration below.

### Render FastAPI edition

1. Create a repository on GitHub (choose **Public** if the source code should
   also be public), then from this project folder run:

   ```bash
   git init
   git add .
   git commit -m "Prepare FitBuddy for deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR-NAME/YOUR-REPOSITORY.git
   git push -u origin main
   ```

   `.env`, the local SQLite database, and virtual environments are excluded by
   `.gitignore`. Never add API keys to source code or GitHub.
2. For the included Blueprint, connect the repository and apply `render.yaml`.
   That configuration uses a paid web service and persistent disk for SQLite.
   For a free test deployment, create a Web Service manually instead; its
   filesystem is temporary, so do not rely on local SQLite for account storage.
3. When deployment finishes, open the public `*.onrender.com` URL. For a
   custom domain, add it in Render and follow its DNS/HTTPS instructions.

### Keeping logins and improving availability

If a member registered on a different deployment or on a free service whose
SQLite file was lost after a restart/redeploy, that account is not in the live
database, so its old password cannot sign in. Check the Render service's
**Events/Logs** and confirm you are using the same service URL where that
account was created. Do not ask members to send you passwords. With a fresh
database they must register again; with an existing account use password reset.

For account data to survive restarts and for multiple app instances to share
the same users, create a managed PostgreSQL database and set its private
connection string as `DATABASE_URL` in the Render Web Service environment.
The app accepts a standard `postgresql://` URL and uses SQLAlchemy connection
pooling. Switching from SQLite to PostgreSQL does not copy old accounts; migrate
the data safely or have members register again. Keep the same `SESSION_SECRET`
across all deploys/instances so sign-in cookies remain valid.

Render Free Web Services sleep after inactivity and may take about a minute to
wake, and local files are temporary. They are suitable for demos, not a promise
of high availability or unlimited concurrent users. For more simultaneous
traffic, use an always-on paid instance, managed PostgreSQL, and increase
`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` only within the database provider's connection
limit. Configure Render's health check path as `/healthz`.

Before publishing, replace any API key that has been shared in chat or other
public places. Configure SMTP, Twilio, and Turnstile credentials privately in
Render for email recovery, SMS sign-in verification, and bot protection.

## Routes

| Route              | Method | Purpose                              |
|---------------------|--------|----------------------------------------|
| `/login`            | GET/POST | Email and password sign-in              |
| `/forgot-password`  | GET/POST | Request a one-time email recovery code |
| `/reset-password`   | GET/POST | Validate the email code and set a new password |
| `/register`         | GET/POST | Create an account and profile            |
| `/verify-mobile`    | GET/POST | Verify the SMS code during registration or sign-in |
| `/verify-mobile/enroll` | GET/POST | Verify a phone for an existing member |
| `/logout`           | POST   | Sign out                               |
| `/`                 | GET    | Member training card (sign-in required)|
| `/generate-workout` | POST   | Generates the 7-day plan + tip         |
| `/submit-feedback`  | POST   | Revises a member's plan from feedback   |
| `/feedback`         | GET/POST | Collects member experience feedback      |
| `/feedback-inbox`   | GET    | Private member feedback inbox for the designated account |
| `/diet-chat`        | GET/POST | Private general meal-planning chat (Gemini when configured) |

## Project Structure

```
FitBuddy/
├── app/
│   ├── auth.py
│   ├── main.py
│   ├── routes.py
│   ├── gemini_generator.py
│   ├── gemini_flash_generator.py
│   ├── updated_plan.py
│   ├── database.py
│   ├── password_reset.py
│   ├── verification.py
│   └── models.py
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── result.html
│   ├── feedback.html
├── static/
│   ├── css/style.css, netlify.css
│   ├── js/app.js, netlify-app.js
│   └── images/fitbuddy-logo.png
├── netlify-site/
│   └── index.html
├── netlify.toml
├── requirements.txt
├── render.yaml
├── .env.example
├── .gitignore
└── README.md
```
