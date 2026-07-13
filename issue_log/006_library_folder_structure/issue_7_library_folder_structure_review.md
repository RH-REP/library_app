# Issue #7 Library Folder Structure Review

## 依頼

Web app の Explorer UI をベースに、図書館アプリで実際に使うフォルダ構成を考え、
フォルダ名、命名規則、実践的なレビューとしてコメントするよう依頼された。

ユーザー案の主な要素:

- `.library_skill/`: PDF、HTML などを text 変換する Python program
- `input/`: ユーザーや調査Agentが raw data を置く場所
- `process_log.csv`: 整理AIの処理状況ログ
- `organized_data/{contents}/`: 整理AIが text で保存する場所
- `raw_data/{contents}/`: 整理AIが raw data を保存する場所

## 実施内容

- `sub_artifact/006_library_folder_structure/` を新設した。
- 既存の `main_artifact/web_app_directory_plan.md` と Web app demo UI を確認した。
- 既存の private data 方針と issue #6 の text extraction 方針に合わせて、
  実運用向けの first cut 構成を整理した。
- ユーザー案の良い点、危険な点、修正案を `artifact.md` にまとめた。

## 判断

- `input/` は未処理 dropbox として採用する。
- `raw_data/` より、既存方針に合わせて `raw_sources/` を推奨する。
- text 抽出結果は `organized_data/` へ直行させず、`extracted_text/` を挟む。
- `organized_data/` は source file 単位ではなく item/content 単位にする。
- `.library_skill` は hidden directory ではなく、`library_skill/` または
  `web_app/scripts/extractors/` として見える場所に置く方がよい。

## できたもの

- `sub_artifact/006_library_folder_structure/sub_goal.md`
- `sub_artifact/006_library_folder_structure/plan.md`
- `sub_artifact/006_library_folder_structure/work_log.md`
- `sub_artifact/006_library_folder_structure/artifact.md`
- `issue_log/006_library_folder_structure/issue_7_library_folder_structure_review.md`

## 次にそのまま切れる issue

- private data README に first cut フォルダ構成を反映する。
- `source_manifest.json` と `extraction_record.json` の schema を決める。
- `process_log.csv` を更新する intake / extractor の first cut を作る。
