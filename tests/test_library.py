"""Tests for library and metadata services."""
import json
import os
import pytest
from pathlib import Path

from backend.services.metadata import (
    _atomic_write_json,
    _read_json,
    ensure_metadata_dir,
    is_library_initialized,
    initialize_library,
    load_categories,
    save_categories,
    add_category,
    delete_category,
    save_model,
    load_model,
    delete_model_metadata,
    load_all_models,
    rebuild_index,
    load_index,
    METADATA_DIR,
    MODELS_DIR,
    CONFIG_FILE,
)
from backend.services.library import (
    get_library_status,
    scan_for_untracked,
    catalog_model,
    update_model_metadata,
    rename_model,
    delete_library_model,
)
from backend.schemas.model import ModelMetadata
from backend.schemas.library import CategoryDefinition
from backend import config


@pytest.fixture(autouse=True)
def temp_library(tmp_path, monkeypatch):
    """Use a temp directory as the library for each test."""
    monkeypatch.setattr(config, "LIBRARY_PATH", tmp_path / "library")
    config.LIBRARY_PATH.mkdir()

    # Update metadata module paths
    import backend.services.metadata as meta
    meta.METADATA_DIR = config.LIBRARY_PATH / config.METADATA_DIR_NAME
    meta.MODELS_DIR = meta.METADATA_DIR / "models"
    meta.THUMBNAILS_DIR = meta.METADATA_DIR / "thumbnails"
    meta.INDEX_FILE = meta.METADATA_DIR / "index.json"
    meta.CONFIG_FILE = meta.METADATA_DIR / "config.json"
    meta.CATEGORIES_FILE = meta.METADATA_DIR / "categories.json"


class TestMetadata:
    def test_atomic_write_and_read(self, tmp_path):
        path = tmp_path / "test.json"
        data = {"key": "value"}
        _atomic_write_json(path, data)
        assert _read_json(path) == data

    def test_read_missing_file(self, tmp_path):
        assert _read_json(tmp_path / "missing.json") is None

    def test_ensure_metadata_dir(self):
        import backend.services.metadata as meta
        fresh = ensure_metadata_dir()
        assert fresh is True
        assert meta.METADATA_DIR.exists()
        assert meta.MODELS_DIR.exists()
        assert meta.THUMBNAILS_DIR.exists()

        # Second call should not be fresh
        fresh2 = ensure_metadata_dir()
        assert fresh2 is False

    def test_initialize_library(self):
        lib_config = initialize_library(name="Test Library")
        assert lib_config.name == "Test Library"
        assert is_library_initialized()
        cats = load_categories()
        assert len(cats) > 0
        assert any(c.id == "checkpoints" for c in cats)

    def test_categories_crud(self):
        initialize_library()
        cats = load_categories()
        initial_count = len(cats)

        new_cat = CategoryDefinition(id="flux", label="Flux Models", extensions=[".safetensors"], description="Flux")
        cats = add_category(new_cat)
        assert len(cats) == initial_count + 1
        assert any(c.id == "flux" for c in cats)

        # Duplicate should fail
        with pytest.raises(ValueError):
            add_category(new_cat)

        cats = delete_category("flux")
        assert not any(c.id == "flux" for c in cats)

    def test_model_save_load_delete(self):
        ensure_metadata_dir()
        model = ModelMetadata(
            name="Test Model",
            filename="test.safetensors",
            relative_path="checkpoints/test.safetensors",
            size=1000,
        )
        save_model(model)
        loaded = load_model(model.id)
        assert loaded is not None
        assert loaded.name == "Test Model"
        assert loaded.filename == "test.safetensors"

        assert delete_model_metadata(model.id)
        assert load_model(model.id) is None

    def test_load_all_models_and_index(self):
        initialize_library()
        for i in range(3):
            model = ModelMetadata(
                name=f"Model {i}",
                filename=f"model_{i}.safetensors",
                relative_path=f"checkpoints/model_{i}.safetensors",
                size=1000 * (i + 1),
            )
            save_model(model)

        all_models = load_all_models()
        assert len(all_models) == 3

        index = rebuild_index()
        assert len(index) == 3

        cached = load_index()
        assert len(cached) == 3


class TestLibraryService:
    def test_get_library_status_uninitialized(self):
        status = get_library_status()
        assert status["exists"] is True
        assert status["initialized"] is False

    def test_get_library_status_initialized(self):
        initialize_library()
        status = get_library_status()
        assert status["initialized"] is True
        assert status["model_count"] == 0

    def test_scan_for_untracked(self):
        initialize_library()

        # Create some model files
        checkpoints = config.LIBRARY_PATH / "checkpoints"
        checkpoints.mkdir()
        (checkpoints / "model_a.safetensors").write_bytes(b"x" * 100)
        (checkpoints / "model_b.ckpt").write_bytes(b"y" * 200)
        (checkpoints / "readme.txt").write_bytes(b"not a model")

        untracked = scan_for_untracked()
        assert len(untracked) == 2
        names = {u["filename"] for u in untracked}
        assert "model_a.safetensors" in names
        assert "model_b.ckpt" in names
        assert "readme.txt" not in names

    def test_catalog_model(self):
        initialize_library()
        filepath = config.LIBRARY_PATH / "checkpoints" / "test.safetensors"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(b"model data" * 100)

        model = catalog_model(
            relative_path="checkpoints/test.safetensors",
            name="Test Model",
            category="checkpoints",
            description="A test model",
            tags=["test"],
        )

        assert model.name == "Test Model"
        assert model.category == "checkpoints"
        assert model.size == 1000
        assert len(model.history) == 1
        assert model.history[0].action == "added"

    def test_update_model_metadata(self):
        initialize_library()
        filepath = config.LIBRARY_PATH / "test.safetensors"
        filepath.write_bytes(b"x" * 100)

        model = catalog_model(relative_path="test.safetensors", name="Original")
        updated = update_model_metadata(model.id, {"name": "Renamed", "description": "Updated desc"})
        assert updated.name == "Renamed"
        assert updated.description == "Updated desc"
        assert any(h.action == "metadata_updated" for h in updated.history)

    def test_rename_model(self):
        initialize_library()
        filepath = config.LIBRARY_PATH / "old_name.safetensors"
        filepath.write_bytes(b"x" * 100)

        model = catalog_model(relative_path="old_name.safetensors", name="Old Name")
        renamed = rename_model(model.id, "New Name", rename_file=True)

        assert renamed.name == "New Name"
        assert "New_Name" in renamed.filename
        assert any(h.action == "renamed" for h in renamed.history)
        # Old file should be gone, new file should exist
        assert not filepath.exists()
        new_path = config.LIBRARY_PATH / renamed.relative_path
        assert new_path.exists()

    def test_delete_library_model(self):
        initialize_library()
        filepath = config.LIBRARY_PATH / "to_delete.safetensors"
        filepath.write_bytes(b"x" * 100)

        model = catalog_model(relative_path="to_delete.safetensors", name="Delete Me")
        result = delete_library_model(model.id, delete_file=True)

        assert result["file_deleted"] is True
        assert result["metadata_deleted"] is True
        assert not filepath.exists()
        assert load_model(model.id) is None
