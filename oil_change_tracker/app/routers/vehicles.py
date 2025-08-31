from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.telemetry import log_event
from ..models.models import Vehicle, Customer
from ..schemas import VehicleCreate, VehicleOut
from ..services.plate_lookup import plate_to_vin, PlateLookupError
from typing import Optional

router = APIRouter(prefix="/vehicles", tags=["vehicles"])

@router.post("/", response_model=VehicleOut)
async def add_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    log_event('vehicle_add', 'vehicle', {'plate': payload.plate, 'vin': payload.vin})
    owner = db.get(Customer, payload.customer_id)
    if not owner:
        raise HTTPException(404, "Customer not found")

    vin = payload.vin
    if not vin and payload.plate:
        try:
            vin = await plate_to_vin(payload.plate)
        except PlateLookupError as e:
            raise HTTPException(400, f"Plate lookup error: {e}")

    v = Vehicle(
        customer_id=payload.customer_id,
        year=payload.year or "",
        make=payload.make or "",
        model=payload.model or "",
        vin=vin or "",
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
    db: Session = Depends(get_db)
):
    v = db.get(Vehicle, vehicle_id)
    if not v:
        return RedirectResponse(f"/ui/customer/{v.customer_id}?error=Vehicle+not+found", status_code=303)
    
    try:
        v.plate = plate.strip().upper()
        v.vin = vin.strip().upper()
        v.year = year.strip()
        v.make = make.strip()
        v.model = model.strip()
        db.add(v)
        db.commit()
        return RedirectResponse(f"/ui/customer/{v.customer_id}", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            f"/ui/customer/{v.customer_id}?error=Error+updating+vehicle:+{str(e)}", 
            status_code=303
        )

@router.post("/{vehicle_id}/refresh_specs", response_model=VehicleOut)
async def refresh_specs(vehicle_id: int, db: Session = Depends(get_db)):
    log_event('spec_lookup', 'vehicle', {'vehicle_id': vehicle_id})
    v = db.get(Vehicle, vehicle_id)
    if not v:
        raise HTTPException(404, "Vehicle not found")

    # try to get engine text from VIN via NHTSA
    engine_text = ""
    if v.vin:
        try:
            print(f"Looking up VIN: {v.vin}")  # Debug log
            from ..services.nhtsa import decode_vin_engine_text
            engine_text = await decode_vin_engine_text(v.vin)
            print(f"NHTSA response for VIN {v.vin}: {engine_text}")  # Debug log
            if not engine_text:
                raise HTTPException(400, "Could not decode VIN information. Please check if the VIN is correct.")
        except Exception as e:
            print(f"Error in NHTSA lookup for VIN {v.vin}: {str(e)}")  # Debug log
            raise HTTPException(500, f"Error looking up VIN: {str(e)}")

    try:
        from ..services.oil_specs import match_spec
        spec = match_spec(v.year, v.make, v.model, engine_text)
        if spec:
            v.oil_type = spec.get("oil_type", "")
            cap = spec.get("capacity_quarts")
            v.oil_capacity_quarts = str(cap) if cap is not None else ""
            db.add(v); db.commit(); db.refresh(v)
        else:
            # Instead of raising an error, redirect with error message
            return RedirectResponse(
                f"/ui/customer/{v.customer_id}?error=No+oil+specifications+found+for+{v.year}+{v.make}+{v.model}", 
                status_code=303
            )
        return v
    except Exception as e:
        error_msg = str(e)
        if isinstance(e, HTTPException):
            error_msg = e.detail
        return RedirectResponse(
            f"/ui/customer/{v.customer_id}?error={error_msg}", 
            status_code=303
        )
