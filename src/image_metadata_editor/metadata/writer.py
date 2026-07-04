from __future__ import annotations

from datetime import datetime
from pathlib import Path

import piexif
from PIL import Image

from image_metadata_editor.metadata.models import GpsInfo, ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata

__all__ = [
    "write_metadata",
]

# ── Tag ID constants ──────────────────────────────────────────────────────
# 0th IFD (image-level tags)
_TAG_ID_IMAGE_DESCRIPTION = 0x010E
_TAG_ID_XP_KEYWORDS = 0x9C9E

# Exif IFD (photo-level tags)
_TAG_ID_DATE_TIME_ORIGINAL = 0x9003

# GPS IFD
_GPS_LATITUDE_REF = 0x0001
_GPS_LATITUDE = 0x0002
_GPS_LONGITUDE_REF = 0x0003
_GPS_LONGITUDE = 0x0004
_GPS_ALTITUDE_REF = 0x0005
_GPS_ALTITUDE = 0x0006

# ── Helpers: Python → EXIF value conversion ──────────────────────────────


def _decimal_to_dms(value: float) -> tuple[tuple[int, int], ...]:
    """Convert decimal degrees to an EXIF DMS rational tuple.

    EXIF always stores DMS components as **positive** values; the sign is
    conveyed separately via the latitude/longitude ref tag (N/S, E/W).
    We therefore take ``abs(value)`` here so that negative coordinates
    (e.g. -33.8688) produce ``((33, 1), (52, 1), (756, 100))`` rather than
    negative degree components, which are invalid in EXIF.

    Returns ``((D, 1), (M, 1), (S, 100))`` so that seconds are stored
    with two-decimal-place precision.
    """
    value = abs(value)
    degrees = int(value)
    minutes = int((value - degrees) * 60)
    seconds = (value - degrees - minutes / 60) * 3600
    seconds_num = int(round(seconds * 100))
    seconds_den = 100
    return ((degrees, 1), (minutes, 1), (seconds_num, seconds_den))


def _float_to_rational_100(value: float) -> tuple[int, int]:
    """Convert a float to a ``(numerator, denominator)`` rational (×100)."""
    return (int(round(value * 100)), 100)


def _keywords_to_xp_bytes(keywords: list[str]) -> bytes:
    """Encode a keyword list to the XPKeywords UTF-16-LE format."""
    return ";".join(keywords).encode("utf-16-le") + b"\x00\x00"


# ── Change detection ──────────────────────────────────────────────────────


def _build_delta(
    old: ImageMetadata,
    new: ImageMetadata,
) -> dict[str, dict[int, object]]:
    """Compare two metadata objects and return only the changed EXIF tags.

    Only fields that were **explicitly set** on *new* are considered
    (i.e. fields that appear in ``new.model_fields_set``).  This lets the
    caller construct a sparse ``ImageMetadata`` with just the fields they
    want to update; all other fields are left untouched on disk.

    Returns a dict keyed by piexif IFD name (``"0th"``, ``"Exif"``, ``"GPS"``).
    Tags whose value should be removed are mapped to ``None``.
    """
    delta: dict[str, dict[int, object]] = {}
    explicit = new.model_fields_set

    # ── 0th IFD ────────────────────────────────────────────────────────
    zeroth: dict[int, object] = {}

    if "title" in explicit and old.title != new.title:
        zeroth[_TAG_ID_IMAGE_DESCRIPTION] = new.title  # None → remove

    if "keywords" in explicit and old.keywords != new.keywords:
        if new.keywords is not None:
            zeroth[_TAG_ID_XP_KEYWORDS] = _keywords_to_xp_bytes(new.keywords)
        else:
            zeroth[_TAG_ID_XP_KEYWORDS] = None  # remove

    if zeroth:
        delta["0th"] = zeroth

    # ── Exif IFD ────────────────────────────────────────────────────────
    exif: dict[int, object] = {}

    if "date_taken" in explicit and old.date_taken != new.date_taken:
        if new.date_taken is not None:
            exif[_TAG_ID_DATE_TIME_ORIGINAL] = new.date_taken.strftime(
                "%Y:%m:%d %H:%M:%S"
            )
        else:
            exif[_TAG_ID_DATE_TIME_ORIGINAL] = None  # remove

    if exif:
        delta["Exif"] = exif

    # ── GPS IFD ────────────────────────────────────────────────────────
    if "gps" in explicit and old.gps != new.gps:
        gps_delta = _build_gps_delta(new.gps)
        if gps_delta is not None:
            delta["GPS"] = gps_delta

    return delta


def _build_gps_delta(gps_info: GpsInfo | None) -> dict[int, object] | None:
    """Build GPS IFD changes from a (possibly ``None``) GpsInfo."""
    gps: dict[int, object] = {}

    if gps_info is None:
        # The caller cleared the entire GPS block — remove all GPS tags.
        for tag_id in range(0x0001, 0x0007):
            gps[tag_id] = None
        return gps

    if gps_info.latitude_ref is not None:
        gps[_GPS_LATITUDE_REF] = gps_info.latitude_ref
    if gps_info.latitude is not None:
        gps[_GPS_LATITUDE] = _decimal_to_dms(gps_info.latitude)
    if gps_info.longitude_ref is not None:
        gps[_GPS_LONGITUDE_REF] = gps_info.longitude_ref
    if gps_info.longitude is not None:
        gps[_GPS_LONGITUDE] = _decimal_to_dms(gps_info.longitude)
    if gps_info.altitude_ref is not None:
        gps[_GPS_ALTITUDE_REF] = bytes([gps_info.altitude_ref])
    if gps_info.altitude is not None:
        gps[_GPS_ALTITUDE] = _float_to_rational_100(gps_info.altitude)

    return gps or None


# ── Format-specific EXIF I/O ─────────────────────────────────────────────

_SUPPORTED_WRITE_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".png",
    ".webp",
}


def _empty_exif_dict() -> dict:
    """Return a blank piexif-style EXIF dict."""
    return {
        "0th": {},
        "Exif": {},
        "GPS": {},
        "Interop": {},
        "1st": {},
        "thumbnail": None,
    }


def _load_exif_dict(path: Path) -> dict:
    """Load the existing EXIF dict from *path*.

    Works for JPEG, TIFF, PNG, and WebP.  Returns an empty dict when no
    EXIF is present.
    """
    ext = path.suffix.lower()

    # PNG stores EXIF as a raw chunk – piexif.load(path) won't work.
    if ext == ".png":
        with Image.open(path) as img:
            raw = img.info.get("exif")
            if raw:
                return piexif.load(raw)
        return _empty_exif_dict()

    # JPEG, TIFF, WebP – piexif can read directly from the file.
    try:
        return piexif.load(str(path))
    except Exception:
        return _empty_exif_dict()


def _write_exif_dict(path: Path, exif_dict: dict) -> None:
    """Write *exif_dict* back to the image at *path*.

    JPEG uses ``piexif.insert()`` (only the EXIF segment is rewritten;
    pixel data is untouched).  All other formats use Pillow's ``save()``
    with the ``exif`` parameter, which re-encodes the image.
    """
    # piexif.dump may fail on MakerNote tags with non-standard types.
    # Retry, stripping only the offending tag.
    import re
    while True:
        try:
            exif_bytes = piexif.dump(exif_dict)
            break
        except ValueError as exc:
            m = re.search(r"(\d+) in (\w+) IFD", str(exc))
            if m:
                tag_id = int(m.group(1))
                ifd = m.group(2)
                if ifd in exif_dict:
                    exif_dict[ifd].pop(tag_id, None)
            else:
                raise

    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        piexif.insert(exif_bytes, str(path))
    else:
        with Image.open(path) as img:
            img.save(path, exif=exif_bytes)


# ── Main entry point ──────────────────────────────────────────────────────


def write_metadata(file_path: str | Path, metadata: ImageMetadata) -> bool:
    """Write changed metadata fields to an image file **in-place**.

    Only fields that differ from the file's current metadata are touched.
    Fields set to ``None`` that were previously populated are removed from
    the EXIF block.

    Supported write formats: JPEG, TIFF, PNG, WebP.

    Args:
        file_path: Path to the image file.
        metadata:  The new metadata to apply.  Fields that are ``None`` and
            match the file's current value are left untouched.

    Returns:
        ``True`` if at least one field was written, ``False`` if the
        metadata was already up to date.

    Raises:
        FileNotFoundError: The given path does not exist.
        ValueError: The file format is unsupported, or writing failed.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    ext = path.suffix.lower()
    if ext not in _SUPPORTED_WRITE_EXTENSIONS:
        raise ValueError(
            f"Writing metadata is not supported for '{ext}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_WRITE_EXTENSIONS))}"
        )

    # 1. Read current metadata for comparison
    old_metadata = read_metadata(path)

    # 2. Compute the delta (only changed fields)
    delta = _build_delta(old_metadata, metadata)
    if not delta:
        return False  # nothing to do

    # 3. Load existing EXIF, apply changes, write back
    exif_dict = _load_exif_dict(path)

    for ifd_name, tags in delta.items():
        # Ensure the IFD exists in the dict
        if ifd_name not in exif_dict or exif_dict[ifd_name] is None:
            exif_dict[ifd_name] = {}

        for tag_id, value in tags.items():
            if value is None:
                exif_dict[ifd_name].pop(tag_id, None)  # remove tag
            else:
                exif_dict[ifd_name][tag_id] = value

    try:
        _write_exif_dict(path, exif_dict)
    except Exception as exc:
        raise ValueError(
            f"Failed to write EXIF data to '{path}': {exc}"
        ) from exc

    return True
