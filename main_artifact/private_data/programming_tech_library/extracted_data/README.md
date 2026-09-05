# Extracted Data

source ID ごとに、原本から抽出した text と metadata を保存する場所である。
`raw_text` は OCR や parser の出力に近い一次 text、`extracted_text` は人間または整理処理が編集できる構造化 text とする。

想定単位:

```text
extracted_data/
└── src_YYYYMMDD_NNN_short_slug/
    ├── raw_text.txt
    ├── extracted_text.json
    └── extraction_record.json
```

ここに置く text は整理済み知識ではない。OCR ノイズ、HTML navigation、
PDF 読み順崩れが残る可能性があるため、`organized_data/` と分ける。
