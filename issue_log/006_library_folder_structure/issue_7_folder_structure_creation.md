# Issue #7 Folder Structure Creation

## 依頼

follow-up comment で、前回レビューの「案B: 独立した library skill として置く」を採用し、
まずフォルダ構成を作成するよう依頼された。

あわせて、他に相談するレビュー項目があるか確認された。

## 実施内容

- `main_artifact/library_skill/` を作成した。
- `main_artifact/library_skill/extractors/` と `schemas/` を作成した。
- HTML / PDF / image OCR extractor の Python skeleton を追加した。
- extraction record と source manifest の最小 JSON schema を追加した。
- `main_artifact/private_data/programming_tech_library/` 配下に first cut のフォルダ構成を作成した。
- `process_log.csv` の header、template、README を追加した。
- `main_artifact/README.md` と `main_artifact/web_app_directory_plan.md` を更新した。
- `.gitignore` を更新し、実データは拾いすぎず、README、template、schema、log header は追跡できるようにした。

## 残るレビュー項目

- source ID と item ID の境界。
- `items.jsonl` を正本にするか、DB へ移すか。
- OCR 結果の保存範囲。
- Explorer UI で raw source をどこまで表示するか。
- private data をどの範囲まで commit するか。

## できたもの

- `main_artifact/library_skill/`
- `main_artifact/private_data/programming_tech_library/` の first cut フォルダ構成
- `sub_artifact/006_library_folder_structure/artifact.md` の follow-up 追記
