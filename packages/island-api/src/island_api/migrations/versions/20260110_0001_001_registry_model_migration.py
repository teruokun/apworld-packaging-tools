# SPDX-License-Identifier: MIT
"""Registry model migration - external URLs instead of file storage.

This migration converts the Distribution model from a file storage model
to a registry model where only metadata and external URLs are stored.

Changes:
- Remove storage_path column (no longer storing files)
- Remove download_count column (can't track external downloads)
- Remove uploaded_at column (replaced by registered_at)
- Add external_url column (URL to download from)
- Add registered_at column (when the distribution was registered)
- Add last_verified_at column (URL health tracking)
- Add url_status column (active/unavailable)

Revision ID: 001
Revises: None (initial migration for registry model)
Create Date: 2026-01-10

Requirements: 1.1, 1.2, 1.3, 1.4, 6.5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema to registry model.

    Converts Distribution table from file storage to external URL references.
    """
    # Add new columns for registry model
    op.add_column(
        "distributions",
        sa.Column("external_url", sa.String(2000), nullable=True),
    )
    op.add_column(
        "distributions",
        sa.Column("registered_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "distributions",
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "distributions",
        sa.Column("url_status", sa.String(20), nullable=True, server_default="active"),
    )

    # Migrate existing data: convert storage_path to external_url placeholder
    # In production, this would need to be updated with actual external URLs
    op.execute(
        """
        UPDATE distributions 
        SET external_url = 'https://example.com/migration-required/' || storage_path,
            registered_at = uploaded_at,
            url_status = 'active'
        WHERE external_url IS NULL
        """
    )

    # Make external_url non-nullable after data migration
    op.alter_column(
        "distributions",
        "external_url",
        existing_type=sa.String(2000),
        nullable=False,
    )

    # Set default for registered_at
    op.execute(
        """
        UPDATE distributions 
        SET registered_at = CURRENT_TIMESTAMP
        WHERE registered_at IS NULL
        """
    )
    op.alter_column(
        "distributions",
        "registered_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )

    # Set default for url_status
    op.execute(
        """
        UPDATE distributions 
        SET url_status = 'active'
        WHERE url_status IS NULL
        """
    )
    op.alter_column(
        "distributions",
        "url_status",
        existing_type=sa.String(20),
        nullable=False,
        server_default="active",
    )

    # Remove old columns (file storage model)
    op.drop_column("distributions", "storage_path")
    op.drop_column("distributions", "uploaded_at")
    op.drop_column("distributions", "download_count")


def downgrade() -> None:
    """Downgrade database schema back to file storage model.

    WARNING: This will lose external_url data and URL health tracking.
    """
    # Add back old columns
    op.add_column(
        "distributions",
        sa.Column("storage_path", sa.String(500), nullable=True),
    )
    op.add_column(
        "distributions",
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "distributions",
        sa.Column("download_count", sa.Integer(), nullable=True, server_default="0"),
    )

    # Migrate data back: extract path from external_url
    op.execute(
        """
        UPDATE distributions 
        SET storage_path = REPLACE(external_url, 'https://example.com/migration-required/', ''),
            uploaded_at = registered_at,
            download_count = 0
        WHERE storage_path IS NULL
        """
    )

    # Make columns non-nullable
    op.alter_column(
        "distributions",
        "storage_path",
        existing_type=sa.String(500),
        nullable=False,
    )
    op.alter_column(
        "distributions",
        "uploaded_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )
    op.alter_column(
        "distributions",
        "download_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )

    # Remove new columns
    op.drop_column("distributions", "external_url")
    op.drop_column("distributions", "registered_at")
    op.drop_column("distributions", "last_verified_at")
    op.drop_column("distributions", "url_status")
