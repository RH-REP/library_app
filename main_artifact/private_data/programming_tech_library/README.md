# Programming Tech Library Private Data

このディレクトリは、開発中に使う個別データの置き場である。

Issue #7 のレビューを受け、first cut の実フォルダ構成を次にする。

```text
programming_tech_library/
├── input/
│   └── inbox/
├── process_log.csv
├── raw_sources/
│   └── _template/
│       ├── original/
│       ├── source_manifest.example.json
│       └── attachments/
├── extracted_text/
│   └── _template/
│       ├── plain_text.example.txt
│       └── extraction_record.example.json
├── organized_data/
│   └── _template/
│       ├── index.md
│       ├── source_refs.example.json
│       └── notes.md
├── library_records/
│   ├── sources.csv
│   └── items.example.jsonl
├── research_requests/
├── review_queue/
└── notes/
```

## 役割

- `input/inbox/`: ユーザーや調査Agentが未処理ファイルを置く場所。
- `raw_sources/`: source ID ごとに原本を保存する場所。
- `extracted_text/`: source ID ごとの機械抽出 text を保存する場所。
- `organized_data/`: item ID ごとの整理済み知識を保存する場所。
- `library_records/`: UI、検索、import/export 用の正規化レコードを置く場所。
- `process_log.csv`: intake、抽出、整理の処理履歴を append-only で残すログ。
- `research_requests/`: 追加調査依頼や収集依頼を置く場所。
- `review_queue/`: 失敗、OCR 待ち、人間レビュー待ちの作業メモを置く場所。
- `notes/`: データセット全体に関する運用メモを置く場所。

## 運用ルール

- 原本は `raw_sources/{source_id}/original/` に保存し、原則として変更しない。
- 抽出 text は `extracted_text/{source_id}/plain_text.txt` に保存する。
- 整理済みの知識単位は `organized_data/{item_id}/index.md` に保存する。
- `organized_data/{item_id}/index.md` の冒頭には、収集日、収集URL、要約、タグの metadata block を置く。
- source と item の対応は `source_refs.json` と `library_records/` で管理する。
- 実データの大きな PDF、画像、OCR 出力、個人メモは配布用 software 本体とは別物として扱う。

この配下は、現段階では private な開発履歴として commit してよい。ただし、Web app 本体とは別物として扱う。
`main_artifact/private_data/**` は `.gitattributes` で `export-ignore` 対象である。
