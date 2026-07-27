"""Validation contract for untrusted map image uploads."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import PurePath

from PIL import Image, UnidentifiedImageError

MAX_MAP_IMAGE_BYTES = 10 * 1024 * 1024

FORMAT_TO_MIME_TYPE = {
    "WEBP": "image/webp",
    "PNG": "image/png",
    "JPEG": "image/jpeg",
}
EXTENSION_TO_FORMAT = {
    ".webp": "WEBP",
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
}
MIME_TYPE_TO_FORMAT = {
    mime_type: image_format
    for image_format, mime_type in FORMAT_TO_MIME_TYPE.items()
}


@dataclass(frozen=True)
class MapImageMetadata:
    width: int
    height: int
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str


class MapImageValidationError(ValueError):
    """Raised when uploaded bytes violate the map image contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _reject(code: str, message: str) -> None:
    raise MapImageValidationError(code, message)


def _declared_format(
    *,
    filename: str | None,
    content_type: str | None,
) -> str | None:
    filename_format = None
    if filename is not None:
        filename_format = EXTENSION_TO_FORMAT.get(PurePath(filename).suffix.lower())
        if filename_format is None:
            _reject(
                "unsupported_media_type",
                "The filename must use .webp, .png, .jpg, or .jpeg.",
            )

    content_type_format = None
    if content_type is not None:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        content_type_format = MIME_TYPE_TO_FORMAT.get(normalized_type)
        if content_type_format is None:
            _reject(
                "unsupported_media_type",
                "The content type must be image/webp, image/png, or image/jpeg.",
            )

    if (
        filename_format is not None
        and content_type_format is not None
        and filename_format != content_type_format
    ):
        _reject(
            "unsupported_media_type",
            "The filename extension and content type must describe the same format.",
        )
    return filename_format or content_type_format


def validate_map_image(
    content: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> MapImageMetadata:
    if not content:
        _reject("empty_file", "The uploaded file is empty.")

    file_size = len(content)
    if file_size >= MAX_MAP_IMAGE_BYTES:
        _reject("file_too_large", "The image file must be smaller than 10 MB.")

    expected_format = _declared_format(
        filename=filename,
        content_type=content_type,
    )

    try:
        with Image.open(BytesIO(content)) as image:
            actual_format = str(image.format or "").upper()
            if actual_format not in FORMAT_TO_MIME_TYPE:
                _reject(
                    "invalid_image",
                    "The uploaded bytes are not a supported map image.",
                )
            if expected_format is not None and actual_format != expected_format:
                _reject(
                    "format_mismatch",
                    "The decoded image format does not match its filename or MIME type.",
                )

            width, height = image.size
            frame_count = getattr(image, "n_frames", 1)
            is_animated = getattr(image, "is_animated", False)
            if frame_count != 1 or is_animated:
                _reject(
                    "animated_image",
                    "Animated map images are not supported.",
                )
            image.verify()

        with Image.open(BytesIO(content)) as image:
            image.load()
    except MapImageValidationError:
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        _reject("invalid_image", "The uploaded image cannot be decoded.")

    return MapImageMetadata(
        width=width,
        height=height,
        mime_type=FORMAT_TO_MIME_TYPE[actual_format],
        file_size_bytes=file_size,
        checksum_sha256=sha256(content).hexdigest(),
    )
