# Organized Data

item ID ごとに、整理AIまたは人間がまとめた知識単位を保存する場所である。

想定単位:

```text
organized_data/
└── item_YYYYMMDD_NNN_short_slug/
    ├── index.md
    ├── source_refs.json
    └── notes.md
```

1 item は 1 source と限らない。複数の PDF、HTML、画像を 1 つの知識単位として
まとめる場合は、`source_refs.json` で参照元 source ID を列挙する。

## `index.md` 冒頭メタ情報

`index.md` の先頭には、整理AIと人間がすぐ読める metadata block を置く。

```text
""""""
収集日：YYYY-MM-DD
収集URL：https://example.com/source
ファイルの要約：1〜3文で内容を要約する。
タグ：tag1, tag2
""""""
```

この block は表示・編集しやすさのために置く。機械的な正本は
`source_refs.json`、`library_records/items.jsonl`、source manifest 側にも残す。

運用ルール:

- metadata block は `index.md` の最初の行から始める。
- 開始行と終了行は `""""""` に統一する。
- 最低項目は `収集日`、`収集URL`、`ファイルの要約`、`タグ` とする。
- 不明な値は空欄にせず `未確認` と書く。
- `タグ` は comma-separated の短い語にする。
