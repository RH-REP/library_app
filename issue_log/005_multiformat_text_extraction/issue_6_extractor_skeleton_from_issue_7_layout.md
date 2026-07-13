# Issue #6 Extractor Skeleton From Issue #7 Layout

## 依頼

Issue #6 の follow-up として、Issue #7 で決まったフォルダ構成を確認し、
そこにまず作成すべき program の雛形を置くよう依頼された。

## 確認した構成

Issue #7 のレビューでは、HTML / PDF / image OCR の Python helper は
`main_artifact/library_skill/extractors/` に置く方針になっている。

## 実施内容

次の雛形を追加した。

- `main_artifact/library_skill/extractors/common.py`
- `main_artifact/library_skill/extractors/html_to_text.py`
- `main_artifact/library_skill/extractors/pdf_to_text.py`
- `main_artifact/library_skill/extractors/image_ocr_to_text.py`

あわせて package 化のために次を追加した。

- `main_artifact/library_skill/__init__.py`
- `main_artifact/library_skill/extractors/__init__.py`

## 判断

- 細部実装はまだ入れない。
- 各 extractor は `extract(source_path, source_id, language_hint)` を入口にする。
- 共通結果は `ExtractionResult` / `ExtractionRecord` にそろえる。
- 現時点では `failed` status と warning を返し、後続 issue で parser / OCR 処理を入れる。

## 次に入れる実装

1. `html_to_text.py` に Beautiful Soup / lxml ベースの本文抽出を入れる。
2. `pdf_to_text.py` に pypdf / PyMuPDF ベースの text PDF 抽出を入れる。
3. `image_ocr_to_text.py` に Pillow / pytesseract ベースの OCR を入れる。
