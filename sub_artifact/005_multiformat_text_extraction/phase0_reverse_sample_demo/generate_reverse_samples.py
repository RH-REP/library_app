"""Generate phase 0 reverse samples for multiformat text extraction.

The demo starts from three short source texts, renders them into HTML, PDF,
and JPG, then writes the extraction outputs we expect future extractors to
produce. This keeps the intended pipeline concrete before implementing parsers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
COLLECTED_DATE = "2026-07-13"


@dataclass(frozen=True)
class ExpectedOutput:
    source_id: str
    media_type: str
    generated_path: str
    extractor: str
    status: str
    warnings: list[str]
    ocr_used: bool
    language_hint: str
    layout_warnings: list[str]
    extraction_method: str
    body_text: str = ""
    caption_text: str = ""
    figure_text: str = ""
    diagram_transcription: str = ""

    @property
    def plain_text(self) -> str:
        parts = [
            self.body_text.strip(),
            self.caption_text.strip(),
            self.diagram_transcription.strip(),
        ]
        return "\n\n".join(part for part in parts if part)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_lines(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width))
    return lines


def write_simple_text_pdf(path: Path) -> None:
    """Write a one-page text-layer PDF without external PDF dependencies."""
    left_text = (
        "Phase 0 PDF sample. The extractor should detect that this PDF has a "
        "native text layer before considering OCR. Body text is arranged in a "
        "left column and a right column so the future extractor must preserve "
        "reading order by using coordinates."
    )
    right_text = (
        "The caption below is not part of the main paragraph. It should be "
        "stored as caption_text. Header and footer strings are useful for "
        "testing whether layout cleanup can ignore repeated noise."
    )
    caption = (
        "Figure 1: Expected extraction flow from native PDF text to structured "
        "text fields."
    )
    content_lines: list[str] = []

    def emit(x: int, y: int, text: str, size: int = 11) -> None:
        content_lines.append(
            f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm ({pdf_escape(text)}) Tj ET"
        )

    emit(72, 754, "Header: Library Skill Phase 0 PDF Demo", 9)
    emit(72, 720, "PDF Layout Note", 18)
    emit(72, 690, "Left column", 12)
    y = 670
    for line in wrap_lines(left_text, 48):
        emit(72, y, line)
        y -= 16
    emit(330, 690, "Right column", 12)
    y = 670
    for line in wrap_lines(right_text, 42):
        emit(330, y, line)
        y -= 16
    emit(168, 470, "[ diagram placeholder ]", 13)
    emit(120, 444, caption, 10)
    emit(72, 52, "Footer: local demo page 1", 9)

    stream = "\n".join(content_lines).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f\n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n\n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(output))


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int]) -> None:
    draw.line([start, end], fill=(35, 52, 68), width=4)
    x1, y1 = start
    x2, y2 = end
    if x2 >= x1:
        head = [(x2, y2), (x2 - 16, y2 - 9), (x2 - 16, y2 + 9)]
    else:
        head = [(x2, y2), (x2 + 16, y2 - 9), (x2 + 16, y2 + 9)]
    draw.polygon(head, fill=(35, 52, 68))


def draw_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    fill: tuple[int, int, int],
) -> None:
    title_font = load_font(24)
    body_font = load_font(16)
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=(35, 52, 68), width=3)
    x1, y1, x2, _ = box
    draw.text((x1 + 18, y1 + 20), title, font=title_font, fill=(18, 32, 43))
    wrapped = textwrap.wrap(subtitle, width=24)
    y = y1 + 58
    for line in wrapped[:3]:
        draw.text((x1 + 18, y), line, font=body_font, fill=(18, 32, 43))
        y += 22
    draw.line((x1 + 18, y2 := box[3] - 22, x2 - 18, y2), fill=(120, 135, 145), width=1)


def write_diagram_jpg(path: Path) -> None:
    image = Image.new("RGB", (1200, 750), color=(248, 246, 239))
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    small_font = load_font(17)
    draw.text(
        (48, 34),
        "Phase 0 JPG sample: document intake flow",
        font=title_font,
        fill=(19, 40, 52),
    )
    draw.text(
        (50, 84),
        "This diagram is intentionally visual. OCR candidates are not enough; the extractor needs diagram_transcription.",
        font=small_font,
        fill=(65, 82, 92),
    )
    boxes = {
        "source": (60, 180, 300, 330),
        "extractor": (370, 180, 610, 330),
        "structured": (680, 180, 920, 330),
        "organized": (680, 450, 920, 600),
        "review": (370, 450, 610, 600),
    }
    draw_box(draw, boxes["source"], "Source file", "HTML, PDF, or JPG saved in source_samples", (219, 236, 226))
    draw_box(draw, boxes["extractor"], "Extractor", "Produces plain_text plus structured_text fields", (236, 228, 206))
    draw_box(draw, boxes["structured"], "Structured text", "body, caption, figure, diagram fields", (220, 229, 242))
    draw_box(draw, boxes["review"], "Human review", "Required when OCR is low confidence", (242, 224, 220))
    draw_box(draw, boxes["organized"], "Organized item", "metadata header and searchable Markdown", (230, 222, 240))
    draw_arrow(draw, (300, 255), (370, 255))
    draw_arrow(draw, (610, 255), (680, 255))
    draw_arrow(draw, (800, 330), (800, 450))
    draw_arrow(draw, (680, 525), (610, 525))
    draw_arrow(draw, (490, 450), (490, 330))
    draw.text(
        (960, 210),
        "Warning examples:\n- scattered labels\n- arrows are relationships\n- OCR may miss boxes\n- review before search",
        font=small_font,
        fill=(88, 69, 48),
        spacing=8,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=92)


def source_texts() -> dict[str, str]:
    return {
        "requirements_note": """\
Title: Minimum library feature note

The alpha library should accept a source file, keep the original file path,
extract readable text, and create one searchable organized item.

Required behavior:
- Keep source files separate from software code.
- Create plain_text.txt for search.
- Keep metadata in extraction_record.json and source_refs.json.
- Add a human-readable metadata header only to organized index.md.

Non-goal:
The alpha does not need automatic summarization or perfect OCR.
""",
        "pdf_layout_note": """\
Title: PDF layout note

This source text is rendered into a two-column PDF. The expected extractor
should use the native text layer, identify header and footer noise, keep body
text in reading order, and store the figure caption separately.

Caption:
Figure 1: Expected extraction flow from native PDF text to structured text
fields.
""",
        "diagram_note": """\
Title: Diagram note

This text becomes a JPG diagram. The future image extractor should not pretend
that OCR alone can understand the diagram. It should save OCR candidates as
figure_text, then rely on a reviewed diagram_transcription for search.
""",
    }


def write_html_sample(path: Path) -> None:
    html = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Minimum library feature note</title>
  <style>nav, footer { color: #777; }</style>
</head>
<body>
  <nav>Home | Tags | Folder map | Import queue</nav>
  <main>
    <article>
      <h1>Minimum library feature note</h1>
      <p>The alpha library should accept a source file, keep the original file path, extract readable text, and create one searchable organized item.</p>
      <h2>Required behavior</h2>
      <ul>
        <li>Keep source files separate from software code.</li>
        <li>Create <code>plain_text.txt</code> for search.</li>
        <li>Keep metadata in <code>extraction_record.json</code> and <code>source_refs.json</code>.</li>
        <li>Add a human-readable metadata header only to organized <code>index.md</code>.</li>
      </ul>
      <h2>Non-goal</h2>
      <p>The alpha does not need automatic summarization or perfect OCR.</p>
    </article>
  </main>
  <footer>Demo footer that the extractor should treat as navigation noise.</footer>
</body>
</html>
"""
    write_text(path, html)


def expected_outputs() -> list[ExpectedOutput]:
    return [
        ExpectedOutput(
            source_id="requirements_note_html",
            media_type="text/html",
            generated_path="generated/html/requirements_note.html",
            extractor="html_to_text",
            status="ok",
            warnings=["navigation and footer should be removed before indexing"],
            ocr_used=False,
            language_hint="eng",
            layout_warnings=[],
            extraction_method="html_dom_cleanup",
            body_text=(
                "Minimum library feature note\n\n"
                "The alpha library should accept a source file, keep the original file path, "
                "extract readable text, and create one searchable organized item.\n\n"
                "Required behavior\n"
                "- Keep source files separate from software code.\n"
                "- Create plain_text.txt for search.\n"
                "- Keep metadata in extraction_record.json and source_refs.json.\n"
                "- Add a human-readable metadata header only to organized index.md.\n\n"
                "Non-goal\n"
                "The alpha does not need automatic summarization or perfect OCR."
            ),
        ),
        ExpectedOutput(
            source_id="pdf_layout_note_pdf",
            media_type="application/pdf",
            generated_path="generated/pdf/pdf_layout_note.pdf",
            extractor="pdf_to_text",
            status="ok",
            warnings=["header and footer are layout noise and should not dominate search text"],
            ocr_used=False,
            language_hint="eng",
            layout_warnings=[
                "two-column reading order",
                "caption should be separated from body_text",
                "native text layer is present",
            ],
            extraction_method="text_layer_coordinate_blocks",
            body_text=(
                "PDF Layout Note\n\n"
                "Phase 0 PDF sample. The extractor should detect that this PDF has a native text layer "
                "before considering OCR. Body text is arranged in a left column and a right column so "
                "the future extractor must preserve reading order by using coordinates.\n\n"
                "The caption below is not part of the main paragraph. It should be stored as caption_text. "
                "Header and footer strings are useful for testing whether layout cleanup can ignore repeated noise."
            ),
            caption_text=(
                "Figure 1: Expected extraction flow from native PDF text to structured text fields."
            ),
        ),
        ExpectedOutput(
            source_id="diagram_note_jpg",
            media_type="image/jpeg",
            generated_path="generated/image/diagram_note.jpg",
            extractor="image_ocr_to_text",
            status="needs_review",
            warnings=["OCR candidates are not sufficient to recover arrows or relationships"],
            ocr_used=True,
            language_hint="eng",
            layout_warnings=[
                "diagram contains scattered labels",
                "arrows encode relationships",
                "human-reviewed diagram_transcription is required for search",
            ],
            extraction_method="ocr_candidate_plus_manual_reviewed_diagram",
            caption_text="Phase 0 JPG sample: document intake flow.",
            figure_text=(
                "OCR candidate labels: Source file; Extractor; Structured text; "
                "Human review; Organized item; Warning examples."
            ),
            diagram_transcription=(
                "Diagram transcription:\n"
                "- Source file stores HTML, PDF, or JPG in source_samples.\n"
                "- Extractor creates plain_text.txt and structured_text.json.\n"
                "- Structured text separates body, caption, figure, and diagram fields.\n"
                "- Low-confidence OCR goes to Human review before final search use.\n"
                "- Organized item receives metadata header and searchable Markdown.\n"
                "- Arrows show Source file -> Extractor -> Structured text -> Organized item, with Human review as a correction loop."
            ),
        ),
    ]


def write_expected_output(output: ExpectedOutput) -> None:
    base = ROOT / "expected_extracted" / output.source_id
    record = {
        "source_id": output.source_id,
        "source_path": output.generated_path,
        "media_type": output.media_type,
        "extractor": output.extractor,
        "status": output.status,
        "warnings": output.warnings,
        "ocr_used": output.ocr_used,
        "language_hint": output.language_hint,
        "layout_warnings": output.layout_warnings,
        "extraction_method": output.extraction_method,
    }
    structured = {
        "body_text": output.body_text,
        "caption_text": output.caption_text,
        "figure_text": output.figure_text,
        "diagram_transcription": output.diagram_transcription,
    }
    write_text(base / "plain_text.txt", output.plain_text)
    write_json(base / "extraction_record.json", record)
    write_json(base / "structured_text.json", structured)


def metadata_header(*, summary: str, tags: str, source_path: str) -> str:
    return "\n".join(
        [
            '""""""',
            f"収集日：{COLLECTED_DATE}",
            f"収集URL：local:{source_path}",
            f"ファイルの要約：{summary}",
            f"タグ：{tags}",
            '""""""',
            "",
        ]
    )


def write_organized_examples(outputs: list[ExpectedOutput]) -> None:
    examples = {
        "requirements_note_html": (
            "requirements_note",
            "HTML から抽出した alpha 最小機能の要件メモ。",
            "alpha, requirements, html",
            "## 整理済みメモ\n\nHTML source から navigation と footer を除外し、本文、箇条書き、non-goal を検索用の Markdown として整理する。",
        ),
        "pdf_layout_note_pdf": (
            "pdf_layout_note",
            "2 段組 PDF から本文と caption を分けるための確認メモ。",
            "pdf, layout, caption",
            "## 整理済みメモ\n\nPDF source は native text layer を優先し、header/footer を layout noise として扱う。caption は本文とは別の文脈として保持する。",
        ),
        "diagram_note_jpg": (
            "diagram_note",
            "図表 JPG を OCR 候補と diagram transcription に分ける確認メモ。",
            "image, ocr, diagram",
            "## 整理済みメモ\n\nJPG source は OCR candidate だけで検索に投入せず、human review 済みの diagram transcription を検索用 text として使う。",
        ),
    }
    by_id = {output.source_id: output for output in outputs}
    for source_id, (item_id, summary, tags, body) in examples.items():
        output = by_id[source_id]
        item_dir = ROOT / "organized_examples" / item_id
        write_text(
            item_dir / "index.md",
            metadata_header(summary=summary, tags=tags, source_path=output.generated_path)
            + body,
        )
        write_json(
            item_dir / "source_refs.json",
            {
                "item_id": item_id,
                "source_ids": [source_id],
                "source_paths": [output.generated_path],
                "expected_extracted_dir": f"expected_extracted/{source_id}",
                "note": "This is a phase 0 organized example, not production data.",
            },
        )


def write_manifest(outputs: list[ExpectedOutput]) -> None:
    samples = []
    for output in outputs:
        source_text = {
            "requirements_note_html": "source_texts/requirements_note.txt",
            "pdf_layout_note_pdf": "source_texts/pdf_layout_note.txt",
            "diagram_note_jpg": "source_texts/diagram_note.txt",
        }[output.source_id]
        item_id = output.source_id.removesuffix("_html").removesuffix("_pdf").removesuffix("_jpg")
        samples.append(
            {
                "source_id": output.source_id,
                "source_text": source_text,
                "generated_file": output.generated_path,
                "media_type": output.media_type,
                "expected_extracted_dir": f"expected_extracted/{output.source_id}",
                "organized_example_dir": f"organized_examples/{item_id}",
                "planned_processing": [
                    "read generated source",
                    "write plain_text.txt without metadata header",
                    "write extraction_record.json and structured_text.json",
                    "write organized index.md with metadata header",
                ],
            }
        )
    write_json(
        ROOT / "manifest.json",
        {
            "artifact": "phase0_reverse_sample_demo",
            "generated_at": COLLECTED_DATE,
            "purpose": (
                "Make the future extraction pipeline tangible by generating "
                "HTML, PDF, and JPG from known source texts, then storing the "
                "expected extraction outputs."
            ),
            "samples": samples,
        },
    )


def write_readme(outputs: list[ExpectedOutput]) -> None:
    rows = "\n".join(
        f"| `{output.source_id}` | `{output.generated_path}` | `expected_extracted/{output.source_id}/` |"
        for output in outputs
    )
    readme = f"""\
# Phase 0 Reverse Sample Demo

この directory は、Issue #6 の「完成品の実態がつかみにくい」という指摘に対する
Phase 0 の確認用 sub-artifact である。

先に 3 つの短い source text を作り、それを逆向きに HTML / PDF / JPG へ変換した。
そのうえで、将来 extractor が出すべき `plain_text.txt`、
`extraction_record.json`、`structured_text.json`、および
metadata header 付き `organized_examples/*/index.md` を置いた。

## 見る順序

1. `source_texts/` で元文章を見る。
2. `generated/` で HTML / PDF / JPG に変換された原本を見る。
3. `expected_extracted/` で extractor の期待出力を見る。
4. `organized_examples/` で metadata header 付きの整理済み item を見る。
5. `manifest.json` で対応関係を確認する。

## Sample Mapping

| source_id | generated source | expected extraction |
| --- | --- | --- |
{rows}

## 確認コマンド

```sh
python3 sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generate_reverse_samples.py
python3 -m json.tool sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/manifest.json >/tmp/phase0_manifest_check.json
find sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/expected_extracted -name '*.json' -print -exec python3 -m json.tool {{}} \\; >/tmp/phase0_expected_json_check.txt
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/pdf/pdf_layout_note.pdf
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/image/diagram_note.jpg
```

## 処理イメージ

HTML sample は、`nav` と `footer` を落として本文、見出し、箇条書きを
`body_text` として保存する想定である。

PDF sample は、text layer を持つ 2 段組文書として扱う。将来の extractor は
OCR に逃げる前に native text を確認し、座標で本文順序を作り、
caption を `caption_text` に分ける。

JPG sample は、OCR 候補だけで文章化しない。図中 label は `figure_text` に置き、
検索用には human review 済みの `diagram_transcription` を使う。

## metadata header contract

`organized_examples/*/index.md` は Issue #7 の metadata header contract に合わせ、
先頭に `収集日`、`収集URL`、`ファイルの要約`、`タグ` を置く。
`expected_extracted/*/plain_text.txt` には metadata header を付けない。
"""
    write_text(ROOT / "README.md", readme)


def main() -> None:
    for name, content in source_texts().items():
        write_text(ROOT / "source_texts" / f"{name}.txt", content)

    write_html_sample(ROOT / "generated" / "html" / "requirements_note.html")
    write_simple_text_pdf(ROOT / "generated" / "pdf" / "pdf_layout_note.pdf")
    write_diagram_jpg(ROOT / "generated" / "image" / "diagram_note.jpg")

    outputs = expected_outputs()
    for output in outputs:
        write_expected_output(output)
    write_organized_examples(outputs)
    write_manifest(outputs)
    write_readme(outputs)


if __name__ == "__main__":
    main()
