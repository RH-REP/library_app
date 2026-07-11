# Sub Goal: Issue #6 各種原本の plain text 化

## 目的

HTML、PDF、画像を将来 LLM や非 AI 検索へ渡せるように、plain text 化機能の
first cut を独立した workstream として定義する。

## 成果物

- `sub_artifact/005_multiformat_text_extraction/artifact.md`
- `sub_artifact/005_multiformat_text_extraction/plan.md`
- `sub_artifact/005_multiformat_text_extraction/work_log.md`
- `issue_log/005_multiformat_text_extraction/issue_6_multiformat_text_extraction_plan.md`

## 範囲

- HTML -> plain text の first cut 契約を定義する。
- PDF -> plain text の first cut 契約を定義する。
- image -> plain text の first cut 契約を定義する。
- 各機能について 3 段階レビューの工程と完了条件を示す。
- 入力データとして issue #5 で集めた sample を参照する。

## 範囲外

- 実際の extractor 実装。
- OCR エンジンや parser ライブラリの最終選定。
- UI 実装や検索 index 実装。
- scanned PDF の OCR 品質最適化。
