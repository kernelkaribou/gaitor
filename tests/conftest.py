"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient

from backend.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
