"""
Destination management API endpoints.
"""
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
    """Sync a single model to a destination."""
    try:
        result = sync_model_to_destination(req.model_id, dest_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.post("/{dest_id}/sync/bulk")
async def bulk_sync(dest_id: str, req: BulkSyncRequest):
    """Sync multiple models to a destination."""
    results = []
    errors = []
    for model_id in req.model_ids:
        try:
            result = sync_model_to_destination(model_id, dest_id)
            results.append(result)
        except Exception as e:
            errors.append({"model_id": model_id, "error": str(e)})
    return {"synced": results, "errors": errors, "count": len(results)}


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
