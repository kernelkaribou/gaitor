"""
Sync service - file copy operations between library and hosts with progress tracking.
"""
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Callable

from .. import config
from ..utils import get_now, to_iso, safe_resolve, validate_host_id, sanitize_filename
from ..schemas.model import ModelMetadata, ModelSource, SyncMetadata
from .metadata import load_model, save_model, rebuild_index, load_all_models, load_categories
from .library import cleanup_empty_parents

logger = logging.getLogger(__name__)

SIDECAR_SUFFIX = ".gaitor.json"


def _load_sidecar(path: Path) -> Optional[dict]:
    """Load and validate a sidecar JSON file. Returns None if invalid."""
    try:
        with open(path) as f:
            data = json.load(f)
        # Validate required fields
        if not isinstance(data, dict) or "library_model_id" not in data:
            logger.warning(f"Invalid sidecar (missing library_model_id): {path}")
            return None
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load sidecar {path}: {e}")
        return None


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


def list_hosts() -> list[dict]:
    """List all available host directories (mounted under /hosts/)."""
    host_root = config.HOSTS_ROOT
    if not host_root.exists():
        return []

    hosts = []
    for entry in sorted(host_root.iterdir()):
        if entry.is_dir():
            try:
                stat = os.statvfs(str(entry))
                disk_total = stat.f_blocks * stat.f_frsize
                disk_free = stat.f_bavail * stat.f_frsize
            except OSError:
                disk_total = 0
                disk_free = 0

            hosts.append({
                "id": entry.name,
                "name": entry.name,
                "path": str(entry),
                "disk_total": disk_total,
                "disk_free": disk_free,
                "health": check_host_health(entry),
            })

    return hosts


def check_host_health(path: Path) -> dict:
    """Check if a host mount is accessible and writable."""
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


def get_host_models(host_id: str) -> list[dict]:
    """List all synced models on a host (by reading sidecar files)."""
    validate_host_id(host_id)
    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    models = []
    for root, dirs, files in os.walk(host_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue

            sidecar_path = Path(root) / filename
            sidecar_data = _load_sidecar(sidecar_path)
            if sidecar_data is None:
                continue

            try:
                model_filename = sidecar_data.get("current_filename", "")
                model_path = (Path(root) / model_filename).resolve()
                if not model_path.is_relative_to(host_path.resolve()):
                    logger.warning(f"Sidecar references path outside host: {sidecar_path}")
                    continue
                file_exists = model_path.exists()

                models.append({
                    **sidecar_data,
                    "sidecar_path": str(sidecar_path.relative_to(host_path)),
                    "file_exists": file_exists,
                    "file_size": model_path.stat().st_size if file_exists else 0,
                    "host_id": host_id,
                })
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Invalid sidecar file {sidecar_path}: {e}")

    return models


def get_sync_status(host_id: str) -> list[dict]:
    """Compare library models with what's on a host to determine sync status."""
    host_models = get_host_models(host_id)
    library_models = load_all_models()

    host_by_lib_id = {m["library_model_id"]: m for m in host_models}
    lib_by_id = {m.id: m for m in library_models}

    status_list = []

    # Check library models against host
    for lib_model in library_models:
        host_model = host_by_lib_id.get(lib_model.id)
        base_fields = {
            "model_id": lib_model.id,
            "model_name": lib_model.name,
            "filename": lib_model.filename,
            "category": lib_model.category,
            "size": lib_model.size,
            "thumbnail": lib_model.thumbnail,
            "hash": lib_model.hash,
            "base_model": lib_model.base_model,
        }
        if not host_model:
            status_list.append({**base_fields, "status": "not_synced"})
        else:
            lib_hash = lib_model.hash.get("sha256") if lib_model.hash else None
            host_hash_raw = host_model.get("hash") or ""
            host_hash = host_hash_raw.replace("sha256:", "")

            if lib_model.filename != host_model.get("current_filename"):
                sync_status = "rename_pending"
            elif lib_hash and host_hash and lib_hash != host_hash:
                sync_status = "outdated"
            else:
                sync_status = "synced"

            status_list.append({
                **base_fields,
                "status": sync_status,
                "synced_at": host_model.get("synced_at"),
                "host_filename": host_model.get("current_filename"),
            })

    # Check for orphaned models on host (exist on host but not in library)
    for host_model in host_models:
        if host_model["library_model_id"] not in lib_by_id:
            status_list.append({
                "model_id": host_model["library_model_id"],
                "model_name": host_model.get("library_name", "Unknown"),
                "filename": host_model.get("current_filename", ""),
                "category": "",
                "size": host_model.get("file_size", 0),
                "status": "orphaned",
                "synced_at": host_model.get("synced_at"),
            })

    return status_list


def get_model_host_status(model_id: str) -> list[dict]:
    """Get sync status of a single model across all hosts."""
    hosts = list_hosts()
    model = load_model(model_id)
    if not model:
        return []

    result = []
    for host in hosts:
        host_id = host["id"]
        try:
            host_models = get_host_models(host_id)
        except (ValueError, OSError):
            result.append({
                "host_id": host_id,
                "host_name": host["name"],
                "status": "error",
                "disk_free": host.get("disk_free", 0),
            })
            continue

        host_model = None
        for hm in host_models:
            if hm.get("library_model_id") == model_id:
                host_model = hm
                break

        if not host_model:
            result.append({
                "host_id": host_id,
                "host_name": host["name"],
                "status": "not_synced",
                "disk_free": host.get("disk_free", 0),
            })
        else:
            lib_hash = model.hash.get("sha256") if model.hash else None
            host_hash_raw = host_model.get("hash") or ""
            host_hash = host_hash_raw.replace("sha256:", "")

            if model.filename != host_model.get("current_filename"):
                status = "rename_pending"
            elif lib_hash and host_hash and lib_hash != host_hash:
                status = "outdated"
            else:
                status = "synced"

            result.append({
                "host_id": host_id,
                "host_name": host["name"],
                "status": status,
                "synced_at": host_model.get("synced_at"),
                "host_filename": host_model.get("current_filename"),
                "disk_free": host.get("disk_free", 0),
            })

    return result


def sync_model_to_host(
    model_id: str,
    host_id: str,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Copy a model from the library to a host with sidecar metadata."""
    validate_host_id(host_id)
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    src_path = safe_resolve(config.LIBRARY_PATH, model.relative_path)
    if not src_path.exists():
        raise ValueError(f"Source file not found: {model.relative_path}")

    # Preserve full subfolder structure: category/subfolder/.../filename
    rel_parts = Path(model.relative_path).parts
    # Build host path preserving all directories from relative_path
    host_model_dir = host_path / str(Path(*rel_parts[:-1]))
    host_model_dir.mkdir(parents=True, exist_ok=True)

    dest_file = host_model_dir / model.filename
    total_size = src_path.stat().st_size
    copied_size = 0

    # Copy with progress
    temp_path = str(dest_file) + ".syncing"
    try:
        with open(src_path, "rb") as src, open(temp_path, "wb") as dst:
            while True:
                chunk = src.read(config.COPY_BUFFER_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                copied_size += len(chunk)
                if progress_callback:
                    progress_callback(copied_size, total_size)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    # Atomic rename
    os.replace(temp_path, str(dest_file))

    # Write sidecar metadata
    now = to_iso(get_now())
    sidecar = SyncMetadata(
        library_model_id=model.id,
        library_name=model.name,
        current_filename=model.filename,
        synced_at=now,
        hash=f"sha256:{model.hash['sha256']}" if model.hash and model.hash.get("sha256") else None,
    )
    sidecar_path = host_model_dir / f".{model.filename}{SIDECAR_SUFFIX}"
    _atomic_write_sidecar(sidecar_path, sidecar.model_dump())

    model.updated_at = now
    save_model(model)
    rebuild_index()

    logger.info(f"Synced {model.name} to {host_id}")
    return {
        "model_id": model.id,
        "host": host_id,
        "path": str(dest_file.relative_to(host_path)),
        "size": total_size,
        "synced_at": now,
    }


def remove_from_host(model_id: str, host_id: str) -> dict:
    """Remove a synced model and its sidecar from a host."""
    validate_host_id(host_id)
    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    # Find the sidecar for this model
    for root, dirs, files in os.walk(host_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue
            sidecar_path = Path(root) / filename
            data = _load_sidecar(sidecar_path)
            if data is None:
                continue
            try:
                if data.get("library_model_id") == model_id:
                    current_filename = data.get("current_filename", "")
                    model_file = (Path(root) / current_filename).resolve()
                    if not model_file.is_relative_to(host_path.resolve()):
                        logger.warning(f"Sidecar references path outside host: {sidecar_path}")
                        continue
                    result = {"model_id": model_id, "host": host_id, "file_deleted": False, "sidecar_deleted": False}
                    if model_file.exists():
                        model_file.unlink()
                        result["file_deleted"] = True
                    sidecar_path.unlink()
                    result["sidecar_deleted"] = True
                    # Clean up empty subfolders (but not the host root or category root)
                    cleanup_empty_parents(model_file, host_path)
                    logger.info(f"Removed {data.get('library_name', model_id)} from {host_id}")
                    return result
            except OSError:
                continue

    raise ValueError(f"Model {model_id} not found on host {host_id}")


def apply_rename_on_host(model_id: str, host_id: str) -> dict:
    """Apply a pending library rename to a synced model on a host."""
    validate_host_id(host_id)
    model = load_model(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    for root, dirs, files in os.walk(host_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue
            sidecar_path = Path(root) / filename
            data = _load_sidecar(sidecar_path)
            if data is None:
                continue
            try:
                if data.get("library_model_id") != model_id:
                    continue

                old_filename = data["current_filename"]
                old_path = (Path(root) / old_filename).resolve()
                new_filename = model.filename
                new_path = (Path(root) / new_filename).resolve()

                if not old_path.is_relative_to(host_path.resolve()) or not new_path.is_relative_to(host_path.resolve()):
                    logger.warning(f"Sidecar references path outside host: {sidecar_path}")
                    continue

                now = to_iso(get_now())

                if old_path.exists() and old_filename != new_filename:
                    os.rename(str(old_path), str(new_path))

                # Update sidecar
                data["current_filename"] = new_filename
                data["library_name"] = model.name

                # Write updated sidecar with new name
                sidecar_path.unlink()
                new_sidecar_path = Path(root) / f".{new_filename}{SIDECAR_SUFFIX}"
                _atomic_write_sidecar(new_sidecar_path, data)

                logger.info(f"Applied rename {old_filename} \u2192 {new_filename} on {host_id}")
                return {
                    "model_id": model_id,
                    "host": host_id,
                    "old_filename": old_filename,
                    "new_filename": new_filename,
                }
            except (OSError) as e:
                logger.error(f"Error processing sidecar {sidecar_path}: {e}")
                continue

    raise ValueError(f"Model {model_id} not found on host {host_id}")


def scan_host(host_id: str) -> dict:
    """Scan a host for model files that are not managed by gAItor sidecars."""
    validate_host_id(host_id)
    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    # Collect all sidecar-managed filenames so we can skip them
    managed_files = set()
    for root, dirs, files in os.walk(host_path):
        for filename in files:
            if not filename.endswith(SIDECAR_SUFFIX):
                continue
            sidecar_path = Path(root) / filename
            data = _load_sidecar(sidecar_path)
            if data is None:
                continue
            managed_name = data.get("current_filename", "")
            if managed_name:
                managed_abs = (Path(root) / managed_name).resolve()
                if managed_abs.is_relative_to(host_path.resolve()):
                    managed_files.add(str(managed_abs))

    # Load library models for matching
    library_models = load_all_models()
    lib_by_filename = {}
    for m in library_models:
        lib_by_filename.setdefault(m.filename, []).append(m)

    categories = load_categories()

    unmanaged = []
    already_managed = 0

    for root, dirs, files in os.walk(host_path):
        for filename in files:
            filepath = Path(root) / filename

            # Skip sidecars and non-model files
            if filename.endswith(SIDECAR_SUFFIX):
                continue
            ext = filepath.suffix.lower()
            if ext not in config.MODEL_EXTENSIONS:
                continue

            abs_path = filepath.resolve()
            if str(abs_path) in managed_files:
                already_managed += 1
                continue

            rel_path = str(filepath.relative_to(host_path))
            try:
                size = filepath.stat().st_size
            except OSError:
                size = 0

            # Guess category from top-level folder
            rel_parts = Path(rel_path).parts
            guessed_category = "other"
            if len(rel_parts) > 1:
                top_folder = rel_parts[0].lower()
                for cat in categories:
                    if cat.id == top_folder or cat.label.lower() == top_folder:
                        guessed_category = cat.id
                        break

            # Try to match against library models
            match = None
            candidates = lib_by_filename.get(filename, [])
            for lib_model in candidates:
                if lib_model.size == size:
                    match = {
                        "library_model_id": lib_model.id,
                        "library_name": lib_model.name,
                        "match_type": "filename_and_size",
                        "confidence": "high",
                    }
                    break
            if not match and candidates:
                lib_model = candidates[0]
                match = {
                    "library_model_id": lib_model.id,
                    "library_name": lib_model.name,
                    "match_type": "filename",
                    "confidence": "medium",
                }

            unmanaged.append({
                "filename": filename,
                "relative_path": rel_path,
                "size": size,
                "extension": ext,
                "guessed_category": guessed_category,
                "match": match,
            })

    logger.info(f"Host scan {host_id}: {len(unmanaged)} unmanaged, {already_managed} managed")
    return {
        "host_id": host_id,
        "unmanaged": unmanaged,
        "count": len(unmanaged),
        "already_managed": already_managed,
    }


def _compute_file_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(config.COPY_BUFFER_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def link_host_model(host_id: str, relative_path: str, library_model_id: str) -> dict:
    """Link an existing host file to a library model by creating a sidecar.

    Verifies the files match by computing and comparing SHA-256 hashes.
    """
    validate_host_id(host_id)
    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    host_file = safe_resolve(host_path, relative_path)
    if not host_file.exists():
        raise FileNotFoundError(f"File not found on host: {relative_path}")

    model = load_model(library_model_id)
    if not model:
        raise ValueError(f"Library model not found: {library_model_id}")

    # Compute hash of host file
    host_hash = _compute_file_hash(host_file)

    # Ensure library model has a hash; compute if missing
    lib_hash = model.hash.get("sha256") if model.hash else None
    if not lib_hash:
        lib_file = safe_resolve(config.LIBRARY_PATH, model.relative_path)
        if lib_file.exists():
            lib_hash = _compute_file_hash(lib_file)
            model.hash = {"sha256": lib_hash}
            model.updated_at = to_iso(get_now())
            save_model(model)
            rebuild_index()

    # Verify hashes match
    if lib_hash and host_hash != lib_hash:
        raise ValueError(
            f"Hash mismatch: host file does not match library model. "
            f"Host: {host_hash[:16]}... Library: {lib_hash[:16]}..."
        )

    # Create sidecar
    now = to_iso(get_now())
    sidecar = SyncMetadata(
        library_model_id=model.id,
        library_name=model.name,
        current_filename=host_file.name,
        synced_at=now,
        hash=f"sha256:{host_hash}",
    )
    sidecar_path = host_file.parent / f".{host_file.name}{SIDECAR_SUFFIX}"
    _atomic_write_sidecar(sidecar_path, sidecar.model_dump())

    model.updated_at = now
    save_model(model)
    rebuild_index()

    logger.info(f"Linked {model.name} on {host_id} (hash verified)")
    return {
        "model_id": model.id,
        "host": host_id,
        "path": relative_path,
        "hash_verified": True,
        "linked_at": now,
    }


def import_from_host(
    host_id: str,
    relative_path: str,
    name: str,
    category: str = "other",
    description: str = "",
    tags: Optional[list[str]] = None,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Import a model from a host into the library (reverse sync)."""
    validate_host_id(host_id)
    host_path = safe_resolve(config.HOSTS_ROOT, host_id)
    if not host_path.exists():
        raise ValueError(f"Host not found: {host_id}")

    src_file = safe_resolve(host_path, relative_path)
    if not src_file.exists():
        raise FileNotFoundError(f"File not found on host: {relative_path}")

    filename = sanitize_filename(src_file.stem, src_file.suffix)

    # Build library destination path
    dest_dir = safe_resolve(config.LIBRARY_PATH, category)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / filename

    if dest_file.exists():
        raise ValueError(f"File already exists in library: {category}/{filename}")

    # Copy with progress tracking
    total_size = src_file.stat().st_size
    copied_size = 0
    temp_path = str(dest_file) + ".importing"
    try:
        with open(src_file, "rb") as src, open(temp_path, "wb") as dst:
            while True:
                chunk = src.read(config.COPY_BUFFER_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                copied_size += len(chunk)
                if progress_callback:
                    progress_callback(copied_size, total_size)
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    os.replace(temp_path, str(dest_file))

    # Create library metadata
    now = to_iso(get_now())
    lib_rel_path = f"{category}/{filename}"
    model = ModelMetadata(
        id=str(uuid.uuid4()),
        name=name,
        filename=filename,
        category=category,
        relative_path=lib_rel_path,
        size=total_size,
        source=ModelSource(provider="host_import"),
        description=description,
        tags=tags or [],
        created_at=now,
        updated_at=now,
    )
    save_model(model)
    rebuild_index()

    # Create sidecar on the host linking back to the new library model
    sidecar = SyncMetadata(
        library_model_id=model.id,
        library_name=model.name,
        current_filename=src_file.name,
        synced_at=now,
    )
    sidecar_path = src_file.parent / f".{src_file.name}{SIDECAR_SUFFIX}"
    _atomic_write_sidecar(sidecar_path, sidecar.model_dump())

    logger.info(f"Imported {name} from {host_id} into library")
    return {
        "model_id": model.id,
        "host": host_id,
        "library_path": lib_rel_path,
        "size": total_size,
        "imported_at": now,
    }
