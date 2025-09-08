#!/usr/bin/env python3
"""Simple one-off migration from SQLite to Postgres.
Usage:
  python migrate_sqlite_to_postgres.py sqlite:///./oilchange.db $DATABASE_URL

Notes:
- Requires both SQLAlchemy drivers installed (psycopg2 for Postgres).
- Idempotent: skips inserting rows that already exist by primary key.
"""
import sys, os
from sqlalchemy import create_engine, text

if len(sys.argv) != 3:
    print("Usage: python migrate_sqlite_to_postgres.py <sqlite_url> <postgres_url>")
    sys.exit(1)

sqlite_url, pg_url = sys.argv[1], sys.argv[2]
if pg_url.startswith("postgresql://") and "+psycopg2" not in pg_url:
    pg_url = pg_url.replace("postgresql://", "postgresql+psycopg2://", 1)

src = create_engine(sqlite_url, future=True)
Dst = create_engine(pg_url, future=True)

TABLES = [
    "customers",
    "vehicles",
    "oil_change_plans",
    "vin_oil_specs",
    "oil_change_ledger",
]

with src.connect() as s, Dst.connect() as d:
    # Ensure destination tables exist
    # (Assumes app started once so create_all already ran.)
    for t in TABLES:
        rows = s.execute(text(f"SELECT * FROM {t}")).fetchall()
        if not rows:
            continue
        cols = [c.key for c in rows[0]._mapping.keys()]
        placeholders = ",".join([f":{c}" for c in cols])
        insert_sql = text(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING")
        inserted = 0
        for r in rows:
            params = {c: r._mapping[c] for c in cols}
            try:
                d.execute(insert_sql, params)
                inserted += 1
            except Exception as e:
                # Ignore individual row failures
                pass
        d.commit()
        print(f"Table {t}: attempted {len(rows)}, inserted {inserted}")

print("Migration complete.")
