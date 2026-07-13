# Issue #7 Organized Text Metadata Contract

## 依頼

`organized_data/{contents}/file_A,B,C` に相当する整理済み text の冒頭へ、
収集日、収集URL、ファイルの要約、タグを埋め込む metadata area を作りたい、
という follow-up があった。

## 実施内容

- `organized_data/{item_id}/index.md` の冒頭 metadata block 契約を整理した。
- template の `index.md` 先頭へ metadata block を追加した。
- `organized_data/README.md` に運用ルールを追記した。
- `library_records/items.example.jsonl` に、metadata block と同期する項目例を追加した。
- `sub_artifact/006_library_folder_structure/metadata_header_contract.md` を追加した。

## 判断

- metadata block は表示用・編集用であり、機械処理の唯一の正本にはしない。
- structured data は `source_refs.json`、`library_records/items.jsonl`、source manifest、
  extraction record にも残す。
- format はユーザー指定に近い quoted block を採用し、必須 label を固定する。
