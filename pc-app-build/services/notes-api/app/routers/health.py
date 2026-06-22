"""
Health check endpoint for the Notes API.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Return the basic service health state."""

    return {
        "status": "ok",
        "service": "notes-api",
        "version": "0.2.0",
    }
