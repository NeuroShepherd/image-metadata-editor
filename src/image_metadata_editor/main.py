"""FastAPI application serving the Image Metadata Editor web UI."""

import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter

from image_metadata_editor.metadata.models import ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata
from image_metadata_editor.metadata.writer import write_metadata

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
TEST_IMAGE = PROJECT_ROOT / "testing-image.jpeg"
UPLOADS_DIR = PROJECT_ROOT / "uploads"

app = FastAPI(title="Image Metadata Editor")


# ── Helpers ───────────────────────────────────────────────────────────────


def _resolve_image(file: str | None) -> Path:
    """Resolve ``file`` to an absolute path.

    If *file* is ``None`` or empty, falls back to ``testing-image.jpeg``
    at the project root.  Otherwise looks for the file inside the uploads
    directory.
    """
    if not file:
        return TEST_IMAGE
    candidate = UPLOADS_DIR / file
    if not candidate.exists():
        raise HTTPException(
            status_code=404, detail=f"Image file not found: {file}"
        )
    return candidate


# ── Image management ──────────────────────────────────────────────────────


@app.get("/api/images")
def list_images() -> list[str]:
    """Return the list of uploaded image filenames (sorted by name)."""
    if not UPLOADS_DIR.exists():
        return []
    files = sorted(
        p.name
        for p in UPLOADS_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower()
        in {
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".webp",
            ".heic",
            ".heif",
        }
    )
    return files


@app.post("/api/images/upload")
async def upload_images(files: list[UploadFile]) -> list[str]:
    """Upload one or more image files to the uploads directory.

    Returns the list of saved filenames.
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    for upload in files:
        if not upload.filename:
            continue
        dest = UPLOADS_DIR / upload.filename
        # Avoid overwrites by appending a number if needed
        counter = 1
        stem = dest.stem
        suffix = dest.suffix
        while dest.exists():
            dest = UPLOADS_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
        try:
            with dest.open("wb") as f:
                shutil.copyfileobj(upload.file, f)
            saved.append(dest.name)
        finally:
            upload.file.close()

    return saved


@app.get("/api/images/{filename:path}")
def serve_image(filename: str):
    """Serve an uploaded image file for preview."""
    if not filename:
        raise HTTPException(status_code=404, detail="No filename provided")
    # Prevent directory traversal
    safe_path = (UPLOADS_DIR / filename).resolve()
    if not str(safe_path).startswith(str(UPLOADS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(safe_path)


# ── Metadata endpoints ────────────────────────────────────────────────────


@app.get("/api/metadata")
def get_metadata(file: str | None = None) -> ImageMetadata:
    """Read metadata from an image file.

    Pass ``?file=filename`` to target an uploaded image; omitting the
    parameter reads the default ``testing-image.jpeg``.
    """
    image_path = _resolve_image(file)
    try:
        metadata = read_metadata(image_path)
        return metadata
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/metadata")
def update_metadata(
    metadata: ImageMetadata,
    file: str | None = None,
) -> ImageMetadata:
    """Write metadata to an image file.

    Pass ``?file=filename`` to target an uploaded image; omitting the
    parameter writes to ``testing-image.jpeg``.
    """
    image_path = _resolve_image(file)
    try:
        write_metadata(image_path, metadata)
        return read_metadata(image_path)
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
