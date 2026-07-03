"""FastAPI application serving the Image Metadata Editor web UI."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter

from image_metadata_editor.metadata.models import ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata
from image_metadata_editor.metadata.writer import write_metadata

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
TEST_IMAGE = PROJECT_ROOT / "testing-image.jpeg"

app = FastAPI(title="Image Metadata Editor")


# ── API endpoints ─────────────────────────────────────────────────────────


@app.get("/api/metadata")
def get_metadata() -> ImageMetadata:
    """Read metadata from the testing image file."""
    try:
        metadata = read_metadata(TEST_IMAGE)
        return metadata
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/metadata")
def update_metadata(metadata: ImageMetadata) -> ImageMetadata:
    """Write metadata to the testing image file and return the updated result."""
    try:
        write_metadata(TEST_IMAGE, metadata)
        return read_metadata(TEST_IMAGE)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/metadata/supported-fields")
def get_supported_fields():
    """Return the JSON schema of the ImageMetadata model for the UI."""
    ta = TypeAdapter(ImageMetadata)
    return ta.json_schema()


# ── Static file serving ───────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=str(HERE / "ui"), html=True), name="ui")
