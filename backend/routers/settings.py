"""
Settings API endpoints — version checking and configuration.
"""
from fastapi import APIRouter, Request
import logging
import urllib.request
import json

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/version")
async def get_version(request: Request):
    """Get the application version and check for updates."""
    current = request.app.version
    result = {"version": current, "latest": None, "update_available": False}

    try:
        from .. import config
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


def _is_newer(latest: str, current: str) -> bool:
    """Compare semver strings. Returns True if latest > current."""
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False
