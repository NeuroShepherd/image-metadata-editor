"""Tests for the image metadata reader using generated test images."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from image_metadata_editor.metadata.models import GpsInfo, ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_exif(
    zeroth_tags: dict[int, object] | None = None,
    exif_tags: dict[int, object] | None = None,
    gps_tags: dict[int, bytes | tuple] | None = None,
) -> bytes | None:
    """Encode EXIF tags into raw EXIF bytes via ``piexif``.

    *zeroth_tags* → 0th IFD (image-level tags such as ImageDescription).
    *exif_tags*   → Exif IFD (photo-level tags such as DateTimeOriginal).
    *gps_tags*    → GPS IFD.
    Returns ``None`` if all are empty / ``None``.
    """
    if not zeroth_tags and not exif_tags and not gps_tags:
        return None

    zeroth: dict[int, bytes | tuple] = dict(zeroth_tags or {})
    exif: dict[int, bytes | tuple] = dict(exif_tags or {})
    gps: dict[int, bytes | tuple] = dict(gps_tags or {})

    exif_dict = {
        "0th": zeroth,
        "Exif": exif,
        "GPS": gps,
        "Interop": {},
        "1st": {},
        "thumbnail": None,
    }
    return piexif.dump(exif_dict)


def _make_test_image(
    ext: str = ".jpg",
    zeroth_tags: dict[int, object] | None = None,
    exif_tags: dict[int, object] | None = None,
    gps_tags: dict[int, object] | None = None,
) -> Path:
    """Create a small image file at a temp path and return the path.

    *zeroth_tags* → 0th IFD (ImageDescription, Make, …).
    *exif_tags*   → Exif IFD (DateTimeOriginal, …).
    *gps_tags*    → GPS IFD.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.close()
    path = Path(tmp.name)

    img = Image.new("RGB", (32, 32), color="red")

    exif_bytes = _encode_exif(zeroth_tags, exif_tags, gps_tags)
    if exif_bytes is not None:
        img.save(path, exif=exif_bytes)
    else:
        img.save(path)

    return path


def _build_exif(**known: object) -> dict[int, object]:
    """Build a minimal EXIF 0th-IFD dict from keyword arguments.

    Keys are PIL tag names (e.g. ``ImageDescription``, ``DateTimeOriginal``).
    They are resolved to integer tag IDs via ``TAGS``.
    """
    exif: dict[int, object] = {}
    for name, value in known.items():
        tag_id = next((k for k, v in TAGS.items() if v == name), None)
        if tag_id is not None:
            exif[tag_id] = value
    return exif


def _build_gps(**known: object) -> dict[int, object]:
    """Build a GPS IFD dict from keyword arguments (using GPSTAGS names)."""
    gps: dict[int, object] = {}
    for name, value in known.items():
        tag_id = next((k for k, v in GPSTAGS.items() if v == name), None)
        if tag_id is not None:
            gps[tag_id] = value
    return gps


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadMetadata:
    """Happy-path tests for ``read_metadata``."""

    def test_title_from_image_description(self) -> None:
        """ImageDescription tag maps to ``title``."""
        exif = _build_exif(ImageDescription="A lovely sunset")
        path = _make_test_image(zeroth_tags=exif)
        try:
            result = read_metadata(path)
            assert result.title == "A lovely sunset"
        finally:
            os.unlink(path)

    def test_date_taken_from_datetime_original(self) -> None:
        """DateTimeOriginal tag maps to ``date_taken``."""
        exif = _build_exif(DateTimeOriginal="2024:12:25 14:30:00")
        path = _make_test_image(exif_tags=exif)
        try:
            result = read_metadata(path)
            assert result.date_taken == datetime(2024, 12, 25, 14, 30, 0)
        finally:
            os.unlink(path)

    def test_keywords_from_xp_keywords(self) -> None:
        """XPKeywords (UTF-16-LE semicolon-separated) maps to ``keywords``."""
        xp_data = "holiday;beach;sunset".encode("utf-16-le") + b"\x00\x00"
        exif = _build_exif(**{})  # XPKeywords may not be in TAGS on all Pillow
        exif[0x9C9E] = xp_data
        path = _make_test_image(zeroth_tags=exif)
        try:
            result = read_metadata(path)
            assert result.keywords == ["holiday", "beach", "sunset"]
        finally:
            os.unlink(path)

    def test_gps_coordinates(self) -> None:
        """GPS latitude/longitude/altitude are parsed correctly."""
        # 48.8584° N, 2.2945° E → DMS: 48°51'30", 2°17'40"
        gps = _build_gps(
            GPSLatitudeRef="N",
            GPSLatitude=((48, 1), (51, 1), (30, 1)),
            GPSLongitudeRef="E",
            GPSLongitude=((2, 1), (17, 1), (40, 1)),
            GPSAltitudeRef=0,
            GPSAltitude=(300, 1),
        )
        exif = _build_exif(ImageDescription="Eiffel Tower")
        path = _make_test_image(zeroth_tags=exif, gps_tags=gps)
        try:
            result = read_metadata(path)
            assert result.title == "Eiffel Tower"
            assert result.gps is not None
            assert result.gps.latitude_ref == "N"
            assert result.gps.latitude is not None
            assert abs(result.gps.latitude - 48.85833) < 0.001
            assert result.gps.longitude_ref == "E"
            assert result.gps.longitude is not None
            assert abs(result.gps.longitude - 2.29444) < 0.001
            assert result.gps.altitude_ref == 0
            assert result.gps.altitude is not None
            assert abs(result.gps.altitude - 300.0) < 0.001
        finally:
            os.unlink(path)

    def test_gps_returns_none_when_not_present(self) -> None:
        """No GPS info in EXIF → ``gps`` is ``None``."""
        exif = _build_exif(ImageDescription="No GPS")
        path = _make_test_image(zeroth_tags=exif)
        try:
            result = read_metadata(path)
            assert result.gps is None
        finally:
            os.unlink(path)

    def test_no_exif_returns_empty_metadata(self) -> None:
        """File with no EXIF data returns an all-None ImageMetadata."""
        path = _make_test_image(zeroth_tags=None)
        try:
            result = read_metadata(path)
            assert result.title is None
            assert result.description is None
            assert result.keywords is None
            assert result.date_taken is None
            assert result.gps is None
        finally:
            os.unlink(path)

    def test_png_supported(self) -> None:
        """PNG files are readable (even without EXIF)."""
        path = _make_test_image(ext=".png", zeroth_tags=None)
        try:
            result = read_metadata(path)
            # PNG has no native EXIF, so all fields should be None
            assert result.title is None
        finally:
            os.unlink(path)

    def test_tiff_supported(self) -> None:
        """TIFF files are readable with EXIF."""
        exif = _build_exif(ImageDescription="TIFF test")
        path = _make_test_image(ext=".tiff", zeroth_tags=exif)
        try:
            result = read_metadata(path)
            assert result.title == "TIFF test"
        finally:
            os.unlink(path)

    def test_webp_supported(self) -> None:
        """WebP files are readable (even without EXIF)."""
        path = _make_test_image(ext=".webp", zeroth_tags=None)
        try:
            result = read_metadata(path)
            assert result.title is None
        finally:
            os.unlink(path)


class TestReadMetadataErrors:
    """Error-path tests for ``read_metadata``."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_metadata("/nonexistent/image.jpg")

    def test_unsupported_format(self) -> None:
        path = _make_test_image(ext=".bmp")
        try:
            with pytest.raises(ValueError, match="Unsupported image format"):
                read_metadata(path)
        finally:
            os.unlink(path)

    def test_invalid_file(self) -> None:
        """A non-image file raises ValueError."""
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(b"not an image")
        tmp.close()
        path = Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="Failed to read image file"):
                read_metadata(path)
        finally:
            os.unlink(path)
