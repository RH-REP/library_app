"""PDF to plain text extractor skeleton."""

from __future__ import annotations

from pathlib import Path

try:
    from .common import ExtractionResult, not_implemented_result
except ImportError:  # Allows direct execution during early prototyping.
    from common import ExtractionResult, not_implemented_result


EXTRACTOR_NAME = "pdf_to_text"
MEDIA_TYPE = "application/pdf"


def extract(
    source_path: str | Path,
    source_id: str,
    language_hint: str = "",
) -> ExtractionResult:
    return not_implemented_result(
        source_path=source_path,
        source_id=source_id,
        media_type=MEDIA_TYPE,
        extractor=EXTRACTOR_NAME,
        language_hint=language_hint,
    )
