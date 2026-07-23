from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image

from app.core.webp_validator import WebPValidationError, validate_webp


def make_webp(width: int = 800, height: int = 488) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="WEBP")
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
    with pytest.raises(WebPValidationError) as error:
        validate_webp(content, **kwargs)

    assert error.value.code == expected_code


def test_valid_webp_returns_trusted_metadata_and_checksum() -> None:
    content = make_webp()

    metadata = validate_webp(
        content,
        filename="Floor_1.webp",
        content_type="image/webp",
    )

    assert metadata.width == 800
    assert metadata.height == 488
    assert metadata.file_size_bytes == len(content)
    assert metadata.checksum_sha256 == sha256(content).hexdigest()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("Floor_1.png", "image/webp"),
        ("Floor_1.webp", "image/png"),
    ],
)
def test_declared_file_type_must_be_webp(
    filename: str, content_type: str
) -> None:
    assert_validation_code(
        make_webp(),
        "unsupported_media_type",
        filename=filename,
        content_type=content_type,
    )


def test_content_must_decode_as_webp_even_when_declared_webp() -> None:
    png = BytesIO()
    Image.new("RGB", (800, 10), "white").save(png, format="PNG")

    assert_validation_code(
        png.getvalue(),
        "invalid_webp",
        filename="fake.webp",
        content_type="image/webp",
    )


def empty_file() -> bytes:
    return b""


def oversized_file() -> bytes:
    return b"x" * (5 * 1024 * 1024 + 1)


def wrong_width_file() -> bytes:
    return make_webp(width=799)


def excessive_height_file() -> bytes:
    return make_webp(height=8001)


def animated_file() -> bytes:
    return make_animated_webp()


@pytest.mark.parametrize(
    ("content_factory", "expected_code"),
    [
        (empty_file, "empty_file"),
        (oversized_file, "file_too_large"),
        (wrong_width_file, "invalid_width"),
        (excessive_height_file, "invalid_height"),
        (animated_file, "animated_webp"),
    ],
    ids=["empty", "too-large", "wrong-width", "too-tall", "animated"],
)
def test_webp_rejects_invalid_boundaries(
    content_factory, expected_code: str
) -> None:
    assert_validation_code(
        content_factory(),
        expected_code,
        filename="floor.webp",
        content_type="image/webp",
    )
