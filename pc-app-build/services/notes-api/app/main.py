"""
Notes API — FastAPI application entry point.

Provides RESTful CRUD and fuzzy search for notes,
backed by SQLite via SQLAlchemy.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Notes API",
    version="0.1.0",
    description="Note management service for Note Assistant",
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "notes-api", "version": "0.1.0"}
