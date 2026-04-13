"""
Sync service - file copy operations between library and destinations with progress tracking.
"""
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Callable

from .. import config
from ..utils import get_now, to_iso, safe_resolve, validate_dest_id
from ..schemas.model import ModelMetadata, SyncMetadata, ModelHistoryEntry
from .metadata import load_model, save_model, rebuild_index, load_all_models

logger = logging.getLogger(__name__)

SIDECAR_SUFFIX = ".gaitor.json"


def _atomic_write_sidecar(path: Path, data: dict) -> None:
    """Write sidecar JSON atomically: temp file + rename."""
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


def list_destinations() -> list[dict]:
    """List all available destination directories (mounted under /targets/)."""
    dest_root = config.DESTINATIONS_ROOT
    if not dest_root.exists():
        return []

    destinations = []
    for entry in sorted(dest_root.iterdir()):
        if entry.is_dir():
            try:
                stat = os.statvfs(str(entry))
                disk_total = stat.f_blocks * stat.f_frsize
                disk_free = stat.f_bavail * stat.f_frsize
            except OSError:
                disk_total = 0
                disk_free = 0

            destinations.append({
                "id": entry.name,
                "name": entry.name,
                "path": str(entry),
                "disk_total": disk_total,
                "disk_free": disk_free,
                "health": check_destination_health(entry),
            })

    return destinations


def check_destination_health(path: Path) -> dict:
    """Check if a destination mount is accessible and writable."""
    result = {"status": "unknown", "readable": False, "writable": False, "message": ""}

    if not path.exists():
        result["status"] = "offline"
        result["message"] = "Path does not exist"
        return result

    try:
        os.listdir(str(path))
        result["readable"] = True
    except PermissionError:
        result["status"] = "error"
        result["message"] = "Permission denied (read)"
        return result
    except OSError as e:
        result["status"] = "offline"
        result["message"] = f"Not accessible: {e}"
        return result

    probe = path / ".gaitor_health_probe"
    try:
        probe.write_text("ok")
        probe.unlink()
        result["writable"] = True
    except PermissionError:
        result["status"] = "degraded"
        result["message"] = "Read-only (cannot write)"
        return result
    except OSError as e:
        result["status"] = "degraded"
        result["message"] = f"Write check failed: {e}"
        return result

    result["status"] = "healthy"
    result["message"] = "Accessible and writable"
    return result


def get_destination_models(dest_id: str) -> list[dict]:
    """List all synced models on a destination (by reading sidecar files)."""
    validate_dest_id(dest_id)
    dest_path = safe_resolve(config.DESTINATIONS_ROOT, dest_id)
    if not dest_path.exists():
        raise ValueError(f"Destination not found: {dest_id}")

    models = []
    for root, dirs, files in os.walk(dest_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue

            sidecar_path = Path(root) / filename
            try:
                with open(sidecar_path) as f:
                    sidecar_data = json.load(f)

                model_filename = sidecar_data.get("current_filename", "")
                model_path = (Path(root) / model_filename).resolve()
                if not model_path.is_relative_to(dest_path.resolve()):
                    logger.warning(f"Sidecar references path outside destination: {sidecar_path}")
                    continue
                file_exists = model_path.exists()

                models.append({
                    **sidecar_data,
                    "sidecar_path": str(sidecar_path.relative_to(dest_path)),
                    "file_exists": file_exists,
                    "file_size": model_path.stat().st_size if file_exists else 0,
                    "destination_id": dest_id,
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Invalid sidecar file {sidecar_path}: {e}")

    return models


def get_sync_status(dest_id: str) -> list[dict]:
    """Compare library models with what's on a destination to determine sync status."""
    dest_models = get_destination_models(dest_id)
    library_models = load_all_models()

    dest_by_lib_id = {m["library_model_id"]: m for m in dest_models}
    lib_by_id = {m.id: m for m in library_models}

    status_list = []

    # Check library models against destination
    for lib_model in library_models:
        dest_model = dest_by_lib_id.get(lib_model.id)
        if not dest_model:
            status_list.append({
                "model_id": lib_model.id,
                "model_name": lib_model.name,
                "filename": lib_model.filename,
                "category": lib_model.category,
                "size": lib_model.size,
                "status": "not_synced",
            })
        else:
            # Check if hashes match (outdated if different)
            lib_hash = lib_model.hash.get("sha256") if lib_model.hash else None
            dest_hash_raw = dest_model.get("hash") or ""
            dest_hash = dest_hash_raw.replace("sha256:", "")

            if lib_model.filename != dest_model.get("current_filename"):
                sync_status = "rename_pending"
            elif lib_hash and dest_hash and lib_hash != dest_hash:
                sync_status = "outdated"
            else:
                sync_status = "synced"

            status_list.append({
                "model_id": lib_model.id,
                "model_name": lib_model.name,
                "filename": lib_model.filename,
                "category": lib_model.category,
                "size": lib_model.size,
                "status": sync_status,
                "synced_at": dest_model.get("synced_at"),
                "dest_filename": dest_model.get("current_filename"),
            })

    # Check for orphaned models on destination (exist on dest but not in library)
    for dest_model in dest_models:
        if dest_model["library_model_id"] not in lib_by_id:
            status_list.append({
                "model_id": dest_model["library_model_id"],
                "model_name": dest_model.get("library_name", "Unknown"),
                "filename": dest_model.get("current_filename", ""),
                "category": "",
                "size": dest_model.get("file_size", 0),
                "status": "orphaned",
                "synced_at": dest_model.get("synced_at"),
            })

    return status_list


def sync_model_to_destination(
    model_id: str,
    dest_id: str,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Copy a model from the library to a destination with sidecar metadata."""
    validate_dest_id(dest_id)
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    dest_path = safe_resolve(config.DESTINATIONS_ROOT, dest_id)
    if not dest_path.exists():
        raise ValueError(f"Destination not found: {dest_id}")

    src_path = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    if not src_path.exists():
        raise ValueError(f"Source file not found: {model.relative_path}")

    # Preserve full subfolder structure: category/subfolder/.../filename
    rel_parts = Path(model.relative_path).parts
    # Build destination path preserving all directories from relative_path
    dest_model_dir = dest_path / str(Path(*rel_parts[:-1]))
    dest_model_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_model_dir / model.filename
    total_size = src_path.stat().st_size
    copied_size = 0

    # Copy with progress
    with open(src_path, "rb") as src, open(str(dest_file) + ".syncing", "wb") as dst:
        while True:
            chunk = src.read(config.COPY_BUFFER_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            copied_size += len(chunk)
            if progress_callback:
                progress_callback(copied_size, total_size)

    # Atomic rename
    os.replace(str(dest_file) + ".syncing", str(dest_file))

    # Write sidecar metadata
    now = to_iso(get_now())
    sidecar = SyncMetadata(
        library_model_id=model.id,
        library_name=model.name,
        current_filename=model.filename,
        synced_at=now,
        hash=f"sha256:{model.hash['sha256']}" if model.hash and model.hash.get("sha256") else None,
        rename_history=[],
    )
    sidecar_path = dest_model_dir / f".{model.filename}{SIDECAR_SUFFIX}"
    _atomic_write_sidecar(sidecar_path, sidecar.model_dump())

    # Record sync in model history
    model.history.append(
        ModelHistoryEntry(
            action="synced",
            timestamp=now,
            details={"destination": dest_id, "path": str(dest_file.relative_to(dest_path))},
        )
    )
    model.updated_at = now
    save_model(model)
    rebuild_index()

    logger.info(f"Synced {model.name} to {dest_id}")
    return {
        "model_id": model.id,
        "destination": dest_id,
        "path": str(dest_file.relative_to(dest_path)),
        "size": total_size,
        "synced_at": now,
    }


def remove_from_destination(model_id: str, dest_id: str) -> dict:
    """Remove a synced model and its sidecar from a destination."""
    validate_dest_id(dest_id)
    dest_path = safe_resolve(config.DESTINATIONS_ROOT, dest_id)
    if not dest_path.exists():
        raise ValueError(f"Destination not found: {dest_id}")

    # Find the sidecar for this model
    for root, dirs, files in os.walk(dest_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue
            sidecar_path = Path(root) / filename
            try:
                with open(sidecar_path) as f:
                    data = json.load(f)
                if data.get("library_model_id") == model_id:
                    current_filename = data.get("current_filename", "")
                    model_file = (Path(root) / current_filename).resolve()
                    if not model_file.is_relative_to(dest_path.resolve()):
                        logger.warning(f"Sidecar references path outside destination: {sidecar_path}")
                        continue
                    result = {"model_id": model_id, "destination": dest_id, "file_deleted": False, "sidecar_deleted": False}
                    if model_file.exists():
                        model_file.unlink()
                        result["file_deleted"] = True
                    sidecar_path.unlink()
                    result["sidecar_deleted"] = True
                    logger.info(f"Removed {data.get('library_name', model_id)} from {dest_id}")
                    return result
            except (json.JSONDecodeError, OSError):
                continue

    raise ValueError(f"Model {model_id} not found on destination {dest_id}")


def apply_rename_on_destination(model_id: str, dest_id: str) -> dict:
    """Apply a pending library rename to a synced model on a destination."""
    validate_dest_id(dest_id)
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    dest_path = safe_resolve(config.DESTINATIONS_ROOT, dest_id)
    if not dest_path.exists():
        raise ValueError(f"Destination not found: {dest_id}")

    for root, dirs, files in os.walk(dest_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue
            sidecar_path = Path(root) / filename
            try:
                with open(sidecar_path) as f:
                    data = json.load(f)
                if data.get("library_model_id") != model_id:
                    continue

                old_filename = data["current_filename"]
                old_path = (Path(root) / old_filename).resolve()
                new_filename = model.filename
                new_path = (Path(root) / new_filename).resolve()

                if not old_path.is_relative_to(dest_path.resolve()) or not new_path.is_relative_to(dest_path.resolve()):
                    logger.warning(f"Sidecar references path outside destination: {sidecar_path}")
                    continue

                now = to_iso(get_now())

                if old_path.exists() and old_filename != new_filename:
                    os.rename(str(old_path), str(new_path))

                # Update sidecar
                data["current_filename"] = new_filename
                data["library_name"] = model.name
                rename_history = data.get("rename_history", [])
                rename_history.append({
                    "from": old_filename,
                    "to": new_filename,
                    "at": now,
                })
                data["rename_history"] = rename_history

                # Write updated sidecar with new name
                sidecar_path.unlink()
                new_sidecar_path = Path(root) / f".{new_filename}{SIDECAR_SUFFIX}"
                _atomic_write_sidecar(new_sidecar_path, data)

                logger.info(f"Applied rename {old_filename} → {new_filename} on {dest_id}")
                return {
                    "model_id": model_id,
                    "destination": dest_id,
                    "old_filename": old_filename,
                    "new_filename": new_filename,
                }
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error processing sidecar {sidecar_path}: {e}")
                continue

    raise ValueError(f"Model {model_id} not found on destination {dest_id}")
