# Plan

## 方針

Issue #7 は実装そのものではなく、ユーザー案に対するフォルダ名、命名規則、
運用上のレビューを求めている。したがって、この sub-artifact では
`main_artifact/private_data/programming_tech_library/` の次段階案として、
データの流れに沿った最小構成を提案する。

## 作業項目

- [x] `main_artifact/goal.md` と `main_artifact/development_process.md` の有無を確認する。
- [x] `main_artifact/README.md`、`web_app_directory_plan.md`、`web_app/README.md` を読む。
- [x] `main_artifact/web_app/index.html` の Explorer UI と表示データを確認する。
- [x] 既存の private data / fixture 構成を確認する。
- [x] issue #6 の multiformat text extraction 方針を確認する。
- [x] `sub_artifact/006_library_folder_structure/` を作成する。
- [x] ユーザー案の良い点、危険な点、修正案を整理する。
- [x] 実用的な first cut のフォルダ構成と命名規則を定義する。
- [x] issue log を残す。
- [x] follow-up comment で承認された案Bに合わせ、`main_artifact/library_skill/` を作成する。
- [x] private data の first cut フォルダ構成を作成する。
- [x] `process_log.csv`、schema、template、README を追加する。
- [x] 残るレビュー項目を整理する。

## 判断

- `input/` は未処理 dropbox として残す。
- 原本保存は `raw_data/` より既存方針に近い `raw_sources/` が分かりやすい。
- text 抽出結果は `organized_data/` へ直行させず、`extracted_text/` を挟む方が安全である。
- `organized_data/` は「整理AIが読書・知識単位にまとめた結果」に限定する。
- 処理履歴は `process_log.csv` だけに寄せず、各 source の `source_manifest.json` と併用する。
- `.library_skill` は hidden directory なので、Python package としては `library_skill/` または
  `web_app/scripts/extractors/` の方が扱いやすい。
- ユーザーが案Bを承認したため、`main_artifact/library_skill/` を独立した補助 program 置き場として採用する。
- 実装前の段階では、抽出本体を持たない contract-shaped な Python skeleton までに留める。
- private data の実体ファイルは template と header に留め、実PDFや実OCR出力は追加しない。
