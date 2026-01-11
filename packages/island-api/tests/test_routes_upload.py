# SPDX-License-Identifier: MIT
"""Tests for package management routes (yank, collaborators).

Note: Upload endpoint tests have been removed as the upload functionality
has been removed in favor of the registry-only model. Use the /register
endpoint instead.
"""

from island_api.routes.upload import (
    CollaboratorRequest,
    YankRequest,
)


class TestManagementModels:
    """Tests for Pydantic models."""

    def test_yank_request_default(self):
        """Test YankRequest default values."""
        request = YankRequest()
        assert request.reason == ""

    def test_yank_request_with_reason(self):
        """Test YankRequest with reason."""
        request = YankRequest(reason="Security vulnerability")
        assert request.reason == "Security vulnerability"

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

    def test_collaborator_request_defaults(self):
        """Test CollaboratorRequest default values."""
        request = CollaboratorRequest(user_id="user123")
        assert request.user_id == "user123"
        assert request.publisher_type == "user"
        assert request.github_repository is None
        assert request.github_workflow is None
