"""
Settings API endpoints - version checking, configuration, disk space, metadata export.
"""
from fastapi import APIRouter, Request
from fastapi.responses import Response
import logging
import os
import json
from pathlib import Path

import httpx

from .. import config
from ..services.metadata import load_all_models, load_categories, get_library_config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/version")
async def get_version(request: Request):
    """Get the application version and check for updates."""
    current = request.app.version
    result = {"version": current, "latest": None, "update_available": False}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "gaitor"},
            )
            resp.raise_for_status()
            data = resp.json()
            latest_tag = data.get("tag_name", "").lstrip("v")
            if latest_tag:
                result["latest"] = latest_tag
                result["update_available"] = _is_newer(latest_tag, current)
                result["release_url"] = data.get("html_url", "")
    except Exception:
        pass

    return result


@router.get("/disk")
async def get_disk_usage():
    """Get disk usage for library and all hosts."""
    result = {"library": _disk_info(config.LIBRARY_PATH), "hosts": {}}
    if config.HOSTS_ROOT.exists():
        for entry in sorted(config.HOSTS_ROOT.iterdir()):
            if entry.is_dir():
                result["hosts"][entry.name] = _disk_info(entry)
    return result


@router.get("/auth")
async def get_auth_status():
    """Check which auth tokens are configured (without revealing values)."""
    return {
        "huggingface": {
            "configured": bool(config.HUGGINGFACE_TOKEN),
            "source": "environment" if config.HUGGINGFACE_TOKEN else "not set",
        },
        "civitai": {
            "configured": bool(config.CIVITAI_API_KEY),
            "source": "environment" if config.CIVITAI_API_KEY else "not set",
        },
    }


def _disk_info(path: Path) -> dict:
    """Get disk usage info for a path."""
    try:
        stat = os.statvfs(str(path))
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return {"total": total, "free": free, "used": used, "path": str(path)}
    except OSError:
        return {"total": 0, "free": 0, "used": 0, "path": str(path)}


def _is_newer(latest: str, current: str) -> bool:
    """Compare semver strings. Returns True if latest > current."""
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


@router.get("/export")
async def export_metadata():
    """Export all library metadata as a single JSON file for backup."""
    import asyncio
    lib_config = await asyncio.to_thread(get_library_config)
    all_models = await asyncio.to_thread(load_all_models)
    cats = await asyncio.to_thread(load_categories)

    export_data = {
        "export_version": 1,
        "library": lib_config.model_dump() if lib_config else None,
        "categories": [c.model_dump() for c in cats],
        "models": [m.model_dump() for m in all_models],
        "model_count": len(all_models),
    }

    content = json.dumps(export_data, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=gaitor-export.json"},
    )
