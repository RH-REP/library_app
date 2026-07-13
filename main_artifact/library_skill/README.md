# Library Skill

このディレクトリは、図書館データを取り込むための独立した補助 program と contract を置く場所である。

first cut では、HTML、PDF、image などの原本から plain text と metadata を作る
Python helper をここに育てる。

想定構成:

```text
library_skill/
├── README.md
├── extractors/
│   ├── README.md
│   ├── common.py
│   ├── html_to_text.py
│   ├── pdf_to_text.py
│   └── image_ocr_to_text.py
└── schemas/
    ├── extraction_record.schema.json
    └── source_manifest.schema.json
```

## 役割

- `extractors/`: HTML、PDF、image OCR などの抽出 program を置く。
- `schemas/`: 抽出結果や原本 manifest の最小 contract を置く。

ここには個別の PDF、画像、HTML snapshot、抽出済み text は置かない。
実データは `main_artifact/private_data/programming_tech_library/` に置く。

## 現在の状態

Issue #7 の follow-up では、まず extractor の Python 雛形だけを置いた。
HTML / PDF / OCR の細部実装は後続 issue で追加する。
