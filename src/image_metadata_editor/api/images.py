"""Image endpoints — list images in a directory and serve image files."""

import platform
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/images", tags=["images"])

_SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg",".jpeg",".png",".tif",".tiff",".webp",".heic",".heif",
}


@router.post("/dialog")
def open_file_dialog(mode: str = Query("files", enum=["files", "folder"])):
    """Open a native OS file dialog and return absolute paths.

    macOS uses osascript (tkinter crashes on worker threads).
    Other platforms use tkinter.
    """
    if platform.system() == "Darwin":
        return _dialog_macos(mode)

    # Linux / Windows — use tkinter
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
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


def _dialog_macos(mode: str) -> list[str]:
    """Open a native macOS file dialog via osascript and return POSIX paths."""
    mode_flag = "folder" if mode == "folder" else "file"
    script = f'''
        tell application "Finder" to activate
        try
            set thePaths to choose {mode_flag} with prompt "Select {'a folder' if mode == 'folder' else 'images'}" {"with multiple selections allowed" if mode == "files" else ""}
            set resultPaths to {{}}
            repeat with f in thePaths
                set end of resultPaths to quoted form of POSIX path of f
            end repeat
            set AppleScript's text item delimiters to linefeed
            return resultPaths as text
        on error
            return "CANCELLED"
        end try
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    output = result.stdout.strip()
    if output == "CANCELLED":
        return []
    paths = []
    for line in output.splitlines():
        p = line.strip().strip("'")
        if p:
            paths.append(p)
    return paths


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
