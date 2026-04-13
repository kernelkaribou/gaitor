"""Tests for core API endpoints."""


def test_health_check(client):
    """Health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_version_endpoint(client):
    """Version endpoint returns current version."""
    response = client.get("/api/settings/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "update_available" in data


def test_library_status(client):
    """Library status endpoint works."""
    response = client.get("/api/library/status")
    assert response.status_code == 200


def test_models_list(client):
    """Models list endpoint works."""
    response = client.get("/api/models/")
    assert response.status_code == 200


def test_destinations_list(client):
    """Destinations list endpoint works."""
    response = client.get("/api/destinations/")
    assert response.status_code == 200


def test_retrieve_providers(client):
    """Retrieve providers endpoint works."""
    response = client.get("/api/retrieve/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data


def test_frontend_fallback(client):
    """Non-API routes return frontend or fallback."""
    response = client.get("/")
    assert response.status_code == 200
