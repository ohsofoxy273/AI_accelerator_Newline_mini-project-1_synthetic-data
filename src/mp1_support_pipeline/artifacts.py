"""Helpers for semantic, timestamped pipeline artifact names."""

from __future__ import annotations

from datetime import datetime


def default_run_id() -> str:
    """Return a timestamp run identifier for audit-safe artifact names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def artifact_slug(value: str) -> str:
    """Normalize a short artifact label for filenames."""
    slug = (
        value.strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
        .replace("/", "-")
    )
    return slug or "unknown"


def artifact_filename(
    *,
    artifact_name: str,
    artifact_variant: str,
    run_id: str,
    extension: str,
) -> str:
    """Build a semantic, timestamped artifact filename."""
    return f"{artifact_name}_{artifact_variant}_{run_id}.{extension}"
