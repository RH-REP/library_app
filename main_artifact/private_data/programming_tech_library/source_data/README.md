# Source Data

source ID ごとに、PDF、JPG、HTML などの原本を保存する場所である。

想定単位:

```text
source_data/
└── src_YYYYMMDD_NNN_short_slug/
    ├── original/
    ├── source_manifest.json
    └── attachments/
```

原本は原則として変更しない。OCR、text 抽出、整理の結果は別ディレクトリに保存する。
