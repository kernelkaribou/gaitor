"""
Pydantic schemas for bookmark metadata.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid


class BookmarkSource(BaseModel):
    """Where the bookmarked model can be found."""
    url: Optional[str] = None
    provider: Optional[str] = None  # "huggingface", "civitai", "url", "other"


class BookmarkMetadata(BaseModel):
    """Metadata-only reference to an AI model. Stored as {uuid}.json."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    notes: str = ""
    source: BookmarkSource = Field(default_factory=BookmarkSource)
    thumbnail_url: Optional[str] = None
    thumbnail: Optional[str] = None
    base_model: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    target_category: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
