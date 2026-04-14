"""
External model retrieval API endpoints.
"""
import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from .. import config
from ..services import huggingface, civitai
from ..services.retrieval import detect_provider, resolve_url, download_model
from ..services.tasks import task_manager

router = APIRouter()
logger = logging.getLogger(__name__)


class ResolveRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    filename: str
    category: str
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    provider: Optional[str] = None
    thumbnail_url: Optional[str] = None
    model_type: Optional[str] = None
    subfolder: Optional[str] = None
    base_model: Optional[str] = None


@router.get("/providers")
async def list_providers():
    """List supported providers and their configuration status."""
    return {
        "providers": [
            {
                "id": "huggingface",
                "name": "Hugging Face",
                "configured": bool(config.HUGGINGFACE_TOKEN),
            },
            {
                "id": "civitai",
                "name": "CivitAI",
                "configured": bool(config.CIVITAI_API_KEY),
            },
            {
                "id": "url",
                "name": "Direct URL",
                "configured": True,
            },
        ]
    }


@router.post("/resolve")
async def resolve_url_endpoint(req: ResolveRequest):
    """Parse and resolve a URL to show available files/versions."""
    try:
        result = await resolve_url(req.url)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve URL: {e}")
        raise HTTPException(status_code=502, detail="Failed to resolve URL")


@router.post("/download")
async def download_model_endpoint(req: DownloadRequest):
    """Start a model download as a background task with progress tracking."""
    from ..services.tasks import CancelledByUser

    provider = req.provider or detect_provider(req.url) or "url"
    display_name = req.name or req.filename

    task_id = task_manager.create_task("download", f"Downloading {display_name}")

    async def _do_download():
        try:
            def progress_cb(downloaded, total):
                task_manager.update_progress(task_id, downloaded, total)

            model = await download_model(
                url=req.url,
                filename=req.filename,
                category=req.category,
                name=req.name,
                description=req.description,
                tags=req.tags,
                provider=provider,
                progress_callback=progress_cb,
                thumbnail_url=req.thumbnail_url,
                subfolder=req.subfolder,
                base_model=req.base_model,
            )
            task_manager.complete_task(
                task_id,
                f"Downloaded {model.name} to {req.category}",
            )
        except (CancelledByUser, asyncio.CancelledError):
            logger.info(f"Download cancelled: {display_name}")
            # Clean up partial download file
            from .. import config
            from ..utils import safe_resolve, sanitize_filename
            try:
                safe_name = sanitize_filename(Path(req.filename).stem, Path(req.filename).suffix)
                tmp_path = safe_resolve(config.LIBRARY_PATH, req.category) / (safe_name + ".downloading")
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Download task failed: {e}")
            task_manager.fail_task(task_id, str(e))

    atask = asyncio.create_task(_do_download())
    task_manager.set_asyncio_task(task_id, atask)
    return {"task_id": task_id, "status": "started"}


@router.get("/hf/{repo_id:path}/files")
async def list_hf_files(repo_id: str):
    """List files in a HuggingFace repository."""
    try:
        files = await huggingface.list_repo_files(repo_id)
        return {"files": files, "repo_id": repo_id}
    except Exception as e:
        logger.error(f"Failed to list HF files: {e}")
        raise HTTPException(status_code=502, detail="Failed to list files")


@router.get("/civitai/{model_id}")
async def get_civitai_model(model_id: str):
    """Get CivitAI model details."""
    try:
        info = await civitai.get_model_info(model_id)
        return info
    except Exception as e:
        logger.error(f"Failed to get CivitAI model: {e}")
        raise HTTPException(status_code=502, detail="Failed to get model info")
