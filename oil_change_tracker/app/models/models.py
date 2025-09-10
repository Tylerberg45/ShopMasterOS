from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime, date
from ..database import Base

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), index=True)
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    phone: Mapped[str] = mapped_column(String(20), index=True, unique=False, default="")
    landline: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")

    vehicles = relationship("Vehicle", foreign_keys="[Vehicle.customer_id]", back_populates="owner", cascade="all, delete-orphan")
    plans = relationship("OilChangePlan", back_populates="customer", cascade="all, delete-orphan")
    ledger_entries = relationship("OilChangeLedger", back_populates="customer", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="customer", cascade="all, delete-orphan")

    @property
    def name(self):
        """Return the full name of the customer"""
        # If last_name is empty, first_name contains the full name (possibly combined)
        if not self.last_name:
            return self.first_name.strip()
        else:
            return f"{self.first_name} {self.last_name}".strip()

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    # Optional primary driver (can point to any customer)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    year: Mapped[str] = mapped_column(String(10), default="")
    make: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    vin: Mapped[str] = mapped_column(String(30), index=True, default="")
    plate: Mapped[str] = mapped_column(String(20), index=True, default="")
    oil_type: Mapped[str] = mapped_column(String(20), default="")
    oil_capacity_quarts: Mapped[str] = mapped_column(String(10), default="")
    oil_weight: Mapped[str] = mapped_column(String(10), default="")

    owner = relationship("Customer", foreign_keys=[customer_id], back_populates="vehicles")
    driver = relationship("Customer", foreign_keys=[driver_id])

class OilChangePlan(Base):
    __tablename__ = "oil_change_plans"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    total_allowed: Mapped[int] = mapped_column(Integer, default=4)
    remaining: Mapped[int] = mapped_column(Integer, default=4)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer = relationship("Customer", back_populates="plans")

class VinOilSpec(Base):
    """Store learned oil specifications for each VIN"""
    __tablename__ = "vin_oil_specs"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vin: Mapped[str] = mapped_column(String(17), index=True, unique=True)
    oil_weight: Mapped[str] = mapped_column(String(10), default="")
    oil_capacity_quarts: Mapped[str] = mapped_column(String(10), default="")
    oil_type: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    usage_count: Mapped[int] = mapped_column(Integer, default=1)  # How many times this spec has been used

class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="")
    mobile: Mapped[str] = mapped_column(String(20), default="")
    landline: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    customer = relationship("Customer", back_populates="contacts")

class OilChangeLedger(Base):
    __tablename__ = "oil_change_ledger"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    mileage: Mapped[int] = mapped_column(Integer, nullable=True)
    oil_weight: Mapped[str] = mapped_column(String(10), nullable=True)
    oil_quarts: Mapped[float] = mapped_column(Float, nullable=True)
    delta: Mapped[int] = mapped_column(Integer)  # -1 for use, +4 for tire purchase
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    # Manual ordering support for UI drag/drop (lower value displayed first). Null = fallback ordering.
    order_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    customer = relationship("Customer", back_populates="ledger_entries")
    vehicle = relationship("Vehicle")

    @property
    def was_free(self) -> bool:
        return self.delta == -1

    @property
    def is_addition(self) -> bool:
        return self.delta > 0

    @property
    def is_note(self) -> bool:
        return self.delta == 0
