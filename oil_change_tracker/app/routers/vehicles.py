from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.telemetry import log_event
from ..models.models import Vehicle, Customer
from ..schemas import VehicleCreate, VehicleOut
from typing import Optional

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.post("/", response_model=VehicleOut)
async def add_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    log_event('vehicle_add', 'vehicle', {'plate': payload.plate, 'vin': payload.vin})
    owner = db.get(Customer, payload.customer_id)
    if not owner:
        raise HTTPException(404, "Customer not found")

    # Simply use the provided VIN without lookup
    v = Vehicle(
        customer_id=payload.customer_id,
        year=payload.year or "",
        make=payload.make or "",
        model=payload.model or "",
        vin=payload.vin or "",
        plate=(payload.plate or "").upper(),
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v

@router.post("/{vehicle_id}/update")
async def update_vehicle(
    vehicle_id: int,
    plate: str = Form(...),
    vin: str = Form(""),
    year: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    oil_weight: str = Form(""),
    oil_capacity_quarts: str = Form(""),
    db: Session = Depends(get_db)
):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        # Can't use v.customer_id here since v is None
        return RedirectResponse(f"/?error=Vehicle+not+found", status_code=303)
    
    try:
        v.plate = plate.strip().upper()
        v.vin = vin.strip().upper()
        v.year = year.strip()
        v.make = make.strip()
        v.model = model.strip()
        v.oil_weight = oil_weight.strip()
        v.oil_capacity_quarts = oil_capacity_quarts.strip()
        db.add(v)
        db.commit()
        return RedirectResponse(f"/ui/customer/{v.customer_id}", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            f"/ui/customer/{v.customer_id}?error=Error+updating+vehicle:+{str(e)}", 
            status_code=303
        )


