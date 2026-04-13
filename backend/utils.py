"""
Utility functions for Model gAItor.
"""
from datetime import datetime
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
