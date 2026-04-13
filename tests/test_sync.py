"""Tests for sync service - host management and model syncing."""
import json
import pytest
from pathlib import Path

from backend.services.metadata import (
    ensure_metadata_dir,
    initialize_library,
    save_model,
    load_model,
    rebuild_index,
)
from backend.services.library import catalog_model
from backend.services.sync import (
    list_hosts,
    get_host_models,
    get_sync_status,
    sync_model_to_host,
    remove_from_host,
    apply_rename_on_host,
    SIDECAR_SUFFIX,
)
from backend.services.library import rename_model
from backend.schemas.model import ModelMetadata
from backend import config


@pytest.fixture(autouse=True)
def temp_env(tmp_path, monkeypatch):
    """Set up temp library and host directories."""
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(config, "LIBRARY_PATH", lib)
    monkeypatch.setattr(config, "HOSTS_ROOT", tmp_path / "hosts")
    (tmp_path / "hosts").mkdir()

    import backend.services.metadata as meta
    meta.METADATA_DIR = lib / config.METADATA_DIR_NAME
    meta.MODELS_DIR = meta.METADATA_DIR / "models"
    meta.THUMBNAILS_DIR = meta.METADATA_DIR / "thumbnails"
    meta.INDEX_FILE = meta.METADATA_DIR / "index.json"
    meta.CONFIG_FILE = meta.METADATA_DIR / "config.json"
    meta.CATEGORIES_FILE = meta.METADATA_DIR / "categories.json"


@pytest.fixture
def setup_library():
    """Initialize library and return the path."""
    initialize_library()
    return config.LIBRARY_PATH


@pytest.fixture
def host_path():
    """Create a host and return its path."""
    d = config.HOSTS_ROOT / "test-gpu"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def sample_model(setup_library):
    """Create a cataloged model in the library."""
    filepath = config.LIBRARY_PATH / "checkpoints" / "sdxl.safetensors"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(b"model-data" * 100)

    model = catalog_model(
        relative_path="checkpoints/sdxl.safetensors",
        name="SDXL Base",
        category="checkpoints",
    )
    return model


class TestListHosts:
    def test_no_hosts(self):
        hosts = list_hosts()
        assert hosts == []

    def test_finds_hosts(self, host_path):
        hosts = list_hosts()
        assert len(hosts) == 1
        assert hosts[0]["id"] == "test-gpu"
        assert hosts[0]["name"] == "test-gpu"

    def test_multiple_hosts(self):
        (config.HOSTS_ROOT / "gpu-a").mkdir()
        (config.HOSTS_ROOT / "gpu-b").mkdir()
        hosts = list_hosts()
        assert len(hosts) == 2
        names = {d["id"] for d in hosts}
        assert names == {"gpu-a", "gpu-b"}


class TestGetHostModels:
    def test_missing_host(self):
        with pytest.raises(ValueError, match="not found"):
            get_host_models("nonexistent")

    def test_empty_host(self, host_path):
        models = get_host_models("test-gpu")
        assert models == []

    def test_reads_sidecar(self, host_path):
        # Manually place a sidecar
        sidecar = {
            "library_model_id": "abc-123",
            "library_name": "Test Model",
            "current_filename": "test.safetensors",
            "synced_at": "2025-01-01T00:00:00Z",
            "hash": "sha256:deadbeef",
            "rename_history": [],
        }
        (host_path / "checkpoints").mkdir()
        (host_path / "checkpoints" / "test.safetensors").write_bytes(b"x" * 50)
        with open(host_path / "checkpoints" / f".test.safetensors{SIDECAR_SUFFIX}", "w") as f:
            json.dump(sidecar, f)

        models = get_host_models("test-gpu")
        assert len(models) == 1
        assert models[0]["library_model_id"] == "abc-123"
        assert models[0]["file_exists"] is True
        assert models[0]["file_size"] == 50


class TestSyncModel:
    def test_sync_creates_file_and_sidecar(self, sample_model, host_path):
        result = sync_model_to_host(sample_model.id, "test-gpu")
        assert result["host"] == "test-gpu"
        assert result["size"] == 1000

        host_file = host_path / "checkpoints" / "sdxl.safetensors"
        assert host_file.exists()
        assert host_file.stat().st_size == 1000

        sidecar_file = host_path / "checkpoints" / f".sdxl.safetensors{SIDECAR_SUFFIX}"
        assert sidecar_file.exists()
        with open(sidecar_file) as f:
            data = json.load(f)
        assert data["library_model_id"] == sample_model.id
        assert data["current_filename"] == "sdxl.safetensors"

    def test_sync_records_history(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")
        updated = load_model(sample_model.id)
        assert any(h.action == "synced" for h in updated.history)

    def test_sync_missing_model(self, setup_library, host_path):
        with pytest.raises(ValueError, match="Invalid model ID format"):
            sync_model_to_host("nonexistent-id", "test-gpu")

    def test_sync_missing_host(self, sample_model):
        with pytest.raises(ValueError, match="not found"):
            sync_model_to_host(sample_model.id, "no-such-host")

    def test_sync_with_progress(self, sample_model, host_path):
        progress_calls = []
        def on_progress(copied, total):
            progress_calls.append((copied, total))

        sync_model_to_host(sample_model.id, "test-gpu", progress_callback=on_progress)
        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == progress_calls[-1][1]  # 100%


class TestSyncStatus:
    def test_not_synced(self, sample_model, host_path):
        status = get_sync_status("test-gpu")
        assert len(status) == 1
        assert status[0]["status"] == "not_synced"
        assert status[0]["model_id"] == sample_model.id

    def test_synced(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")
        status = get_sync_status("test-gpu")
        assert len(status) == 1
        assert status[0]["status"] == "synced"

    def test_rename_pending(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")
        rename_model(sample_model.id, "Renamed Model", rename_file=True)
        status = get_sync_status("test-gpu")
        matched = [s for s in status if s["model_id"] == sample_model.id]
        assert len(matched) == 1
        assert matched[0]["status"] == "rename_pending"

    def test_orphaned(self, setup_library, host_path):
        # Place a sidecar referencing a model that doesn't exist in library
        sidecar = {
            "library_model_id": "deleted-model-id",
            "library_name": "Ghost Model",
            "current_filename": "ghost.safetensors",
            "synced_at": "2025-01-01T00:00:00Z",
            "hash": None,
            "rename_history": [],
        }
        (host_path / "checkpoints").mkdir()
        (host_path / "checkpoints" / "ghost.safetensors").write_bytes(b"x")
        with open(host_path / "checkpoints" / f".ghost.safetensors{SIDECAR_SUFFIX}", "w") as f:
            json.dump(sidecar, f)

        status = get_sync_status("test-gpu")
        orphaned = [s for s in status if s["status"] == "orphaned"]
        assert len(orphaned) == 1
        assert orphaned[0]["model_name"] == "Ghost Model"


class TestRemoveFromHost:
    def test_remove_synced_model(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")

        host_file = host_path / "checkpoints" / "sdxl.safetensors"
        sidecar_file = host_path / "checkpoints" / f".sdxl.safetensors{SIDECAR_SUFFIX}"
        assert host_file.exists()
        assert sidecar_file.exists()

        result = remove_from_host(sample_model.id, "test-gpu")
        assert result["file_deleted"] is True
        assert result["sidecar_deleted"] is True
        assert not host_file.exists()
        assert not sidecar_file.exists()

    def test_remove_nonexistent(self, setup_library, host_path):
        with pytest.raises(ValueError, match="not found"):
            remove_from_host("no-such-model", "test-gpu")


class TestApplyRename:
    def test_apply_rename(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")
        rename_model(sample_model.id, "Better Name", rename_file=True)

        result = apply_rename_on_host(sample_model.id, "test-gpu")
        assert result["old_filename"] == "sdxl.safetensors"
        assert "better_name" in result["new_filename"].lower()

        updated_model = load_model(sample_model.id)
        new_host_file = host_path / "checkpoints" / updated_model.filename
        assert new_host_file.exists()

        new_sidecar = host_path / "checkpoints" / f".{updated_model.filename}{SIDECAR_SUFFIX}"
        assert new_sidecar.exists()
        with open(new_sidecar) as f:
            data = json.load(f)
        assert data["current_filename"] == updated_model.filename
        assert len(data["rename_history"]) == 1

    def test_apply_rename_missing_model(self, setup_library, host_path):
        with pytest.raises(ValueError, match="Invalid model ID format"):
            apply_rename_on_host("no-such-model", "test-gpu")
