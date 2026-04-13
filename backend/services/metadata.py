"""
JSON metadata service — atomic reads/writes for model metadata on network shares.

Strategy:
- Individual {uuid}.json files per model (safe writes on NFS/SMB)
- Compiled index.json cache for fast reads
- Atomic writes via temp file + rename
- Self-healing: index can always be rebuilt from individual files
"""
import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional

from ..schemas.model import ModelMetadata
from ..schemas.library import CategoryDefinition, LibraryConfig, DEFAULT_CATEGORIES
from ..utils import validate_model_id
from .. import config

logger = logging.getLogger(__name__)

METADATA_DIR = config.LIBRARY_PATH / config.METADATA_DIR_NAME
MODELS_DIR = METADATA_DIR / "models"
INDEX_FILE = METADATA_DIR / "index.json"
CONFIG_FILE = METADATA_DIR / "config.json"
CATEGORIES_FILE = METADATA_DIR / "categories.json"


def _atomic_write_json(path: Path, data: dict | list) -> None:
    """Write JSON atomically: write to temp file then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Optional[dict | list]:
    """Read a JSON file, returning None if it doesn't exist or is corrupt."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if isinstance(e, json.JSONDecodeError):
            logger.warning(f"Corrupt JSON file: {path}")
        return None


def ensure_metadata_dir() -> bool:
    """Ensure the .modelgaitor directory structure exists. Returns True if it was freshly created."""
    fresh = not METADATA_DIR.exists()
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return fresh


def is_library_initialized() -> bool:
    """Check if the library metadata directory exists and has a config."""
    return CONFIG_FILE.exists()


def initialize_library(name: str = "Model Library", template: str = "default") -> LibraryConfig:
    """Initialize library metadata structure with default categories."""
    ensure_metadata_dir()
    lib_config = LibraryConfig(name=name, categories_template=template)
    _atomic_write_json(CONFIG_FILE, lib_config.model_dump())
    save_categories(DEFAULT_CATEGORIES)
    rebuild_index()
    logger.info(f"Library initialized: {name}")
    return lib_config


def get_library_config() -> Optional[LibraryConfig]:
    """Read library configuration."""
    data = _read_json(CONFIG_FILE)
    if data:
        return LibraryConfig(**data)
    return None


def save_library_config(lib_config: LibraryConfig) -> None:
    """Save library configuration."""
    _atomic_write_json(CONFIG_FILE, lib_config.model_dump())


# --- Category operations ---

def load_categories() -> list[CategoryDefinition]:
    """Load category definitions."""
    data = _read_json(CATEGORIES_FILE)
    if data and isinstance(data, list):
        return [CategoryDefinition(**c) for c in data]
    return list(DEFAULT_CATEGORIES)


def save_categories(categories: list[CategoryDefinition]) -> None:
    """Save category definitions."""
    _atomic_write_json(CATEGORIES_FILE, [c.model_dump() for c in categories])


def add_category(category: CategoryDefinition) -> list[CategoryDefinition]:
    """Add a new category."""
    cats = load_categories()
    if any(c.id == category.id for c in cats):
        raise ValueError(f"Category '{category.id}' already exists")
    cats.append(category)
    save_categories(cats)
    return cats


def update_category(category_id: str, updates: dict) -> list[CategoryDefinition]:
    """Update an existing category."""
    cats = load_categories()
    for i, c in enumerate(cats):
        if c.id == category_id:
            data = c.model_dump()
            data.update(updates)
            cats[i] = CategoryDefinition(**data)
            save_categories(cats)
            return cats
    raise ValueError(f"Category '{category_id}' not found")


def delete_category(category_id: str) -> list[CategoryDefinition]:
    """Delete a category."""
    cats = load_categories()
    cats = [c for c in cats if c.id != category_id]
    save_categories(cats)
    return cats


# --- Model metadata operations ---

def save_model(model: ModelMetadata) -> None:
    """Save a single model's metadata."""
    model_file = MODELS_DIR / f"{model.id}.json"
    _atomic_write_json(model_file, model.model_dump())


def load_model(model_id: str) -> Optional[ModelMetadata]:
    """Load a single model's metadata by ID."""
    validate_model_id(model_id)
    model_file = MODELS_DIR / f"{model_id}.json"
    data = _read_json(model_file)
    if data:
        return ModelMetadata(**data)
    return None


def delete_model_metadata(model_id: str) -> bool:
    """Delete a model's metadata file. Returns True if deleted."""
    validate_model_id(model_id)
    model_file = MODELS_DIR / f"{model_id}.json"
    try:
        model_file.unlink()
        return True
    except FileNotFoundError:
        return False


def load_all_models() -> list[ModelMetadata]:
    """Load all model metadata from individual files."""
    models = []
    if not MODELS_DIR.exists():
        return models
    for f in MODELS_DIR.glob("*.json"):
        data = _read_json(f)
        if data:
            try:
                models.append(ModelMetadata(**data))
            except Exception as e:
                logger.warning(f"Skipping invalid model metadata {f.name}: {e}")
    return models


# --- Index operations ---

def rebuild_index() -> list[dict]:
    """Rebuild index.json from individual model files."""
    models = load_all_models()
    index_data = [m.model_dump() for m in models]
    _atomic_write_json(INDEX_FILE, index_data)
    logger.info(f"Index rebuilt with {len(index_data)} models")
    return index_data


def load_index() -> list[dict]:
    """Load the cached index. Rebuilds if missing."""
    data = _read_json(INDEX_FILE)
    if data is not None and isinstance(data, list):
        return data
    return rebuild_index()
