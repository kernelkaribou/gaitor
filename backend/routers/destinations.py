"""
Destination management API endpoints — placeholder.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_destinations():
    """List all registered destinations."""
    return {"destinations": [], "message": "Destination management coming in Phase 3"}
