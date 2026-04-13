"""
Model CRUD API endpoints.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import logging

from .. import config
from ..utils import validate_model_id
from ..services.library import (
    catalog_model,
    upload_model,
    update_model_metadata,
    rename_model,
    delete_library_model,
    compute_hash,
)
from ..services.metadata import (
    load_all_models,
    load_model,
    load_index,
    is_library_initialized,
    THUMBNAILS_DIR,
    ensure_metadata_dir,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class CatalogRequest(BaseModel):
    relative_path: str
    name: str
    category: str = "other"
    description: str = ""
    tags: list[str] = []


class BulkCatalogRequest(BaseModel):
    models: list[CatalogRequest]


class UpdateModelRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None


class RenameRequest(BaseModel):
    new_name: str
    rename_file: bool = True


class DeleteConfirmation(BaseModel):
    confirm_name: str


@router.get("/")
async def list_models():
    """List all models in the library (uses cached index)."""
    if not is_library_initialized():
        return {"models": [], "count": 0, "initialized": False}
    index = load_index()
    return {"models": index, "count": len(index), "initialized": True}


@router.get("/{model_id}")
async def get_model(model_id: str):
    """Get a single model's full metadata."""
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
        )
        # Compute hash in background
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
            )
            background_tasks.add_task(compute_hash, model.id)
            results.append(model.model_dump())
        except Exception as e:
            errors.append({"relative_path": item.relative_path, "error": str(e)})
    return {"cataloged": results, "errors": errors, "count": len(results)}


@router.post("/upload")
async def upload_model_endpoint(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form("other"),
    description: str = Form(""),
    tags: str = Form(""),
    background_tasks: BackgroundTasks = None,
):
    """Upload a model file to the library."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        model = upload_model(
            filename=file.filename,
            category=category,
            name=name,
            data_stream=file.file,
            description=description,
            tags=tag_list,
        )
        if background_tasks:
            background_tasks.add_task(compute_hash, model.id)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")


@router.put("/{model_id}")
async def update_model_endpoint(model_id: str, req: UpdateModelRequest):
    """Update a model's metadata."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    try:
        model = update_model_metadata(model_id, updates)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{model_id}/rename")
async def rename_model_endpoint(model_id: str, req: RenameRequest):
    """Rename a model (metadata and optionally the physical file)."""
    try:
        model = rename_model(model_id, req.new_name, req.rename_file)
        return model.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"File rename failed: {e}")


@router.delete("/{model_id}")
async def delete_model_endpoint(model_id: str, req: DeleteConfirmation):
    """Delete a model from the library. Requires typing the model name to confirm."""
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if req.confirm_name != model.name:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation name does not match. Type '{model.name}' to confirm deletion.",
        )

    result = delete_library_model(model_id, delete_file=True)
    return result


@router.post("/{model_id}/hash")
async def compute_hash_endpoint(model_id: str):
    """Compute or recompute SHA-256 hash for a model."""
    model = load_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    hash_value = compute_hash(model_id)
    if not hash_value:
        raise HTTPException(status_code=500, detail="Hash computation failed")
    return {"model_id": model_id, "hash": {"sha256": hash_value}}


@router.get("/{model_id}/download")
async def download_model(model_id: str):
    """Download a model file to the user's browser."""
    from ..utils import safe_resolve

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
    """Upload a thumbnail image for a model."""
    model_id = validate_model_id(model_id)
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

    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    ext = ext_map.get(file.content_type, ".jpg")
    ensure_metadata_dir()
    thumb_path = THUMBNAILS_DIR / f"{model_id}{ext}"

    # Remove any existing thumbnail with different extension
    for old in THUMBNAILS_DIR.glob(f"{model_id}.*"):
        old.unlink(missing_ok=True)

    thumb_path.write_bytes(content)

    # Update model metadata with thumbnail path
    rel_thumb = f"thumbnails/{model_id}{ext}"
    update_model_metadata(model_id, {"thumbnail": rel_thumb})

    return {"thumbnail": rel_thumb}


@router.delete("/{model_id}/thumbnail")
async def delete_thumbnail(model_id: str):
    """Remove a model's thumbnail."""
    model_id = validate_model_id(model_id)
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
    model_id = validate_model_id(model_id)
    model = load_model(model_id)
    if not model or not model.thumbnail:
        raise HTTPException(status_code=404, detail="No thumbnail found")

    thumb_path = THUMBNAILS_DIR / Path(model.thumbnail).name
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
    media_type = media_map.get(thumb_path.suffix.lower(), "image/jpeg")

    return FileResponse(path=str(thumb_path), media_type=media_type)
