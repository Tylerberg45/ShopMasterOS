import httpx

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
