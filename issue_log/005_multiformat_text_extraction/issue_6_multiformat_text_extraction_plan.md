# Issue #6 Multiformat Text Extraction Plan

## 依頼

HTML、PDF、image を plain text 化する機能を新規 sub-artifact として立ち上げ、
それぞれ 3 段階レビューで工程を示すよう依頼された。

## 実施内容

- `sub_artifact/005_multiformat_text_extraction/` を新設した。
- HTML / PDF / image の text extraction を共通出力 contract で整理した。
- 3 形式それぞれに `レビュー1: contract` `レビュー2: fixture` `レビュー3: integration`
  を定義した。
- issue #5 で集めた source sample を、この機能の入力 fixture として参照する形にした。

## 判断

- 実装順は HTML -> PDF -> image が妥当。
- PDF は first cut では text PDF を優先し、 scanned PDF の OCR は後回しにする。
- image は OCR 品質の不確実性が高いため、alpha 完了条件に含める前に review gate を置く。

## できたもの

- `sub_artifact/005_multiformat_text_extraction/sub_goal.md`
- `sub_artifact/005_multiformat_text_extraction/plan.md`
- `sub_artifact/005_multiformat_text_extraction/work_log.md`
- `sub_artifact/005_multiformat_text_extraction/artifact.md`

## 次にそのまま切れる issue

- HTML extractor first cut
- text PDF extractor first cut
- image OCR の alpha 採否判断
