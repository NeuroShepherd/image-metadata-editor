"""Metadata endpoints — read, update, and discover supported fields."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import TypeAdapter

from image_metadata_editor.metadata.models import ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata
from image_metadata_editor.metadata.writer import write_metadata

router = APIRouter(prefix="/api/metadata", tags=["metadata"])

_SUPPORTED_UPLOAD_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic", ".heif",
}


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
    """Write metadata to an image file (path-based, in-place)."""
    image_path = _resolve_path(file)
    try:
        write_metadata(image_path, metadata)
        return read_metadata(image_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload")
async def upload_metadata(file: UploadFile) -> ImageMetadata:
    """Upload an image file and return its metadata — no persistent copy made.

    The file is written to a temporary location, metadata is extracted,
    and the temp file is removed before responding.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{ext}'",
        )

    # Write to a temp file so existing path-based readers can work
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        metadata = read_metadata(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return metadata


@router.post("/apply")
async def apply_metadata(
    file: UploadFile,
    metadata: str = Query(..., description="JSON-serialised ImageMetadata"),
) -> Response:
    """Upload an image + new metadata and return the modified image bytes.

    The original file is written to a temp location, metadata changes
    are applied in-place, and the modified file is streamed back.
    The temp file is removed after the response.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{ext}'",
        )

    # Parse the metadata JSON
    try:
        import json
        parsed = ImageMetadata.model_validate_json(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {exc}")

    # Write upload to a temp file
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        write_metadata(tmp_path, parsed)
        # Read the modified file back
        modified_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    return Response(
        content=modified_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
        },
    )


@router.get("/supported-fields")
def get_supported_fields():
    """Return the JSON schema of the ImageMetadata model for the UI."""
    ta = TypeAdapter(ImageMetadata)
    return ta.json_schema()
