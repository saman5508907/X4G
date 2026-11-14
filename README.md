# PayPilot

PayPilot is an MVP for small businesses to track customers, invoices, outstanding balances, and payment reminders.

## Features
- Account registration and login
- Dashboard with invoice totals
- Customer create/list/delete
- Invoice create/list/update/delete
- Overdue invoice status
- Copy-ready payment reminder message
- PostgreSQL on Railway, SQLite for local development

## Run locally
1. Install Python 3.11+
2. Create a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and set a long random `SECRET_KEY`.
5. Run: `uvicorn app.main:app --reload`
6. Open `http://127.0.0.1:8000`

## Deploy to Railway
1. Push the complete repository to GitHub.
2. In Railway, create a project and deploy from the GitHub repository.
3. Add a PostgreSQL database service.
4. In the web service variables, set `DATABASE_URL` to the PostgreSQL connection variable exposed by Railway (usually `${{Postgres.DATABASE_URL}}`).
5. Set `SECRET_KEY` to a long random value.
6. Railway uses the included Procfile. If needed, set the start command to:
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
7. Generate a Railway domain from the service settings.

## Important
This is an MVP foundation, not a finished regulated payment platform. It does not move money, connect to banks, or send emails automatically. Reminder text is generated locally and must be reviewed before sending. Before public launch, add CSRF protection, rate limiting, email verification, password reset, audit logs, backups, privacy/legal pages, and security testing. Do not enter real customer financial or personal data until those controls are implemented.
