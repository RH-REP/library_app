# Review 1 Report: Extraction Contract

Issue #6 の Phase 1 実装結果をレビューするための report である。

## レビュー対象

- `main_artifact/library_skill/extractors/common.py`
- `main_artifact/library_skill/schemas/extraction_record.schema.json`
- `main_artifact/library_skill/schemas/structured_text.schema.json`
- `main_artifact/library_skill/extractors/README.md`
- `main_artifact/library_skill/README.md`
- `sub_artifact/005_multiformat_text_extraction/implementation_phases.md`

## 今回確認してほしい判断

1. `plain_text.txt` は検索用の合成 text として維持する。
2. `extraction_record.json` は machine metadata に限定する。
3. `structured_text.json` に `body_text`, `caption_text`, `figure_text`,
   `diagram_transcription` を分けて保存する。
4. 低信頼な `figure_text` は default では `plain_text.txt` に混ぜない。
5. metadata header は `extracted_text/{source_id}/plain_text.txt` には付けず、
   `organized_data/{item_id}/index.md` にだけ付ける。

## Review 1 通過条件

- `ExtractionRecord` と `extraction_record.schema.json` の field が対応している。
- `ExtractionResult` と `structured_text.schema.json` の field が対応している。
- `write_extraction_result()` が次の 3 ファイルを出力する。
  - `plain_text.txt`
  - `extraction_record.json`
  - `structured_text.json`
- `plain_text.txt` に metadata header が入らない。
- `figure_text` が default の `plain_text.txt` に混ざらない。

## 手元で試すコマンド

Repository root で実行する。

### 1. Python compile

```bash
python3 -m py_compile \
  main_artifact/library_skill/extractors/common.py \
  main_artifact/library_skill/extractors/html_to_text.py \
  main_artifact/library_skill/extractors/pdf_to_text.py \
  main_artifact/library_skill/extractors/image_ocr_to_text.py
```

期待:
何も出力されず exit code 0。

### 2. JSON schema syntax check

```bash
python3 -m json.tool main_artifact/library_skill/schemas/extraction_record.schema.json >/tmp/extraction_record.schema.pretty.json
python3 -m json.tool main_artifact/library_skill/schemas/structured_text.schema.json >/tmp/structured_text.schema.pretty.json
```

期待:
両方とも exit code 0。

### 3. Contract output smoke test

```bash
python3 - <<'PY'
from pathlib import Path
import json
import tempfile

from main_artifact.library_skill.extractors.common import (
    ExtractionRecord,
    ExtractionResult,
    write_extraction_result,
)

out = Path(tempfile.mkdtemp(prefix="library_contract_review_"))
result = ExtractionResult(
    record=ExtractionRecord(
        source_id="review_sample",
        source_path="local:review_sample",
        media_type="application/pdf",
        extractor="review_contract_test",
        status="needs_review",
        warnings=("sample warning",),
        ocr_used=False,
        language_hint="eng",
        layout_warnings=("two-column layout",),
        extraction_method="coordinate_blocks",
    ),
    body_text="Body text for search.",
    caption_text="Figure 1: sample caption.",
    figure_text="LOW CONFIDENCE OCR SHOULD NOT BE IN DEFAULT PLAIN TEXT",
    diagram_transcription="Diagram: sample reviewed transcription.",
)

write_extraction_result(result, out)

plain_text = (out / "plain_text.txt").read_text(encoding="utf-8")
record = json.loads((out / "extraction_record.json").read_text(encoding="utf-8"))
structured = json.loads((out / "structured_text.json").read_text(encoding="utf-8"))

assert "Body text for search." in plain_text
assert "Figure 1: sample caption." in plain_text
assert "Diagram: sample reviewed transcription." in plain_text
assert "LOW CONFIDENCE OCR" not in plain_text
assert record["extraction_method"] == "coordinate_blocks"
assert record["layout_warnings"] == ["two-column layout"]
assert structured["figure_text"].startswith("LOW CONFIDENCE OCR")

print(out)
PY
```

期待:

- 一時 directory path が表示される。
- その directory に `plain_text.txt`, `extraction_record.json`,
  `structured_text.json` が生成される。
- assertion error が出ない。

### 4. 生成物を目視する

上の command が出力した directory path を `OUT_DIR` に入れて確認する。

```bash
OUT_DIR=/tmp/library_contract_review_xxxxx
sed -n '1,120p' "$OUT_DIR/plain_text.txt"
python3 -m json.tool "$OUT_DIR/extraction_record.json"
python3 -m json.tool "$OUT_DIR/structured_text.json"
```

見る点:

- `plain_text.txt` に metadata header がない。
- `plain_text.txt` に low confidence OCR の `figure_text` が混ざっていない。
- `extraction_record.json` に `extraction_method` と `layout_warnings` がある。
- `structured_text.json` に `body_text`, `caption_text`, `figure_text`,
  `diagram_transcription` がある。

### 5. git diff whitespace check

```bash
git diff --check
```

期待:
何も出力されず exit code 0。

## Review 1 の判定

この contract で問題なければ、次は Review 2 に向けて次を実装する。

- HTML extractor first cut
- PDF coordinate extraction first cut
- Image OCR candidate / diagram transcription first cut

問題がある場合は、Review 1 で contract を戻してから Phase 3 へ進む。
