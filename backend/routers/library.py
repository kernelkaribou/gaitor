"""
Library management API endpoints — placeholder.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def library_status():
    """Get library status."""
    return {"status": "not_initialized", "message": "Library management coming in Phase 2"}
