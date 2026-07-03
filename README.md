# Image Metadata Editor

Context: images can have a plethora of associated metadata such as capture data, geographic location, photographer, and more. This data is utilized by photo gallery applications like Apple Photos, Immich, Google Photos, and more to organize photos chronologically, by location, and by other options.

However, if a camera was not configured to capture and retain this information for each photo or if, for example, the images were scanned from analogue to digital format then this information is not readily available thus rendering many photo gallery applications useless.

Command line tools, namely [Exiftool](https://exiftool.org/), exist to allow users to add and edit such metadata in their images. Unfortunately, this requires command line knowledge, and may be daunting to users.

The goal of this tool is to provide a GUI interface for quickly and easily editing metadata for common image formats (goal supported: .png, .jpg, .heic, ...)
