"""
Bookmark API endpoints - CRUD for metadata-only model references.
"""
import os
import logging
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from io import BytesIO
from PIL import Image
import httpx

Image.MAX_IMAGE_PIXELS = 25_000_000

logger = logging.getLogger(__name__)

from ..schemas.bookmark import BookmarkMetadata, BookmarkSource
from ..services.bookmarks import (
    load_bookmark,
    save_bookmark,
    delete_bookmark,
    load_bookmark_index,
)
from ..services.metadata import load_categories
from ..services import metadata as meta_service
from ..utils import validate_model_id
from datetime import datetime, timezone

router = APIRouter()

ALLOWED_THUMBNAIL_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_THUMBNAIL_UPLOAD = 12 * 1024 * 1024


class CreateBookmarkRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    source_url: Optional[str] = None
    description: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=2000)
    base_model: Optional[str] = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=50)
    thumbnail_url: Optional[str] = None
    target_category: Optional[str] = None


class UpdateBookmarkRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    source_url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=2000)
    base_model: Optional[str] = Field(default=None, max_length=200)
    tags: Optional[list[str]] = None
    thumbnail_url: Optional[str] = None
    target_category: Optional[str] = None


def _validate_url(url: Optional[str]) -> Optional[str]:
    """Validate URL is https or None."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="URLs must use HTTPS")
    if len(url) > 2000:
        raise HTTPException(status_code=400, detail="URL too long")
    return url


def _derive_provider(url: Optional[str]) -> Optional[str]:
    """Derive provider from URL hostname."""
    if not url:
        return None
    lower = url.lower()
    if "huggingface.co" in lower or "hf.co" in lower:
        return "huggingface"
    if "civitai.com" in lower:
        return "civitai"
    return "url"


def _validate_target_category(category: Optional[str]) -> Optional[str]:
    """Validate target_category exists in library categories."""
    if not category:
        return None
    category = category.strip()
    if not category:
        return None
    known = {c.id for c in load_categories()}
    if category not in known:
        raise HTTPException(status_code=400, detail=f"Unknown category '{category}'")
    return category


MAX_REMOTE_THUMB = 12 * 1024 * 1024  # 12MB download limit


async def _fetch_and_store_thumbnail(url: str, bookmark_id: str) -> str:
    """Download a remote image URL, convert to webp, store locally.

    Returns the relative thumbnail path (e.g. 'thumbnails/bm-{id}.webp').
    On failure, logs a warning and returns None (non-fatal).
    """
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            logger.warning(f"Thumbnail URL is not an image: {content_type}")
            return None

        if len(resp.content) > MAX_REMOTE_THUMB:
            logger.warning(f"Thumbnail URL too large: {len(resp.content)} bytes")
            return None

        img = Image.open(BytesIO(resp.content))
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=85)
        webp_data = buf.getvalue()

        meta_service.ensure_metadata_dir()
        thumb_path = meta_service.THUMBNAILS_DIR / f"bm-{bookmark_id}.webp"
        fd, tmp_path = tempfile.mkstemp(
            dir=str(meta_service.THUMBNAILS_DIR), suffix=".tmp"
        )
        try:
            os.fdopen(fd, "wb").write(webp_data)
            os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, str(thumb_path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return f"thumbnails/bm-{bookmark_id}.webp"

    except Exception as e:
        logger.warning(f"Failed to fetch thumbnail from {url}: {e}")
        return None


@router.get("/")
async def list_bookmarks():
    """List all bookmarks."""
    return {"bookmarks": load_bookmark_index()}


@router.post("/")
async def create_bookmark(req: CreateBookmarkRequest):
    """Create a new bookmark."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be blank")
    source_url = _validate_url(req.source_url)
    target_cat = _validate_target_category(req.target_category)
    thumb_url = _validate_url(req.thumbnail_url)

    source = BookmarkSource(url=source_url, provider=_derive_provider(source_url))

    bookmark = BookmarkMetadata(
        name=name,
        description=req.description.strip(),
        notes=req.notes.strip(),
        source=source,
        thumbnail_url=thumb_url,
        base_model=req.base_model.strip() if req.base_model else None,
        tags=[t.strip() for t in req.tags if t.strip()][:50],
        target_category=target_cat,
    )

    # Download remote thumbnail and store locally
    if thumb_url and not bookmark.thumbnail:
        local_thumb = await _fetch_and_store_thumbnail(thumb_url, bookmark.id)
        if local_thumb:
            bookmark.thumbnail = local_thumb

    save_bookmark(bookmark)
    return bookmark.model_dump()


@router.put("/{bookmark_id}")
async def update_bookmark(bookmark_id: str, req: UpdateBookmarkRequest):
    """Update an existing bookmark."""
    try:
        bookmark_id = validate_model_id(bookmark_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bookmark ID")

    bookmark = load_bookmark(bookmark_id)
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    if req.name is not None:
        stripped = req.name.strip()
        if not stripped:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        bookmark.name = stripped
    if req.description is not None:
        bookmark.description = req.description.strip()
    if req.notes is not None:
        bookmark.notes = req.notes.strip()
    if req.source_url is not None:
        new_url = _validate_url(req.source_url)
        bookmark.source = BookmarkSource(url=new_url, provider=_derive_provider(new_url))
    if req.thumbnail_url is not None:
        new_thumb_url = _validate_url(req.thumbnail_url)
        bookmark.thumbnail_url = new_thumb_url
        # Download new remote thumbnail if URL changed
        if new_thumb_url:
            local_thumb = await _fetch_and_store_thumbnail(
                new_thumb_url, bookmark_id
            )
            if local_thumb:
                bookmark.thumbnail = local_thumb
    if req.base_model is not None:
        bookmark.base_model = req.base_model.strip() or None
    if req.tags is not None:
        bookmark.tags = [t.strip() for t in req.tags if t.strip()][:50]
    if req.target_category is not None:
        bookmark.target_category = _validate_target_category(req.target_category)

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
    # Atomic write: temp file + replace (NFS-safe, matches JSON write pattern)
    import tempfile
    fd, tmp_path = tempfile.mkstemp(
        dir=str(meta_service.THUMBNAILS_DIR), suffix=".tmp"
    )
    try:
        os.fdopen(fd, "wb").write(webp_data)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, str(thumb_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

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
