from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models.models import Customer, OilChangePlan, OilChangeLedger, Vehicle
from .routers import customers as customers_router
from .routers import vehicles as vehicles_router
from .services.phone import normalize_phone
import re
from urllib.parse import urlencode

app = FastAPI(title="Oil Change Tracker (MVP)")
templates = Jinja2Templates(directory="oil_change_tracker/app/templates")
from .services.auto_backup import start_periodic_backup, backup_once
from .services.netinfo import get_host_info


Base.metadata.create_all(bind=engine)

# --- lightweight SQLite auto-migration for new Vehicle columns ---
from sqlalchemy import text
def _ensure_vehicle_columns():
    try:
        with engine.connect() as conn:
            cols = [r[1].lower() for r in conn.exec_driver_sql("PRAGMA table_info('vehicles')").fetchall()]
            alters = []
            if 'oil_type' not in cols:
                alters.append("ALTER TABLE vehicles ADD COLUMN oil_type VARCHAR(20) DEFAULT ''")
            if 'oil_capacity_quarts' not in cols:
                alters.append("ALTER TABLE vehicles ADD COLUMN oil_capacity_quarts VARCHAR(10) DEFAULT ''")
            for stmt in alters:
                conn.exec_driver_sql(stmt)
    except Exception:
        # ignore on non-SQLite or if table doesn't exist yet
        pass
_ensure_vehicle_columns()
# --- end auto-migration ---

# start background backup every 6 hours
start_periodic_backup(interval_hours=6)

app.include_router(customers_router.router)
app.include_router(vehicles_router.router)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
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
        # Handle name search
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
    
    return templates.TemplateResponse("search_results.html", {
        "request": request,
        "results": results,
        "term": term
    })

@app.get("/ui/customer/{customer_id}", response_class=HTMLResponse)
def ui_customer(request: Request, customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        return HTMLResponse("Customer not found", status_code=404)
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    vehicles = db.query(Vehicle).filter_by(customer_id=customer_id).all()
    ledger = db.query(OilChangeLedger).filter_by(customer_id=customer_id).order_by(OilChangeLedger.created_at.desc()).limit(25).all()
    return templates.TemplateResponse("customer.html", {"request": request, "c": c, "plan": plan, "vehicles": vehicles, "ledger": ledger})

@app.post("/ui/customer/{customer_id}/deduct")
def ui_deduct(customer_id: int, note: str = Form("Oil change used"), db: Session = Depends(get_db)):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan or plan.remaining <= 0:
        return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)
    plan.remaining -= 1
    db.add(OilChangeLedger(customer_id=customer_id, delta=-1, note=note))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/restore")
def ui_restore(customer_id: int, note: str = Form("Restored oil change"), db: Session = Depends(get_db)):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan or plan.remaining >= plan.total_allowed:
        return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)
    plan.remaining += 1
    db.add(OilChangeLedger(customer_id=customer_id, delta=+1, note=note))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/new")
def ui_new_customer(first_name: str = Form(...), last_name: str = Form(...), phone: str = Form(""), db: Session = Depends(get_db)):
    try:
        print(f"Creating customer: {first_name} {last_name} {phone}")  # Debug print
        c = Customer(first_name=first_name.strip(), last_name=last_name.strip(), phone=normalize_phone(phone))
        db.add(c)
        db.flush()  # This will assign the ID
        print(f"Created customer with ID: {c.id}")  # Debug print
        
        plan = OilChangePlan(customer_id=c.id, total_allowed=4, remaining=4, active=True)
        db.add(plan)
        db.commit()
        db.refresh(c)
        print(f"Created plan for customer {c.id}")  # Debug print
        
        return RedirectResponse(f"/ui/customer/{c.id}", status_code=303)
    except Exception as e:
        print(f"Error creating customer: {str(e)}")  # Debug print
        db.rollback()
        raise

@app.post("/ui/customer/{customer_id}/vehicle")
async def ui_add_vehicle(customer_id: int, plate: str = Form(""), year: str = Form(""), make: str = Form(""), model: str = Form(""), vin: str = Form("")):
    from sqlalchemy.orm import Session
    from fastapi import Depends
    return RedirectResponse(f"/vehicles/ui/add?customer_id={customer_id}&plate={plate}&year={year}&make={make}&model={model}&vin={vin}", status_code=303)

@app.get("/vehicles/ui/add", response_class=HTMLResponse)
async def vehicles_ui_add(request: Request, customer_id: int, plate: str = "", year: str = "", make: str = "", model: str = "", vin: str = "", db: Session = Depends(get_db)):
    from .services.plate_lookup import plate_to_vin
    if not vin and plate:
        looked = await plate_to_vin(plate)
        if looked:
            vin = looked
    v = Vehicle(customer_id=customer_id, plate=plate.upper(), year=year, make=make, model=model, vin=vin)
    db.add(v); db.commit(); db.refresh(v)
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)


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
