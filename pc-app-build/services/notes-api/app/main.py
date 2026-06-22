"""
Notes API — FastAPI application entry point.

Provides RESTful CRUD and fuzzy search for notes, backed by SQLite via
SQLAlchemy. Phase 1 only wires the app shell and health router; CRUD/search
implementation is completed in Phase 2.
"""

from fastapi import FastAPI

from app.routers.health import router as health_router

app = FastAPI(
    title="Notes API",
    version="0.1.0",
    description="Note management service for Note Assistant",
)

app.include_router(health_router)
