"""Tests for security hardening - path traversal, input validation, etc."""
import pytest
from pathlib import Path

from backend.utils import safe_resolve, validate_model_id, validate_dest_id, sanitize_filename
from backend import config


class TestSafeResolve:
    def test_valid_path(self, tmp_path):
        (tmp_path / "sub" / "file.txt").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "sub" / "file.txt").touch()
        result = safe_resolve(tmp_path, "sub/file.txt")
        assert result == (tmp_path / "sub" / "file.txt").resolve()

    def test_rejects_parent_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="illegal"):
            safe_resolve(tmp_path, "../../etc/shadow")

    def test_rejects_absolute_path_breakout(self, tmp_path):
        with pytest.raises(ValueError, match="illegal|escapes"):
            safe_resolve(tmp_path, "../outside")

    def test_rejects_dot_dot_in_middle(self, tmp_path):
        with pytest.raises(ValueError, match="illegal"):
            safe_resolve(tmp_path, "sub/../../etc/passwd")

    def test_rejects_empty(self, tmp_path):
        with pytest.raises(ValueError, match="illegal"):
            safe_resolve(tmp_path, "")


class TestValidateModelId:
    def test_valid_uuid(self):
        assert validate_model_id("550e8400-e29b-41d4-a716-446655440000")

    def test_rejects_non_uuid(self):
        with pytest.raises(ValueError, match="Invalid model ID"):
            validate_model_id("not-a-uuid")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid model ID"):
            validate_model_id("../../etc/passwd")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid model ID"):
            validate_model_id("")


class TestValidateDestId:
    def test_valid_dest(self):
        assert validate_dest_id("my-gpu-1")

    def test_valid_with_dots(self):
        assert validate_dest_id("server.local")

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match="Invalid destination ID"):
            validate_dest_id("../library")

    def test_rejects_slashes(self):
        with pytest.raises(ValueError, match="Invalid destination ID"):
            validate_dest_id("path/to/dir")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid destination ID"):
            validate_dest_id("")


class TestSanitizeFilename:
    def test_basic_name(self):
        assert sanitize_filename("My Model", ".safetensors") == "My_Model.safetensors"

    def test_strips_dangerous_chars(self):
        result = sanitize_filename("../../etc/passwd", ".txt")
        assert "/" not in result
        assert ".." not in result

    def test_rejects_empty_result(self):
        with pytest.raises(ValueError, match="empty"):
            sanitize_filename("!!!@@@", ".txt")

    def test_collapses_whitespace(self):
        assert sanitize_filename("a   b  c", "") == "a_b_c"
