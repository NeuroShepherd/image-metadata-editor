"""Tests for the image metadata writer."""

from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image

from image_metadata_editor.metadata.models import GpsInfo, ImageMetadata
from image_metadata_editor.metadata.reader import read_metadata
from image_metadata_editor.metadata.writer import write_metadata


# ── Helpers ─────────────────────────────────────────────────────────────────


def _create_test_jpeg(
    exif_dict: dict | None = None,
) -> Path:
    """Create a temporary JPEG with optional EXIF data and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    path = Path(tmp.name)

    img = Image.new("RGB", (32, 32), color="red")

    if exif_dict is not None:
        exif_bytes = piexif.dump(exif_dict)
        img.save(path, exif=exif_bytes)
    else:
        img.save(path)

    return path


def _make_exif(
    title: str | None = None,
    keywords: list[str] | None = None,
    date_taken: str | None = None,
    gps_lat: tuple | None = None,
    gps_lat_ref: str = "N",
    gps_lon: tuple | None = None,
    gps_lon_ref: str = "E",
    gps_alt: tuple | None = None,
    gps_alt_ref: int = 0,
) -> dict:
    """Build a piexif-style exif_dict for test image creation."""
    zeroth: dict[int, object] = {}
    exif: dict[int, object] = {}
    gps: dict[int, object] = {}

    if title is not None:
        zeroth[0x010E] = title
    if keywords is not None:
        xp_data = ";".join(keywords).encode("utf-16-le") + b"\x00\x00"
        zeroth[0x9C9E] = xp_data
    if date_taken is not None:
        exif[0x9003] = date_taken
    if gps_lat is not None:
        gps[0x0002] = gps_lat
        gps[0x0001] = gps_lat_ref
    if gps_lon is not None:
        gps[0x0004] = gps_lon
        gps[0x0003] = gps_lon_ref
    if gps_alt is not None:
        gps[0x0006] = gps_alt
        gps[0x0005] = bytes([gps_alt_ref])

    return {
        "0th": zeroth,
        "Exif": exif,
        "GPS": gps,
        "Interop": {},
        "1st": {},
        "thumbnail": None,
    }


# ── Tests ───────────────────────────────────────────────────────────────────


class TestWriteMetadata:
    """Happy-path tests for ``write_metadata``."""

    def test_update_title(self) -> None:
        """Updating only the title changes only that field."""
        exif_dict = _make_exif(title="Old Title")
        path = _create_test_jpeg(exif_dict)

        try:
            new_meta = ImageMetadata(title="New Title")
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.title == "New Title"
        finally:
            os.unlink(path)

    def test_no_change_returns_false(self) -> None:
        """Writing identical metadata returns False and leaves file untouched."""
        exif_dict = _make_exif(title="Sunset")
        path = _create_test_jpeg(exif_dict)

        try:
            meta = read_metadata(path)
            changed = write_metadata(path, meta)
            assert changed is False
        finally:
            os.unlink(path)

    def test_update_keywords(self) -> None:
        """Updating keywords changes only that field."""
        exif_dict = _make_exif(keywords=["old"])
        path = _create_test_jpeg(exif_dict)

        try:
            new_meta = ImageMetadata(keywords=["new", "keywords"])
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.keywords == ["new", "keywords"]
        finally:
            os.unlink(path)

    def test_update_date_taken(self) -> None:
        """Updating date_taken changes only that field."""
        exif_dict = _make_exif(date_taken="2024:01:01 12:00:00")
        path = _create_test_jpeg(exif_dict)

        try:
            new_meta = ImageMetadata(
                date_taken=datetime(2025, 6, 15, 14, 30, 0)
            )
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.date_taken == datetime(2025, 6, 15, 14, 30, 0)
        finally:
            os.unlink(path)

    def test_update_gps(self) -> None:
        """Updating GPS changes only that field."""
        exif_dict = _make_exif(title="Original")
        path = _create_test_jpeg(exif_dict)

        try:
            new_meta = ImageMetadata(
                gps=GpsInfo(
                    latitude_ref="N",
                    latitude=48.85833,
                    longitude_ref="E",
                    longitude=2.29444,
                    altitude_ref=0,
                    altitude=300.0,
                )
            )
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.title == "Original"  # unchanged
            assert result.gps is not None
            assert abs(result.gps.latitude - 48.85833) < 0.001  # type: ignore[operator]
            assert abs(result.gps.longitude - 2.29444) < 0.001  # type: ignore[operator]
            assert abs(result.gps.altitude - 300.0) < 0.001  # type: ignore[operator]
        finally:
            os.unlink(path)

    def test_selective_update_preserves_other_fields(self) -> None:
        """Changing one field leaves all other fields intact."""
        exif_dict = _make_exif(
            title="Title",
            keywords=["a", "b"],
            date_taken="2024:01:01 12:00:00",
            gps_lat=((48, 1), (51, 1), (30, 1)),
            gps_lon=((2, 1), (17, 1), (40, 1)),
            gps_alt=(300, 1),
        )
        path = _create_test_jpeg(exif_dict)

        try:
            # Change only the title
            new_meta = ImageMetadata(title="New Title")
            write_metadata(path, new_meta)

            result = read_metadata(path)
            assert result.title == "New Title"
            assert result.keywords == ["a", "b"]
            assert result.date_taken == datetime(2024, 1, 1, 12, 0, 0)
            assert result.gps is not None
            assert abs(result.gps.latitude - 48.85833) < 0.001  # type: ignore[operator]
        finally:
            os.unlink(path)

    def test_clear_title(self) -> None:
        """Setting title to None removes the ImageDescription tag."""
        exif_dict = _make_exif(title="To Be Removed")
        path = _create_test_jpeg(exif_dict)

        try:
            # Before: title is set
            assert read_metadata(path).title == "To Be Removed"

            new_meta = ImageMetadata(title=None)
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.title is None
        finally:
            os.unlink(path)

    def test_clear_gps(self) -> None:
        """Setting gps to None removes the entire GPS IFD."""
        exif_dict = _make_exif(
            title="Has GPS",
            gps_lat=((48, 1), (51, 1), (30, 1)),
            gps_lon=((2, 1), (17, 1), (40, 1)),
        )
        path = _create_test_jpeg(exif_dict)

        try:
            assert read_metadata(path).gps is not None

            new_meta = ImageMetadata(title="Has GPS", gps=None)
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.title == "Has GPS"
            assert result.gps is None
        finally:
            os.unlink(path)

    def test_add_exif_to_image_without_exif(self) -> None:
        """Writing metadata to an image with no EXIF creates fresh EXIF."""
        path = _create_test_jpeg(exif_dict=None)  # no EXIF at all

        try:
            new_meta = ImageMetadata(title="Brand New")
            changed = write_metadata(path, new_meta)

            assert changed is True
            result = read_metadata(path)
            assert result.title == "Brand New"
        finally:
            os.unlink(path)


class TestWriteMetadataFormats:
    """Write tests for non-JPEG formats (TIFF, PNG, WebP)."""

    @staticmethod
    def _create_test_image(ext: str, exif_dict: dict | None = None) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.close()
        path = Path(tmp.name)
        img = Image.new("RGB", (32, 32), color="red")
        if exif_dict is not None:
            exif_bytes = piexif.dump(exif_dict)
            img.save(path, exif=exif_bytes)
        else:
            img.save(path)
        return path

    @pytest.mark.parametrize("ext", [".tiff", ".png", ".webp"])
    def test_write_title(self, ext: str) -> None:
        """Write title to TIFF, PNG, and WebP."""
        path = self._create_test_image(ext)
        try:
            new_meta = ImageMetadata(title=f"Hello {ext}")
            changed = write_metadata(path, new_meta)
            assert changed is True
            result = read_metadata(path)
            assert result.title == f"Hello {ext}"
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("ext", [".tiff", ".png", ".webp"])
    def test_preserve_other_tags(self, ext: str) -> None:
        """Updating one field preserves existing EXIF tags."""
        exif = _make_exif(
            title="Original",
            date_taken="2024:06:15 10:30:00",
        )
        path = self._create_test_image(ext, exif)
        try:
            new_meta = ImageMetadata(title="Updated")
            changed = write_metadata(path, new_meta)
            assert changed is True
            result = read_metadata(path)
            assert result.title == "Updated"
            assert result.date_taken == datetime(2024, 6, 15, 10, 30, 0)
        finally:
            os.unlink(path)

    @pytest.mark.parametrize("ext", [".tiff", ".png", ".webp"])
    def test_no_change_returns_false(self, ext: str) -> None:
        """Writing identical metadata returns False."""
        exif = _make_exif(title="Same")
        path = self._create_test_image(ext, exif)
        try:
            meta = read_metadata(path)
            changed = write_metadata(path, meta)
            assert changed is False
        finally:
            os.unlink(path)


class TestWriteMetadataErrors:
    """Error-path tests for ``write_metadata``."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            write_metadata("/nonexistent/image.jpg", ImageMetadata())

    def test_unsupported_format(self) -> None:
        path = TestWriteMetadataFormats._create_test_image(".bmp")
        try:
            with pytest.raises(ValueError, match="not supported for"):
                write_metadata(path, ImageMetadata())
        finally:
            os.unlink(path)

    def test_write_to_corrupted_file(self) -> None:
        """A file that exists but is not a valid image raises ValueError."""
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(b"not an image")
        tmp.close()
        path = Path(tmp.name)
        try:
            with pytest.raises(ValueError, match="Failed to "):
                write_metadata(path, ImageMetadata(title="X"))
        finally:
            os.unlink(path)
