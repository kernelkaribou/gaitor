"""
Destination management API endpoints.
"""
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from ..services.sync import (
    list_destinations,
    get_destination_models,
    get_sync_status,
    sync_model_to_destination,
    remove_from_destination,
    apply_rename_on_destination,
)
from ..services.metadata import load_model
from ..services.tasks import task_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class SyncRequest(BaseModel):
    model_id: str


class BulkSyncRequest(BaseModel):
    model_ids: list[str]

    def model_post_init(self, __context):
        if len(self.model_ids) > 100:
            raise ValueError("Bulk sync limited to 100 models at a time")


class RemoveRequest(BaseModel):
    model_id: str


@router.get("/")
async def list_destinations_endpoint():
    """List all available destinations."""
    dests = list_destinations()
    return {"destinations": dests, "count": len(dests)}


@router.get("/{dest_id}/models")
async def destination_models(dest_id: str):
    """List synced models on a destination."""
    try:
        models = get_destination_models(dest_id)
        return {"models": models, "count": len(models)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dest_id}/status")
async def destination_sync_status(dest_id: str):
    """Get sync status comparing library with a destination."""
    try:
        status = get_sync_status(dest_id)
        return {"status": status, "count": len(status)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{dest_id}/sync")
async def sync_model(dest_id: str, req: SyncRequest):
    """Sync a single model to a destination with progress tracking."""
    model = load_model(req.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    task_id = task_manager.create_task("sync", f"Syncing {model.name} to {dest_id}")

    async def _do_sync():
        try:
            def progress_cb(copied, total):
                task_manager.update_progress(task_id, copied, total)
            result = await asyncio.to_thread(
                sync_model_to_destination, req.model_id, dest_id, progress_cb
            )
            task_manager.complete_task(task_id, f"Synced {model.name} to {dest_id}")
            return result
        except Exception as e:
            task_manager.fail_task(task_id, str(e))
            raise

    atask = asyncio.create_task(_do_sync())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "message": f"Sync started for {model.name}"}


@router.post("/{dest_id}/sync/bulk")
async def bulk_sync(dest_id: str, req: BulkSyncRequest):
    """Sync multiple models to a destination with progress tracking."""
    task_id = task_manager.create_task("sync", f"Bulk sync {len(req.model_ids)} models to {dest_id}")

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
                        sync_model_to_destination, model_id, dest_id, progress_cb
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


@router.post("/{dest_id}/remove")
async def remove_model(dest_id: str, req: RemoveRequest):
    """Remove a synced model from a destination."""
    try:
        result = remove_from_destination(req.model_id, dest_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{dest_id}/apply-rename")
async def apply_rename(dest_id: str, req: SyncRequest):
    """Apply a pending library rename on a destination."""
    try:
        result = apply_rename_on_destination(req.model_id, dest_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
