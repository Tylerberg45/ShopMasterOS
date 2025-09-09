"""Deployment entrypoint.

This thin wrapper re-exports the full application defined in
oil_change_tracker/app/main.py so that a default start command like:
    uvicorn app:app --host 0.0.0.0 --port 8080
will serve the complete UI (/, /ui, etc.) and API routes.

If you previously relied on the lightweight sqlite-only endpoints that
were here, they have been superseded by the richer implementation.
"""

from oil_change_tracker.app.main import app  # noqa: F401

# Optional: simple health passthrough (already defined inside main app)
# Left here in case infrastructure probes specifically /health before
# internal routes are loaded.
@app.get("/health-wrapper")
def health_wrapper():  # pragma: no cover
        return {"ok": True, "source": "wrapper"}
