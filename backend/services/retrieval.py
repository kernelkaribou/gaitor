"""
Retrieval service - download pipeline for external model sources.
Handles URL detection, downloading with progress, and cataloging into the library.
"""
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Optional, Callable

import httpx
from PIL import Image

from .. import config
from ..utils import get_now, to_iso, safe_resolve, sanitize_filename
from ..schemas.model import ModelMetadata, ModelHistoryEntry, ModelSource
from .metadata import save_model, rebuild_index, ensure_metadata_dir, THUMBNAILS_DIR
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
    """Parse a URL and return structured info about what it points to.

    For known providers (HuggingFace, CivitAI), returns rich metadata.
    For unknown URLs, returns a generic direct-download structure.
    """
    provider = detect_provider(url)

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
            "description": repo_info.get("description", ""),
            "tags": repo_info.get("tags", []),
        }

    elif provider == "civitai":
        parsed = civitai.parse_civitai_url(url)
        if not parsed:
            return {"provider": "civitai", "error": "Could not parse CivitAI URL"}

        info = await civitai.get_model_info(parsed["model_id"])

        # Extract first preview image if available
        preview_url = None
        model_type = info.get("type", "")
        for v in info.get("versions", []):
            for img_url in v.get("images", []):
                if img_url:
                    preview_url = img_url
                    break
            if preview_url:
                break

        return {
            "provider": "civitai",
            "model_id": parsed["model_id"],
            "version_id": parsed.get("version_id"),
            "model_info": info,
            "preview_url": preview_url,
            "model_type": model_type,
            "description": info.get("description", ""),
            "tags": info.get("tags", []),
        }

    else:
        # Generic URL - attempt to resolve filename and size from HEAD request
        filename = url.rsplit("/", 1)[-1].split("?")[0] if "/" in url else "model"
        size = 0
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.head(url)
                size = int(resp.headers.get("content-length", 0))
                # Try content-disposition for filename
                cd = resp.headers.get("content-disposition", "")
                if "filename=" in cd:
                    fn = cd.split("filename=")[-1].strip('"').strip("'")
                    if fn:
                        filename = fn
        except Exception:
            pass

        return {
            "provider": "url",
            "files": [{
                "filename": filename,
                "size": size,
                "download_url": url,
                "is_model": True,
            }],
        }


# Map CivitAI model types to our category IDs
CIVITAI_TYPE_MAP = {
    "Checkpoint": "checkpoints",
    "LORA": "loras",
    "TextualInversion": "embeddings",
    "Hypernetwork": "hypernetworks",
    "AestheticGradient": "embeddings",
    "Controlnet": "controlnet",
    "Poses": "other",
    "Upscaler": "upscale_models",
    "VAE": "vae",
    "LoCon": "loras",
    "DoRA": "loras",
    "Wildcards": "other",
    "Workflows": "other",
    "MotionModule": "animatediff_models",
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
    thumbnail_url: Optional[str] = None,
) -> ModelMetadata:
    """Download a model file from an external URL into the library.

    1. Stream download to category folder
    2. Optionally download thumbnail
    3. Create metadata entry
    4. Return the cataloged model
    """
    ensure_metadata_dir()

    # Sanitize filename and validate path stays within library
    safe_name = sanitize_filename(Path(filename).stem, Path(filename).suffix)
    category_dir = safe_resolve(config.LIBRARY_PATH, category)
    category_dir.mkdir(parents=True, exist_ok=True)
    dest_path = category_dir / safe_name

    if dest_path.exists():
        raise ValueError(f"File already exists: {category}/{safe_name}")

    tmp_path = str(dest_path) + ".downloading"
    total_size = 0
    downloaded = 0

    headers = {}
    if provider == "huggingface" and config.HUGGINGFACE_TOKEN:
        headers["Authorization"] = f"Bearer {config.HUGGINGFACE_TOKEN}"
    elif provider == "civitai" and config.CIVITAI_API_KEY:
        headers["Authorization"] = f"Bearer {config.CIVITAI_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=600), follow_redirects=True) as client:
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
    import uuid
    model_id = str(uuid.uuid4())

    # Download thumbnail if provided (convert to max 512x512 webp)
    thumb_rel = None
    if thumbnail_url:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(thumbnail_url)
                resp.raise_for_status()
                THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
                img = Image.open(BytesIO(resp.content))
                img.thumbnail((512, 512), Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="WEBP", quality=85)
                thumb_path = THUMBNAILS_DIR / f"{model_id}.webp"
                thumb_path.write_bytes(buf.getvalue())
                thumb_rel = f"thumbnails/{model_id}.webp"
        except Exception as e:
            logger.warning(f"Failed to download thumbnail: {e}")

    model = ModelMetadata(
        id=model_id,
        name=name or filename.rsplit(".", 1)[0],
        filename=safe_name,
        category=category,
        relative_path=f"{category}/{safe_name}",
        size=actual_size,
        description=description or "",
        tags=tags or [],
        thumbnail=thumb_rel,
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
