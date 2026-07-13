# Work Log

## 2026-07-13

- Issue #7 の本文を確認した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` はこの時点では存在しないことを確認した。
- 代わりに `main_artifact/README.md`、`main_artifact/web_app_directory_plan.md`、
  `main_artifact/web_app/README.md` を確認した。
- `main_artifact/web_app/index.html` の Explorer UI と demo data の path、kind、tag、status の扱いを確認した。
- `main_artifact/private_data/programming_tech_library/README.md` の既存構成案を確認した。
- `sub_artifact/005_multiformat_text_extraction/artifact.md` を確認し、HTML / PDF / image から
  `plain_text.txt` と `extraction_record.json` を作る前提を取り込んだ。
- `sub_artifact/006_library_folder_structure/` を作成した。
- ユーザー案の `input/`、`process_log.csv`、`organized_data/`、`raw_data/`、
  `.library_skill` を実運用の観点からレビューした。
- `raw_sources/`、`extracted_text/`、`organized_data/`、`library_records/` を分ける first cut を提案した。
- `issue_log/006_library_folder_structure/issue_7_library_folder_structure_review.md` を作成した。
- follow-up comment で、案Bの独立 `library_skill/` とフォルダ構成作成が承認された。
- `main_artifact/library_skill/`、`extractors/`、`schemas/` を作成し、抽出本体を持たない Python skeleton を置いた。
- `main_artifact/private_data/programming_tech_library/` 配下に `input/`、`raw_sources/`、
  `extracted_text/`、`organized_data/`、`library_records/`、`research_requests/`、
  `review_queue/`、`notes/` を作成した。
- `process_log.csv`、schema、template、各ディレクトリの README を追加した。
- `main_artifact/README.md` と `main_artifact/web_app_directory_plan.md` を更新した。
- 残るレビュー項目を `artifact.md` と issue log に追記した。
- follow-up comment で、整理済み text 冒頭にメタ情報エリアを作りたいという依頼を確認した。
- `organized_data/{item_id}/index.md` の metadata block 契約を整理した。
- `organized_data/_template/index.md`、`organized_data/README.md`、`library_records/items.example.jsonl` を更新した。
- `sub_artifact/006_library_folder_structure/metadata_header_contract.md` を追加した。
- `issue_log/006_library_folder_structure/issue_7_organized_text_metadata_contract.md` を追加した。
