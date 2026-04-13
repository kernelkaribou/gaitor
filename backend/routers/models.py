"""
Model CRUD API endpoints — placeholder.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_models():
    """List all models in the library."""
    return {"models": [], "message": "Model management coming in Phase 2"}
