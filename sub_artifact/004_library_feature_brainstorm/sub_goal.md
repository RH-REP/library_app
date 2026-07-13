# Sub Goal: Issue #4 図書館アプリ機能ブレインストーミング

## 目的

Issue #4 で挙がった「タグ」「フォルダ構成」「用語集」「PDF scan program」「html」「原本の保存」「原本のマスターテーブル」を起点に、図書館アプリに必要そうな要素を採否未決の候補として洗い出す。

## 成果物

- `sub_artifact/004_library_feature_brainstorm/artifact.md`
- `issue_log/004_library_feature_brainstorm/issue_4_library_feature_brainstorm.md`
- この sub-artifact の標準ファイル一式

## 範囲

- 既存の制作目標と工程を踏まえて、図書館アプリの候補機能を整理する。
- データ項目、取り込み、検索、閲覧、Web UI、運用境界の観点で候補を広げる。
- 後続 issue で優先順位を決めやすいように、未決定論点を明示する。

## 範囲外

- 機能の採用可否や優先順位の最終決定。
- OCR、DB、フレームワーク、PDF 処理方式などの技術選定。
- 実装、画面制作、データ移行。

## 2026-07-11 follow-up: Issue #5 アルファ開発の最小構成

### 目的

Issue #4 で広げた候補から、アルファ開発で先に作るべき必須要素だけを抽出し、開発マイルストーンを定義する。

### 追加成果物

- `issue_log/004_library_feature_brainstorm/issue_5_alpha_milestones.md`

### 追加範囲

- 候補機能のうち、登録・検索・参照に最低限必要なものだけを選ぶ。
- アルファ段階で後回しにする要素を明示する。
- 実装前に使えるマイルストーンと完了条件を定義する。

## 2026-07-11 follow-up 2: Issue #5 サンプル原本収集

### 目的

Issue #5 の追加コメントに合わせて、alpha 開発で登録・検索・参照の確認に使える原本サンプルを 3 種類の形式で保存する。

### 追加成果物

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/`
- `main_artifact/fixtures/demo_programming_tech_library/records/alpha_source_samples.json`
- `issue_log/004_library_feature_brainstorm/issue_5_alpha_source_samples.md`

### 追加範囲

- HTML、PDF、画像の 3 種類で共有可能な fixture 原本を用意する。
- 各サンプルを alpha 開発テーマの 3 項目へ対応づける。
- 後続の登録、検索、preview 検証で使える index を残す。

## 2026-07-11 follow-up 3: Issue #5 実在ソース収集

### 目的

Issue #5 の追加コメントに合わせて、実際に検索した HTML、PDF、画像を保存し、
plain text 化や OCR の入力として使える provenance 付きサンプルセットを作る。

### 追加成果物

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/`
- `main_artifact/fixtures/demo_programming_tech_library/records/actual_web_source_samples.json`
- `issue_log/004_library_feature_brainstorm/issue_5_actual_source_samples.md`

## 2026-07-13 follow-up: 自作 sample file 削除

### 目的

Issue #5 の追加コメントに合わせて、自作側の synthetic sample file を削除し、
実在ソース sample だけを今後の入力として残す。

### 追加成果物

- `issue_log/004_library_feature_brainstorm/issue_5_remove_synthetic_source_samples.md`
