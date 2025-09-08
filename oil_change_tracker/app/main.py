from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import case, desc
from .database import Base, engine, get_db
from .models.models import Customer, OilChangePlan, OilChangeLedger, Vehicle
from .routers import customers as customers_router
from .routers import vehicles as vehicles_router
from .services.phone import normalize_phone
import re
from urllib.parse import urlencode
from pathlib import Path
import os, json, traceback, uuid, threading

# Custom middleware for request logging
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()
        
        # Log the request
        print(f"🌐 {request.method} {request.url.path}")
        if request.query_params:
            print(f"   📋 Query params: {dict(request.query_params)}")
        if request.headers.get('referer'):
            print(f"   🔗 Referer: {request.headers.get('referer')}")
        
        response = await call_next(request)
        
        # Log the response
        duration = (datetime.now() - start_time).total_seconds() * 1000
        print(f"   ✅ {response.status_code} ({duration:.1f}ms)")
        
        return response

app = FastAPI(title="Oil Change Tracker (MVP)")
app.add_middleware(RequestLoggingMiddleware)

# Resolve templates directory robustly regardless of working directory
_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _BASE_DIR / "templates"
if not _TEMPLATE_DIR.exists():
    # Fallback: try relative path used previously (useful for local odd launches)
    legacy = Path.cwd() / "app" / "templates"
    if legacy.exists():
        _TEMPLATE_DIR = legacy
        print(f"⚠️ Using legacy template path fallback: {_TEMPLATE_DIR}")
    else:
        print(f"❌ Template directory not found at expected path: {_TEMPLATE_DIR}")
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# --- Error Reporting Setup ---
_ERROR_LOG_PATH = _BASE_DIR / "errors.jsonl"
_LOG_LOCK = threading.Lock()
_MAX_ERROR_FILE_BYTES = int(os.getenv("ERROR_LOG_MAX_BYTES", str(5 * 1024 * 1024)))  # 5MB default

def _rotate_error_log_if_needed():
    try:
        if _ERROR_LOG_PATH.exists() and _ERROR_LOG_PATH.stat().st_size > _MAX_ERROR_FILE_BYTES:
            rotated = _ERROR_LOG_PATH.with_name(f"errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
            _ERROR_LOG_PATH.rename(rotated)
            print(f"♻️ Rotated error log to {rotated.name}")
    except Exception as e:
        print(f"Error rotating log: {e}")

def log_error(event: dict):
    event.setdefault("ts", datetime.utcnow().isoformat())
    with _LOG_LOCK:
        _rotate_error_log_if_needed()
        try:
            with _ERROR_LOG_PATH.open('a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Failed writing error log: {e}")

# Optional Sentry integration
_SENTRY_DSN = os.getenv("SENTRY_DSN")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=_SENTRY_DSN, traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.0")))
        print("🛰️  Sentry initialized")
    except Exception as e:
        print(f"Sentry init failed: {e}")

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Skip HTTPException (FastAPI will map status codes) but still log >=500
    status_code = 500
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        if status_code < 500:
            return PlainTextResponse(str(exc.detail if hasattr(exc, 'detail') else str(exc)), status_code=status_code)
    error_id = uuid.uuid4().hex[:10]
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    event = {
        "id": error_id,
        "path": request.url.path,
        "method": request.method,
        "status": status_code,
        "headers": {k: v for k, v in request.headers.items() if k.lower() in ("user-agent", "referer")},
        "query": dict(request.query_params),
        "error": str(exc),
        "trace": tb.splitlines()[-25:],  # last lines for brevity
    }
    log_error(event)
    if _SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
    return PlainTextResponse(f"Internal Server Error (id={error_id})", status_code=status_code)

@app.get("/admin/errors", response_class=HTMLResponse)
def view_errors(request: Request, limit: int = 50):
    rows = []
    try:
        if _ERROR_LOG_PATH.exists():
            with _ERROR_LOG_PATH.open('r', encoding='utf-8') as f:
                for line in f.readlines()[-limit:]:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
            rows.sort(key=lambda r: r.get('ts', ''), reverse=True)
    except Exception as e:
        return HTMLResponse(f"Failed to read errors: {e}", status_code=500)
    return templates.TemplateResponse("errors.html", {"request": request, "errors": rows, "count": len(rows)})
from .services.auto_backup import start_periodic_backup, backup_once
from .services.netinfo import get_host_info


Base.metadata.create_all(bind=engine)

# --- lightweight SQLite auto-migration for new columns ---
from sqlalchemy import text
def _ensure_vehicle_columns():
    try:
        with engine.connect() as conn:
            # Add missing columns to vehicles table
            cols = [r[1].lower() for r in conn.exec_driver_sql("PRAGMA table_info('vehicles')").fetchall()]
            alters = []
            if 'oil_type' not in cols:
                alters.append("ALTER TABLE vehicles ADD COLUMN oil_type VARCHAR(20) DEFAULT ''")
            if 'oil_capacity_quarts' not in cols:
                alters.append("ALTER TABLE vehicles ADD COLUMN oil_capacity_quarts VARCHAR(10) DEFAULT ''")
            if 'oil_weight' not in cols:
                alters.append("ALTER TABLE vehicles ADD COLUMN oil_weight VARCHAR(10) DEFAULT ''")
            for stmt in alters:
                conn.exec_driver_sql(stmt)
            
            # Add missing columns to oil_change_ledger table
            ledger_cols = [r[1].lower() for r in conn.exec_driver_sql("PRAGMA table_info('oil_change_ledger')").fetchall()]
            ledger_alters = []
            if 'oil_weight' not in ledger_cols:
                ledger_alters.append("ALTER TABLE oil_change_ledger ADD COLUMN oil_weight VARCHAR(10)")
            if 'oil_quarts' not in ledger_cols:
                ledger_alters.append("ALTER TABLE oil_change_ledger ADD COLUMN oil_quarts FLOAT")
            if 'mileage' not in ledger_cols:
                ledger_alters.append("ALTER TABLE oil_change_ledger ADD COLUMN mileage INTEGER")
            if 'vehicle_id' not in ledger_cols:
                ledger_alters.append("ALTER TABLE oil_change_ledger ADD COLUMN vehicle_id INTEGER")
            for stmt in ledger_alters:
                conn.exec_driver_sql(stmt)
            
            # Create VIN oil specs table if it doesn't exist
            try:
                conn.exec_driver_sql("""
                    CREATE TABLE IF NOT EXISTS vin_oil_specs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vin VARCHAR(17) UNIQUE NOT NULL,
                        oil_weight VARCHAR(10) DEFAULT '',
                        oil_capacity_quarts VARCHAR(10) DEFAULT '',
                        oil_type VARCHAR(20) DEFAULT '',
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        usage_count INTEGER DEFAULT 1
                    )
                """)
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_vin_oil_specs_vin ON vin_oil_specs(vin)")
            except Exception as e:
                print(f"Error creating vin_oil_specs table: {e}")
            
            conn.commit()
    except Exception:
        # ignore on non-SQLite or if table doesn't exist yet
        pass
_ensure_vehicle_columns()
# --- end auto-migration ---

# start background backup every 6 hours
start_periodic_backup(interval_hours=6)

app.include_router(customers_router.router)
app.include_router(vehicles_router.router)

def get_abs(value):
    return abs(value)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    print(f"🏠 HOME PAGE REQUEST: {request.method} {request.url}")
    print(f"📍 User-Agent: {request.headers.get('user-agent', 'Unknown')}")
    print(f"🔗 Referer: {request.headers.get('referer', 'Direct access')}")
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

def get_vehicle_oil_changes(db: Session, vehicle_id: int) -> int:
    """Get the number of oil changes used for a specific vehicle"""
    return db.query(OilChangeLedger).filter_by(
        vehicle_id=vehicle_id,
        delta=-1
    ).count()

def find_duplicate_vehicles(db: Session, vin: str = "", plate: str = "", year: str = "", make: str = "", model: str = ""):
    """Find vehicles that might be duplicates based on VIN, plate, or vehicle details"""
    potential_duplicates = []
    
    # Primary check: VIN match (most reliable)
    if vin and vin.strip():
        vin_matches = db.query(Vehicle).filter(Vehicle.vin.ilike(f"%{vin.strip()}%")).all()
        for match in vin_matches:
            potential_duplicates.append({
                'vehicle': match,
                'customer': db.get(Customer, match.customer_id),
                'match_reason': 'VIN match',
                'confidence': 'high'
            })
    
    # Secondary check: License plate match
    if plate and plate.strip():
        plate_matches = db.query(Vehicle).filter(Vehicle.plate.ilike(f"%{plate.strip().upper()}%")).all()
        for match in plate_matches:
            # Skip if already found by VIN
            if not any(d['vehicle'].id == match.id for d in potential_duplicates):
                potential_duplicates.append({
                    'vehicle': match,
                    'customer': db.get(Customer, match.customer_id),
                    'match_reason': 'License plate match',
                    'confidence': 'high'
                })
    
    # Tertiary check: Make/Model/Year combination
    if year and make and model:
        detail_matches = db.query(Vehicle).filter(
            Vehicle.year == year,
            Vehicle.make.ilike(f"%{make}%"),
            Vehicle.model.ilike(f"%{model}%")
        ).all()
        for match in detail_matches:
            # Skip if already found by VIN or plate
            if not any(d['vehicle'].id == match.id for d in potential_duplicates):
                potential_duplicates.append({
                    'vehicle': match,
                    'customer': db.get(Customer, match.customer_id),
                    'match_reason': 'Vehicle details match',
                    'confidence': 'medium'
                })
    
    return potential_duplicates

@app.get("/ui/customer/{customer_id}", response_class=HTMLResponse)
def ui_customer(request: Request, customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        return HTMLResponse("Customer not found", status_code=404)
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    vehicles = db.query(Vehicle).filter_by(customer_id=customer_id).all()
    ledger = db.query(OilChangeLedger).filter_by(customer_id=customer_id).order_by(OilChangeLedger.created_at.desc()).limit(50).all()
    
    # Sort by created_at (service_date will be used in the future)
    try:
        ledger.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
    except Exception as e:
        # If sorting fails, keep the original order
        print(f"Sorting error: {e}")
        pass
    
    # Get oil changes used per vehicle
    vehicle_oil_changes = {v.id: get_vehicle_oil_changes(db, v.id) for v in vehicles}
    
    # Get last mileage for each vehicle for validation
    vehicle_last_mileage = {}
    for v in vehicles:
        last_entry = db.query(OilChangeLedger).filter_by(
            customer_id=customer_id, 
            vehicle_id=v.id
        ).filter(
            OilChangeLedger.mileage.isnot(None)
        ).order_by(OilChangeLedger.created_at.desc()).first()
        vehicle_last_mileage[v.id] = last_entry.mileage if last_entry else 0
    
    # Get today's date for form defaults
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    return templates.TemplateResponse("customer.html", {
        "request": request,
        "c": c,
        "plan": plan,
        "vehicles": vehicles,
        "ledger": ledger,
        "vehicle_oil_changes": vehicle_oil_changes,
        "vehicle_last_mileage": vehicle_last_mileage,
        "today_date": today_date,
        "abs": abs
    })

@app.post("/ui/customer/{customer_id}/deduct")
def ui_deduct(
    customer_id: int,
    vehicle_id: int = Form(...),
    mileage: int = Form(...),
    service_date: str = Form(None),
    note: str = Form("Oil change used"),
    db: Session = Depends(get_db)
):
    # Verify vehicle exists and belongs to customer
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+vehicle", status_code=303)

    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    
    plan.remaining -= 1
    # Parse the service date or use current date
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(
            f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD",
            status_code=303
        )

    db.add(OilChangeLedger(
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        mileage=mileage,
        delta=-1,
        note=note,
        created_at=created_date
    ))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/edit-plan")
def ui_edit_plan(
    customer_id: int,
    remaining: int = Form(...),
    db: Session = Depends(get_db)
):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    
    # Update the plan - remaining can be negative
    plan.remaining = remaining
    # Keep total_allowed in sync with remaining for now (or set to 0 if negative)
    plan.total_allowed = max(0, remaining)
    db.commit()
    
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/add-oil-changes")
def ui_add_oil_changes(
    customer_id: int,
    quantity: int = Form(...),
    reason: str = Form(...),
    service_date: str = Form(None),
    db: Session = Depends(get_db)
):
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    
    if quantity <= 0:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Quantity+must+be+greater+than+zero", status_code=303)
    
    plan.remaining += quantity
    # Keep total_allowed in sync
    plan.total_allowed = max(0, plan.remaining)
    
    # Parse the service date or use current date
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(
            f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD",
            status_code=303
        )

    db.add(OilChangeLedger(
        customer_id=customer_id,
        delta=quantity,
        note=f"Added {quantity} oil changes: {reason.strip()}",
        created_at=created_date
    ))
    db.commit()
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/ui/customer/{customer_id}/add-four")
def ui_add_four(
    customer_id: int,
    vehicle_id: int = Form(...),
    service_date: str = Form(None),
    db: Session = Depends(get_db)
):
    # Verify vehicle exists and belongs to customer
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+vehicle", status_code=303)

    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    
    plan.total_allowed += 4
    plan.remaining += 4
    # Parse the service date or use current date
    try:
        created_date = datetime.strptime(service_date, '%Y-%m-%d') if service_date else datetime.utcnow()
    except ValueError:
        return RedirectResponse(
            f"/ui/customer/{customer_id}?error=Invalid+date+format.+Use+YYYY-MM-DD",
            status_code=303
        )

    db.add(OilChangeLedger(
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        delta=+4,
        note="Added 4 oil changes (tire purchase)",
        created_at=created_date
    ))
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
        
        plan = OilChangePlan(customer_id=c.id, total_allowed=0, remaining=0, active=True)
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
async def vehicles_ui_add(request: Request, customer_id: int, plate: str = "", year: str = "", make: str = "", model: str = "", vin: str = "", force: bool = False, db: Session = Depends(get_db)):
    print(f"Vehicle add request: customer_id={customer_id}, plate='{plate}', year='{year}', make='{make}', model='{model}', vin='{vin}', force={force}")
    
    # Check for potential duplicates unless force=True
    if not force:
        duplicates = find_duplicate_vehicles(db, vin, plate, year, make, model)
        print(f"Found {len(duplicates)} potential duplicates")
        if duplicates:
            # Show duplicate warning page
            customer = db.get(Customer, customer_id)
            print(f"Showing duplicate warning for customer: {customer.name if customer else 'None'}")
            return templates.TemplateResponse("duplicate_warning.html", {
                "request": request,
                "customer": customer,
                "new_vehicle": {
                    "plate": plate,
                    "vin": vin,
                    "year": year,
                    "make": make,
                    "model": model
                },
                "duplicates": duplicates
            })
    
    # No duplicates found or force=True, create the vehicle
    print(f"Creating new vehicle for customer {customer_id}")
    v = Vehicle(customer_id=customer_id, plate=plate.upper(), year=year, make=make, model=model, vin=vin.upper())
    db.add(v)
    db.commit()
    db.refresh(v)
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.post("/admin/link-customer-to-vehicle")
async def link_customer_to_vehicle(
    customer_id: int = Form(...),
    vehicle_id: int = Form(...),
    existing_customer_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Merge customers and link to existing vehicle"""
    try:
        # Get the entities
        new_customer = db.get(Customer, customer_id)
        vehicle = db.get(Vehicle, vehicle_id)
        existing_customer = db.get(Customer, existing_customer_id)
        
        if not new_customer or not vehicle or not existing_customer:
            return RedirectResponse(f"/ui/customer/{customer_id}?error=Invalid+customer+or+vehicle", status_code=303)
        
        print(f"Merging customer {new_customer.name} (ID: {customer_id}) into {existing_customer.name} (ID: {existing_customer_id})")
        
        # Merge customer information - combine names and phone numbers intelligently
        existing_full_name = existing_customer.name.strip()
        new_full_name = new_customer.name.strip()
        
        # Only combine if the names are actually different
        if existing_full_name.lower() != new_full_name.lower():
            combined_name = f"{existing_full_name} / {new_full_name}"
        else:
            combined_name = existing_full_name
        
        # Split the combined name back into first and last for storage
        # For display purposes, we'll store the combined name in first_name and clear last_name
        existing_customer.first_name = combined_name
        existing_customer.last_name = ""
        
        # Combine phone numbers only if they're different
        combined_phone = existing_customer.phone
        if new_customer.phone and new_customer.phone.strip() and new_customer.phone != existing_customer.phone:
            if existing_customer.phone:
                combined_phone = f"{existing_customer.phone} / {new_customer.phone}"
            else:
                combined_phone = new_customer.phone
        
        existing_customer.phone = combined_phone
        db.add(existing_customer)
        
        # Move all vehicles from new customer to existing customer (except duplicates)
        new_customer_vehicles = db.query(Vehicle).filter_by(customer_id=customer_id).all()
        for v in new_customer_vehicles:
            v.customer_id = existing_customer_id
            db.add(v)
        
        # Move all oil change plans from new customer to existing customer
        new_customer_plans = db.query(OilChangePlan).filter_by(customer_id=customer_id).all()
        for plan in new_customer_plans:
            plan.customer_id = existing_customer_id
            db.add(plan)
        
        # Move all oil change ledger entries from new customer to existing customer
        new_customer_ledger = db.query(OilChangeLedger).filter_by(customer_id=customer_id).all()
        for entry in new_customer_ledger:
            entry.customer_id = existing_customer_id
            db.add(entry)
        
        # Delete the old customer record
        db.delete(new_customer)
        
        # Add a note to track this merge in the ledger
        from datetime import datetime
        merge_entry = OilChangeLedger(
            customer_id=existing_customer_id,
            vehicle_id=vehicle_id,
            delta=0,  # No oil change impact
            note=f"Customer records merged: {new_customer.name} merged into this account",
            created_at=datetime.now()
        )
        db.add(merge_entry)
        
        db.commit()
        
        return RedirectResponse(f"/ui/customer/{existing_customer_id}?success=Customers+successfully+merged", status_code=303)
        
    except Exception as e:
        print(f"Error merging customers: {str(e)}")
        db.rollback()
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Error+merging+customers:+{str(e)}", status_code=303)

@app.get("/admin/duplicates", response_class=HTMLResponse)
async def admin_duplicates(request: Request, db: Session = Depends(get_db)):
    """Admin page for finding and managing potential duplicate customers/vehicles"""
    
    print(f"🔧 ADMIN DUPLICATES REQUEST: {request.method} {request.url}")
    print(f"📍 User-Agent: {request.headers.get('user-agent', 'Unknown')}")
    print(f"🔗 Referer: {request.headers.get('referer', 'Direct access')}")
    
    # Find potential customer duplicates (by phone or similar names)
    customers = db.query(Customer).all()
    customer_duplicates = []
    
    # Group customers by phone number
    phone_groups = {}
    for customer in customers:
        normalized_phone = customer.phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '') if customer.phone else ''
        if normalized_phone and len(normalized_phone) >= 10:
            if normalized_phone not in phone_groups:
                phone_groups[normalized_phone] = []
            phone_groups[normalized_phone].append(customer)
    
    # Find phone groups with multiple customers
    for phone, customer_list in phone_groups.items():
        if len(customer_list) > 1:
            customer_duplicates.append({
                'type': 'phone',
                'phone': phone,
                'customers': customer_list,
                'vehicles': [db.query(Vehicle).filter_by(customer_id=c.id).all() for c in customer_list]
            })
    
    # Find potential vehicle duplicates
    vehicles = db.query(Vehicle).all()
    vehicle_duplicates = []
    
    # Group by VIN
    vin_groups = {}
    for vehicle in vehicles:
        if vehicle.vin and vehicle.vin.strip():
            vin = vehicle.vin.strip().upper()
            if vin not in vin_groups:
                vin_groups[vin] = []
            vin_groups[vin].append(vehicle)
    
    for vin, vehicle_list in vin_groups.items():
        if len(vehicle_list) > 1:
            vehicle_duplicates.append({
                'type': 'vin',
                'vin': vin,
                'vehicles': vehicle_list,
                'customers': [db.get(Customer, v.customer_id) for v in vehicle_list]
            })
    
    # Group by license plate
    plate_groups = {}
    for vehicle in vehicles:
        if vehicle.plate and vehicle.plate.strip():
            plate = vehicle.plate.strip().upper()
            if plate not in plate_groups:
                plate_groups[plate] = []
            plate_groups[plate].append(vehicle)
    
    for plate, vehicle_list in plate_groups.items():
        if len(vehicle_list) > 1:
            # Skip if already found by VIN
            if not any(d['type'] == 'vin' and any(v.id in [veh.id for veh in d['vehicles']] for v in vehicle_list) for d in vehicle_duplicates):
                vehicle_duplicates.append({
                    'type': 'plate',
                    'plate': plate,
                    'vehicles': vehicle_list,
                    'customers': [db.get(Customer, v.customer_id) for v in vehicle_list]
                })
    
    return templates.TemplateResponse("admin_duplicates.html", {
        "request": request,
        "customer_duplicates": customer_duplicates,
        "vehicle_duplicates": vehicle_duplicates
    })

@app.post("/admin/merge-customers")
async def admin_merge_customers(
    primary_customer_id: int = Form(...),
    secondary_customer_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Merge two customer accounts - move all data from secondary to primary"""
    try:
        primary = db.get(Customer, primary_customer_id)
        secondary = db.get(Customer, secondary_customer_id)
        
        if not primary or not secondary:
            return RedirectResponse("/admin/duplicates?error=Invalid+customer+IDs", status_code=303)
        
        # Move all vehicles from secondary to primary
        vehicles = db.query(Vehicle).filter_by(customer_id=secondary_customer_id).all()
        for vehicle in vehicles:
            vehicle.customer_id = primary_customer_id
            db.add(vehicle)
        
        # Move all oil change ledger entries from secondary to primary
        ledger_entries = db.query(OilChangeLedger).filter_by(customer_id=secondary_customer_id).all()
        for entry in ledger_entries:
            entry.customer_id = primary_customer_id
            db.add(entry)
        
        # Move oil change plan from secondary to primary (if primary doesn't have one)
        primary_plan = db.query(OilChangePlan).filter_by(customer_id=primary_customer_id, active=True).first()
        secondary_plan = db.query(OilChangePlan).filter_by(customer_id=secondary_customer_id, active=True).first()
        
        if secondary_plan and not primary_plan:
            secondary_plan.customer_id = primary_customer_id
            db.add(secondary_plan)
        elif secondary_plan and primary_plan:
            # Combine the remaining oil changes
            primary_plan.remaining += secondary_plan.remaining
            secondary_plan.active = False
            db.add(primary_plan)
            db.add(secondary_plan)
        
        # Add a note about the merge
        merge_note = OilChangeLedger(
            customer_id=primary_customer_id,
            delta=0,
            note=f"Customer accounts merged: {secondary.name} ({secondary.phone}) merged into {primary.name} ({primary.phone})"
        )
        db.add(merge_note)
        
        # Delete the secondary customer
        db.delete(secondary)
        db.commit()
        
        return RedirectResponse(f"/admin/duplicates?success=Successfully+merged+{secondary.name}+into+{primary.name}", status_code=303)
        
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin/duplicates?error=Error+merging+customers:+{str(e)}", status_code=303)


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


@app.post("/ui/customer/{customer_id}/ledger/{entry_id}/delete")
def ui_delete_ledger_entry(customer_id: int, entry_id: int, db: Session = Depends(get_db)):
    # Get the ledger entry
    entry = db.get(OilChangeLedger, entry_id)
    if not entry or entry.customer_id != customer_id:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=Entry+not+found", status_code=303)
    
    # Get the active plan
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        return RedirectResponse(f"/ui/customer/{customer_id}?error=No+active+free+oil+changes", status_code=303)
    
    # Update the plan's remaining count (reverse the original delta)
    plan.remaining -= entry.delta  # Subtract because we're reversing: -(-1) = +1 for deletion of use, -(+1) = -1 for deletion of restore
    
    # Delete the entry
    db.delete(entry)
    db.commit()
    
    return RedirectResponse(f"/ui/customer/{customer_id}", status_code=303)

@app.get('/healthz')
def healthz():
    return {'ok': True}

@app.get('/health')
def health():
    """Health check endpoint for Railway deployment"""
    return {
        'status': 'healthy',
        'service': 'Oil Change Tracker',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }
