"""Image endpoints — list images in a directory and serve image files."""

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/images", tags=["images"])

_SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg",".jpeg",".png",".tif",".tiff",".webp",".heic",".heif",
}

_SUPPORTED_UTIS = {
    "public.jpeg",
    "public.png",
    "public.tiff",
    "com.compuserve.gif",
    "com.microsoft.bmp",
}

# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/dialog")
def open_file_dialog(mode: str = Query("files", enum=["files", "folder"])):
    """Open a native OS file/folder dialog and return absolute paths.

    The server opens the dialog on the user's desktop — no browser
    file picker limitations, fully server-driven.  On macOS this uses
    osascript/AppleScript.
    """
    import platform

    system = platform.system()
    paths: list[str] = []

    if system == "Darwin":
        uti_list = ", ".join(f'"{u}"' for u in sorted(_SUPPORTED_UTIS))
        if mode == "folder":
            script = f'''
                set theFolder to choose folder with prompt "Select a folder of images"
                return POSIX path of theFolder
            '''
        else:
            script = f'''
                set theFiles to choose file with prompt "Select images" of type {{{uti_list}}} with multiple selections allowed
                set paths to {{}}
                repeat with f in theFiles
                    set end of paths to POSIX path of f
                end repeat
                return paths
            '''
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            if result.stderr and "User canceled" in result.stderr:
                return []  # user cancelled
            raise HTTPException(status_code=500, detail=f"File dialog failed: {result.stderr.strip()}")
        raw = result.stdout.strip()
        # osascript returns comma-separated list, possibly with trailing comma
        paths = [p.strip() for p in raw.rstrip(",").split(", ") if p.strip()]
    else:
        # Fallback for other platforms: try tkinter
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            if mode == "folder":
                p = filedialog.askdirectory(title="Select a folder of images")
                if p:
                    paths = [p]
            else:
                paths = list(filedialog.askopenfilenames(
                    title="Select images",
                    filetypes=[("Images", "*.jpg *.jpeg *.png *.tif *.tiff *.webp *.heic *.heif")],
                ))
            root.destroy()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"File dialog failed: {exc}")

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
