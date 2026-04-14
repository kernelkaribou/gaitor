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

    def test_sync_updates_timestamp(self, sample_model, host_path):
        sync_model_to_host(sample_model.id, "test-gpu")
        updated = load_model(sample_model.id)
        assert updated.updated_at is not None

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

    def test_apply_rename_missing_model(self, setup_library, host_path):
        with pytest.raises(ValueError, match="Invalid model ID format"):
            apply_rename_on_host("no-such-model", "test-gpu")


class TestScanHost:
    def test_scan_empty_host(self, setup_library, host_path):
        from backend.services.sync import scan_host
        result = scan_host("test-gpu")
        assert result["count"] == 0
        assert result["already_managed"] == 0
        assert result["unmanaged"] == []

    def test_scan_finds_unmanaged_model(self, setup_library, host_path):
        from backend.services.sync import scan_host
        # Place a model file on the host without a sidecar
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        (model_dir / "test_model.safetensors").write_bytes(b"data" * 50)

        result = scan_host("test-gpu")
        assert result["count"] == 1
        assert result["already_managed"] == 0
        item = result["unmanaged"][0]
        assert item["filename"] == "test_model.safetensors"
        assert item["guessed_category"] == "checkpoints"
        assert item["match"] is None

    def test_scan_skips_managed_files(self, sample_model, host_path):
        from backend.services.sync import scan_host
        # Sync a model to create a sidecar
        sync_model_to_host(sample_model.id, "test-gpu")

        result = scan_host("test-gpu")
        assert result["count"] == 0
        assert result["already_managed"] == 1

    def test_scan_matches_library_model(self, sample_model, host_path):
        from backend.services.sync import scan_host
        # Place an identical file on the host (same name and size)
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        (model_dir / "sdxl.safetensors").write_bytes(b"model-data" * 100)

        result = scan_host("test-gpu")
        assert result["count"] == 1
        item = result["unmanaged"][0]
        assert item["match"] is not None
        assert item["match"]["library_model_id"] == sample_model.id
        assert item["match"]["match_type"] == "filename_and_size"
        assert item["match"]["confidence"] == "high"

    def test_scan_filename_only_match(self, sample_model, host_path):
        from backend.services.sync import scan_host
        # Same filename but different size
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        (model_dir / "sdxl.safetensors").write_bytes(b"different-data")

        result = scan_host("test-gpu")
        assert result["count"] == 1
        item = result["unmanaged"][0]
        assert item["match"] is not None
        assert item["match"]["match_type"] == "filename"
        assert item["match"]["confidence"] == "medium"

    def test_scan_skips_non_model_files(self, setup_library, host_path):
        from backend.services.sync import scan_host
        (host_path / "readme.txt").write_text("not a model")
        (host_path / "config.yaml").write_text("config: true")

        result = scan_host("test-gpu")
        assert result["count"] == 0


class TestLinkHostModel:
    def test_link_matching_file(self, sample_model, host_path):
        from backend.services.sync import link_host_model
        from backend.services.metadata import load_model as _load
        # Place identical file on host
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        host_file = model_dir / "sdxl.safetensors"
        host_file.write_bytes(b"model-data" * 100)

        result = link_host_model("test-gpu", "checkpoints/sdxl.safetensors", sample_model.id)
        assert result["hash_verified"] is True
        assert result["model_id"] == sample_model.id

        # Check sidecar was created
        sidecar = model_dir / f".sdxl.safetensors{SIDECAR_SUFFIX}"
        assert sidecar.exists()
        with open(sidecar) as f:
            data = json.load(f)
        assert data["library_model_id"] == sample_model.id

        # Check library model was updated
        updated = _load(sample_model.id)
        assert updated.updated_at is not None

    def test_link_hash_mismatch(self, sample_model, host_path):
        from backend.services.sync import link_host_model
        # Place file with different content
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        (model_dir / "sdxl.safetensors").write_bytes(b"totally-different")

        with pytest.raises(ValueError, match="Hash mismatch"):
            link_host_model("test-gpu", "checkpoints/sdxl.safetensors", sample_model.id)

    def test_link_file_not_found(self, sample_model, host_path):
        from backend.services.sync import link_host_model
        with pytest.raises(FileNotFoundError):
            link_host_model("test-gpu", "checkpoints/nonexistent.safetensors", sample_model.id)


class TestImportFromHost:
    def test_import_model(self, setup_library, host_path):
        from backend.services.sync import import_from_host
        from backend.services.metadata import load_model as _load
        # Place a model on the host
        model_dir = host_path / "loras"
        model_dir.mkdir()
        host_file = model_dir / "my_lora.safetensors"
        host_file.write_bytes(b"lora-data" * 50)

        result = import_from_host(
            "test-gpu", "loras/my_lora.safetensors",
            name="My LoRA", category="loras", description="A test lora",
        )
        assert result["library_path"] == "loras/my_lora.safetensors"
        assert result["model_id"] is not None

        # Check file was copied to library
        lib_file = config.LIBRARY_PATH / "loras" / "my_lora.safetensors"
        assert lib_file.exists()
        assert lib_file.read_bytes() == b"lora-data" * 50

        # Check library metadata was created
        model = _load(result["model_id"])
        assert model.name == "My LoRA"
        assert model.category == "loras"
        assert model.source.provider == "host_import"

        # Check sidecar was created on host
        sidecar = model_dir / f".my_lora.safetensors{SIDECAR_SUFFIX}"
        assert sidecar.exists()

    def test_import_duplicate_fails(self, setup_library, host_path):
        from backend.services.sync import import_from_host
        # Create file in both places
        model_dir = host_path / "checkpoints"
        model_dir.mkdir()
        (model_dir / "dup.safetensors").write_bytes(b"data")
        lib_dir = config.LIBRARY_PATH / "checkpoints"
        lib_dir.mkdir(parents=True, exist_ok=True)
        (lib_dir / "dup.safetensors").write_bytes(b"other-data")

        with pytest.raises(ValueError, match="already exists"):
            import_from_host(
                "test-gpu", "checkpoints/dup.safetensors",
                name="Dup", category="checkpoints",
            )

    def test_import_file_not_found(self, setup_library, host_path):
        from backend.services.sync import import_from_host
        with pytest.raises(FileNotFoundError):
            import_from_host(
                "test-gpu", "loras/nonexistent.safetensors",
                name="Missing", category="loras",
            )
