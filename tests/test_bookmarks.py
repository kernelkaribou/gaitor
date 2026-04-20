"""Tests for bookmark CRUD and thumbnail endpoints."""
import pytest
import tempfile
import shutil
from pathlib import Path
from io import BytesIO
from PIL import Image

from backend.services import bookmarks as bm_svc
from backend.services import metadata as meta


@pytest.fixture(autouse=True)
def bookmark_dirs(tmp_path):
    """Redirect bookmark and metadata dirs to temp for each test."""
    orig_meta = meta.METADATA_DIR
    orig_models = meta.MODELS_DIR
    orig_thumbs = meta.THUMBNAILS_DIR
    orig_index = meta.INDEX_FILE
    orig_bm_dir = bm_svc.BOOKMARKS_DIR
    orig_bm_index = bm_svc.BOOKMARKS_INDEX

    meta.METADATA_DIR = tmp_path / ".gaitor"
    meta.MODELS_DIR = meta.METADATA_DIR / "models"
    meta.THUMBNAILS_DIR = meta.METADATA_DIR / "thumbnails"
    meta.INDEX_FILE = meta.METADATA_DIR / "index.json"
    bm_svc.BOOKMARKS_DIR = meta.METADATA_DIR / "bookmarks"
    bm_svc.BOOKMARKS_INDEX = meta.METADATA_DIR / "index_bookmarks.json"

    meta.METADATA_DIR.mkdir(parents=True)
    meta.MODELS_DIR.mkdir(parents=True)
    meta.THUMBNAILS_DIR.mkdir(parents=True)

    yield

    meta.METADATA_DIR = orig_meta
    meta.MODELS_DIR = orig_models
    meta.THUMBNAILS_DIR = orig_thumbs
    meta.INDEX_FILE = orig_index
    bm_svc.BOOKMARKS_DIR = orig_bm_dir
    bm_svc.BOOKMARKS_INDEX = orig_bm_index


def _make_test_image():
    """Create a small valid PNG in memory."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class TestBookmarkCRUD:
    """Test bookmark create, read, update, delete via API."""

    def test_list_empty(self, client):
        resp = client.get("/api/bookmarks/")
        assert resp.status_code == 200
        assert resp.json()["bookmarks"] == []

    def test_create_bookmark(self, client):
        resp = client.post("/api/bookmarks/", json={
            "name": "Test Model",
            "source_url": "https://huggingface.co/test/model",
            "provider": "huggingface",
            "description": "A test model",
            "base_model": "SDXL 1.0",
            "tags": ["test", "sdxl"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Model"
        assert data["source"]["url"] == "https://huggingface.co/test/model"
        assert data["source"]["provider"] == "huggingface"
        assert data["tags"] == ["test", "sdxl"]
        assert data["id"]

    def test_create_requires_name(self, client):
        resp = client.post("/api/bookmarks/", json={"name": ""})
        assert resp.status_code == 422

    def test_create_missing_name(self, client):
        resp = client.post("/api/bookmarks/", json={})
        assert resp.status_code == 422

    def test_list_after_create(self, client):
        client.post("/api/bookmarks/", json={"name": "BM1"})
        client.post("/api/bookmarks/", json={"name": "BM2"})
        resp = client.get("/api/bookmarks/")
        assert len(resp.json()["bookmarks"]) == 2

    def test_update_bookmark(self, client):
        create = client.post("/api/bookmarks/", json={"name": "Original"})
        bm_id = create.json()["id"]

        resp = client.put(f"/api/bookmarks/{bm_id}", json={
            "name": "Updated",
            "tags": ["new-tag"],
            "base_model": "Flux.1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["tags"] == ["new-tag"]
        assert data["base_model"] == "Flux.1"

    def test_update_empty_name_rejected(self, client):
        create = client.post("/api/bookmarks/", json={"name": "Test"})
        bm_id = create.json()["id"]
        resp = client.put(f"/api/bookmarks/{bm_id}", json={"name": ""})
        assert resp.status_code == 422

    def test_update_nonexistent(self, client):
        resp = client.put("/api/bookmarks/00000000-0000-0000-0000-000000000000", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_bookmark(self, client):
        create = client.post("/api/bookmarks/", json={"name": "ToDelete"})
        bm_id = create.json()["id"]

        resp = client.delete(f"/api/bookmarks/{bm_id}")
        assert resp.status_code == 200

        # Verify gone
        listing = client.get("/api/bookmarks/")
        assert len(listing.json()["bookmarks"]) == 0

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/bookmarks/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_invalid_id_format(self, client):
        resp = client.put("/api/bookmarks/not-a-uuid", json={"name": "X"})
        assert resp.status_code == 400
        resp = client.delete("/api/bookmarks/not-a-uuid")
        assert resp.status_code == 400


class TestBookmarkThumbnails:
    """Test bookmark thumbnail upload, serve, delete."""

    def test_upload_thumbnail(self, client):
        create = client.post("/api/bookmarks/", json={"name": "ThumbTest"})
        bm_id = create.json()["id"]

        img = _make_test_image()
        resp = client.post(
            f"/api/bookmarks/{bm_id}/thumbnail",
            files={"file": ("test.png", img, "image/png")},
        )
        assert resp.status_code == 200
        assert "thumbnail" in resp.json()

    def test_serve_thumbnail(self, client):
        create = client.post("/api/bookmarks/", json={"name": "ServeTest"})
        bm_id = create.json()["id"]

        img = _make_test_image()
        client.post(
            f"/api/bookmarks/{bm_id}/thumbnail",
            files={"file": ("test.png", img, "image/png")},
        )

        resp = client.get(f"/api/bookmarks/{bm_id}/thumbnail")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"

    def test_delete_thumbnail(self, client):
        create = client.post("/api/bookmarks/", json={"name": "DelThumb"})
        bm_id = create.json()["id"]

        img = _make_test_image()
        client.post(
            f"/api/bookmarks/{bm_id}/thumbnail",
            files={"file": ("test.png", img, "image/png")},
        )

        resp = client.delete(f"/api/bookmarks/{bm_id}/thumbnail")
        assert resp.status_code == 200

        # Thumbnail should be gone
        resp = client.get(f"/api/bookmarks/{bm_id}/thumbnail")
        assert resp.status_code == 404

    def test_thumbnail_no_bookmark(self, client):
        resp = client.get("/api/bookmarks/00000000-0000-0000-0000-000000000000/thumbnail")
        assert resp.status_code == 404

    def test_invalid_image_type(self, client):
        create = client.post("/api/bookmarks/", json={"name": "BadType"})
        bm_id = create.json()["id"]

        resp = client.post(
            f"/api/bookmarks/{bm_id}/thumbnail",
            files={"file": ("test.txt", BytesIO(b"not an image"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_delete_bookmark_cleans_thumbnail(self, client):
        """Deleting a bookmark should also remove its thumbnail file."""
        create = client.post("/api/bookmarks/", json={"name": "CleanupTest"})
        bm_id = create.json()["id"]

        img = _make_test_image()
        client.post(
            f"/api/bookmarks/{bm_id}/thumbnail",
            files={"file": ("test.png", img, "image/png")},
        )

        # Confirm thumbnail exists
        thumb_path = meta.THUMBNAILS_DIR / f"bm-{bm_id}.webp"
        assert thumb_path.exists()

        # Delete bookmark
        client.delete(f"/api/bookmarks/{bm_id}")

        # Thumbnail should be cleaned up
        assert not thumb_path.exists()


class TestBookmarkValidation:
    """Test input validation for bookmark endpoints."""

    def test_http_url_rejected(self, client):
        resp = client.post("/api/bookmarks/", json={
            "name": "Bad URL",
            "source_url": "http://insecure.example.com/model",
        })
        assert resp.status_code == 400
        assert "HTTPS" in resp.json()["detail"]

    def test_invalid_provider_rejected(self, client):
        resp = client.post("/api/bookmarks/", json={
            "name": "Bad Provider",
            "provider": "unknown_source",
        })
        assert resp.status_code == 400
        assert "provider" in resp.json()["detail"].lower()

    def test_malformed_types_rejected(self, client):
        """Pydantic rejects wrong types (e.g. list for name, string for tags)."""
        resp = client.post("/api/bookmarks/", json={"name": ["not", "a", "string"]})
        assert resp.status_code == 422

        resp = client.post("/api/bookmarks/", json={"name": "OK", "tags": "not-a-list"})
        assert resp.status_code == 422

    def test_thumbnail_url_must_be_https(self, client):
        resp = client.post("/api/bookmarks/", json={
            "name": "Bad Thumb",
            "thumbnail_url": "http://example.com/img.png",
        })
        assert resp.status_code == 400

    def test_valid_provider_accepted(self, client):
        for provider in ("huggingface", "civitai", "url", "other"):
            resp = client.post("/api/bookmarks/", json={
                "name": f"Provider {provider}",
                "provider": provider,
            })
            assert resp.status_code == 200, f"Provider {provider} should be accepted"
