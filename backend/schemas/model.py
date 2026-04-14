"""
Pydantic schemas for model metadata.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class ModelSource(BaseModel):
    """Where a model was originally obtained from."""
    url: Optional[str] = None
    provider: Optional[str] = None  # "huggingface", "civitai", "upload", "manual"
    downloaded_at: Optional[str] = None


class ModelMetadata(BaseModel):
    """Full metadata for a library model. Stored as {uuid}.json."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    filename: str
    category: str = "other"
    relative_path: str  # Path relative to library root
    size: int = 0
    hash: Optional[dict] = None  # {"sha256": "abc123..."}
    source: ModelSource = Field(default_factory=ModelSource)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    base_model: Optional[str] = None  # Associated base model (e.g. "SDXL 1.0" for a LoRA)
    group_id: Optional[str] = None  # Shared UUID linking related models (e.g. LLM + mmproj)
    preview_image: Optional[str] = None
    thumbnail: Optional[str] = None  # Relative path to thumbnail within .gaitor/thumbnails/
    created_at: str = ""
    updated_at: str = ""


class SyncMetadata(BaseModel):
    """Sidecar metadata placed alongside a model on a host."""
    library_model_id: str
    library_name: str
    library_relative_path: str
    current_filename: str
    synced_at: str
    hash: Optional[str] = None
