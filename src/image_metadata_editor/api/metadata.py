"""Metadata endpoints — read, update, and discover supported fields."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import TypeAdapter

from image_metadata_editor.metadata.models import ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata
from image_metadata_editor.metadata.writer import write_metadata

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


# ── Helpers ───────────────────────────────────────────────────────────────


def _resolve_path(file: str) -> Path:
    """Resolve *file* to an absolute path."""
    candidate = Path(file).expanduser().resolve()
    if not candidate.exists():
        raise HTTPException(
            status_code=404, detail=f"Image file not found: {file}"
        )
    return candidate


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=ImageMetadata)
def get_metadata(
    file: str = Query(..., description="Path to the image file"),
) -> ImageMetadata:
    """Read metadata from an image file.

    Pass ``?file=/path/to/image.jpg`` to target a specific file.
    """
    image_path = _resolve_path(file)
    try:
        return read_metadata(image_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("", response_model=ImageMetadata)
def update_metadata(
    metadata: ImageMetadata,
    file: str = Query(..., description="Path to the image file"),
) -> ImageMetadata:
    """Write metadata to an image file.

    Pass ``?file=/path/to/image.jpg`` to target a specific file.
    """
    image_path = _resolve_path(file)
    try:
        write_metadata(image_path, metadata)
        return read_metadata(image_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/supported-fields")
def get_supported_fields():
    """Return the JSON schema of the ImageMetadata model for the UI."""
    ta = TypeAdapter(ImageMetadata)
    return ta.json_schema()
