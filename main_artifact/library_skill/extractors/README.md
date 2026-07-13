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

各 extractor は現時点では細部実装を持たず、contract に合う `failed` result を返す。
後続 issue で parser / OCR 処理を差し込む。
