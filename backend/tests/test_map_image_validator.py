from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image

from app.core.map_image_validator import (
    MAX_MAP_IMAGE_BYTES,
    MapImageValidationError,
    validate_map_image,
)


def make_image(
    image_format: str,
    *,
    width: int = 640,
    height: int = 480,
) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format=image_format)
    return output.getvalue()


def make_animated_webp() -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (800, 10), "white")
    second = Image.new("RGB", (800, 10), "black")
    first.save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
    )
    return output.getvalue()


def assert_validation_code(content: bytes, expected_code: str, **kwargs) -> None:
    with pytest.raises(MapImageValidationError) as error:
        validate_map_image(content, **kwargs)

    assert error.value.code == expected_code


@pytest.mark.parametrize(
    ("image_format", "filename", "content_type"),
    [
        ("WEBP", "Floor_1.webp", "image/webp"),
        ("PNG", "Floor_1.png", "image/png"),
        ("JPEG", "Floor_1.jpg", "image/jpeg"),
        ("JPEG", "Floor_1.jpeg", "image/jpeg"),
    ],
)
def test_supported_static_images_return_trusted_metadata_and_checksum(
    image_format: str,
    filename: str,
    content_type: str,
) -> None:
    content = make_image(image_format, width=321, height=987)

    metadata = validate_map_image(
        content,
        filename=filename,
        content_type=content_type,
    )

    assert metadata.width == 321
    assert metadata.height == 987
    assert metadata.mime_type == content_type
    assert metadata.file_size_bytes == len(content)
    assert metadata.checksum_sha256 == sha256(content).hexdigest()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("Floor_1.svg", "image/svg+xml"),
        ("Floor_1.gif", "image/gif"),
        ("Floor_1.webp", "image/png"),
    ],
)
def test_declared_file_type_must_be_supported_and_consistent(
    filename: str,
    content_type: str,
) -> None:
    assert_validation_code(
        make_image("WEBP"),
        "unsupported_media_type",
        filename=filename,
        content_type=content_type,
    )


def test_decoded_format_must_match_the_declared_type() -> None:
    assert_validation_code(
        make_image("PNG"),
        "format_mismatch",
        filename="fake.webp",
        content_type="image/webp",
    )


def test_arbitrary_positive_dimensions_are_allowed() -> None:
    for width, height in ((1, 1), (799, 8001), (2048, 512)):
        metadata = validate_map_image(
            make_image("PNG", width=width, height=height),
            filename="floor.png",
            content_type="image/png",
        )
        assert (metadata.width, metadata.height) == (width, height)


def test_file_size_must_be_strictly_below_ten_mebibytes() -> None:
    assert_validation_code(
        b"x" * MAX_MAP_IMAGE_BYTES,
        "file_too_large",
        filename="floor.webp",
        content_type="image/webp",
    )


def test_empty_file_is_rejected() -> None:
    assert_validation_code(
        b"",
        "empty_file",
        filename="floor.webp",
        content_type="image/webp",
    )


def test_animated_image_is_rejected() -> None:
    assert_validation_code(
        make_animated_webp(),
        "animated_image",
        filename="floor.webp",
        content_type="image/webp",
    )


def test_corrupt_image_is_rejected() -> None:
    assert_validation_code(
        b"not-an-image",
        "invalid_image",
        filename="floor.png",
        content_type="image/png",
    )
