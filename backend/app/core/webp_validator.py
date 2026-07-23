"""Validation contract for untrusted WebP floorplan uploads."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_WEBP_BYTES = 5 * 1024 * 1024
REQUIRED_WIDTH = 800
MIN_HEIGHT = 1
MAX_HEIGHT = 8000
WEBP_MIME_TYPE = "image/webp"


@dataclass(frozen=True)
class WebPMetadata:
    width: int
    height: int
    file_size_bytes: int
    checksum_sha256: str


class WebPValidationError(ValueError):
    """Raised when uploaded bytes violate the floorplan contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _reject(code: str, message: str) -> None:
    raise WebPValidationError(code, message)


def validate_webp(
    content: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> WebPMetadata:
    if not content:
        _reject("empty_file", "The uploaded file is empty.")

    file_size = len(content)
    if file_size > MAX_WEBP_BYTES:
        _reject("file_too_large", "The WebP file must not exceed 5 MB.")

    if filename is not None and not filename.lower().endswith(".webp"):
        _reject(
            "unsupported_media_type",
            "The uploaded filename must use the .webp extension.",
        )

    if content_type is not None:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        if normalized_type != WEBP_MIME_TYPE:
            _reject(
                "unsupported_media_type",
                "The uploaded content type must be image/webp.",
            )

    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != "WEBP":
                _reject("invalid_webp", "The uploaded bytes are not WebP.")

            width, height = image.size
            frame_count = getattr(image, "n_frames", 1)
            is_animated = getattr(image, "is_animated", False)

            if width != REQUIRED_WIDTH:
                _reject(
                    "invalid_width",
                    f"The WebP width must be exactly {REQUIRED_WIDTH}px.",
                )
            if height < MIN_HEIGHT or height > MAX_HEIGHT:
                _reject(
                    "invalid_height",
                    f"The WebP height must be between 1 and {MAX_HEIGHT}px.",
                )
            if frame_count != 1 or is_animated:
                _reject(
                    "animated_webp",
                    "Animated WebP floorplans are not supported.",
                )

            image.verify()

        # verify() invalidates the decoder, so re-open and force a full decode.
        with Image.open(BytesIO(content)) as image:
            image.load()
    except WebPValidationError:
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        _reject("invalid_webp", "The uploaded WebP cannot be decoded.")

    return WebPMetadata(
        width=width,
        height=height,
        file_size_bytes=file_size,
        checksum_sha256=sha256(content).hexdigest(),
    )
