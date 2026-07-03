# Image Metadata Editor

A local web app for viewing and editing image metadata — title, description,
keywords, date taken, and GPS coordinates — with a visual map and bulk editing
support.

## Features

- **Browse files or folders** via native OS dialogs — no typing paths
- **Edit metadata** in-place via a web form (title, description, keywords, date, GPS)
- **Interactive map** for GPS coordinates (click to set, drag to adjust)
- **Bulk edit mode** — apply changes to all loaded images at once
- **Preserves filesystem timestamps** — server writes directly via `writer.py`
- **Works in any browser** — Safari, Firefox, Chrome, Edge

## Supported Formats

| Format | Read | Write |
| ------ | ---- | ----- |
| JPEG   | ✅   | ✅    |
| TIFF   | ✅   | ✅    |
| PNG    | ✅   | ✅    |
| WebP   | ✅   | ✅    |
| HEIC   | ✅   | ✅    |

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repo
git clone https://github.com/NeuroShepherd/image-metadata-editor
cd image-metadata-editor

# Install dependencies
uv sync

# Start the server
uv run uvicorn src.image_metadata_editor.main:app --reload --port 8000

# Open in browser
open http://127.0.0.1:8000
```

## Usage

1. Click **Browse Files…** to pick individual images, or **📁 Folder…** to load a directory
2. Navigate between images with the ◀ ▶ arrows
3. Edit title, description, keywords, date, and GPS coordinates
4. Click the map to set GPS location, or type coordinates manually
5. Click **Save Changes** to write metadata directly to the files
6. Use **Bulk Edit** to apply metadata to all loaded images at once (title excluded)

## Architecture

- **Frontend** — Single-page HTML/CSS/JS with Leaflet for the map
- **Backend** — FastAPI server handling all file I/O
- **Metadata** — Custom `reader.py` / `writer.py` using Pillow + piexif
- **File dialogs** — Native OS pickers via osascript (macOS) or tkinter (Linux/Windows)

## Lessons Learned

- The browser-based approach had significant growing pains:
  - Firefox and Safari don't support the File System Access API — Chromium browsers was needed for in-place writes via `createWritable()` (which I wound up removing anyway)
  - `createWritable()` kept updating the file's Created date — technically a new file was being written each save
  - Solved both by switching to **server-side native file dialogs** (osascript on macOS, tkinter fallback elsewhere) and letting the server handle all I/O via `reader.py` / `writer.py` — timestamps preserved, any browser works
  - Using FastAPI was arguably overkill for a local-only tool, but good practice regardless
  - Something more direct like tkinter would have been easier and more efficient overall, but I got to learn some new skills
