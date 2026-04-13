"""
Retrieval service — download pipeline for external model sources.
Handles URL detection, downloading with progress, and cataloging into the library.
"""
import logging
import os
from pathlib import Path
from typing import Optional, Callable

import httpx

from .. import config
from ..utils import get_now, to_iso
from ..schemas.model import ModelMetadata, ModelHistoryEntry, ModelSource
from .metadata import save_model, rebuild_index, ensure_metadata_dir
from . import huggingface, civitai

logger = logging.getLogger(__name__)


def detect_provider(url: str) -> Optional[str]:
    """Auto-detect which provider a URL belongs to."""
    url_lower = url.lower()
    if "huggingface.co" in url_lower:
        return "huggingface"
    if "civitai.com" in url_lower:
        return "civitai"
    return None


async def resolve_url(url: str) -> dict:
    """Parse a URL and return structured info about what it points to."""
    provider = detect_provider(url)
    if not provider:
        return {"provider": None, "error": "Unsupported URL. Supported: huggingface.co, civitai.com"}

    if provider == "huggingface":
        parsed = huggingface.parse_hf_url(url)
        if not parsed:
            return {"provider": "huggingface", "error": "Could not parse HuggingFace URL"}

        repo_info = await huggingface.get_repo_info(parsed["repo_id"])
        files = await huggingface.list_repo_files(parsed["repo_id"])
        model_files = [f for f in files if f["is_model"]]

        return {
            "provider": "huggingface",
            "repo_id": parsed["repo_id"],
            "repo_info": repo_info,
            "files": model_files,
            "suggested_file": parsed.get("filename"),
        }

    elif provider == "civitai":
        parsed = civitai.parse_civitai_url(url)
        if not parsed:
            return {"provider": "civitai", "error": "Could not parse CivitAI URL"}

        info = await civitai.get_model_info(parsed["model_id"])
        return {
            "provider": "civitai",
            "model_id": parsed["model_id"],
            "version_id": parsed.get("version_id"),
            "model_info": info,
        }


async def download_model(
    url: str,
    filename: str,
    category: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    provider: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> ModelMetadata:
    """Download a model file from an external URL into the library.

    1. Stream download to category folder
    2. Create metadata entry
    3. Return the cataloged model
    """
    ensure_metadata_dir()

    category_dir = config.LIBRARY_PATH / category
    category_dir.mkdir(parents=True, exist_ok=True)
    dest_path = category_dir / filename

    if dest_path.exists():
        raise ValueError(f"File already exists: {category}/{filename}")

    tmp_path = str(dest_path) + ".downloading"
    total_size = 0
    downloaded = 0

    headers = {}
    if provider == "huggingface" and config.HUGGINGFACE_TOKEN:
        headers["Authorization"] = f"Bearer {config.HUGGINGFACE_TOKEN}"
    elif provider == "civitai" and config.CIVITAI_API_KEY:
        headers["Authorization"] = f"Bearer {config.CIVITAI_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get("content-length", 0))

                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=config.COPY_BUFFER_SIZE):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

        os.replace(tmp_path, str(dest_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    actual_size = dest_path.stat().st_size
    now = to_iso(get_now())
    relative_path = f"{category}/{filename}"

    model = ModelMetadata(
        name=name or filename.rsplit(".", 1)[0],
        filename=filename,
        category=category,
        relative_path=relative_path,
        size=actual_size,
        description=description or "",
        tags=tags or [],
        source=ModelSource(
            url=url,
            provider=provider or detect_provider(url) or "url",
            downloaded_at=now,
        ),
        history=[
            ModelHistoryEntry(
                action="retrieved",
                timestamp=now,
                details={"source": url, "provider": provider or "url"},
            )
        ],
        created_at=now,
        updated_at=now,
    )

    save_model(model)
    rebuild_index()

    logger.info(f"Retrieved model: {model.name} from {url}")
    return model
