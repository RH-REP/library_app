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

### `main_artifact/private_data/programming_tech_library/`

開発中に使う個別データを置く。

想定する内部構成:

```text
private_data/programming_tech_library/
├── raw_sources/
├── staging/
├── library_records/
├── research_requests/
├── notes/
└── attachments/
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
- `main_artifact/private_data/programming_tech_library/` の最小ディレクトリを具体化する。
- `main_artifact/fixtures/demo_programming_tech_library/` の最小サンプルを作る。
