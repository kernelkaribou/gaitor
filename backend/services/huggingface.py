"""
HuggingFace integration — browse repos, resolve files, download models.
"""
import logging
import re
from typing import Optional

import httpx

from .. import config

logger = logging.getLogger(__name__)

HF_API_BASE = "https://huggingface.co/api"


def _get_headers() -> dict:
    """Build auth headers if token is available."""
    token = config.HUGGINGFACE_TOKEN
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def parse_hf_url(url: str) -> Optional[dict]:
    """Parse a HuggingFace URL into repo_id and optional filename.

    Supports:
      https://huggingface.co/user/repo
      https://huggingface.co/user/repo/blob/main/file.safetensors
      https://huggingface.co/user/repo/resolve/main/file.safetensors
    """
    patterns = [
        r"huggingface\.co/([^/]+/[^/]+)/(?:blob|resolve)/[^/]+/(.+)",
        r"huggingface\.co/([^/]+/[^/]+?)(?:/tree.*)?$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url.strip())
        if m:
            repo_id = m.group(1)
            filename = m.group(2) if m.lastindex >= 2 else None
            return {"repo_id": repo_id, "filename": filename}
    return None


async def get_repo_info(repo_id: str) -> dict:
    """Fetch repository metadata from HuggingFace."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{HF_API_BASE}/models/{repo_id}",
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "repo_id": data.get("modelId", repo_id),
            "author": data.get("author", ""),
            "description": data.get("description", ""),
            "tags": data.get("tags", []),
            "downloads": data.get("downloads", 0),
            "likes": data.get("likes", 0),
            "last_modified": data.get("lastModified", ""),
            "private": data.get("private", False),
            "gated": data.get("gated", False),
        }


async def list_repo_files(repo_id: str) -> list[dict]:
    """List files in a HuggingFace repo, filtered to model-relevant extensions."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{HF_API_BASE}/models/{repo_id}",
            params={"blobs": True},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    siblings = data.get("siblings", [])
    files = []
    for s in siblings:
        fname = s.get("rfilename", "")
        size = s.get("size", 0)
        ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
        is_model = ext.lower() in config.MODEL_EXTENSIONS
        files.append({
            "filename": fname,
            "size": size,
            "extension": ext,
            "is_model": is_model,
            "download_url": f"https://huggingface.co/{repo_id}/resolve/main/{fname}",
        })

    return files


def get_download_url(repo_id: str, filename: str) -> str:
    """Build the direct download URL for a file."""
    return f"https://huggingface.co/{repo_id}/resolve/main/{filename}"


async def search_models(query: str, limit: int = 20) -> list[dict]:
    """Search HuggingFace models by keyword."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{HF_API_BASE}/models",
            params={"search": query, "limit": limit, "sort": "downloads", "direction": -1},
            headers=_get_headers(),
        )
        resp.raise_for_status()
        results = resp.json()

    return [
        {
            "repo_id": r.get("modelId", ""),
            "author": r.get("author", ""),
            "downloads": r.get("downloads", 0),
            "likes": r.get("likes", 0),
            "tags": r.get("tags", [])[:5],
            "last_modified": r.get("lastModified", ""),
        }
        for r in results
    ]
