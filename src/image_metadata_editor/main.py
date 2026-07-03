"""FastAPI application serving the Image Metadata Editor web UI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from image_metadata_editor.api.images import router as images_router
from image_metadata_editor.api.metadata import router as metadata_router

HERE = Path(__file__).resolve().parent

app = FastAPI(title="Image Metadata Editor")

# ── API routers ───────────────────────────────────────────────────────────

app.include_router(images_router)
app.include_router(metadata_router)

# ── Static file serving ───────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=str(HERE / "ui"), html=True), name="ui")
