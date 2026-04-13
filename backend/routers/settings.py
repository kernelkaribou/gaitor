"""
Settings API endpoints - version checking, configuration, disk space.
"""
from fastapi import APIRouter, Request
import logging
import os
import urllib.request
import json
from pathlib import Path

from .. import config

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/version")
async def get_version(request: Request):
    """Get the application version and check for updates."""
    current = request.app.version
    result = {"version": current, "latest": None, "update_available": False}

    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "model-gaitor"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
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
    """Get disk usage for library and all destinations."""
    result = {"library": _disk_info(config.LIBRARY_PATH), "destinations": {}}
    if config.DESTINATIONS_ROOT.exists():
        for entry in sorted(config.DESTINATIONS_ROOT.iterdir()):
            if entry.is_dir():
                result["destinations"][entry.name] = _disk_info(entry)
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
