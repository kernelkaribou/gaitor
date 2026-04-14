"""
Pydantic schemas for hosts.
"""
from pydantic import BaseModel
from typing import Optional


class Host(BaseModel):
    """A registered host for model syncing."""
    id: str
    name: str
    path: str
    description: str = ""
    created_at: str = ""
