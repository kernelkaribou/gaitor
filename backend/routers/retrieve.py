"""
External model retrieval API endpoints — placeholder.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/providers")
async def list_providers():
    """List supported model retrieval providers."""
    return {
        "providers": [
            {"id": "huggingface", "name": "Hugging Face", "configured": False},
            {"id": "civitai", "name": "CivitAI", "configured": False},
        ],
        "message": "External retrieval coming in Phase 4",
    }
