"""
Host management API endpoints.
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

from ..services.sync import (
    list_hosts,
    get_host_models,
    get_sync_status,
    get_model_host_status,
    sync_model_to_host,
    remove_from_host,
    apply_rename_on_host,
    scan_host,
    link_host_model,
    import_from_host,
    add_ignore_pattern,
    get_ignore_patterns,
    remove_ignore_pattern,
    delete_unmanaged_file,
)
from ..services.metadata import load_model
from ..services.tasks import task_manager
from ..utils import validate_host_id as _validate_host_id

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_host_id(host_id: str) -> str:
    """Validate host_id at router level, raise 400 on invalid."""
    try:
        return _validate_host_id(host_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid host ID")


class SyncRequest(BaseModel):
    model_id: str


class BulkSyncRequest(BaseModel):
    model_ids: list[str]

    def model_post_init(self, __context):
        if len(self.model_ids) > 100:
            raise ValueError("Bulk sync limited to 100 models at a time")


class RemoveRequest(BaseModel):
    model_id: str


class LinkRequest(BaseModel):
    relative_path: str
    library_model_id: str


class ImportRequest(BaseModel):
    relative_path: str
    name: str
    category: str = "other"
    description: str = ""
    tags: list[str] = []


class BulkLinkRequest(BaseModel):
    links: list[LinkRequest]

    def model_post_init(self, __context):
        if len(self.links) > 100:
            raise ValueError("Bulk link limited to 100 models at a time")


class IgnoreRequest(BaseModel):
    pattern: str = Field(max_length=500)


class DeleteFileRequest(BaseModel):
    relative_path: str


@router.get("/")
async def list_hosts_endpoint():
    """List all available hosts."""
    hosts = await asyncio.to_thread(list_hosts)
    return {"hosts": hosts, "count": len(hosts)}


@router.get("/{host_id}/models")
async def host_models(host_id: str):
    """List synced models on a host."""
    host_id = _check_host_id(host_id)
    try:
        models = await asyncio.to_thread(get_host_models, host_id)
        return {"models": models, "count": len(models)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{host_id}/status")
async def host_sync_status(host_id: str):
    """Get sync status comparing library with a host."""
    host_id = _check_host_id(host_id)
    try:
        status = await asyncio.to_thread(get_sync_status, host_id)
        return {"status": status, "count": len(status)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{host_id}/sync")
async def sync_model(host_id: str, req: SyncRequest):
    """Sync a single model to a host with progress tracking."""
    host_id = _check_host_id(host_id)
    model = load_model(req.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    task_id = task_manager.create_task("sync", f"Syncing {model.name} to {host_id}")

    async def _do_sync():
        try:
            def progress_cb(copied, total):
                task_manager.update_progress(task_id, copied, total)
            result = await asyncio.to_thread(
                sync_model_to_host, req.model_id, host_id, progress_cb
            )
            task_manager.complete_task(task_id, f"Synced {model.name} to {host_id}")
            return result
        except Exception as e:
            task_manager.fail_task(task_id, str(e))
            raise

    atask = asyncio.create_task(_do_sync())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "message": f"Sync started for {model.name}"}


@router.post("/{host_id}/sync/bulk")
async def bulk_sync(host_id: str, req: BulkSyncRequest):
    """Sync multiple models to a host with progress tracking."""
    host_id = _check_host_id(host_id)
    task_id = task_manager.create_task("sync", f"Bulk sync {len(req.model_ids)} models to {host_id}")

    async def _do_bulk_sync():
        results = []
        errors = []
        total_models = len(req.model_ids)
        try:
            for i, model_id in enumerate(req.model_ids):
                try:
                    def progress_cb(copied, total, idx=i):
                        overall = int(((idx + copied / max(total, 1)) / total_models) * 100)
                        task_manager.update_progress(task_id, overall, 100)
                    result = await asyncio.to_thread(
                        sync_model_to_host, model_id, host_id, progress_cb
                    )
                    results.append(result)
                except Exception as e:
                    errors.append({"model_id": model_id, "error": str(e)})
            task_manager.complete_task(task_id, f"Synced {len(results)}/{total_models} models")
        except Exception as e:
            task_manager.fail_task(task_id, str(e))

    atask = asyncio.create_task(_do_bulk_sync())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "message": f"Bulk sync started for {len(req.model_ids)} models"}


@router.post("/{host_id}/remove")
async def remove_model(host_id: str, req: RemoveRequest):
    """Remove a synced model from a host."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(remove_from_host, req.model_id, host_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{host_id}/apply-rename")
async def apply_rename(host_id: str, req: SyncRequest):
    """Apply a pending library rename on a host."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(apply_rename_on_host, req.model_id, host_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{host_id}/scan")
async def scan_host_endpoint(host_id: str):
    """Scan a host for unmanaged model files and match against library."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(scan_host, host_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{host_id}/link")
async def link_model_endpoint(host_id: str, req: LinkRequest):
    """Link an existing host file to a library model (hash verified)."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(
            link_host_model, host_id, req.relative_path, req.library_model_id
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        detail = str(e)
        status = 409 if "Hash mismatch" in detail else 404
        raise HTTPException(status_code=status, detail=detail)


@router.post("/{host_id}/link/bulk")
async def bulk_link_endpoint(host_id: str, req: BulkLinkRequest):
    """Link multiple existing host files to library models."""
    host_id = _check_host_id(host_id)
    task_id = task_manager.create_task("link", f"Linking {len(req.links)} models on {host_id}")

    async def _do_bulk_link():
        results = []
        errors = []
        for item in req.links:
            try:
                result = await asyncio.to_thread(
                    link_host_model, host_id, item.relative_path, item.library_model_id
                )
                results.append(result)
            except Exception as e:
                errors.append({"relative_path": item.relative_path, "error": str(e)})
        task_manager.complete_task(
            task_id, f"Linked {len(results)}/{len(req.links)} models"
        )
        return {"linked": results, "errors": errors}

    atask = asyncio.create_task(_do_bulk_link())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "message": f"Linking {len(req.links)} models on {host_id}"}


@router.post("/{host_id}/import")
async def import_model_endpoint(host_id: str, req: ImportRequest):
    """Import a model from a host into the library (reverse sync)."""
    host_id = _check_host_id(host_id)
    task_id = task_manager.create_task("import", f"Importing {req.name} from {host_id}")

    async def _do_import():
        try:
            def progress_cb(copied, total):
                task_manager.update_progress(task_id, copied, total)
            result = await asyncio.to_thread(
                import_from_host,
                host_id, req.relative_path, req.name,
                req.category, req.description, req.tags,
                progress_cb,
            )
            task_manager.complete_task(task_id, f"Imported {req.name}")
            return result
        except Exception as e:
            task_manager.fail_task(task_id, str(e))
            raise

    atask = asyncio.create_task(_do_import())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "message": f"Importing {req.name} from {host_id}"}


@router.post("/{host_id}/ignore")
async def ignore_pattern_endpoint(host_id: str, req: IgnoreRequest):
    """Add a pattern to the host's .gaitor-ignore file."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(add_ignore_pattern, host_id, req.pattern)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write ignore file: {e}")


@router.get("/{host_id}/ignore")
async def list_ignore_patterns_endpoint(host_id: str):
    """List all ignore patterns for a host."""
    host_id = _check_host_id(host_id)
    try:
        patterns = await asyncio.to_thread(get_ignore_patterns, host_id)
        return {"patterns": patterns}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{host_id}/ignore")
async def remove_ignore_pattern_endpoint(host_id: str, req: IgnoreRequest):
    """Remove a pattern from the host's .gaitor-ignore file."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(remove_ignore_pattern, host_id, req.pattern)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ignore file: {e}")


@router.post("/{host_id}/delete-file")
async def delete_file_endpoint(host_id: str, req: DeleteFileRequest):
    """Delete an unmanaged file from a host."""
    host_id = _check_host_id(host_id)
    try:
        result = await asyncio.to_thread(delete_unmanaged_file, host_id, req.relative_path)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
