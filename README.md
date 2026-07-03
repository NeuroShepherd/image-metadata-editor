# Image Metadata Editor

Context: images can have a plethora of associated metadata such as capture data, geographic location, photographer, and more. This data is utilized by photo gallery applications like Apple Photos, Immich, Google Photos, and more to organize photos chronologically, by location, and by other options.

However, if a camera was not configured to capture and retain this information for each photo or if, for example, the images were scanned from analogue to digital format then this information is not readily available thus rendering many photo gallery applications useless.

Command line tools, namely [Exiftool](https://exiftool.org/), exist to allow users to add and edit such metadata in their images. Unfortunately, this requires command line knowledge, and may be daunting to users.

The goal of this tool is to provide a GUI interface for quickly and easily editing metadata for common image formats (goal supported: .png, .jpg, .heic, ...)

## Supported Metadata Standards by Format

**Note: This is not necessarily what this app supports, but is for informational purposes.**

| Format                | Metadata Standards                                                                                                            |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **JPEG**              | **EXIF**, **IPTC IIM**, **XMP**, JFIF                                                                                         |
| **TIFF**              | **EXIF**, **IPTC**, **XMP** (TIFF is the native container for EXIF)                                                           |
| **HEIC/HEIF**         | **EXIF**, **XMP**                                                                                                             |
| **WebP**              | **EXIF**, **XMP**                                                                                                             |
| **PNG**               | **XMP** (embedded in `iTXt` chunk), **text chunks** (tEXt/zTXt), no native EXIF — GPS data still possible via `Xmp.exif.GPS*` |
| **GIF**               | **XMP** (via extension block), very limited otherwise                                                                         |
| **RAW** (CR2/NEF/ARW) | Extended **EXIF** with **MakerNotes** (camera-proprietary)                                                                    |

### Targeted Support

The editor aims to support **most EXIF features** across formats that support it (JPEG, TIFF, HEIC, WebP, RAW), and **XMP** for formats that lack native EXIF (particularly **PNG**). This covers the most common metadata needs: camera capture data, GPS location, dates, copyright, and descriptive tags.

## Current State

- Data classes and utilities for reading and writing image files have been defined
  - This should probably just be outsourced to the exiftool though. Future task to simplify everything here.
- A web application can read in one or multiple files or a folder at a time that the user can flip through to edit metadata information.
  - This is hardcoded right now and files that are added are uploaded to an uploads/ folder currently.
- Need to implement an API between the UI and the models and helpers described above that allows for direct reading/writing from the path of the image rather than creating copies of the image
