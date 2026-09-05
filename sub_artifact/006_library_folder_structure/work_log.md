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
- follow-up comment で、既存 viewer demo と組み合わせた静的HTMLで完成品イメージを作る依頼を確認した。
- `sub_artifact/006_library_folder_structure/viewer_demo.html` を追加した。
- GitHub Pages 用に `docs/sub_artifact/006_library_folder_structure/viewer_demo.html` へ同じ HTML をミラーした。
- Explorer、metadata header panel、raw content pane、source pipeline を 1 つの静的HTMLで確認できるようにした。
- HTML parse、duplicate id check、docs mirror の一致確認、埋め込み JavaScript の `node --check` を実行した。

## 2026-07-14

- follow-up comment で、Phase 0 sample と static viewer を組み合わせ、
  完成品として確認できるものを作る依頼を確認した。
- `sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/` の
  `generated/`、`expected_extracted/`、`organized_examples/`、`manifest.json` を確認した。
- `main_artifact/web_app/index.html` を正本として、reverse sample 統合版 static viewer に更新した。
- `docs/main_artifact/web_app/index.html`、`sub_artifact/006_library_folder_structure/viewer_demo.html`、
  `docs/sub_artifact/006_library_folder_structure/viewer_demo.html` を同じ内容へ同期した。
- 統合 viewer で、`raw_text`、`extracted_text`、metadata header 付き organized item を
  1 つの Explorer / preview / raw pane / source pipeline で辿れるようにした。
- PDF と JPG は static HTML 内に preview 用 data URI として埋め込み、docs mirror でも確認できるようにした。
- 追加フィードバックを受け、`source_texts/` の段階を viewer から外し、
  pipeline を `raw_text -> extracted_text -> organized item` に変更した。
- 右側の raw pane に `Save edit` と `Reset` を追加し、HTML 内メモリ上で編集を preview に反映できるようにした。
- follow-up comment で、整理済みメモの追加と tag の追加・編集をできるようにする依頼を確認した。
- `Add memo` を追加し、現在の sample に対応する organized item へ `## 追加メモ YYYY-MM-DD` を追記できるようにした。
- tag editor と `Apply tags` を追加し、comma-separated の tag を HTML 内メモリで追加・編集できるようにした。
- follow-up comment で、正規用語を `source_data`、`extracted_data`、`organized_data` に整理する方針を確認した。
- `main_artifact/private_data/programming_tech_library/` の `raw_sources/` を `source_data/`、
  `extracted_text/` を `extracted_data/` に改名した。
- `extracted_data/_template/` に `raw_text.example.txt`、`extracted_text.example.json`、
  `extraction_record.example.json` の構成を反映した。
- static viewer の仮想 path と source pipeline を `source_data -> raw_text -> extracted_text -> organized_data` に更新した。
