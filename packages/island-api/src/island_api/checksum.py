# SPDX-License-Identifier: MIT
"""Checksum utilities for package integrity verification."""

import hashlib
from pathlib import Path
from typing import BinaryIO


def compute_sha256(data: bytes) -> str:
    """Compute SHA256 hash of bytes data.

    Args:
        data: Bytes to hash

    Returns:
        Lowercase hex-encoded SHA256 hash
    """
    return hashlib.sha256(data).hexdigest()


def compute_sha256_file(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Lowercase hex-encoded SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_sha256_stream(stream: BinaryIO) -> str:
    """Compute SHA256 hash from a binary stream.

    Args:
        stream: Binary file-like object

    Returns:
        Lowercase hex-encoded SHA256 hash
    """
    sha256 = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8192), b""):
        sha256.update(chunk)
    return sha256.hexdigest()


def verify_checksum(data: bytes, expected_hash: str) -> bool:
    """Verify that data matches expected SHA256 hash.

    Args:
        data: Bytes to verify
        expected_hash: Expected SHA256 hash (hex-encoded)

    Returns:
        True if hash matches, False otherwise
    """
    actual_hash = compute_sha256(data)
    return actual_hash.lower() == expected_hash.lower()


def verify_checksum_file(file_path: Path, expected_hash: str) -> bool:
    """Verify that a file matches expected SHA256 hash.

    Args:
        file_path: Path to the file
        expected_hash: Expected SHA256 hash (hex-encoded)

    Returns:
        True if hash matches, False otherwise
    """
    actual_hash = compute_sha256_file(file_path)
    return actual_hash.lower() == expected_hash.lower()


class ChecksumMismatchError(Exception):
    """Raised when checksum verification fails."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Checksum mismatch: expected {expected}, got {actual}")
