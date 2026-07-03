"""Image endpoints — list images in a directory and serve image files."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/images", tags=["images"])

_SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg",".jpeg",".png",".tif",".tiff",".webp",".heic",".heif",
}


@router.post("/dialog")
def open_file_dialog(mode: str = Query("files", enum=["files", "folder"])):
    """Open a native OS file/folder dialog via tkinter and return absolute paths.

    The dialog runs modally on the server — no browser file picker
    limitations, cross-platform, fully server-driven.
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # hide the empty tkinter window
    try:
        if mode == "folder":
            p = filedialog.askdirectory(title="Select a folder of images")
            paths = [p] if p else []
        else:
            paths = list(filedialog.askopenfilenames(
                title="Select images",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic *.heif")],
            ))
    finally:
        root.destroy()

    return [p for p in paths if p]


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("")
def list_images(dir: str | None = Query(None, description="Directory to scan for images")) -> list[str]:
    """List supported image files in a directory.

    Pass ``?dir=/path/to/dir`` to scan a specific directory.
    If omitted, returns an empty list (caller must provide a path).
    """
    if not dir:
        return []
    target = Path(dir).expanduser().resolve()
    if not target.is_dir():
        raise HTTPException(
            status_code=404, detail=f"Directory not found: {dir}"
        )
    files = sorted(
        str(p)
        for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    )
    return files


@router.get("/serve")
def serve_image(path: str = Query(..., description="Absolute path to the image file")):
    """Serve an image file for preview by its filesystem path."""
    if not path:
        raise HTTPException(status_code=400, detail="No path provided")
    safe_path = Path(path).expanduser().resolve()
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    # Basic sanity — refuse to serve non-image files
    if safe_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format: {safe_path.suffix}",
        )
    return FileResponse(safe_path)
