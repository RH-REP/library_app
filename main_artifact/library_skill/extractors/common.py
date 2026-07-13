"""Shared contracts for plain text extractor skeletons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Literal


ExtractionStatus = Literal["ok", "needs_ocr", "needs_review", "failed"]


@dataclass(frozen=True)
class ExtractionRecord:
    source_id: str
    source_path: str
    media_type: str
    extractor: str
    status: ExtractionStatus
    warnings: tuple[str, ...]
    ocr_used: bool
    language_hint: str


@dataclass(frozen=True)
class ExtractionResult:
    record: ExtractionRecord
    plain_text: str


def not_implemented_result(
    *,
    source_path: str | Path,
    source_id: str,
    media_type: str,
    extractor: str,
    language_hint: str = "",
    ocr_used: bool = False,
) -> ExtractionResult:
    """Return a contract-shaped result until the extractor body is implemented."""
    return ExtractionResult(
        record=ExtractionRecord(
            source_id=source_id,
            source_path=str(source_path),
            media_type=media_type,
            extractor=extractor,
            status="failed",
            warnings=(f"{extractor} is a skeleton; extraction is not implemented yet.",),
            ocr_used=ocr_used,
            language_hint=language_hint,
        ),
        plain_text="",
    )


def write_extraction_result(result: ExtractionResult, output_dir: str | Path) -> None:
    """Write plain_text.txt and extraction_record.json using the issue #7 layout."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "plain_text.txt").write_text(result.plain_text, encoding="utf-8")
    (destination / "extraction_record.json").write_text(
        json.dumps(asdict(result.record), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
