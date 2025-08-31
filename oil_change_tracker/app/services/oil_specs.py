import json
import os
from typing import Optional

SPECS_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "oil_specs.json")

def _load_specs():
    with open(SPECS_PATH, "r") as f:
        data = json.load(f)
    return data.get("specs", [])

def match_spec(year: str, make: str, model: str, engine_text: str = "") -> Optional[dict]:
    """Return a dict with oil_type and capacity_quarts if found, else None."""
    if not (year and make and model):
        print(f"Missing required fields: year={year}, make={make}, model={model}")
        return None
    Y = str(year).strip()
    M = (make or "").upper().strip()
    MD = (model or "").upper().strip()
    E = (engine_text or "").upper()
    
    print(f"Looking for match with: year={Y}, make={M}, model={MD}, engine={E}")  # Debug log

    best = None
    specs = _load_specs()
    print(f"Loaded {len(specs)} specs to check")  # Debug log
    for row in specs:
        print(f"Checking spec: {row}")  # Debug log
        spec_year = str(row.get("year", "")).strip()
        spec_make = (row.get("make", "") or "").upper().strip()
        spec_model = (row.get("model", "") or "").upper().strip()
        
        if spec_year and spec_year != Y:
            print(f"Year mismatch: {spec_year} != {Y}")  # Debug log
            continue
            
        # Case-insensitive make comparison
        if spec_make and spec_make != M:
            print(f"Make mismatch: {spec_make} != {M}")  # Debug log
            continue
            
        # Case-insensitive model comparison, also try with and without spaces
        model_matches = (
            MD == spec_model or  # Exact match
            MD.replace(" ", "") == spec_model.replace(" ", "")  # No spaces match
        )
        if spec_model and not model_matches:
            print(f"Model mismatch: {spec_model} != {MD}")  # Debug log
            continue
        engine_contains = [s.upper() for s in row.get("engine_contains", [])]
        if engine_contains:
            if not any(s in E for s in engine_contains):
                continue
        best = {"oil_type": row.get("oil_type", ""), "capacity_quarts": row.get("capacity_quarts", None)}
        break
    return best
