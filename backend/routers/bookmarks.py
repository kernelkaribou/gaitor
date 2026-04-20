"""
Bookmark API endpoints - CRUD for metadata-only model references.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from io import BytesIO
from PIL import Image

from ..schemas.bookmark import BookmarkMetadata, BookmarkSource
from ..services.bookmarks import (
    load_bookmark,
    save_bookmark,
    delete_bookmark,
    load_bookmark_index,
)
from ..services import metadata as meta_service
from ..utils import validate_model_id
from datetime import datetime, timezone

router = APIRouter()

ALLOWED_THUMBNAIL_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_THUMBNAIL_UPLOAD = 12 * 1024 * 1024


@router.get("/")
async def list_bookmarks():
    """List all bookmarks."""
    return {"bookmarks": load_bookmark_index()}


@router.post("/")
async def create_bookmark(data: dict):
    """Create a new bookmark."""
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    source = BookmarkSource(
        url=data.get("source_url", "").strip() or None,
        provider=data.get("provider", "").strip() or None,
    )

    bookmark = BookmarkMetadata(
        name=name,
        description=data.get("description", "").strip(),
        notes=data.get("notes", "").strip(),
        source=source,
        thumbnail_url=data.get("thumbnail_url", "").strip() or None,
        base_model=data.get("base_model", "").strip() or None,
        tags=[t.strip() for t in data.get("tags", []) if t.strip()],
        target_category=data.get("target_category", "").strip() or None,
    )

    save_bookmark(bookmark)
    return bookmark.model_dump()


@router.put("/{bookmark_id}")
async def update_bookmark(bookmark_id: str, data: dict):
    """Update an existing bookmark."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    bookmark = load_bookmark(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    if "name" in data:
        name = data["name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        bookmark.name = name
    if "description" in data:
        bookmark.description = data["description"].strip()
    if "notes" in data:
        bookmark.notes = data["notes"].strip()
    if "source_url" in data or "provider" in data:
        bookmark.source = BookmarkSource(
            url=data.get("source_url", bookmark.source.url),
            provider=data.get("provider", bookmark.source.provider),
        )
    if "thumbnail_url" in data:
        bookmark.thumbnail_url = data["thumbnail_url"].strip() or None
    if "base_model" in data:
        bookmark.base_model = data["base_model"].strip() or None
    if "tags" in data:
        bookmark.tags = [t.strip() for t in data["tags"] if t.strip()]
    if "target_category" in data:
        bookmark.target_category = data["target_category"].strip() or None

    bookmark.updated_at = datetime.now(timezone.utc).isoformat()
    save_bookmark(bookmark)
    return bookmark.model_dump()


@router.delete("/{bookmark_id}")
async def remove_bookmark(bookmark_id: str):
    """Delete a bookmark."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    if not delete_bookmark(bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}


# --- Thumbnail endpoints ---

@router.post("/{bookmark_id}/thumbnail")
async def upload_bookmark_thumbnail(bookmark_id: str, file: UploadFile = File(...)):
    """Upload a thumbnail for a bookmark. Auto-converts to max 400x400 webp."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    bookmark = load_bookmark(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    if file.content_type not in ALLOWED_THUMBNAIL_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Allowed: JPEG, PNG, WebP, GIF")

    content = await file.read()
    if len(content) > MAX_THUMBNAIL_UPLOAD:
        raise HTTPException(status_code=400, detail="Thumbnail must be under 12MB")

    try:
        img = Image.open(BytesIO(content))
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=85)
        webp_data = buf.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="Could not process image")

    meta_service.ensure_metadata_dir()
    thumb_path = meta_service.THUMBNAILS_DIR / f"bm-{bookmark_id}.webp"
    for old in meta_service.THUMBNAILS_DIR.glob(f"bm-{bookmark_id}.*"):
        old.unlink(missing_ok=True)
    thumb_path.write_bytes(webp_data)

    bookmark.thumbnail = f"thumbnails/bm-{bookmark_id}.webp"
    bookmark.updated_at = datetime.now(timezone.utc).isoformat()
    save_bookmark(bookmark)

    return {"thumbnail": bookmark.thumbnail}


@router.delete("/{bookmark_id}/thumbnail")
async def remove_bookmark_thumbnail(bookmark_id: str):
    """Remove a bookmark's thumbnail."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    bookmark = load_bookmark(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    if bookmark.thumbnail:
        thumb_path = meta_service.THUMBNAILS_DIR / f"bm-{bookmark_id}.webp"
        thumb_path.unlink(missing_ok=True)
        bookmark.thumbnail = None
        bookmark.updated_at = datetime.now(timezone.utc).isoformat()
        save_bookmark(bookmark)

    return {"status": "removed"}


@router.get("/{bookmark_id}/thumbnail")
async def get_bookmark_thumbnail(bookmark_id: str):
    """Serve a bookmark's thumbnail image."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    bookmark = load_bookmark(bookmark_id)
    if not bookmark or not bookmark.thumbnail:
        raise HTTPException(status_code=404, detail="No thumbnail found")

    thumb_path = meta_service.THUMBNAILS_DIR / f"bm-{bookmark_id}.webp"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    return FileResponse(str(thumb_path), media_type="image/webp")
