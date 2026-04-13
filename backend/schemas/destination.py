"""
Pydantic schemas for destinations.
"""
from pydantic import BaseModel
from typing import Optional


class Destination(BaseModel):
    """A registered destination for model syncing."""
    id: str
    name: str
    path: str
    description: str = ""
    created_at: str = ""
