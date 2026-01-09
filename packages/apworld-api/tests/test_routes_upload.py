# SPDX-License-Identifier: MIT
"""Tests for upload routes."""

import io
import json
import zipfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apworld_api.auth.tokens import AuthenticatedUser
from apworld_api.routes.upload import (
    CollaboratorRequest,
    UploadResponse,
    YankRequest,
    compute_sha256,
    extract_manifest_from_apworld,
    router,
    validate_manifest,
    validate_semver,
)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_compute_sha256(self):
        """Test SHA256 computation."""
        data = b"test data"
        result = compute_sha256(data)
        assert len(result) == 64
        assert result == "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"

    def test_validate_semver_valid(self):
        """Test valid semver strings."""
        assert validate_semver("1.0.0") is True
        assert validate_semver("0.0.1") is True
        assert validate_semver("10.20.30") is True
        assert validate_semver("1.0.0-alpha") is True
        assert validate_semver("1.0.0-alpha.1") is True
        assert validate_semver("1.0.0-beta.2") is True
        assert validate_semver("1.0.0-rc.1") is True
        assert validate_semver("1.0.0+build.123") is True
        assert validate_semver("1.0.0-alpha+build") is True

    def test_validate_semver_invalid(self):
        """Test invalid semver strings."""
        assert validate_semver("1.0") is False
        assert validate_semver("1") is False
        assert validate_semver("v1.0.0") is False
        assert validate_semver("1.0.0.0") is False
        assert validate_semver("") is False
        assert validate_semver("abc") is False


class TestManifestExtraction:
    """Tests for manifest extraction from .apworld files."""

    def create_apworld(self, manifest: dict, filename: str = "test/archipelago.json") -> bytes:
        """Create a mock .apworld file with the given manifest."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename, json.dumps(manifest))
        return buffer.getvalue()

    def test_extract_manifest_success(self):
        """Test successful manifest extraction."""
        manifest = {
            "game": "Test Game",
            "version": 7,
            "compatible_version": 5,
            "world_version": "1.0.0",
        }
        apworld = self.create_apworld(manifest)
        result = extract_manifest_from_apworld(apworld)
        assert result == manifest

    def test_extract_manifest_root_level(self):
        """Test extraction prefers root-level manifest."""
        manifest = {"game": "Root", "version": 7, "compatible_version": 5}
        nested = {"game": "Nested", "version": 7, "compatible_version": 5}

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("archipelago.json", json.dumps(manifest))
            zf.writestr("subdir/archipelago.json", json.dumps(nested))

        result = extract_manifest_from_apworld(buffer.getvalue())
        assert result["game"] == "Root"

    def test_extract_manifest_no_manifest(self):
        """Test error when no manifest found."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("other.txt", "content")

        with pytest.raises(Exception) as exc_info:
            extract_manifest_from_apworld(buffer.getvalue())
        assert "No archipelago.json found" in str(exc_info.value)

    def test_extract_manifest_invalid_zip(self):
        """Test error for invalid zip file."""
        with pytest.raises(Exception) as exc_info:
            extract_manifest_from_apworld(b"not a zip file")
        assert "Invalid .apworld file" in str(exc_info.value)

    def test_extract_manifest_invalid_json(self):
        """Test error for invalid JSON in manifest."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("archipelago.json", "not valid json")

        with pytest.raises(Exception) as exc_info:
            extract_manifest_from_apworld(buffer.getvalue())
        assert "Invalid JSON" in str(exc_info.value)


class TestManifestValidation:
    """Tests for manifest validation."""

    def test_validate_manifest_valid(self):
        """Test valid manifest passes validation."""
        manifest = {
            "game": "Test Game",
            "version": 7,
            "compatible_version": 5,
            "world_version": "1.0.0",
        }
        errors = validate_manifest(manifest)
        assert len(errors) == 0

    def test_validate_manifest_missing_required(self):
        """Test missing required fields."""
        manifest = {"game": "Test"}
        errors = validate_manifest(manifest)
        assert len(errors) == 2
        error_fields = [e.field for e in errors]
        assert "version" in error_fields
        assert "compatible_version" in error_fields

    def test_validate_manifest_invalid_version_type(self):
        """Test version must be integer."""
        manifest = {
            "game": "Test",
            "version": "7",  # Should be int
            "compatible_version": 5,
        }
        errors = validate_manifest(manifest)
        assert any(e.field == "version" for e in errors)

    def test_validate_manifest_invalid_world_version(self):
        """Test world_version must be semver."""
        manifest = {
            "game": "Test",
            "version": 7,
            "compatible_version": 5,
            "world_version": "invalid",
        }
        errors = validate_manifest(manifest)
        assert any(e.field == "world_version" for e in errors)


class TestUploadModels:
    """Tests for Pydantic models."""

    def test_upload_response(self):
        """Test UploadResponse model."""
        response = UploadResponse(
            package="test",
            version="1.0.0",
            filename="test-1.0.0-py3-none-any.apworld",
            sha256="abc123",
            message="Success",
        )
        assert response.package == "test"
        assert response.version == "1.0.0"

    def test_yank_request_default(self):
        """Test YankRequest default values."""
        request = YankRequest()
        assert request.reason == ""

    def test_collaborator_request(self):
        """Test CollaboratorRequest model."""
        request = CollaboratorRequest(
            user_id="user123",
            publisher_type="trusted_publisher",
            github_repository="owner/repo",
        )
        assert request.user_id == "user123"
        assert request.publisher_type == "trusted_publisher"
        assert request.github_repository == "owner/repo"
