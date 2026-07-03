from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from image_metadata_editor.metadata.models import GpsInfo, ImageMetadata

__all__ = [
    "read_metadata",
]

_SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".png",
    ".webp",
    ".heic",
    ".heif",
}

# Tag ID constants for tags that may not be present in older Pillow versions
_TAG_ID_XP_KEYWORDS = 0x9C9E
_TAG_ID_GPS_INFO = 0x8825


def _decode_bytes(value: bytes, encoding: str = "utf-8", fallback: str = "replace") -> str:
    """Safely decode bytes to a string."""
    if isinstance(value, bytes):
        return value.decode(encoding, errors=fallback)
    return str(value)


def _rational_to_float(value: object) -> float | None:
    """Convert a PIL rational value to float.

    Handles:
    * ``(numerator, denominator)`` tuple
    * :class:`~PIL.TiffImagePlugin.IFDRational` (Pillow's rational type)
    * Plain ``int`` / ``float``
    """
    # IFDRational from Pillow — behaves like a number but isn't int/float
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        try:
            return float(value.numerator) / float(value.denominator)
        except (ZeroDivisionError, TypeError, ValueError):
            return None
    # Tuple rational (numerator, denominator)
    if isinstance(value, tuple) and len(value) == 2:
        try:
            return float(value[0]) / float(value[1])
        except (ZeroDivisionError, TypeError, ValueError):
            return None
    # Plain number
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _dms_to_decimal(coordinate: object) -> float | None:
    """Convert GPS degrees/minutes/seconds rationals to decimal degrees.

    The EXIF GPS coordinate is stored as three rational values:
    (degrees, minutes, seconds).
    """
    if not isinstance(coordinate, tuple) or len(coordinate) != 3:
        return None

    d = _rational_to_float(coordinate[0])
    m = _rational_to_float(coordinate[1])
    s = _rational_to_float(coordinate[2])

    if d is None or m is None or s is None:
        return None

    return d + m / 60.0 + s / 3600.0


def _parse_xp_keywords(value: object) -> list[str] | None:
    """Decode XPKeywords (stored as UTF-16-LE semicolon-separated bytes)."""
    if not isinstance(value, bytes):
        return None
    try:
        decoded = value.decode("utf-16-le").strip("\x00").strip()
    except (UnicodeDecodeError, ValueError):
        return None
    if not decoded:
        return None
    keywords = [kw.strip() for kw in decoded.split(";") if kw.strip()]
    return keywords or None


def _parse_exif_tags(exif_data: dict) -> ImageMetadata:
    """Extract core metadata fields from raw EXIF data."""
    metadata = ImageMetadata()

    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, "")

        if tag_name == "ImageDescription":
            # Maps to title
            if isinstance(value, bytes):
                value = _decode_bytes(value)
            metadata.title = str(value).strip() if value else None

        elif tag_id == _TAG_ID_XP_KEYWORDS or tag_name == "XPKeywords":
            keywords = _parse_xp_keywords(value)
            if keywords:
                metadata.keywords = keywords

        elif tag_name == "DateTimeOriginal":
            # EXIF date format: "YYYY:MM:DD HH:MM:SS"
            if isinstance(value, str) and value.strip():
                try:
                    metadata.date_taken = datetime.strptime(
                        value.strip(), "%Y:%m:%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    pass

    return metadata


def _parse_gps_data(gps_data: dict) -> GpsInfo | None:
    """Extract GPS location data from the GPS IFD dictionary."""
    if not gps_data:
        return None

    gps = GpsInfo()

    for tag_id, value in gps_data.items():
        tag_name = GPSTAGS.get(tag_id, "")

        if tag_name == "GPSLatitudeRef":
            if isinstance(value, bytes):
                value = _decode_bytes(value)
            gps.latitude_ref = str(value).strip() if value else None

        elif tag_name == "GPSLatitude":
            lat = _dms_to_decimal(value)
            if lat is not None:
                gps.latitude = lat

        elif tag_name == "GPSLongitudeRef":
            if isinstance(value, bytes):
                value = _decode_bytes(value)
            gps.longitude_ref = str(value).strip() if value else None

        elif tag_name == "GPSLongitude":
            lon = _dms_to_decimal(value)
            if lon is not None:
                gps.longitude = lon

        elif tag_name == "GPSAltitudeRef":
            if isinstance(value, bytes):
                gps.altitude_ref = int.from_bytes(value, byteorder="big")
            elif value is not None:
                gps.altitude_ref = int(value)
            else:
                gps.altitude_ref = None

        elif tag_name == "GPSAltitude":
            alt = _rational_to_float(value)
            if alt is not None:
                gps.altitude = alt

    # Return None if no meaningful GPS data was found
    if gps.latitude is None and gps.longitude is None and gps.altitude is None:
        return None

    return gps


def read_metadata(file_path: str | Path) -> ImageMetadata:
    """Read metadata from an image file and return an ``ImageMetadata`` object.

    Supports the following image formats:
      - JPEG / JFIF (``.jpg``, ``.jpeg``)
      - TIFF (``.tif``, ``.tiff``)
      - PNG (``.png``)
      - WebP (``.webp``)
      - HEIC / HEIF (``.heic``, ``.heif``) – requires ``pillow-heif``

    Args:
        file_path: Path to the image file.

    Returns:
        An ``ImageMetadata`` instance with any fields that could be parsed
        from the file's EXIF / XMP / IPTC metadata.  Fields that are absent
        in the source file are left as ``None``.

    Raises:
        FileNotFoundError: The given path does not exist.
        ValueError: The file format is unsupported, or the file could not be
            read as an image.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    ext = path.suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{ext}'. "
            f"Supported extensions: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )

    try:
        with Image.open(path) as img:
            exif_obj = img.getexif()

            # Build a flat dict from the main Exif object (0th IFD).
            # For JPEG, the Exif sub-IFD (DateTimeOriginal etc.) is NOT
            # included automatically, so we merge it in via get_ifd(0x8769).
            # NOTE: get_ifd() MUST be called while the file is still open.
            exif_data: dict[int, object] = dict(exif_obj)

            # Merge Exif sub-IFD (tag 0x8769 = ExifOffset)
            exif_sub_ifd = exif_obj.get_ifd(0x8769)
            if exif_sub_ifd:
                exif_data.update(exif_sub_ifd)

            # Merge GPS sub-IFD (tag 0x8825)
            gps_raw = exif_obj.get_ifd(_TAG_ID_GPS_INFO)

    except Exception as exc:
        raise ValueError(f"Failed to read image file '{path}': {exc}") from exc

    if not exif_data:
        return ImageMetadata()

    metadata = _parse_exif_tags(exif_data)

    if gps_raw:
        gps = _parse_gps_data(gps_raw)
        if gps is not None:
            metadata.gps = gps

    return metadata