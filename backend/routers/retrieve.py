"""
External model retrieval API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from .. import config
from ..services import huggingface, civitai
from ..services.retrieval import detect_provider, resolve_url, download_model

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


class SearchRequest(BaseModel):
    query: str
    provider: str = "huggingface"
    limit: int = 20

    def model_post_init(self, __context):
        if self.limit < 1:
            self.limit = 1
        elif self.limit > 100:
            self.limit = 100


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
    """Download a model file from an external source into the library."""
    try:
        model = await download_model(
            url=req.url,
            filename=req.filename,
            category=req.category,
            name=req.name,
            description=req.description,
            tags=req.tags,
            provider=req.provider or detect_provider(req.url),
        )
        return {"model": model.model_dump(), "status": "downloaded"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=502, detail="Download failed")


@router.post("/search")
async def search_models(req: SearchRequest):
    """Search for models on a provider."""
    try:
        if req.provider == "huggingface":
            results = await huggingface.search_models(req.query, limit=req.limit)
        elif req.provider == "civitai":
            results = await civitai.search_models(req.query, limit=req.limit)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")
        return {"results": results, "provider": req.provider, "count": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=502, detail="Search failed")


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
