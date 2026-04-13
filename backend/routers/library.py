"""
Library management API endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from ..services.library import get_library_status, scan_for_untracked
from ..services.metadata import (
    is_library_initialized,
    initialize_library,
    load_categories,
    add_category,
    update_category,
    delete_category,
)
from ..schemas.library import CategoryDefinition, PRIMARY_CATEGORY_IDS

router = APIRouter()
logger = logging.getLogger(__name__)


class InitializeRequest(BaseModel):
    name: str = "Model Library"
    template: str = "default"


class CategoryRequest(BaseModel):
    id: str
    label: str
    extensions: list[str] = []
    description: str = ""


class CategoryUpdateRequest(BaseModel):
    label: Optional[str] = None
    extensions: Optional[list[str]] = None
    description: Optional[str] = None


@router.get("/status")
async def library_status_endpoint():
    """Get library status including initialization state and model count."""
    return get_library_status()


@router.post("/initialize")
async def initialize_library_endpoint(req: InitializeRequest):
    """Initialize the library metadata structure."""
    if is_library_initialized():
        raise HTTPException(status_code=409, detail="Library is already initialized")
    lib_config = initialize_library(name=req.name, template=req.template)
    return {"message": "Library initialized", "config": lib_config.model_dump()}


@router.post("/scan")
async def scan_library():
    """Scan library directory for untracked model files."""
    if not is_library_initialized():
        raise HTTPException(status_code=400, detail="Library not initialized. Call POST /api/library/initialize first.")
    untracked = scan_for_untracked()
    return {"untracked": untracked, "count": len(untracked)}


# --- Category endpoints ---

@router.get("/categories")
async def list_categories():
    """List all model categories with primary/extended grouping."""
    categories = load_categories()
    return {
        "categories": [
            {**c.model_dump(), "is_primary": c.id in PRIMARY_CATEGORY_IDS}
            for c in categories
        ],
    }


@router.post("/categories")
async def create_category(req: CategoryRequest):
    """Create a new category."""
    try:
        cat = CategoryDefinition(**req.model_dump())
        categories = add_category(cat)
        return {"categories": [c.model_dump() for c in categories]}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/categories/{category_id}")
async def update_category_endpoint(category_id: str, req: CategoryUpdateRequest):
    """Update a category."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        categories = update_category(category_id, updates)
        return {"categories": [c.model_dump() for c in categories]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/categories/{category_id}")
async def delete_category_endpoint(category_id: str):
    """Delete a category."""
    categories = delete_category(category_id)
    return {"categories": [c.model_dump() for c in categories]}
