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
    ├── structured_text.schema.json
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

## Phase 1 extraction contract

抽出結果は `extracted_text/{source_id}/` に保存する。

- `plain_text.txt`: search-oriented synthesized text。default では本文・caption・diagram transcription を統合した text として扱う。低信頼な `figure_text` は caller が明示した場合だけ混ぜる。
- `extraction_record.json`: machine metadata。`source_id`、`source_path`、`media_type`、`extractor`、`extraction_method`、`status`、`warnings`、`layout_warnings`、`ocr_used`、`language_hint` を持つ。
- `structured_text.json`: structured text。`body_text`、`caption_text`、`figure_text`、`diagram_transcription` を field 別に保持する。

`extraction_method` は native extraction、OCR、manual transcription など、実際に使った high-level method を記録する。
`layout_warnings` は reading order、caption association、figure/table/diagram の layout fidelity など、構造に関する warning を記録する。

`plain_text.txt` は metadata header を持たない。
metadata header は organized output の `organized_data/{item_id}/index.md` にだけ置く。
