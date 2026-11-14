import os
from datetime import date
from pathlib import Path
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from starlette.middleware.sessions import SessionMiddleware
from .database import Base, engine, get_db
from .models import User, Customer, Invoice
from .security import hash_password, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="PayPilot")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-only-change-me"),
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    max_age=60 * 60 * 24 * 7,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def money(value, currency="USD"):
    return f"{value:,.2f} {currency}"

templates.env.filters["money"] = money
Base.metadata.create_all(bind=engine)

def current_user(request: Request, db: Session):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()

def page(request, name, **context):
    return templates.TemplateResponse(name, {"request": request, **context})

def require_user(request: Request, db: Session):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401)
    return user

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return page(request, "landing.html")

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return page(request, "auth.html", mode="register", error=None)

@app.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email = email.strip().lower()
    if len(password) < 10:
        return page(request, "auth.html", mode="register", error="Use a password with at least 10 characters.")
    if db.query(User).filter(User.email == email).first():
        return page(request, "auth.html", mode="register", error="An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user); db.commit(); db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return page(request, "auth.html", mode="login", error=None)

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return page(request, "auth.html", mode="login", error="Email or password is incorrect.")
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    invoices = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.owner_id == user.id).order_by(Invoice.due_date.asc()).all()
    today = date.today()
    unpaid = [i for i in invoices if i.status != "paid"]
    overdue = [i for i in unpaid if i.due_date < today]
    paid_total = sum(i.amount_cents for i in invoices if i.status == "paid")
    outstanding = sum(i.amount_cents for i in unpaid)
    return page(request, "dashboard.html", user=user, invoices=invoices, today=today,
                outstanding=outstanding, paid_total=paid_total, overdue_count=len(overdue),
                customer_count=db.query(Customer).filter(Customer.owner_id == user.id).count())

@app.get("/customers", response_class=HTMLResponse)
def customers_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    customers = db.query(Customer).filter(Customer.owner_id == user.id).order_by(Customer.name).all()
    return page(request, "customers.html", user=user, customers=customers, error=None)

@app.post("/customers")
def add_customer(request: Request, name: str = Form(...), email: str = Form(""), company: str = Form(""), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    name = name.strip()
    if not name: raise HTTPException(400, "Customer name is required")
    db.add(Customer(owner_id=user.id, name=name, email=email.strip(), company=company.strip()))
    db.commit()
    return RedirectResponse("/customers", status_code=303)

@app.post("/customers/{customer_id}/delete")
def delete_customer(customer_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.owner_id == user.id).first()
    if customer:
        if db.query(Invoice).filter(Invoice.customer_id == customer.id).first():
            raise HTTPException(400, "This customer has invoices. Delete or reassign them first.")
        db.delete(customer); db.commit()
    return RedirectResponse("/customers", status_code=303)

@app.get("/invoices/new", response_class=HTMLResponse)
def new_invoice_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    customers = db.query(Customer).filter(Customer.owner_id == user.id).order_by(Customer.name).all()
    return page(request, "invoice_form.html", user=user, customers=customers, error=None)

@app.post("/invoices")
def create_invoice(request: Request, customer_id: int = Form(...), number: str = Form(...),
                   description: str = Form(""), amount: str = Form(...), currency: str = Form("USD"),
                   due_date: date = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.owner_id == user.id).first()
    if not customer: raise HTTPException(400, "Choose a valid customer")
    try:
        cents = round(float(amount) * 100)
        if cents <= 0: raise ValueError()
    except ValueError:
        raise HTTPException(400, "Amount must be greater than zero")
    currency = currency.upper()
    if currency not in {"USD", "EUR", "GBP", "CAD", "AUD"}: currency = "USD"
    db.add(Invoice(owner_id=user.id, customer_id=customer.id, number=number.strip(),
                   description=description.strip(), amount_cents=cents, currency=currency,
                   due_date=due_date, status="unpaid"))
    db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: int, request: Request, status: str = Form(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.owner_id == user.id).first()
    if invoice and status in {"unpaid", "paid"}:
        invoice.status = status
        db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/invoices/{invoice_id}/delete")
def delete_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.owner_id == user.id).first()
    if invoice:
        db.delete(invoice); db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/invoices/{invoice_id}/reminder", response_class=HTMLResponse)
def reminder(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user: return RedirectResponse("/login", status_code=303)
    invoice = db.query(Invoice).options(joinedload(Invoice.customer)).filter(Invoice.id == invoice_id, Invoice.owner_id == user.id).first()
    if not invoice: raise HTTPException(404, "Invoice not found")
    amount = f"{invoice.amount_cents / 100:,.2f} {invoice.currency}"
    body = f"""Subject: Friendly reminder — Invoice {invoice.number}

Hi {invoice.customer.name},

I hope you are doing well. This is a friendly reminder that invoice {invoice.number} for {amount} was due on {invoice.due_date:%B %d, %Y}.

When convenient, please let us know when we can expect payment. If you have already paid, please disregard this message.

Thank you,
Your Accounts Team"""
    return page(request, "reminder.html", user=user, invoice=invoice, body=body)
