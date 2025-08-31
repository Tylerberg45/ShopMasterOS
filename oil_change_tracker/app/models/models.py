from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from ..database import Base

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), index=True)
    last_name: Mapped[str] = mapped_column(String(100), index=True)
    phone: Mapped[str] = mapped_column(String(20), index=True, unique=False, default="")

    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    plans = relationship("OilChangePlan", back_populates="customer", cascade="all, delete-orphan")
    ledger_entries = relationship("OilChangeLedger", back_populates="customer", cascade="all, delete-orphan")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    year: Mapped[str] = mapped_column(String(10), default="")
    make: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    vin: Mapped[str] = mapped_column(String(30), index=True, default="")
    plate: Mapped[str] = mapped_column(String(20), index=True, default="")
    oil_type: Mapped[str] = mapped_column(String(20), default="")
    oil_capacity_quarts: Mapped[str] = mapped_column(String(10), default="")

    owner = relationship("Customer", back_populates="vehicles")

class OilChangePlan(Base):
    __tablename__ = "oil_change_plans"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    total_allowed: Mapped[int] = mapped_column(Integer, default=4)
    remaining: Mapped[int] = mapped_column(Integer, default=4)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer = relationship("Customer", back_populates="plans")

class OilChangeLedger(Base):
    __tablename__ = "oil_change_ledger"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    delta: Mapped[int] = mapped_column(Integer)  # -1 for use, +1 for restore
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="ledger_entries")
