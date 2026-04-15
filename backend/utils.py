"""
Utility functions for gAItor.
"""
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os


def get_local_timezone() -> ZoneInfo:
    """Get the configured timezone from TZ environment variable."""
    tz_str = os.getenv("TZ", "UTC")
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")


def get_now() -> datetime:
    """Get current datetime in the configured timezone."""
    return datetime.now(get_local_timezone())


def to_iso(dt: datetime) -> str:
    """Convert datetime to ISO format string with timezone info."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_local_timezone())
    return dt.isoformat()


def format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# --- Security utilities ---

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.-]*$")


def safe_resolve(base: Path, untrusted: str) -> Path:
    """Resolve an untrusted path and ensure it stays within the base directory.

    Prevents path traversal attacks (e.g., '../../etc/shadow').
    Also rejects symlinks that escape the base directory.
    """
    if not untrusted or ".." in untrusted.split("/") or ".." in untrusted.split("\\"):
        raise ValueError("Path contains illegal components")
    resolved = (base / untrusted).resolve()
    base_resolved = base.resolve()
    if not resolved.is_relative_to(base_resolved):
        raise ValueError("Path escapes allowed directory")
    return resolved


def validate_model_id(model_id: str) -> str:
    """Validate that model_id is a proper UUID."""
    if not _UUID_RE.match(model_id):
        raise ValueError(f"Invalid model ID format: {model_id}")
    return model_id


def validate_host_id(host_id: str) -> str:
    """Validate host ID - alphanumeric, dashes, underscores only."""
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$", host_id):
        raise ValueError(f"Invalid host ID: {host_id}")
    return host_id


def sanitize_filename(name: str, extension: str = "") -> str:
    """Sanitize a user-provided name into a safe filename.

    Strips dangerous characters, replaces spaces with underscores,
    and ensures the result is non-empty.
    Allowed: alphanumeric, space, hyphen, underscore, dot, parentheses, plus.
    """
    safe = "".join(c for c in name if c.isalnum() or c in " -_.()+" ).strip()
    safe = re.sub(r"\s+", "_", safe)  # spaces → underscores
    safe = safe.lstrip(".")  # no hidden files
    safe = safe.replace("..", ".")  # collapse double dots
    if not safe:
        raise ValueError("Name produces an empty filename after sanitization")
    return f"{safe}{extension}" if extension else safe
