import httpx
from typing import Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

async def decode_vin_vehicle_info(vin: str, db: Session = None) -> Dict[str, str]:
    """Decode VIN and return vehicle information dictionary"""
    vin = (vin or '').strip().upper()
    if len(vin) < 11:
        print(f"VIN too short: {vin}")  # Debug log
        return {}
        
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
    print(f"Calling NHTSA API: {url}")  # Debug log
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            print(f"NHTSA API response keys: {list(data.keys()) if data else 'None'}")  # Debug log
            
            if "Results" not in data:
                print("No Results in NHTSA response")  # Debug log
                return {}
                
            rows = data["Results"]
            if not rows:
                print("Empty Results in NHTSA response")  # Debug log
                return {}
                
            row = rows[0]
            
            # Extract vehicle information
            vehicle_info = {}
            
            # Basic vehicle info
            year = (row.get("ModelYear") or "").strip()
            make = (row.get("Make") or "").strip()
            model = (row.get("Model") or "").strip()
            
            if year and year.lower() not in ["null", "not applicable"]:
                vehicle_info["year"] = year
            if make and make.lower() not in ["null", "not applicable"]:
                vehicle_info["make"] = make
            if model and model.lower() not in ["null", "not applicable"]:
                vehicle_info["model"] = model
            
            # Check if we have learned oil specifications for this VIN
            if db and len(vin) == 17:  # Full VIN
                from ..models.models import VinOilSpec
                learned_spec = db.query(VinOilSpec).filter_by(vin=vin).first()
                if learned_spec:
                    print(f"Found learned oil spec for VIN {vin}")  # Debug log
                    if learned_spec.oil_weight:
                        vehicle_info["oil_weight"] = learned_spec.oil_weight
                    if learned_spec.oil_capacity_quarts:
                        vehicle_info["oil_capacity_quarts"] = learned_spec.oil_capacity_quarts
                    if learned_spec.oil_type:
                        vehicle_info["oil_type"] = learned_spec.oil_type
                    vehicle_info["_learned"] = True  # Flag to indicate this came from learned data
            
            print(f"Extracted vehicle info: {vehicle_info}")  # Debug log
            return vehicle_info
            
    except Exception as e:
        print(f"Error in NHTSA API call: {str(e)}")  # Debug log
        return {}

def learn_oil_spec_from_vehicle(db: Session, vehicle, update_existing: bool = True):
    """Learn oil specifications from a vehicle and store them for future use"""
    if not vehicle.vin or len(vehicle.vin.strip()) != 17:
        return  # Need full VIN
    
    vin = vehicle.vin.strip().upper()
    
    # Check if we have useful oil information to learn from
    has_oil_info = bool(vehicle.oil_weight or vehicle.oil_capacity_quarts or vehicle.oil_type)
    if not has_oil_info:
        return
    
    from ..models.models import VinOilSpec
    
    # Check if we already have a spec for this VIN
    existing_spec = db.query(VinOilSpec).filter_by(vin=vin).first()
    
    if existing_spec:
        if update_existing:
            # Update existing spec with new information
            if vehicle.oil_weight:
                existing_spec.oil_weight = vehicle.oil_weight
            if vehicle.oil_capacity_quarts:
                existing_spec.oil_capacity_quarts = vehicle.oil_capacity_quarts
            if vehicle.oil_type:
                existing_spec.oil_type = vehicle.oil_type
            existing_spec.usage_count += 1
            existing_spec.updated_at = func.now()
            db.add(existing_spec)
            print(f"Updated learned oil spec for VIN {vin}")
    else:
        # Create new spec
        new_spec = VinOilSpec(
            vin=vin,
            oil_weight=vehicle.oil_weight or "",
            oil_capacity_quarts=vehicle.oil_capacity_quarts or "",
            oil_type=vehicle.oil_type or "",
            usage_count=1
        )
        db.add(new_spec)
        print(f"Created new learned oil spec for VIN {vin}")
    
    try:
        db.commit()
    except Exception as e:
        print(f"Error saving learned oil spec: {e}")
        db.rollback()

async def decode_vin_engine_text(vin: str) -> str:
    vin = (vin or '').strip().upper()
    if len(vin) < 11:
        print(f"VIN too short: {vin}")  # Debug log
        return ""
        
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"
    print(f"Calling NHTSA API: {url}")  # Debug log
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            print(f"NHTSA API response: {data}")  # Debug log
            
            if "Results" not in data:
                print("No Results in NHTSA response")  # Debug log
                return ""
                
            rows = data["Results"]
            if not rows:
                print("Empty Results in NHTSA response")  # Debug log
                return ""
                
            row = rows[0]
            # Combine relevant fields to help matching (displacement, cylinders, engineModel)
            parts = []
            engine_fields = {
                "EngineModel": "Engine Model",
                "EngineManufacturer": "Engine Manufacturer",
                "DisplacementL": "Displacement (L)",
                "DisplacementCC": "Displacement (CC)",
                "EngineCylinders": "Cylinders",
                "FuelTypePrimary": "Fuel Type",
                "EngineConfiguration": "Engine Config",
                "DriveType": "Drive Type",
                "EngineHP": "Horsepower",
                "ValvesPerEngine": "Valves"
            }
            
            for key, label in engine_fields.items():
                val = (row.get(key) or "").strip()
                if val and val.lower() not in ["null", "not applicable"]:
                    parts.append(f"{label}: {val}")
                    
            print(f"Extracted engine info: {parts}")  # Debug log
            result = " | ".join(parts)
            if not result:
                print("No engine information found in NHTSA data")  # Debug log
            return result
            
    except Exception as e:
        print(f"Error in NHTSA API call: {str(e)}")  # Debug log
        raise Exception(f"NHTSA API error: {str(e)}")
