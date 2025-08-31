from fastapi import FastAPI

app = FastAPI(title="ShopMasterOS - Oil Change Tracker (MVP)")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
import sqlite3
from datetime import datetime

DB_PATH = "oilchange.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            plate TEXT,
            oil_changes_remaining INTEGER NOT NULL DEFAULT 4
        );""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS oil_change_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            at_utc TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );""")
        con.commit()

init_db()

class CustomerIn(BaseModel):
    name: str
    phone: str
    plate: Optional[str] = None
    oil_changes_remaining: Optional[int] = 4

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str):
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) < 7:
            raise ValueError("phone looks invalid")
        return digits

class CustomerOut(BaseModel):
    id: int
    name: str
    phone: str
    plate: Optional[str]
    oil_changes_remaining: int

class DecrementIn(BaseModel):
    reason: Optional[str] = "oil change used"

app = FastAPI(title="ShopMasterOS - Oil Change Tracker (MVP)")

def row_to_customer(row) -> CustomerOut:
    return CustomerOut(
        id=row[0], name=row[1], phone=row[2],
        plate=row[3], oil_changes_remaining=row[4]
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/customers", response_model=CustomerOut)
def create_customer(body: CustomerIn):
    with get_conn() as con:
        cur = con.cursor()
        try:
            cur.execute(
                "INSERT INTO customers(name, phone, plate, oil_changes_remaining) VALUES(?,?,?,?)",
                (body.name, body.phone, body.plate, body.oil_changes_remaining or 4),
            )
            con.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Phone already exists")
        cur.execute("SELECT id, name, phone, plate, oil_changes_remaining FROM customers WHERE phone = ?", (body.phone,))
        row = cur.fetchone()
        return row_to_customer(row)

@app.get("/customers/search", response_model=List[CustomerOut])
def search_customers(q: str):
    like = f"%{q}%"
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, name, phone, plate, oil_changes_remaining
            FROM customers
            WHERE name LIKE ? OR phone LIKE ? OR IFNULL(plate,'') LIKE ?
            ORDER BY name
        """, (like, like, like))
        rows = cur.fetchall()
        return [row_to_customer(r) for r in rows]

@app.get("/customers/by-phone/{phone}", response_model=CustomerOut)
def get_by_phone(phone: str):
    digits = "".join(ch for ch in phone if ch.isdigit())
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT id, name, phone, plate, oil_changes_remaining FROM customers WHERE phone = ?", (digits,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return row_to_customer(row)

@app.post("/customers/{customer_id}/decrement", response_model=CustomerOut)
def decrement(customer_id: int, body: DecrementIn):
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("SELECT oil_changes_remaining FROM customers WHERE id = ?", (customer_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        remaining = row[0]
        if remaining <= 0:
            raise HTTPException(status_code=400, detail="No oil changes remaining")

        cur.execute("UPDATE customers SET oil_changes_remaining = oil_changes_remaining - 1 WHERE id = ?", (customer_id,))
        cur.execute("""
            INSERT INTO oil_change_audit(customer_id, delta, reason, at_utc)
            VALUES(?, ?, ?, ?)
        """, (customer_id, -1, body.reason, datetime.utcnow().isoformat(timespec="seconds")))
        con.commit()

        cur.execute("SELECT id, name, phone, plate, oil_changes_remaining FROM customers WHERE id = ?", (customer_id,))
        row = cur.fetchone()
        return row_to_customer(row)

@app.get("/customers/{customer_id}/audit", response_model=List[Dict[str, Any]])
def audit(customer_id: int):
    with get_conn() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT id, delta, reason, at_utc
            FROM oil_change_audit
            WHERE customer_id = ?
            ORDER BY id DESC
        """, (customer_id,))
        rows = cur.fetchall()
        return [{"id": r[0], "delta": r[1], "reason": r[2], "at_utc": r[3]} for r in rows]
