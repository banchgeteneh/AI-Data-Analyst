from __future__ import annotations


class ExtractionError(ValueError):
    """Base class for extraction failures."""


class UnsupportedFileTypeError(ExtractionError):
    """Raised when the file extension or signature is unsupported."""


class MalformedFileError(ExtractionError):
    """Raised when the file content is invalid or unreadable."""


class StructuredDataNotFoundError(ExtractionError):
    """Raised when a file is valid but no structured table can be extracted."""
