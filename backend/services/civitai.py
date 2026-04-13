"""
CivitAI integration - search models, resolve URLs, download.
"""
import logging
import re
from typing import Optional

import httpx

from .. import config

logger = logging.getLogger(__name__)

CIVITAI_API_BASE = "https://civitai.com/api/v1"


def _get_headers() -> dict:
    """Build auth headers if API key is available."""
    key = config.CIVITAI_API_KEY
    if key:
        return {"Authorization": f"Bearer {key}"}
    return {}


def parse_civitai_url(url: str) -> Optional[dict]:
    """Parse a CivitAI URL into model_id and optional version_id.

    Supports:
      https://civitai.com/models/12345
      https://civitai.com/models/12345/model-name
      https://civitai.com/models/12345?modelVersionId=67890
    """
    m = re.search(r"civitai\.com/models/(\d+)", url.strip())
    if not m:
        return None

    model_id = m.group(1)
    version_id = None
    vm = re.search(r"modelVersionId=(\d+)", url)
    if vm:
        version_id = vm.group(1)

    return {"model_id": model_id, "version_id": version_id}


async def get_model_info(model_id: str) -> dict:
    """Fetch model details from CivitAI."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CIVITAI_API_BASE}/models/{model_id}",
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    versions = data.get("modelVersions", [])
    return {
        "id": data.get("id"),
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "description": data.get("description", ""),
        "tags": data.get("tags", []),
        "stats": data.get("stats", {}),
        "creator": data.get("creator", {}).get("username", ""),
        "versions": [
            {
                "id": v.get("id"),
                "name": v.get("name", ""),
                "base_model": v.get("baseModel", ""),
                "files": [
                    {
                        "id": f.get("id"),
                        "name": f.get("name", ""),
                        "size": f.get("sizeKB", 0) * 1024,
                        "type": f.get("type", ""),
                        "format": f.get("metadata", {}).get("format", ""),
                        "download_url": f.get("downloadUrl", ""),
                    }
                    for f in v.get("files", [])
                ],
                "images": [
                    img.get("url", "") for img in v.get("images", [])[:3]
                ],
            }
            for v in versions[:5]
        ],
    }


async def get_download_url(model_id: str, version_id: Optional[str] = None) -> dict:
    """Get the primary download URL for a model version."""
    info = await get_model_info(model_id)
    versions = info.get("versions", [])
    if not versions:
        raise ValueError(f"No versions found for model {model_id}")

    version = versions[0]
    if version_id:
        for v in versions:
            if str(v["id"]) == str(version_id):
                version = v
                break

    files = version.get("files", [])
    if not files:
        raise ValueError(f"No files found for version {version['id']}")

    primary = files[0]
    return {
        "download_url": primary["download_url"],
        "filename": primary["name"],
        "size": primary["size"],
        "version_name": version["name"],
        "model_name": info["name"],
    }


async def search_models(query: str, limit: int = 20, model_type: Optional[str] = None) -> list[dict]:
    """Search CivitAI models."""
    params = {"query": query, "limit": limit, "sort": "Most Downloaded"}
    if model_type:
        params["types"] = model_type

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CIVITAI_API_BASE}/models",
            params=params,
            headers=_get_headers(),
        )
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "id": item.get("id"),
            "name": item.get("name", ""),
            "type": item.get("type", ""),
            "creator": item.get("creator", {}).get("username", ""),
            "tags": item.get("tags", [])[:5],
            "stats": item.get("stats", {}),
        }
        for item in data.get("items", [])
    ]
