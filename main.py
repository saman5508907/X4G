import os, re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from .config import SECRET_KEY, COOKIE_SECURE, ALLOWED_HOSTS, SESSION_MAX_AGE, APP_ENV
from .database import Base, engine, get_db
from .models import User, Customer, Invoice
from .security import hash_password, verify_password, csrf_token, require_csrf

if len(SECRET_KEY) < 32:
    if APP_ENV == "production":
        raise RuntimeError("SECRET_KEY must be at least 32 characters in production.")
    SECRET_KEY = "dev-only-change-this-secret-key-before-deploying-123456"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="PayPilot", docs_url=None if APP_ENV == "production" else "/docs",
              redoc_url=None, openapi_url=None if APP_ENV == "production" else "/openapi.json")
if ALLOWED_HOSTS != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="paypilot_session",
                   max_age=SESSION_MAX_AGE, same_site="lax", https_only=COOKIE_SECURE)
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; script-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

def page(request, name, **context):
    return templates.TemplateResponse(request=request, name=name,
        context={"csrf": csrf_token(request), "user": request.session.get("email"), **context})

def current_user(request: Request, db: Session) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=401)
    user = db.get(User, int(uid))
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401)
    return user

def require_user(request: Request, db: Session):
    try:
        return current_user(request, db)
    except HTTPException:
        return None

def redirect(path):
    return RedirectResponse(path, status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    if require_user(request, db):
        return redirect("/dashboard")
    return page(request, "landing.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return page(request, "auth.html", mode="register", error=None)

@app.post("/register")
async def register(request: Request, email: str = Form(...), password: str = Form(...),
                   db: Session = Depends(get_db)):
    await require_csrf(request)
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        return page(request, "auth.html", mode="register", error="ایمیل معتبر وارد کنید.")
    if len(password) < 12 or len(password) > 128:
        return page(request, "auth.html", mode="register", error="رمز عبور باید حداقل ۱۲ و حداکثر ۱۲۸ کاراکتر باشد.")
    if db.scalar(select(User).where(User.email == email)):
        return page(request, "auth.html", mode="register", error="این ایمیل قبلاً ثبت شده است.")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user); db.commit(); db.refresh(user)
    request.session.clear()
    request.session["uid"] = user.id
    request.session["email"] = user.email
    csrf_token(request)
    return redirect("/dashboard")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return page(request, "auth.html", mode="login", error=None)

@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...),
                db: Session = Depends(get_db)):
    await require_csrf(request)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        return page(request, "auth.html", mode="login", error="ایمیل یا رمز عبور اشتباه است.")
    request.session.clear()
    request.session["uid"] = user.id
    request.session["email"] = user.email
    csrf_token(request)
    return redirect("/dashboard")

@app.post("/logout")
async def logout(request: Request):
    await require_csrf(request)
    request.session.clear()
    return redirect("/")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if not user: return redirect("/login")
    invoices = db.scalars(select(Invoice).options(joinedload(Invoice.customer))
                          .where(Invoice.owner_id == user.id).order_by(Invoice.id.desc()).limit(8)).all()
    customers_count = db.scalar(select(func.count(Customer.id)).where(Customer.owner_id == user.id)) or 0
    total = db.scalar(select(func.coalesce(func.sum(Invoice.amount), 0)).where(Invoice.owner_id == user.id)) or 0
    unpaid = db.scalar(select(func.coalesce(func.sum(Invoice.amount), 0)).where(
        Invoice.owner_id == user.id, Invoice.status == "unpaid")) or 0
    return page(request, "dashboard.html", invoices=invoices, customers_count=customers_count,
                 total=total, unpaid=unpaid)

@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if not user: return redirect("/login")
    rows = db.scalars(select(Customer).where(Customer.owner_id == user.id).order_by(Customer.id.desc())).all()
    return page(request, "customers.html", customers=rows, error=None)

@app.post("/customers")
async def add_customer(request: Request, name: str = Form(...), email: str = Form(""),
                        company: str = Form(""), db: Session = Depends(get_db)):
    await require_csrf(request)
    user = require_user(request, db)
    if not user: return redirect("/login")
    name = name.strip()
    if not name or len(name) > 120 or len(email) > 254 or len(company) > 120:
        raise HTTPException(400, "اطلاعات واردشده معتبر نیست.")
    db.add(Customer(owner_id=user.id, name=name, email=email.strip(), company=company.strip()))
    db.commit()
    return redirect("/customers")

@app.post("/customers/{customer_id}/delete")
async def delete_customer(customer_id: int, request: Request, db: Session = Depends(get_db)):
    await require_csrf(request)
    user = require_user(request, db)
    if not user: return redirect("/login")
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.owner_id == user.id))
    if customer:
        db.delete(customer); db.commit()
    return redirect("/customers")

@app.get("/invoices/new", response_class=HTMLResponse)
def invoice_form(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if not user: return redirect("/login")
    customers = db.scalars(select(Customer).where(Customer.owner_id == user.id).order_by(Customer.name)).all()
    return page(request, "invoice_form.html", customers=customers, error=None)

@app.post("/invoices")
async def create_invoice(request: Request, customer_id: int = Form(...), description: str = Form(...),
                         amount: str = Form(...), currency: str = Form("USD"),
                         due_date: str = Form(...), db: Session = Depends(get_db)):
    await require_csrf(request)
    user = require_user(request, db)
    if not user: return redirect("/login")
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.owner_id == user.id))
    if not customer: raise HTTPException(404, "مشتری پیدا نشد.")
    try:
        value = Decimal(amount)
        due = date.fromisoformat(due_date)
    except (InvalidOperation, ValueError):
        raise HTTPException(400, "مبلغ یا تاریخ معتبر نیست.")
    if not value.is_finite() or value <= 0 or value > Decimal("9999999999.99"):
        raise HTTPException(400, "مبلغ باید مثبت و در محدوده مجاز باشد.")
    if currency not in {"USD", "EUR", "GBP"}: raise HTTPException(400, "ارز انتخابی معتبر نیست.")
    description = description.strip()
    if not description or len(description) > 180: raise HTTPException(400, "شرح فاکتور معتبر نیست.")
    count = db.scalar(select(func.count(Invoice.id)).where(Invoice.owner_id == user.id)) or 0
    number = f"PP-{user.id:04d}-{count+1:06d}"
    db.add(Invoice(owner_id=user.id, customer_id=customer.id, number=number,
                   description=description, amount=value, currency=currency,
                   due_date=due.isoformat(), status="unpaid"))
    db.commit()
    return redirect("/dashboard")

@app.post("/invoices/{invoice_id}/paid")
async def mark_paid(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    await require_csrf(request)
    user = require_user(request, db)
    if not user: return redirect("/login")
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == user.id))
    if invoice:
        invoice.status = "paid"; db.commit()
    return redirect("/dashboard")

@app.get("/invoices/{invoice_id}/reminder", response_class=HTMLResponse)
def reminder(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    if not user: return redirect("/login")
    invoice = db.scalar(select(Invoice).options(joinedload(Invoice.customer)).where(
        Invoice.id == invoice_id, Invoice.owner_id == user.id))
    if not invoice: raise HTTPException(404, "فاکتور پیدا نشد.")
    message = (f"Hello {invoice.customer.name}, a friendly reminder that invoice {invoice.number} "
               f"for {invoice.currency} {invoice.amount} was due on {invoice.due_date}. "
               "Please let us know if you have any questions. Thank you.")
    return page(request, "reminder.html", invoice=invoice, message=message)

@app.exception_handler(401)
async def unauthorized(request: Request, exc):
    return redirect("/login")
