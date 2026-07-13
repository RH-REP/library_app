# Issue #6 Review 1 Report

## 依頼

ユーザーは、レビューを行うための report と、実際に手元で試すためのコマンドがあるか確認した。

## 対応

Review 1: Contract Review 用に、次の report を追加した。

- `sub_artifact/005_multiformat_text_extraction/review_1_contract_review_report.md`

## report に含めた内容

- レビュー対象 file
- 今回確認してほしい判断
- Review 1 の通過条件
- Python compile command
- JSON schema syntax check command
- `write_extraction_result()` の contract output smoke test
- 生成物の目視確認 command
- `git diff --check`

## 判断

Review 1 では、実際の HTML/PDF/OCR extraction 品質ではなく、次を確認する。

- `plain_text.txt`
- `extraction_record.json`
- `structured_text.json`
- metadata header を `plain_text.txt` に付けない境界
- 低信頼な `figure_text` を default の検索 text に混ぜない境界
