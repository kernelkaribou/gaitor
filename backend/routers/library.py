"""
Library management API endpoints.
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.library import get_library_status, scan_for_untracked
from ..services.metadata import (
    is_library_initialized,
    initialize_library,
    load_categories,
    add_category,
    update_category,
    delete_category,
    rename_category,
)
from ..schemas.library import CategoryDefinition, DEFAULT_CATEGORIES

DEFAULT_CATEGORY_IDS = {c.id for c in DEFAULT_CATEGORIES}
from ..utils import safe_resolve
from .. import config

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


class CategoryRenameRequest(BaseModel):
    new_id: str
    new_label: str


@router.get("/status")
async def library_status_endpoint():
    """Get library status including initialization state and model count."""
    return get_library_status()


@router.post("/initialize")
async def initialize_library_endpoint(req: InitializeRequest):
    """Initialize the library metadata structure."""
    if is_library_initialized():
        raise HTTPException(status_code=409, detail="Library is already initialized")
    lib_config = await asyncio.to_thread(initialize_library, name=req.name, template=req.template)
    return {"message": "Library initialized", "config": lib_config.model_dump()}


@router.post("/scan")
async def scan_library():
    """Scan library directory for untracked model files."""
    if not is_library_initialized():
        raise HTTPException(status_code=400, detail="Library not initialized. Call POST /api/library/initialize first.")
    untracked = await asyncio.to_thread(scan_for_untracked)
    return {"untracked": untracked, "count": len(untracked)}


# --- Category endpoints ---

@router.get("/categories")
async def list_categories():
    """List all model categories with primary/extended grouping."""
    categories = load_categories()
    return {
        "categories": [
            {**c.model_dump(), "is_default": c.id in DEFAULT_CATEGORY_IDS}
            for c in categories
        ],
    }


@router.post("/categories")
async def create_category(req: CategoryRequest):
    """Create a new category (also creates the folder on disk)."""
    try:
        cat = CategoryDefinition(**req.model_dump())
        categories = add_category(cat)
        # Create the physical folder
        cat_dir = safe_resolve(config.LIBRARY_PATH, cat.id)
        cat_dir.mkdir(parents=True, exist_ok=True)
        return {"categories": [c.model_dump() for c in categories]}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/categories/{category_id}")
async def update_category_endpoint(category_id: str, req: CategoryUpdateRequest):
    """Update a category's label, extensions, or description."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        categories = update_category(category_id, updates)
        return {"categories": [c.model_dump() for c in categories]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/categories/{category_id}/rename")
async def rename_category_endpoint(category_id: str, req: CategoryRenameRequest):
    """Rename a category (renames folder and updates all model metadata)."""
    if category_id in DEFAULT_CATEGORY_IDS:
        raise HTTPException(status_code=403, detail="Default categories cannot be renamed")
    if not re.match(r'^[a-zA-Z0-9_-]+$', req.new_id):
        raise HTTPException(status_code=400, detail="Category ID must be alphanumeric with dashes/underscores only")
    try:
        categories = rename_category(category_id, req.new_id, req.new_label)
        return {
            "categories": [
                {**c.model_dump(), "is_default": c.id in DEFAULT_CATEGORY_IDS}
                for c in categories
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{category_id}")
async def delete_category_endpoint(category_id: str):
    """Delete a category."""
    if category_id in DEFAULT_CATEGORY_IDS:
        raise HTTPException(status_code=403, detail="Default categories cannot be deleted")
    categories = delete_category(category_id)
    return {"categories": [c.model_dump() for c in categories]}




@router.get("/categories/{category_id}/subfolders")
async def list_subfolders(category_id: str):
    """List all subfolders (recursively) within a category."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', category_id):
        raise HTTPException(status_code=400, detail="Invalid category ID")
    cat_dir = safe_resolve(config.LIBRARY_PATH, category_id)
    if not cat_dir.is_dir():
        raise HTTPException(status_code=404, detail="Category directory not found")
    subfolders = []
    for root, dirs, _files in os.walk(str(cat_dir)):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        root_path = Path(root)
        for d in sorted(dirs):
            rel = str((root_path / d).relative_to(cat_dir))
            subfolders.append(rel)
    return {"subfolders": sorted(subfolders)}

