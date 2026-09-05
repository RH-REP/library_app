"""Shared contracts for text extractor skeletons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


if TYPE_CHECKING:
    ExtractionStatus = Literal["ok", "needs_ocr", "needs_review", "failed"]
else:
    ExtractionStatus = str
ExtractionMethod = str


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
    layout_warnings: tuple[str, ...] = ()
    extraction_method: ExtractionMethod = ""
    raw_text_path: str = ""
    extracted_text_path: str = ""


@dataclass(frozen=True)
class ExtractionResult:
    record: ExtractionRecord
    raw_text: str = ""
    body_text: str = ""
    caption_text: str = ""
    figure_text: str = ""
    diagram_transcription: str = ""

    def searchable_text(self) -> str:
        """Return the text intended for raw_text.txt.

        Low-confidence figure OCR candidates are not included automatically.
        Callers can set raw_text explicitly if they want a different blend.
        """
        if self.raw_text:
            return self.raw_text
        return compose_raw_text(
            body_text=self.body_text,
            caption_text=self.caption_text,
            diagram_transcription=self.diagram_transcription,
        )


def compose_raw_text(
    *,
    body_text: str = "",
    caption_text: str = "",
    diagram_transcription: str = "",
) -> str:
    """Build the default search text from reviewed or structurally trusted text."""
    sections = (
        text.strip()
        for text in (body_text, caption_text, diagram_transcription)
        if text.strip()
    )
    return "\n\n".join(sections)


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
    warning = f"{extractor} is a skeleton; extraction is not implemented yet."
    return ExtractionResult(
        record=ExtractionRecord(
            source_id=source_id,
            source_path=str(source_path),
            media_type=media_type,
            extractor=extractor,
            status="failed",
            warnings=(warning,),
            ocr_used=ocr_used,
            language_hint=language_hint,
            extraction_method="not_implemented",
        ),
    )


def _extracted_text_payload(result: ExtractionResult) -> dict[str, object]:
    return {
        "body_text": result.body_text,
        "caption_text": result.caption_text,
        "figure_text": result.figure_text,
        "diagram_transcription": result.diagram_transcription,
    }


def write_extraction_result(result: ExtractionResult, output_dir: str | Path) -> None:
    """Write extraction outputs using the source/extracted/organized data contract."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    raw_text_path = destination / "raw_text.txt"
    extracted_text_path = destination / "extracted_text.json"
    record_path = destination / "extraction_record.json"

    raw_text_path.write_text(
        result.searchable_text(),
        encoding="utf-8",
    )
    record = asdict(result.record)
    record["raw_text_path"] = record["raw_text_path"] or str(raw_text_path)
    record["extracted_text_path"] = record["extracted_text_path"] or str(extracted_text_path)
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    extracted_text_path.write_text(
        json.dumps(_extracted_text_payload(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
