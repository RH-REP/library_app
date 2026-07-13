# Web App Directory Plan

## 目的

開発段階では、配布用成果物の完全な無汚染化よりも、Web app 本体と個別データを物理的に分けて扱えることを優先する。

この文書は、`main_artifact/` の中で最初に切るフォルダ境界を定義する。

## 初期フォルダ構成

```text
main_artifact/
├── goal.md
├── development_process.md
├── web_app_directory_plan.md
├── library_skill/
│   └── README.md
├── web_app/
│   └── README.md
├── private_data/
│   └── programming_tech_library/
│       └── README.md
└── fixtures/
    └── demo_programming_tech_library/
        └── README.md
```

## 役割分担

### `main_artifact/web_app/`

Web app 本体を置く。

ここに入れるもの:

- frontend UI
- backend API
- shared schema/type
- config template
- migration, seed, test, script

ここに入れないもの:

- 実際の蔵書データ
- 個人メモ
- 収集依頼
- PDF 実ファイル

想定する内部構成:

```text
web_app/
├── frontend/
├── backend/
├── shared/
├── scripts/
├── tests/
└── config.example.yml
```

### `main_artifact/library_skill/`

HTML、PDF、image などの原本を plain text 化する補助 program と schema を置く。

想定する内部構成:

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

ここに入れるもの:

- extractor の Python program
- extraction record や source manifest の schema
- importer / extractor の小さな共通 helper

ここに入れないもの:

- 実際の PDF、画像、HTML snapshot
- 抽出済み text
- 個別の蔵書データ

extractor の出力先は `private_data/programming_tech_library/extracted_text/` とし、
原本保存先は `private_data/programming_tech_library/raw_sources/` とする。

### `main_artifact/private_data/programming_tech_library/`

開発中に使う個別データを置く。

想定する内部構成:

```text
private_data/programming_tech_library/
├── input/
├── process_log.csv
├── raw_sources/
├── extracted_text/
├── organized_data/
├── library_records/
├── research_requests/
├── review_queue/
└── notes/
```

この配下は、開発中は commit してもよい。ただし、将来 public 配布や clean archive を作るときは分離対象になる。

### `main_artifact/fixtures/demo_programming_tech_library/`

共有可能な demo データを置く。

想定する内部構成:

```text
fixtures/demo_programming_tech_library/
├── records/
├── snippets/
└── search_cases/
```

ここには架空データ、十分に匿名化したデータ、再現用の最小データだけを置く。

## なぜこの切り方にするか

- Web app 側の実装者が、個別データに触れずに画面と API を進めやすい。
- 個別データの置き場を固定することで、どこまでが software かが明確になる。
- 後で root-level へ移動する場合も、`web_app/` `private_data/` `fixtures/` をそのまま持ち上げやすい。
- release 対応を後回しにしても、構造の崩れを抑えられる。

## この段階の運用ルール

1. Web app のコード変更は `main_artifact/web_app/` に寄せる。
2. 実データは `main_artifact/private_data/programming_tech_library/` に寄せる。
3. 共有してよい再現データだけを `main_artifact/fixtures/demo_programming_tech_library/` に置く。
4. `web_app/` は `private_data/` の中身を直参照せず、後で env/config で切り替えられるようにする。

## 次にやること

- `main_artifact/web_app/` の frontend/backend の責務を細かく決める。
- `main_artifact/library_skill/extractors/` の first cut 実装方針を決める。
- `source_manifest.json` と `extraction_record.json` の schema を extractor 実装に合わせて固める。
- `main_artifact/fixtures/demo_programming_tech_library/` の最小サンプルを作る。
