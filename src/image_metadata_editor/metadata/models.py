from datetime import datetime

from pydantic import BaseModel, Field


class GpsInfo(BaseModel):
    """GPS coordinates based on the EXIF / XMP GPS tag specification.

    In JPEG, TIFF, HEIC, WebP these map to native Exif.GPSInfo.* tags.
    In PNG (which lacks native EXIF), these map to Xmp.exif.GPS* properties
    stored in an XMP iTXt chunk.

    Internally stores latitude and longitude as decimal degrees for ease of use;
    conversion to/from EXIF's rational degree/minute/second triple is handled
    separately during read/write.
    """

    latitude_ref: str | None = Field(
        default=None,
        pattern=r"^[NS]$",
        description="Latitude reference: 'N' or 'S' (EXIF tag 0x0001)",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees (EXIF tag 0x0002)",
    )
    longitude_ref: str | None = Field(
        default=None,
        pattern=r"^[EW]$",
        description="Longitude reference: 'E' or 'W' (EXIF tag 0x0003)",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees (EXIF tag 0x0004)",
    )
    altitude_ref: int | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Altitude reference: 0 = above sea level, 1 = below sea level (EXIF tag 0x0005)",
    )
    altitude: float | None = Field(
        default=None,
        ge=0.0,
        description="Altitude in meters (EXIF tag 0x0006)",
    )


class ImageMetadata(BaseModel):
    """Top-level model for all metadata fields supported by the editor.

    Tag references (via exiv2.org):
    - EXIF: Exif.Image / Exif.Photo
    - XMP:  Xmp.dc (Dublin Core)
    - IPTC: Iptc.Application2
    """

    title: str | None = Field(
        default=None,
        description=(
            "Short display title. "
            "Maps to Exif.Image.ImageDescription (0x010e), "
            "Exif.Photo.ImageTitle (0xa436), "
            "Xmp.dc.title, "
            "Iptc.Application2.ObjectName"
        ),
    )
    description: str | None = Field(
        default=None,
        description=(
            "Description or caption. "
            "Maps to Xmp.dc.description, "
            "Iptc.Application2.Caption"
        ),
    )
    keywords: list[str] | None = Field(
        default=None,
        description=(
            "Tags / keywords. "
            "Maps to Xmp.dc.subject, "
            "Exif.Image.XPKeywords (0x9c9e), "
            "Iptc.Application2.Keywords"
        ),
    )
    date_taken: datetime | None = Field(
        default=None,
        description=(
            "Date and time the photo was taken. "
            "Maps to Exif.Photo.DateTimeOriginal (0x9003), "
            "Iptc.Application2.DateCreated + TimeCreated"
        ),
    )
    gps: GpsInfo | None = Field(
        default=None,
        description=(
            "GPS location data. "
            "Maps to Exif.GPSInfo.* tags in JPEG/TIFF/HEIC/WebP, "
            "or Xmp.exif.GPS* in PNG (via XMP)"
        ),
    )