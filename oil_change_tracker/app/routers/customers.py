from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.models import Customer, OilChangePlan, OilChangeLedger, Vehicle
from ..schemas import CustomerCreate, CustomerOut, PlanCreate, PlanOut, SearchQuery, OilChangeDeduct
from ..services.telemetry import log_event
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List

router = APIRouter(prefix="/customers", tags=["customers"])

@router.post("/", response_model=CustomerOut)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    log_event('create_customer', 'customer', {'first': payload.first_name, 'last': payload.last_name})
    phone_norm = normalize_phone(payload.phone)
    c = Customer(first_name=payload.first_name.strip(), 
                 last_name=payload.last_name.strip(), 
                 phone=phone_norm)
    db.add(c)
    db.commit()
    db.refresh(c)
    # auto assign empty plan
    plan = OilChangePlan(customer_id=c.id, total_allowed=0, remaining=0, active=True)
    db.add(plan)
    db.commit()
    return c

@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    return c

@router.post("/search", response_model=List[CustomerOut])
def search_customers(q: SearchQuery, db: Session = Depends(get_db)):
    term = q.name_or_phone.strip()
    query = db.query(Customer)
    if term.isdigit() or any(ch.isdigit() for ch in term):
        res = query.filter(Customer.phone.contains(term)).limit(50).all()
    log_event('search', 'customer', {'term': term, 'results': len(res)})
    return res
    parts = term.split()
    if len(parts) == 1:
        res = query.filter((Customer.first_name.ilike(f"%{term}%")) | (Customer.last_name.ilike(f"%{term}%"))).limit(50).all()
    log_event('search', 'customer', {'term': term, 'results': len(res)})
    return res
    first, last = parts[0], " ".join(parts[1:])
    res = query.filter(Customer.first_name.ilike(f"%{first}%"), Customer.last_name.ilike(f"%{last}%")).limit(50).all()
    log_event('search', 'customer', {'term': term, 'results': len(res)})
    return res

@router.post("/{customer_id}/deduct", response_model=PlanOut)
def deduct_oil_change(customer_id: int, payload: OilChangeDeduct, db: Session = Depends(get_db)):
    # Verify vehicle exists and belongs to customer
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        raise HTTPException(404, "Vehicle not found or does not belong to this customer")
    
    log_event('deduct', 'plan', {
        'customer_id': customer_id, 
        'vehicle_id': payload.vehicle_id, 
        'mileage': payload.mileage,
        'note': payload.note
    })
    
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        raise HTTPException(404, "Active plan not found")
    if plan.remaining <= 0:
        raise HTTPException(400, "No remaining oil changes")
        
    plan.remaining -= 1
    db.add(OilChangeLedger(
        customer_id=customer_id,
        vehicle_id=payload.vehicle_id,
        mileage=payload.mileage,
        delta=-1,
        note=payload.note
    ))
    db.commit()
    db.refresh(plan)
    return plan

@router.post("/{customer_id}/restore", response_model=PlanOut)
def restore_oil_change(customer_id: int, note: str = "Restored oil change", db: Session = Depends(get_db)):
    log_event('restore', 'plan', {'customer_id': customer_id, 'note': note})
    plan = db.query(OilChangePlan).filter_by(customer_id=customer_id, active=True).first()
    if not plan:
        raise HTTPException(404, "Active plan not found")
    if plan.remaining >= plan.total_allowed:
        raise HTTPException(400, "Plan already full")
    plan.remaining += 1
    db.add(OilChangeLedger(customer_id=customer_id, delta=+1, note=note))
    db.commit()
    db.refresh(plan)
    return plan

from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse, PlainTextResponse
import io, csv
from ..services.phone import normalize_phone

@router.get("/import", response_class=HTMLResponse)
def import_customers_form(request: Request):
    html = """
    <h2>Import Customers (CSV)</h2>
    <form method="post" action="/customers/import" enctype="multipart/form-data">
      <input type="file" name="file" accept=".csv">
      <button type="submit">Upload</button>
    </form>
    <p class="muted">Tips: Export from Google Contacts as CSV. Columns we look for: 
       <code>Given Name</code>, <code>Family Name</code>, <code>Phone 1 - Value</code>. 
       If not present, we also try <code>Name</code> and <code>Phone</code>.</p>
    """
    return HTMLResponse(html)

@router.post("/import")
def import_customers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = file.file.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    updated = 0
    for row in reader:
        first = (row.get("Given Name") or "").strip()
        last = (row.get("Family Name") or "").strip()
        phone = (row.get("Phone 1 - Value") or row.get("Phone") or "").strip()
        name = (row.get("Name") or "").strip()
        if (not first or not last) and name:
            # try to split name
            parts = name.split()
            if len(parts) >= 2:
                first, last = parts[0], " ".join(parts[1:])
            else:
                first, last = name, ""
        phone = normalize_phone(phone)

        if not (first or last or phone):
            continue

        # dedupe by phone if present
        existing = None
        if phone:
            existing = db.query(Customer).filter(Customer.phone == phone).first()
        if existing:
            # maybe update missing names
            if not existing.first_name and first:
                existing.first_name = first
            if not existing.last_name and last:
                existing.last_name = last
            db.add(existing); db.commit()
            updated += 1
        else:
            c = Customer(first_name=first or "", last_name=last or "", phone=phone or "")
            db.add(c); db.commit(); db.refresh(c)
            # auto plan
            plan = OilChangePlan(customer_id=c.id, total_allowed=0, remaining=0, active=True)
            db.add(plan); db.commit()
            inserted += 1

    return PlainTextResponse(f"Import complete. Inserted: {inserted}, Updated: {updated}")

@router.get("/export")
def export_customers(db: Session = Depends(get_db)):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["first_name", "last_name", "phone"])
    for c in db.query(Customer).order_by(Customer.last_name, Customer.first_name).all():
        writer.writerow([c.first_name, c.last_name, c.phone])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=customers_export.csv"
    })
