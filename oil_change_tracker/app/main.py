from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import case, desc, text
from .database import Base, engine, get_db
from .models.models import Customer, OilChangePlan, OilChangeLedger, Vehicle, Contact
from .routers import customers as customers_router
from .routers import vehicles as vehicles_router
from .services.phone import normalize_phone
import re
from urllib.parse import urlencode

app = FastAPI(title="Oil Change Tracker (MVP)")
from pathlib import Path
import os

# Resolve templates directory relative to this file so deployment CWD does not matter
_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
from .services.auto_backup import start_periodic_backup, backup_once
from .services.netinfo import get_host_info

Base.metadata.create_all(bind=engine)
from alembic.config import Config
from alembic import command

alembic_cfg = Config("alembic.ini")
command.upgrade(alembic_cfg, "head")

app.include_router(customers_router.router)
app.include_router(vehicles_router.router)

# start periodic backup
try:
    start_periodic_backup(interval_hours=6)
except Exception as e:
    print(f"Backup scheduler failed: {e}")

def get_abs(value):
    return abs(value)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/ui", response_class=HTMLResponse)
def ui_home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.post("/ui/search", response_class=HTMLResponse)
def ui_search(request: Request, name_or_phone: str = Form(...), db: Session = Depends(get_db)):
    term = name_or_phone.strip()
    digits = re.sub(r"\D+", "", term)
    print(f"Search term: {term}")
    print(f"Extracted digits: {digits}")
    results = []
    if digits:
        formatted = normalize_phone(digits)
        print(f"Searching for formatted phone: {formatted}")
        results = db.query(Customer).filter(
            (Customer.phone.ilike(f"%{formatted}%")) |
            (Customer.phone.ilike(f"%{digits}%"))
        ).all()
    else:
        parts = term.split()
        if len(parts) == 1:
            results = db.query(Customer).filter(
                (Customer.first_name.ilike(f"%{term}%")) |
                (Customer.last_name.ilike(f"%{term}%"))
            ).all()
        elif len(parts) > 1:
            first, last = parts[0], " ".join(parts[1:])
            results = db.query(Customer).filter(
                Customer.first_name.ilike(f"%{first}%"),
                Customer.last_name.ilike(f"%{last}%")
            ).all()
    if not results:
        return templates.TemplateResponse("home.html", {
            "request": request,
            "pre_fill": {
                "first_name": "",
                "last_name": "",
                "phone": digits if digits else term
            }
        })
    return templates.TemplateResponse("search_results.html", {"request": request, "results": results, "term": term})

def get_vehicle_oil_changes(db: Session, vehicle_id: int) -> int:
    return db.query(OilChangeLedger).filter_by(vehicle_id=vehicle_id, delta=-1).count()

def find_duplicate_vehicles(db: Session, vin: str = "", plate: str = "", year: str = "", make: str = "", model: str = ""):
    potential = []
    if vin and vin.strip():
        vin_matches = db.query(Vehicle).filter(Vehicle.vin.ilike(f"%{vin.strip()}%")).all()
        for match in vin_matches:
            potential.append({'vehicle': match, 'customer': db.get(Customer, match.customer_id), 'match_reason': 'VIN match', 'confidence': 'high'})
    if plate and plate.strip():
        plate_matches = db.query(Vehicle).filter(Vehicle.plate.ilike(f"%{plate.strip().upper()}%")).all()
        for match in plate_matches:
            if not any(d['vehicle'].id == match.id for d in potential):
                potential.append({'vehicle': match, 'customer': db.get(Customer, match.customer_id), 'match_reason': 'License plate match', 'confidence': 'high'})
    if year and make and model:
        detail_matches = db.query(Vehicle).filter(
            Vehicle.year == year,
            Vehicle.make.ilike(f"%{make}%"),
            Vehicle.model.ilike(f"%{model}%")
        ).all()
        for match in detail_matches:
            if not any(d['vehicle'].id == match.id for d in potential):
                potential.append({'vehicle': match, 'customer': db.get(Customer, match.customer_id), 'match_reason': 'Vehicle details match', 'confidence': 'medium'})
    return potential

@app.get("/ui/customer/{customer_id}", response_class=HTMLResponse)
def get_customer(customer_id: int, request: Request, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        return RedirectResponse(url="/ui", status_code=303)
    vehicles = db.query(Vehicle).filter(Vehicle.customer_id == customer_id).all()
    plans = db.query(OilChangePlan).filter(OilChangePlan.customer_id == customer_id, OilChangePlan.active == True).all()
    contacts = db.query(Contact).filter(Contact.customer_id == customer_id).order_by(Contact.preferred.desc(), Contact.contact_name).all()
    ledger_entries = db.query(OilChangeLedger).filter(OilChangeLedger.customer_id == customer_id).order_by(desc(OilChangeLedger.created_at)).all()
    vehicle_last_mileage = {}
    for vehicle in vehicles:
        last_entry = db.query(OilChangeLedger).filter(OilChangeLedger.vehicle_id == vehicle.id, OilChangeLedger.mileage.isnot(None)).order_by(desc(OilChangeLedger.created_at)).first()
        vehicle_last_mileage[vehicle.id] = last_entry.mileage if last_entry else None
    return templates.TemplateResponse("customer.html", {"request": request, "c": c, "vehicles": vehicles, "plans": plans, "contacts": contacts, "ledger_entries": ledger_entries, "vehicle_last_mileage": vehicle_last_mileage})

@app.post("/customers/ui/edit")
async def edit_customer(request: Request, customer_id: int = Form(...), first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(...), email: str = Form(""), landline: str = Form("")):
    try:
        with get_db() as db:
            customer = db.query(Customer).filter(Customer.id == customer_id).first()
            if not customer:
                return RedirectResponse(url="/ui", status_code=303)
            customer.first_name = first_name.strip()
            customer.last_name = last_name.strip()
            customer.phone = phone.strip()
            customer.email = email.strip() if email.strip() else None
            customer.landline = landline.strip() if landline.strip() else None
            db.commit()
        return RedirectResponse(url=f"/ui/customer/{customer_id}", status_code=303)
    except Exception as e:
        print(f"Error editing customer: {e}")
        return RedirectResponse(url=f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/contacts/add")
async def add_contact(customer_id: int, contact_name: str = Form(...), role: str = Form(""), mobile: str = Form(""), landline: str = Form(""), email: str = Form(""), preferred: bool = Form(False), notes: str = Form(""), db: Session = Depends(get_db)):
    try:
        if preferred:
            db.query(Contact).filter(Contact.customer_id == customer_id).update({"preferred": False})
        contact = Contact(customer_id=customer_id, contact_name=contact_name.strip(), role=role.strip(), mobile=mobile.strip(), landline=landline.strip(), email=email.strip(), preferred=preferred, notes=notes.strip())
        db.add(contact)
        db.commit()
        return RedirectResponse(url=f"/ui/customer/{customer_id}", status_code=303)
    except Exception as e:
        print(f"Error adding contact: {e}")
        return RedirectResponse(url=f"/ui/customer/{customer_id}?error=Failed+to+add+contact", status_code=303)

@app.get("/ui/customer/{customer_id}/contacts/{contact_id}/json")
async def get_contact_json(customer_id: int, contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.customer_id == customer_id).first()
    if not contact:
        return {"error": "Contact not found"}
    return {"id": contact.id, "contact_name": contact.contact_name, "role": contact.role, "mobile": contact.mobile, "landline": contact.landline, "email": contact.email, "preferred": contact.preferred, "notes": contact.notes}

@app.post("/ui/customer/{customer_id}/contacts/{contact_id}/edit")
async def edit_contact(customer_id: int, contact_id: int, contact_name: str = Form(...), role: str = Form(""), mobile: str = Form(""), landline: str = Form(""), email: str = Form(""), preferred: bool = Form(False), notes: str = Form(""), db: Session = Depends(get_db)):
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id, Contact.customer_id == customer_id).first()
        if not contact:
            return RedirectResponse(url=f"/ui/customer/{customer_id}?error=Contact+not+found", status_code=303)
        if preferred:
            db.query(Contact).filter(Contact.customer_id == customer_id, Contact.id != contact_id).update({"preferred": False})
        contact.contact_name = contact_name.strip()
        contact.role = role.strip()
        contact.mobile = mobile.strip()
        contact.landline = landline.strip()
        contact.email = email.strip()
        contact.preferred = preferred
        contact.notes = notes.strip()
        db.commit()
        return RedirectResponse(url=f"/ui/customer/{customer_id}", status_code=303)
    except Exception as e:
        print(f"Error editing contact: {e}")
        return RedirectResponse(url=f"/ui/customer/{customer_id}?error=Failed+to+edit+contact", status_code=303)

@app.post("/ui/customer/{customer_id}/contacts/{contact_id}/delete")
async def delete_contact(customer_id: int, contact_id: int, db: Session = Depends(get_db)):
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id, Contact.customer_id == customer_id).first()
        if contact:
            db.delete(contact)
            db.commit()
        return RedirectResponse(url=f"/ui/customer/{customer_id}", status_code=303)
    except Exception as e:
        print(f"Error deleting contact: {e}")
        return RedirectResponse(url=f"/ui/customer/{customer_id}?error=Failed+to+delete+contact", status_code=303)

@app.post("/customers/ui/create")
def ui_deduct(customer_id: int, vehicle_id: int = Form(...), mileage: int = Form(...), service_date: str = Form(None), note: str = Form("Oil change used"), db: Session = Depends(get_db)):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+vehicle", status_code=303)
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    plan.remaining -= 1
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD", status_code=303)
    db.add(OilChangeLedger(customer_id=customer_id, vehicle_id=vehicle_id, mileage=mileage, delta=-1, note=note, created_at=created_date))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/edit-plan")
def ui_edit_plan(customer_id: int, remaining: int = Form(...), db: Session = Depends(get_db)):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    plan.remaining = remaining
    plan.total_allowed = max(0, remaining)
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/add-oil-changes")
def ui_add_oil_changes(customer_id: int, quantity: int = Form(...), reason: str = Form(...), service_date: str = Form(None), db: Session = Depends(get_db)):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    if quantity <= 0:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Quantity+must+be+greater+than+zero", status_code=303)
    plan.remaining += quantity
    plan.total_allowed = max(0, plan.remaining)
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD", status_code=303)
    db.add(OilChangeLedger(customer_id=customer_id, delta=quantity, note=f"Added {quantity} oil changes: {reason.strip()}", created_at=created_date))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/add-four")
def ui_add_four(customer_id: int, vehicle_id: int = Form(...), service_date: str = Form(None), db: Session = Depends(get_db)):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+vehicle", status_code=303)
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    plan.total_allowed += 4
    plan.remaining += 4
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD", status_code=303)
    db.add(OilChangeLedger(customer_id=customer_id, vehicle_id=vehicle_id, delta=+4, note="Added 4 oil changes (tire purchase)", created_at=created_date))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/new")
def ui_new_customer(first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(""), landline: str = Form(""), email: str = Form(""), db: Session = Depends(get_db)):
    try:
        c = Customer(first_name=first_name.strip(), last_name=last_name.strip(), phone=normalize_phone(phone), landline=normalize_phone(landline), email=email.strip())
        db.add(c)
        db.flush()
        plan = OilChangePlan(customer_id=c.id, total_allowed=0, remaining=0, active=True)
        db.add(plan)
        db.commit()
        db.refresh(c)
        return RedirectResponse(f"/ui/customer/{c.id}", status_code=303)
    except Exception as e:
        print(f"Error creating customer: {str(e)}")
        db.rollback()
        raise

@app.post("/ui/customer/{customer_id}/vehicle")
async def ui_add_vehicle(customer_id: int, plate: str = Form(""), year: str = Form(""), make: str = Form(""), model: str = Form(""), vin: str = Form("")):
    return RedirectResponse(f"/vehicles/ui/add?customer_id={customer_id}&plate={plate}&year={year}&make={make}&model={model}&vin={vin}", status_code=303)

@app.get("/vehicles/ui/add", response_class=HTMLResponse)
async def vehicles_ui_add(request: Request, customer_id: int, plate: str = "", year: str = "", make: str = "", model: str = "", vin: str = "", force: bool = False, db: Session = Depends(get_db)):
    if not force:
        duplicates = find_duplicate_vehicles(db, vin, plate, year, make, model)
        if duplicates:
            customer = db.get(Customer, customer_id)
            return templates.TemplateResponse("duplicate_warning.html", {"request": request, "customer": customer, "new_vehicle": {"plate": plate, "vin": vin, "year": year, "make": make, "model": model}, "duplicates": duplicates})
    v = Vehicle(customer_id=customer_id, plate=plate.upper(), year=year, make=make, model=model, vin=vin.upper())
    db.add(v)
    db.commit()
    db.refresh(v)
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/ledger/{entry_id}/delete")
def ui_delete_ledger_entry(customer_id: int, entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(OilChangeLedger, entry_id)
    if not entry or entry.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Entry+not+found", status_code=303)
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    plan.remaining -= entry.delta
    db.delete(entry)
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

# Ledger editing support
@app.get("/ui/customer/{customer_id}/ledger/{entry_id}/json")
def ui_get_ledger_entry_json(customer_id: int, entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(OilChangeLedger, entry_id)
    if not entry or entry.customer_id != customer_id:
        return {"error": "Entry not found"}
    return {"id": entry.id, "vehicle_id": entry.vehicle_id, "mileage": entry.mileage, "oil_weight": entry.oil_weight, "oil_quarts": entry.oil_quarts, "note": entry.note, "delta": entry.delta, "date": entry.created_at.strftime('%Y-%m-%d') if entry.created_at else None}

@app.post("/ui/customer/{customer_id}/ledger/{entry_id}/edit")
def ui_edit_ledger_entry(customer_id: int, entry_id: int, mileage: int = Form(None), service_date: str = Form(None), oil_weight: str = Form(""), oil_quarts: float = Form(None), note: str = Form(""), db: Session = Depends(get_db)):
    entry = db.get(OilChangeLedger, entry_id)
    if not entry or entry.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Entry+not+found", status_code=303)
    try:
        if mileage is not None:
            entry.mileage = mileage
        entry.oil_weight = oil_weight.strip() or None
        if oil_quarts is not None:
            entry.oil_quarts = oil_quarts
        entry.note = note.strip()[:255]
        if service_date:
            try:
                base = datetime.strptime(service_date, '%Y-%m-%d')
                entry.created_at = base
            except ValueError:
                return RedirectResponse(f"/ui/customer/{customer_id}?error=Bad+date+format", status_code=303)
        db.add(entry)
        db.commit()
        return RedirectResponse(f"/ui/customer/{customer_id}?success=Entry+updated", status_code=303)
    except Exception as e:
        print(f"Error editing ledger entry {entry_id}: {e}")
        db.rollback()
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Failed+to+edit+entry", status_code=303)

@app.get("/admin/duplicates", response_class=HTMLResponse)
async def admin_duplicates(request: Request, db: Session = Depends(get_db)):
    customers = db.query(Customer).all()
    customer_duplicates = []
    phone_groups = {}
    for customer in customers:
        normalized_phone = customer.phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '') if customer.phone else ''
        if normalized_phone and len(normalized_phone) >= 10:
            phone_groups.setdefault(normalized_phone, []).append(customer)
    for phone, customer_list in phone_groups.items():
        if len(customer_list) > 1:
            customer_duplicates.append({'type': 'phone', 'phone': phone, 'customers': customer_list, 'vehicles': [db.query(Vehicle).filter_by(customer_id=c.id).all() for c in customer_list]})
    vehicles = db.query(Vehicle).all()
    vehicle_duplicates = []
    vin_groups = {}
    for vehicle in vehicles:
        if vehicle.vin and vehicle.vin.strip():
            vin = vehicle.vin.strip().upper()
            vin_groups.setdefault(vin, []).append(vehicle)
    for vin, vehicle_list in vin_groups.items():
        if len(vehicle_list) > 1:
            vehicle_duplicates.append({'type': 'vin', 'vin': vin, 'vehicles': vehicle_list, 'customers': [db.get(Customer, v.customer_id) for v in vehicle_list]})
    plate_groups = {}
    for vehicle in vehicles:
        if vehicle.plate and vehicle.plate.strip():
            plate = vehicle.plate.strip().upper()
            plate_groups.setdefault(plate, []).append(vehicle)
    for plate, vehicle_list in plate_groups.items():
        if len(vehicle_list) > 1 and not any(d['type'] == 'vin' and any(v.id in [veh.id for veh in d['vehicles']] for v in vehicle_list) for d in vehicle_duplicates):
            vehicle_duplicates.append({'type': 'plate', 'plate': plate, 'vehicles': vehicle_list, 'customers': [db.get(Customer, v.customer_id) for v in vehicle_list]})
    return templates.TemplateResponse("admin_duplicates.html", {"request": request, "customer_duplicates": customer_duplicates, "vehicle_duplicates": vehicle_duplicates})

@app.get("/info")
def info():
    return get_host_info()

@app.get("/advisor", response_class=HTMLResponse)
def advisor_dashboard(request: Request):
    from .services.advisor import compute_metrics, generate_advice
    metrics = compute_metrics(days=30)
    tips = generate_advice(metrics)
    return templates.TemplateResponse("advisor.html", {"request": request, "metrics": metrics, "tips": tips})

@app.post("/advisor/run")
def advisor_run():
    from .services.advisor import run_once
    json_path, html_path = run_once(days=30)
    return {"ok": True, "json_report": json_path, "html_report": html_path}

@app.get('/healthz')
def healthz():
    return {'ok': True}

# Additional health endpoints preserved
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/health/db")
def db_health():
    with engine.connect() as conn:
        try:
            version = conn.execute(text("select sqlite_version()"))
            v = version.scalar()
        except Exception:
            v = None
    return {"ok": True, "db_version": v}

# Optional debug endpoint to list registered routes (enabled when APP_DEBUG=1)
if os.environ.get("APP_DEBUG") == "1":
    @app.get("/routes")
    def list_routes():  # pragma: no cover - diagnostic only
        return {"routes": [getattr(r, 'path', str(r)) for r in app.router.routes]}
