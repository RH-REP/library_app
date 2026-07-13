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
