# Issue #6 Python Skill Set and Implementation Steps

## 依頼

Issue #6 の comment follow-up として、

- Python program 前提で
- HTML のタグ処理
- PDF の取り扱い
- OCR

に必要な skill set を調べ、実装工程をより具体的に書くよう依頼された。

## 今回の整理

### 推奨 stack

- HTML:
  `beautifulsoup4` + `lxml`
- PDF:
  `pypdf` + `PyMuPDF`
- image OCR:
  `Pillow` + `pytesseract` + Tesseract
- scanned PDF OCR:
  `ocrmypdf`

### 役割分担

- HTML は Beautiful Soup で本文候補を抜き、`lxml` を parser backend と補助整形に使う。
- PDF は `pypdf` を標準経路にし、抽出崩れ時だけ `PyMuPDF` を fallback として使う。
- OCR は Python package だけで完結せず、Tesseract binary と language data を先に確認する。
- scanned PDF は text PDF と同じ経路に混ぜず、OCRmyPDF 経路へ分離する。

## 実装工程

1. 環境確認
2. 共通 `ExtractionRecord` と出力 contract の固定
3. HTML extractor first cut
4. text PDF extractor first cut
5. image OCR extractor first cut
6. scanned PDF OCR bridge
7. fixture 回帰確認

## 判断

- alpha 最低構成は HTML と text PDF を先に安定させるのが妥当。
- image OCR は baseline 可否判断までは alpha で扱える。
- scanned PDF OCR は設計まで alpha 必須、実装は次 issue に分けてもよい。

## 反映先

- `sub_artifact/005_multiformat_text_extraction/artifact.md`
- `sub_artifact/005_multiformat_text_extraction/plan.md`
- `sub_artifact/005_multiformat_text_extraction/work_log.md`

## 参照した一次情報

- Beautiful Soup documentation:
  https://beautiful-soup-4.readthedocs.io/en/latest/
- lxml HTML documentation:
  https://lxml.de/lxmlhtml.html
- pypdf text extraction:
  https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- PyMuPDF recipes:
  https://pymupdf.readthedocs.io/en/latest/recipes-text.html
- pytesseract README:
  https://github.com/madmaze/pytesseract
- Tesseract user manual:
  https://tesseract-ocr.github.io/tessdoc/
- OCRmyPDF API:
  https://ocrmypdf.readthedocs.io/en/latest/api.html
