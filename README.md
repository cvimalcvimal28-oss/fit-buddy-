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

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your real key:

```
GOOGLE_API_KEY=your_gemini_api_key_here
SESSION_SECRET=your_unique_random_secret
COOKIE_SECURE=false
COACH_EMAILS=coach@example.com
```

Never commit the real `.env` file — it's already in `.gitignore`.
Generate a session secret with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
For production, use HTTPS and set `COOKIE_SECURE=true`. `COACH_EMAILS` is an
optional comma-separated allowlist for the coach roster; the roster is
disabled when it is empty.

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
2. In Render, choose **New → Blueprint**, connect the GitHub repository, and
   apply the included `render.yaml`. Add `GOOGLE_API_KEY` as a secret and set
   `COACH_EMAILS` to your coach login in the Render dashboard. The blueprint
   uses a persistent disk for SQLite; that requires a Render plan that
   supports disks.
3. When deployment finishes, open the public `*.onrender.com` URL. For a
   custom domain, add it in Render and follow its DNS/HTTPS instructions.

Before publishing, replace any API key that has been shared in chat or other
public places. For a larger production audience, move from SQLite to a managed
database and add account recovery and login rate limiting.

## Routes

| Route              | Method | Purpose                              |
|---------------------|--------|----------------------------------------|
| `/login`            | GET/POST | Email and password sign-in              |
| `/register`         | GET/POST | Create an account and profile            |
| `/logout`           | POST   | Sign out                               |
| `/`                 | GET    | Member training card (sign-in required)|
| `/generate-workout` | POST   | Generates the 7-day plan + tip         |
| `/submit-feedback`  | POST   | Revises a member's plan from feedback   |
| `/feedback`         | GET/POST | Collects member experience feedback      |
| `/view-all-users`   | GET    | Coach roster (coach email allowlist)     |

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
│   └── models.py
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── result.html
│   ├── feedback.html
│   └── all_users.html
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
