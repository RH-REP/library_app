# Extracted Text

source ID ごとに、原本から機械的に抽出した plain text と metadata を保存する場所である。

想定単位:

```text
extracted_text/
└── src_YYYYMMDD_NNN_short_slug/
    ├── plain_text.txt
    └── extraction_record.json
```

ここに置く text は整理済み知識ではなく、抽出 program の出力である。
OCR ノイズ、HTML navigation、PDF 読み順崩れが残る可能性があるため、
`organized_data/` と分ける。
