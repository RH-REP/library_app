# Work Log

## 2026-07-11

- Issue #6 の本文を確認した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` を確認した。
- issue #5 で保存した synthetic fixture と actual source sample の両方を入力候補として確認した。
- `.core_program/assignment_state.json` を更新し、issue #6 を `sub_artifact/005_multiformat_text_extraction` に割り当てた。
- HTML、PDF、image の plain text 化を別機能としてではなく、共通出力 contract を持つ 3 系統の extractor として整理した。
- 各機能の 3 段階レビュー工程と完了条件を `artifact.md` にまとめた。
- `issue_log/005_multiformat_text_extraction/issue_6_multiformat_text_extraction_plan.md` を作成した。
- HTML / PDF / OCR の Python 向け一次情報を確認し、推奨 stack を `artifact.md` に追記した。
- `beautifulsoup4` + `lxml`、`pypdf` + `PyMuPDF`、`pytesseract` + Tesseract、`ocrmypdf` の役割分担を整理した。
- 実装工程を「環境確認 -> 共通 contract -> HTML -> PDF -> image OCR -> scanned PDF OCR -> 回帰確認」に分解した。
- `issue_log/005_multiformat_text_extraction/issue_6_python_skillset_and_implementation_steps.md` を追加した。

## 2026-07-13

- Issue #6 の follow-up comment を確認した。
- Issue #7 のフォルダ構成レビューを確認し、Python extractor の置き場を `main_artifact/library_skill/extractors/` と判断した。
- `common.py`、`html_to_text.py`、`pdf_to_text.py`、`image_ocr_to_text.py` の雛形を追加した。
- 細部実装は入れず、共通 contract に合う `ExtractionResult` を返す構成だけ固定した。
- `main_artifact/library_skill/README.md` と `extractors/README.md` を雛形配置後の内容へ更新した。
- `issue_log/005_multiformat_text_extraction/issue_6_extractor_skeleton_from_issue_7_layout.md` を追加した。

## 2026-07-13 follow-up: Issue #5 sample cleanup 反映

- Issue #5 の follow-up により synthetic fixture が削除されたことを確認した。
- text extraction の入力説明を actual source sample 中心へ更新した。

## 2026-07-13 follow-up: Issue #5 image sample replacement 反映

- Issue #5 の follow-up により画像 sample がソフトウェア開発プロセス図へ差し替えられたことを確認した。
- image OCR の確認対象を `royce_final_model_waterfall.png` に更新した。

## 2026-07-13 follow-up: PDF / image sample visual review

- Issue #6 の追加コメントを確認した。
- `software_through_pictures_arxiv.pdf` を Poppler で 3 ページ分レンダリングし、2 段組、図、caption、縦向き arXiv ラベルを確認した。
- `pdftotext -layout` で text layer は抽出できるが、本文と図キャプションが混ざることを確認した。
- `royce_final_model_waterfall.png` を目視し、Tesseract CLI で原本 OCR と 3 倍拡大・二値化 OCR を試した。
- 画像 OCR は誤読が多いため、diagram transcription と human review を前提にする判断を artifact に追記した。
- `issue_log/005_multiformat_text_extraction/issue_6_pdf_image_sample_textification.md` を作成した。
