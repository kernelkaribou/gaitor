"""
Library service - model scanning, file operations, hashing, upload handling.
"""
import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from .. import config
from ..utils import get_now, to_iso, safe_resolve, sanitize_filename
from ..schemas.model import ModelMetadata, ModelSource, ModelHistoryEntry
from .metadata import (
    ensure_metadata_dir,
    is_library_initialized,
    initialize_library,
    load_all_models,
    save_model,
    load_model,
    delete_model_metadata,
    rebuild_index,
    load_categories,
    get_library_config,
)

logger = logging.getLogger(__name__)


def cleanup_empty_parents(filepath: Path, stop_at: Path) -> None:
    """Remove empty parent directories from filepath up to (not including) stop_at."""
    parent = filepath.parent
    while parent != stop_at and parent.is_relative_to(stop_at):
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
            else:
                break
        except OSError:
            break


def get_library_status() -> dict:
    """Get current library status."""
    lib_path = config.LIBRARY_PATH
    initialized = is_library_initialized()

    result = {
        "path": str(lib_path),
        "exists": lib_path.exists(),
        "initialized": initialized,
        "status": "initialized" if initialized else "not_initialized",
    }

    if initialized:
        lib_config = get_library_config()
        if lib_config:
            result["name"] = lib_config.name
        models = load_all_models()
        result["model_count"] = len(models)

        # Disk space
        try:
            stat = os.statvfs(str(lib_path))
            result["disk_total"] = stat.f_blocks * stat.f_frsize
            result["disk_free"] = stat.f_bavail * stat.f_frsize
        except OSError:
            pass

    return result


def scan_for_untracked() -> list[dict]:
    """Scan library for model files that have no metadata entry."""
    lib_path = config.LIBRARY_PATH
    metadata_dir = config.METADATA_DIR_NAME

    existing_models = load_all_models()
    tracked_paths = {m.relative_path for m in existing_models}

    untracked = []
    for root, dirs, files in os.walk(lib_path):
        # Skip the metadata directory
        dirs[:] = [d for d in dirs if d != metadata_dir]

        for filename in files:
            filepath = Path(root) / filename
            ext = filepath.suffix.lower()
            if ext not in config.MODEL_EXTENSIONS:
                continue

            rel_path = str(filepath.relative_to(lib_path))
            if rel_path in tracked_paths:
                continue

            # Guess category from parent folder name
            parent = filepath.parent.name.lower()
            categories = load_categories()
            guessed_category = "other"
            for cat in categories:
                if cat.id == parent or cat.label.lower() == parent:
                    guessed_category = cat.id
                    break
                if ext in cat.extensions and cat.id != "other":
                    guessed_category = cat.id

            try:
                stat = filepath.stat()
                size = stat.st_size
            except OSError:
                size = 0

            untracked.append({
                "filename": filename,
                "relative_path": rel_path,
                "size": size,
                "extension": ext,
                "guessed_category": guessed_category,
                "parent_folder": filepath.parent.name,
            })

    logger.info(f"Scan found {len(untracked)} untracked model files")
    return untracked


def catalog_model(
    relative_path: str,
    name: str,
    category: str = "other",
    description: str = "",
    tags: Optional[list[str]] = None,
    source_provider: str = "manual",
    target_subfolder: str = "",
    _defer_index: bool = False,
) -> ModelMetadata:
    """Create a metadata entry for an existing file in the library.
    If category differs from current folder or target_subfolder is set, moves the file."""
    filepath = safe_resolve(config.LIBRARY_PATH, relative_path)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {relative_path}")

    # Determine if file needs to be moved
    rel_parts = Path(relative_path).parts
    current_parent = rel_parts[0] if len(rel_parts) > 1 else ""
    needs_move = (current_parent != category) or target_subfolder

    if needs_move:
        if target_subfolder:
            new_dir = safe_resolve(config.LIBRARY_PATH, f"{category}/{target_subfolder}")
        else:
            new_dir = safe_resolve(config.LIBRARY_PATH, category)
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / filepath.name
        if new_path.exists() and new_path != filepath:
            raise ValueError(f"A file named '{filepath.name}' already exists in target location")
        if new_path != filepath:
            shutil.move(str(filepath), str(new_path))
            cleanup_empty_parents(filepath, config.LIBRARY_PATH)
            filepath = new_path
            relative_path = str(filepath.relative_to(config.LIBRARY_PATH))

    stat = filepath.stat()
    now = to_iso(get_now())

    model = ModelMetadata(
        id=str(uuid.uuid4()),
        name=name,
        filename=filepath.name,
        category=category,
        relative_path=relative_path,
        size=stat.st_size,
        source=ModelSource(provider=source_provider),
        description=description,
        tags=tags or [],
        history=[
            ModelHistoryEntry(
                action="added",
                timestamp=now,
                details={"method": "catalog", "source": source_provider},
            )
        ],
        created_at=now,
        updated_at=now,
    )

    save_model(model)
    if not _defer_index:
        rebuild_index()
    logger.info(f"Cataloged model: {name} ({relative_path})")
    return model


def upload_model(
    filename: str,
    category: str,
    name: str,
    data_stream,
    description: str = "",
    tags: Optional[list[str]] = None,
) -> ModelMetadata:
    """Handle an uploaded model file - stream to disk, catalog it."""
    ensure_metadata_dir()

    # Sanitize filename to prevent path traversal
    safe_name = sanitize_filename(Path(filename).stem, Path(filename).suffix)

    # Validate category and host stay within library
    dest_dir = safe_resolve(config.LIBRARY_PATH, category)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name

    # Avoid overwriting
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Stream to temp file then rename (atomic-ish)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".uploading")
    total_size = 0
    try:
        with open(tmp_path, "wb") as f:
            while True:
                chunk = data_stream.read(config.COPY_BUFFER_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > config.MAX_UPLOAD_SIZE:
                    raise ValueError(f"Upload exceeds maximum size ({config.MAX_UPLOAD_SIZE} bytes)")
                f.write(chunk)
        os.replace(str(tmp_path), str(dest_path))
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    relative_path = str(dest_path.relative_to(config.LIBRARY_PATH))
    now = to_iso(get_now())

    model = ModelMetadata(
        id=str(uuid.uuid4()),
        name=name or dest_path.stem,
        filename=dest_path.name,
        category=category,
        relative_path=relative_path,
        size=total_size,
        source=ModelSource(provider="upload"),
        description=description,
        tags=tags or [],
        history=[
            ModelHistoryEntry(
                action="added",
                timestamp=now,
                details={"method": "upload"},
            )
        ],
        created_at=now,
        updated_at=now,
    )

    save_model(model)
    rebuild_index()
    logger.info(f"Uploaded model: {name} ({relative_path}, {total_size} bytes)")
    return model


def update_model_metadata(
    model_id: str,
    updates: dict,
) -> ModelMetadata:
    """Update a model's metadata. Handles category/subfolder moves and file renames."""
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    now = to_iso(get_now())
    changed_fields = {}

    for field in ("name", "description", "category", "tags", "base_model"):
        if field in updates:
            new_val = updates[field]
            if field == "base_model" and not new_val:
                new_val = None
            if getattr(model, field) != new_val:
                changed_fields[field] = {
                    "from": getattr(model, field),
                    "to": new_val,
                }
                setattr(model, field, new_val)

    # Handle source_url
    if "source_url" in updates:
        old_url = model.source.url if model.source else None
        new_url = updates["source_url"] or None
        if old_url != new_url:
            if not model.source:
                model.source = ModelSource()
            model.source.url = new_url
            if new_url:
                if "huggingface.co" in new_url or "hf.co" in new_url:
                    model.source.provider = "huggingface"
                elif "civitai.com" in new_url:
                    model.source.provider = "civitai"
                elif not model.source.provider or model.source.provider == "manual":
                    model.source.provider = None
            changed_fields["source_url"] = {"from": old_url, "to": new_url}

    # Handle thumbnail separately (no history entry needed)
    if "thumbnail" in updates:
        model.thumbnail = updates["thumbnail"]
        model.updated_at = now
        save_model(model)
        rebuild_index()
        return model

    # Handle filename rename
    new_filename = None
    if "filename" in updates and updates["filename"] is not None:
        raw = updates["filename"].strip()
        if raw and raw != model.filename:
            old_ext = model.filename.rsplit(".", 1)[-1] if "." in model.filename else ""
            base = raw.rsplit(".", 1)[0] if "." in raw else raw
            safe_base = sanitize_filename(base, "")
            new_filename = f"{safe_base}.{old_ext}" if old_ext else safe_base
            if new_filename != model.filename:
                changed_fields["filename"] = {"from": model.filename, "to": new_filename}
            else:
                new_filename = None

    # Determine current subfolder from relative_path
    rel_parts = Path(model.relative_path).parts
    current_subfolder = str(Path(*rel_parts[1:-1])) if len(rel_parts) > 2 else ""

    target_category = model.category
    target_subfolder = current_subfolder
    target_filename = new_filename or model.filename

    if "subfolder" in updates and updates["subfolder"] is not None:
        requested_sub = updates["subfolder"].strip().strip("/")
        if requested_sub != current_subfolder:
            changed_fields["subfolder"] = {"from": current_subfolder or "(root)", "to": requested_sub or "(root)"}
            target_subfolder = requested_sub

    # Build target path and move file if needed
    if target_subfolder:
        target_dir = safe_resolve(config.LIBRARY_PATH, f"{target_category}/{target_subfolder}")
    else:
        target_dir = safe_resolve(config.LIBRARY_PATH, target_category)
    target_path = target_dir / target_filename

    old_path = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    if old_path.is_file() and target_path != old_path:
        target_dir.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            raise ValueError(f"A file named '{target_filename}' already exists at target location")
        shutil.move(str(old_path), str(target_path))
        cleanup_empty_parents(old_path, config.LIBRARY_PATH)
        model.filename = target_filename
        model.relative_path = str(target_path.relative_to(config.LIBRARY_PATH))
    elif new_filename:
        model.filename = target_filename
        model.relative_path = str(target_path.relative_to(config.LIBRARY_PATH))

    if changed_fields:
        model.updated_at = now
        model.history.append(
            ModelHistoryEntry(
                action="metadata_updated",
                timestamp=now,
                details=changed_fields,
            )
        )
        save_model(model)
        rebuild_index()

    return model


def rename_model(model_id: str, new_name: str, rename_file: bool = True) -> ModelMetadata:
    """Rename a model - updates metadata and optionally the physical file."""
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    old_name = model.name
    old_filename = model.filename
    now = to_iso(get_now())

    model.name = new_name

    if rename_file:
        old_path = safe_resolve(config.LIBRARY_PATH, model.relative_path)
        ext = old_path.suffix
        new_filename = sanitize_filename(new_name, ext)
        new_path = old_path.parent / new_filename

        # Verify new path stays within library
        if not new_path.resolve().is_relative_to(config.LIBRARY_PATH.resolve()):
            raise ValueError("Rename would escape library directory")

        try:
            os.rename(str(old_path), str(new_path))
            model.filename = new_filename
            model.relative_path = str(new_path.relative_to(config.LIBRARY_PATH))
        except FileNotFoundError:
            pass  # source gone, just update metadata
        except FileExistsError:
            raise ValueError(f"A file named '{new_filename}' already exists")

    model.updated_at = now
    model.history.append(
        ModelHistoryEntry(
            action="renamed",
            timestamp=now,
            details={
                "from_name": old_name,
                "to_name": new_name,
                "from_filename": old_filename,
                "to_filename": model.filename,
            },
        )
    )

    save_model(model)
    rebuild_index()
    logger.info(f"Renamed model: {old_name} → {new_name}")
    return model


def delete_library_model(model_id: str, delete_file: bool = True) -> dict:
    """Delete a model from the library. Returns details of what was deleted."""
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    result = {
        "id": model.id,
        "name": model.name,
        "filename": model.filename,
        "file_deleted": False,
        "metadata_deleted": False,
    }

    if delete_file:
        filepath = safe_resolve(config.LIBRARY_PATH, model.relative_path)
        if filepath.exists():
            filepath.unlink()
            result["file_deleted"] = True
            logger.info(f"Deleted model file: {filepath}")
            cleanup_empty_parents(filepath, config.LIBRARY_PATH)

    result["metadata_deleted"] = delete_model_metadata(model_id)
    rebuild_index()
    logger.info(f"Deleted model from library: {model.name}")
    return result


def compute_hash(model_id: str) -> Optional[str]:
    """Compute SHA-256 hash for a model file. Returns the hash string."""
    model = load_model(model_id)
    if not model:
        return None

    filepath = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    if not filepath.exists():
        return None

    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(config.COPY_BUFFER_SIZE)
            if not chunk:
                break
            sha256.update(chunk)

    hash_value = sha256.hexdigest()
    model.hash = {"sha256": hash_value}
    model.updated_at = to_iso(get_now())
    save_model(model)
    rebuild_index()
    logger.info(f"Computed hash for {model.name}: {hash_value[:16]}...")
    return hash_value
