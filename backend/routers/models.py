"""
Model CRUD API endpoints.
"""
import asyncio
import re
import shutil
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image

Image.MAX_IMAGE_PIXELS = 25_000_000  # ~5000x5000, prevent decompression bombs

from .. import config
from ..services.library import (
    catalog_model,
    upload_model,
    update_model_metadata,
    rename_model,
    delete_library_model,
    compute_hash,
    cleanup_empty_parents,
)
from ..services.metadata import (
    load_all_models,
    load_model,
    load_index,
    is_library_initialized,
    THUMBNAILS_DIR,
    ensure_metadata_dir,
    save_model,
    rebuild_index,
)
from ..schemas.model import ModelHistoryEntry
from ..utils import validate_model_id, safe_resolve
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)


class CatalogRequest(BaseModel):
    relative_path: str
    name: str
    category: str = "other"
    description: str = ""
    tags: list[str] = []
    target_subfolder: str = ""


class BulkCatalogRequest(BaseModel):
    models: list[CatalogRequest]


class UpdateModelRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    base_model: Optional[str] = None
    filename: Optional[str] = None  # Rename the physical file
    subfolder: Optional[str] = None  # Move within category (empty string = category root)


class RenameRequest(BaseModel):
    new_name: str
    rename_file: bool = True


class DeleteConfirmation(BaseModel):
    confirm_text: str


@router.get("/")
async def list_models():
    """List all models in the library (uses cached index)."""
    if not is_library_initialized():
        return {"models": [], "count": 0, "initialized": False}
    index = load_index()
    return {"models": index, "count": len(index), "initialized": True}


@router.get("/stats")
async def model_stats():
    """Get storage statistics: total size, per-category breakdown, and duplicates."""
    index = load_index()
    total_size = 0
    by_category = {}
    hash_map = {}

    for m in index:
        size = m.get("size", 0) or 0
        total_size += size
        cat = m.get("category", "other")
        if cat not in by_category:
            by_category[cat] = {"count": 0, "size": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["size"] += size

        sha = m.get("hash", {})
        if isinstance(sha, dict):
            sha = sha.get("sha256")
        if sha:
            hash_map.setdefault(sha, []).append({
                "id": m["id"],
                "name": m.get("name", ""),
                "filename": m.get("filename", ""),
                "category": m.get("category", ""),
            })

    duplicates = {h: models for h, models in hash_map.items() if len(models) > 1}
    duplicate_ids = set()
    for models in duplicates.values():
        for mdl in models:
            duplicate_ids.add(mdl["id"])

    return {
        "total_models": len(index),
        "total_size": total_size,
        "by_category": by_category,
        "duplicates": duplicates,
        "duplicate_ids": list(duplicate_ids),
    }


@router.get("/{model_id}")
async def get_model(model_id: str):
    """Get a single model's full metadata."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model.model_dump()


@router.post("/catalog")
async def catalog_model_endpoint(req: CatalogRequest, background_tasks: BackgroundTasks):
    """Catalog an existing file in the library (from scan results)."""
    try:
        model = catalog_model(
            relative_path=req.relative_path,
            name=req.name,
            category=req.category,
            description=req.description,
            tags=req.tags,
            target_subfolder=req.target_subfolder,
        )
        background_tasks.add_task(compute_hash, model.id)
        return model.model_dump()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/catalog/bulk")
async def bulk_catalog_endpoint(req: BulkCatalogRequest, background_tasks: BackgroundTasks):
    """Catalog multiple files at once."""
    results = []
    errors = []
    for item in req.models:
        try:
            model = catalog_model(
                relative_path=item.relative_path,
                name=item.name,
                category=item.category,
                description=item.description,
                tags=item.tags,
                target_subfolder=item.target_subfolder,
                _defer_index=True,
            )
            background_tasks.add_task(compute_hash, model.id)
            results.append(model.model_dump())
        except Exception as e:
            errors.append({"relative_path": item.relative_path, "error": str(e)})
    if results:
        rebuild_index()
    return {"cataloged": results, "errors": errors, "count": len(results)}


@router.post("/upload")
async def upload_model_endpoint(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form("other"),
    description: str = Form(""),
    tags: str = Form(""),
    subfolder: str = Form(""),
    base_model: str = Form(""),
    custom_filename: str = Form(""),
    background_tasks: BackgroundTasks = None,
):
    """Upload a model file to the library."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        model = upload_model(
            filename=custom_filename.strip() if custom_filename.strip() else file.filename,
            category=category,
            name=name,
            data_stream=file.file,
            description=description,
            tags=tag_list,
            subfolder=subfolder.strip() if subfolder.strip() else None,
            base_model=base_model.strip() if base_model.strip() else None,
        )
        if background_tasks:
            background_tasks.add_task(compute_hash, model.id)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


class BulkUpdateRequest(BaseModel):
    model_ids: list[str]
    category: Optional[str] = None
    tags_add: Optional[list[str]] = None
    tags_remove: Optional[list[str]] = None
    base_model: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    model_ids: list[str]
    confirm_text: str


@router.post("/bulk/update")
async def bulk_update_models(req: BulkUpdateRequest):
    """Bulk update metadata for multiple models (category, tags, base model)."""
    if len(req.model_ids) > 100:
        raise HTTPException(status_code=400, detail="Bulk update limited to 100 models")

    results = []
    errors = []
    for model_id in req.model_ids:
        try:
            updates = {}
            if req.category is not None:
                updates["category"] = req.category
            if req.base_model is not None:
                updates["base_model"] = req.base_model
            if req.tags_add or req.tags_remove:
                model = load_model(model_id)
                if model:
                    current_tags = list(model.tags or [])
                    if req.tags_add:
                        for t in req.tags_add:
                            if t not in current_tags:
                                current_tags.append(t)
                    if req.tags_remove:
                        current_tags = [t for t in current_tags if t not in req.tags_remove]
                    updates["tags"] = current_tags
            if updates:
                model = update_model_metadata(model_id, updates)
                results.append(model_id)
        except Exception as e:
            errors.append({"id": model_id, "error": str(e)})

    return {"updated": len(results), "errors": errors}


@router.post("/bulk/delete")
async def bulk_delete_models(req: BulkDeleteRequest):
    """Bulk delete multiple models from the library."""
    if req.confirm_text.lower() != "delete":
        raise HTTPException(status_code=400, detail="Type 'delete' to confirm bulk deletion.")
    if len(req.model_ids) > 100:
        raise HTTPException(status_code=400, detail="Bulk delete limited to 100 models")

    results = []
    errors = []
    for model_id in req.model_ids:
        try:
            delete_library_model(model_id, delete_file=True)
            results.append(model_id)
        except Exception as e:
            errors.append({"id": model_id, "error": str(e)})

    return {"deleted": len(results), "errors": errors}


@router.put("/{model_id}")
async def update_model_endpoint(model_id: str, req: UpdateModelRequest):
    """Update a model's metadata."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    if "subfolder" in updates:
        sub = updates["subfolder"].strip()
        if sub and not re.match(r'^[a-zA-Z0-9_\-/ ]+$', sub):
            raise HTTPException(status_code=400, detail="Invalid subfolder name")
    try:
        model = update_model_metadata(model_id, updates)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{model_id}/rename")
async def rename_model_endpoint(model_id: str, req: RenameRequest):
    """Rename a model (metadata and optionally the physical file)."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    try:
        model = rename_model(model_id, req.new_name, req.rename_file)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File rename failed: {e}")


class MoveRequest(BaseModel):
    subfolder: str = ""  # empty string = move to category root


@router.post("/{model_id}/move")
async def move_model_endpoint(model_id: str, req: MoveRequest):
    """Move a model to a subfolder within its category."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    subfolder = req.subfolder.strip()
    if subfolder and not re.match(r'^[a-zA-Z0-9_\-/ ]+$', subfolder):
        raise HTTPException(status_code=400, detail="Invalid subfolder name")

    old_path = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    if not old_path.is_file():
        raise HTTPException(status_code=404, detail="Model file not found on disk")

    if subfolder:
        new_dir = safe_resolve(config.LIBRARY_PATH, f"{model.category}/{subfolder}")
    else:
        new_dir = safe_resolve(config.LIBRARY_PATH, model.category)

    new_dir.mkdir(parents=True, exist_ok=True)
    new_path = new_dir / model.filename

    if new_path.exists() and new_path != old_path:
        raise HTTPException(status_code=409, detail="A file with that name already exists in the target folder")

    if old_path != new_path:
        shutil.move(str(old_path), str(new_path))
        model.relative_path = str(new_path.relative_to(config.LIBRARY_PATH))
        model.updated_at = datetime.now().isoformat()
        model.history.append(ModelHistoryEntry(
            action="moved",
            timestamp=model.updated_at,
            details={"from": str(old_path.relative_to(config.LIBRARY_PATH)), "to": model.relative_path}
        ))
        save_model(model)
        rebuild_index()
        cleanup_empty_parents(old_path, config.LIBRARY_PATH)

    return model.model_dump()


@router.delete("/{model_id}")
async def delete_model_endpoint(model_id: str, req: DeleteConfirmation):
    """Delete a model from the library. Requires typing 'delete' to confirm."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if req.confirm_text.lower() != "delete":
        raise HTTPException(
            status_code=400,
            detail="Type 'delete' to confirm deletion.",
        )

    result = delete_library_model(model_id, delete_file=True)
    return result


@router.post("/{model_id}/hash")
async def compute_hash_endpoint(model_id: str):
    """Compute or recompute SHA-256 hash for a model."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    hash_value = await asyncio.to_thread(compute_hash, model_id)
    if not hash_value:
        raise HTTPException(status_code=500, detail="Hash computation failed")
    return {"model_id": model_id, "hash": {"sha256": hash_value}}


@router.get("/{model_id}/download")
async def download_model(model_id: str):
    """Download a model file to the user's browser."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")

    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        filepath = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model path")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Model file not found on disk")

    return FileResponse(
        path=str(filepath),
        filename=model.filename,
        media_type="application/octet-stream",
    )


ALLOWED_THUMBNAIL_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_THUMBNAIL_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/{model_id}/thumbnail")
async def upload_thumbnail(model_id: str, file: UploadFile = File(...)):
    """Upload a thumbnail image for a model. Auto-converts to max 400x400 webp."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if file.content_type not in ALLOWED_THUMBNAIL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Allowed: JPEG, PNG, WebP, GIF",
        )

    content = await file.read()
    if len(content) > MAX_THUMBNAIL_SIZE:
        raise HTTPException(status_code=400, detail="Thumbnail must be under 5MB")

    try:
        img = Image.open(BytesIO(content))
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=85)
        webp_data = buf.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not process image")

    ensure_metadata_dir()
    thumb_path = THUMBNAILS_DIR / f"{model_id}.webp"

    # Remove any existing thumbnail with different extension
    for old in THUMBNAILS_DIR.glob(f"{model_id}.*"):
        old.unlink(missing_ok=True)

    thumb_path.write_bytes(webp_data)

    rel_thumb = f"thumbnails/{model_id}.webp"
    update_model_metadata(model_id, {"thumbnail": rel_thumb})

    return {"thumbnail": rel_thumb}


@router.delete("/{model_id}/thumbnail")
async def delete_thumbnail(model_id: str):
    """Remove a model's thumbnail."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    for old in THUMBNAILS_DIR.glob(f"{model_id}.*"):
        old.unlink(missing_ok=True)

    update_model_metadata(model_id, {"thumbnail": None})
    return {"deleted": True}


@router.get("/{model_id}/thumbnail")
async def get_thumbnail(model_id: str):
    """Serve a model's thumbnail image."""
    try:
        model_id = validate_model_id(model_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID format")
    model = load_model(model_id)
    if not model or not model.thumbnail:
        raise HTTPException(status_code=404, detail="No thumbnail found")

    thumb_path = THUMBNAILS_DIR / Path(model.thumbnail).name
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    media_type = media_map.get(thumb_path.suffix.lower(), "image/jpeg")

    return FileResponse(path=str(thumb_path), media_type=media_type)
