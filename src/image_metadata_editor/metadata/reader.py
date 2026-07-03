from image_metadata_editor.metadata.models import ImageMetadata

new = ImageMetadata(
    title="Sunset at the Beach",
    description="A beautiful sunset over the ocean with waves crashing on the shore."
)

print(new.title)  # Output: Sunset at the Beach