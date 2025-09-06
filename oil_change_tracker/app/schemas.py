from pydantic import BaseModel, Field
from typing import Optional, List

class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str = ""

class CustomerOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    class Config:
        from_attributes = True

class VehicleCreate(BaseModel):
    customer_id: int
    year: str = ""
    make: str = ""
    model: str = ""
    vin: str = ""
    plate: str = ""

class VehicleOut(BaseModel):
    id: int
    customer_id: int
    year: str
    make: str
    model: str
    vin: str
    plate: str
    class Config:
        from_attributes = True

class PlanCreate(BaseModel):
    customer_id: int
    total_allowed: int = 4

class PlanOut(BaseModel):
    id: int
    customer_id: int
    total_allowed: int
    remaining: int
    active: bool
    class Config:
        from_attributes = True

class OilChangeDeduct(BaseModel):
    vehicle_id: int
    mileage: int
    note: str = "Oil change used"

class LedgerEntryOut(BaseModel):
    id: int
    delta: int
    note: str
    customer_id: int
    vehicle_id: Optional[int] = None
    mileage: Optional[int] = None
    class Config:
        from_attributes = True

class SearchQuery(BaseModel):
    name_or_phone: str = Field(..., description="Enter 'First Last' or phone number")
