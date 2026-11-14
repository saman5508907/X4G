# PayPilot

PayPilot is an early-stage invoice and customer tracking app for small businesses.

## Included
- Account registration and login
- Argon2 password hashing
- Signed, HTTP-only session cookie
- CSRF protection on state-changing forms
- Per-account data isolation
- Customer and invoice tracking
- Copy-ready payment reminder text
- PostgreSQL support for Railway and SQLite for local development
- Security response headers

## Deploy on Railway
1. Push this complete repository to GitHub.
2. In Railway, create a project and choose **Deploy from GitHub repo**.
3. Add a PostgreSQL service to the Railway project.
4. In the web service variables, add:
   - `APP_ENV=production`
   - `SECRET_KEY` = a long random secret (at least 32 characters)
   - `DATABASE_URL` = reference the PostgreSQL service's `DATABASE_URL`
   - `ALLOWED_HOSTS` = your Railway domain, and your custom domain if used
5. Redeploy. Railway uses the included `Procfile`.

Never commit `.env`, real passwords, customer data, or production credentials.

## Local run
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# For local testing, set APP_ENV=development and set a long random SECRET_KEY.
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## Important limitations before real commercial use
This is a secure-minded MVP foundation, not a security certification. Before handling real customer or financial data, add automated tests, database migrations (Alembic), persistent backups and restore drills, account recovery, email verification, login throttling/WAF, audit logs, privacy/terms pages, monitoring, and an independent security review. Payment collection and automatic email sending are intentionally not implemented.
