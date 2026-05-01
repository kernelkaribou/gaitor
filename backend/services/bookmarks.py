"""
Bookmark metadata service - CRUD operations for metadata-only model references.

Follows the same atomic write patterns as the model metadata service.
Storage: .gaitor/bookmarks/{uuid}.json + index_bookmarks.json cache.
"""
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from ..schemas.bookmark import BookmarkMetadata
from ..utils import validate_model_id
from .. import config
from .metadata import _atomic_write_json, _read_json, METADATA_DIR
from . import metadata as _meta

logger = logging.getLogger(__name__)

BOOKMARKS_DIR = METADATA_DIR / "bookmarks"
BOOKMARKS_INDEX = METADATA_DIR / "index_bookmarks.json"


def ensure_bookmarks_dir() -> None:
    """Ensure the bookmarks directory exists."""
    BOOKMARKS_DIR.mkdir(parents=True, exist_ok=True)


def save_bookmark(bookmark: BookmarkMetadata) -> None:
    """Save a single bookmark's metadata."""
    ensure_bookmarks_dir()
    bookmark_file = BOOKMARKS_DIR / f"{bookmark.id}.json"
    _atomic_write_json(bookmark_file, bookmark.model_dump())
    _rebuild_bookmark_index()


def load_bookmark(bookmark_id: str) -> Optional[BookmarkMetadata]:
    """Load a single bookmark by ID."""
    validate_model_id(bookmark_id)
    bookmark_file = BOOKMARKS_DIR / f"{bookmark_id}.json"
    data = _read_json(bookmark_file)
    if data:
        return BookmarkMetadata(**data)
    return None


def delete_bookmark(bookmark_id: str) -> bool:
    """Delete a bookmark and its thumbnail. Returns True if deleted."""
    validate_model_id(bookmark_id)
    bookmark_file = BOOKMARKS_DIR / f"{bookmark_id}.json"
    try:
        bookmark_file.unlink()
    except FileNotFoundError:
        return False

    # Clean up thumbnail
    thumb_path = _meta.THUMBNAILS_DIR / f"bm-{bookmark_id}.webp"
    thumb_path.unlink(missing_ok=True)

    _rebuild_bookmark_index()
    return True


def load_all_bookmarks() -> list[BookmarkMetadata]:
    """Load all bookmarks from individual files."""
    bookmarks = []
    if not BOOKMARKS_DIR.exists():
        return bookmarks
    for f in BOOKMARKS_DIR.glob("*.json"):
        data = _read_json(f)
        if data:
            try:
                bookmarks.append(BookmarkMetadata(**data))
            except Exception as e:
                logger.warning(f"Skipping invalid bookmark {f.name}: {e}")
    return bookmarks


def load_bookmark_index() -> list[dict]:
    """Load the cached bookmark index. Rebuilds if missing."""
    data = _read_json(BOOKMARKS_INDEX)
    if data is not None and isinstance(data, list):
        return data
    return _rebuild_bookmark_index()


def _rebuild_bookmark_index() -> list[dict]:
    """Rebuild index_bookmarks.json from individual files."""
    bookmarks = load_all_bookmarks()
    index_data = [b.model_dump() for b in bookmarks]
    _atomic_write_json(BOOKMARKS_INDEX, index_data)
    logger.info(f"Bookmark index rebuilt with {len(index_data)} bookmarks")
    return index_data
