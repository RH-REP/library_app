# Extractors

このディレクトリは、原本ファイルから plain text を作る Python extractor を置く場所である。

予定する module:

- `html_to_text.py`
- `pdf_to_text.py`
- `image_ocr_to_text.py`
- `common.py`

Issue #7 の follow-up で、実装前の Python 雛形を配置した。

## 現在の雛形

- `common.py`: `ExtractionRecord`、`ExtractionResult`、`plain_text.txt` / `extraction_record.json` の出力 helper。
- `html_to_text.py`: HTML extractor の入口。
- `pdf_to_text.py`: PDF extractor の入口。
- `image_ocr_to_text.py`: image OCR extractor の入口。

各 extractor は現時点では細部実装を持たず、`failed` result を返す雛形である。
後続 issue で parser / OCR 処理を差し込む。

## Phase 1 extraction contract

Extractor output は `extracted_text/{source_id}/` 配下に置く。

- `plain_text.txt`: search-oriented synthesized text。default では本文・caption・diagram transcription を連結する。低信頼な `figure_text` は caller が明示した場合だけ混ぜる。
- `extraction_record.json`: machine metadata。本文そのものは入れず、source、extractor、status、warning、OCR 使用有無などを記録する。
- `structured_text.json`: structured text fields。本文や visual element 由来の text を field ごとに保持する。

`extraction_record.json` は `schemas/extraction_record.schema.json` に従う。
Phase 1 では既存 metadata に加えて次を記録する。

- `extraction_method`: native text extraction、OCR、manual transcription など、この source で使った high-level extraction path。
- `layout_warnings`: reading order、caption association、figure/table/diagram layout など、構造や layout fidelity に関する warning。

`structured_text.json` は `schemas/structured_text.schema.json` に従い、次の field を持つ。

- `body_text`: main readable text。
- `caption_text`: figure、table、screenshot などの caption text。
- `figure_text`: figure、chart、screenshot、embedded image 内から検出した text。
- `diagram_transcription`: diagram の構造、flow、label、relationship などの transcription。

`plain_text.txt` には YAML front matter などの metadata header を付けない。
metadata header は organized output の `organized_data/{item_id}/index.md` にだけ置く。
