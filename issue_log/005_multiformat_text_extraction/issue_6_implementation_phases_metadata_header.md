# Issue #6 Implementation Phases And Metadata Header

## 依頼

ユーザーは、実装準備として提示した方針に沿って工程を切り、
Issue #7 の metadata header contract を読んで取り込むよう依頼した。

参照した contract:

- `sub_artifact/006_library_folder_structure/metadata_header_contract.md`

## 取り込んだ内容

`organized_data/{item_id}/index.md` の冒頭には、次の metadata block を置く。

```text
""""""
収集日：YYYY-MM-DD
収集URL：https://example.com/source
ファイルの要約：1〜3文で内容を要約する。
タグ：tag1, tag2
""""""
```

必須項目:

- `収集日`
- `収集URL`
- `ファイルの要約`
- `タグ`

不明値は空欄にせず `未確認` とする。
local file だけの場合は `収集URL` に `local:` prefix を使う。

## 反映した工程境界

- `extracted_text/{source_id}/plain_text.txt` には metadata header を付けない。
- `extracted_text/{source_id}/extraction_record.json` は機械処理用 metadata とする。
- `organized_data/{item_id}/index.md` には metadata header を付ける。
- `organized_data/{item_id}/source_refs.json` で元 source ID を辿れるようにする。
- metadata header は表示用であり、機械処理の唯一の正本にはしない。
- structured data は `source_refs.json`、`library_records/items.jsonl`、
  source manifest、`extraction_record.json` と同期する。

## 実装工程

1. 環境と依存の固定
2. Extraction contract 更新
3. metadata header adapter
4. HTML extractor first cut
5. PDF coordinate extraction first cut
6. Image OCR candidate と diagram transcription
7. organized_data bridge
8. 回帰確認

詳細は `sub_artifact/005_multiformat_text_extraction/implementation_phases.md` にまとめた。
