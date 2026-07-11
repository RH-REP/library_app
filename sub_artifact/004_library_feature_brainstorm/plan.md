# Plan

## 方針

Issue #4 は採否未決のブレインストーミング依頼である。雑に列挙して終わるのではなく、あとで判断しやすいように整理しつつ、まだ決めるべきでないものは決めない。

## 作業項目

- [x] `main_artifact/goal.md` と `main_artifact/development_process.md` を読む。
- [x] `.core_program/assignment_state.json` を確認し、issue #4 の正式な sub-artifact path が `sub_artifact/004_library_feature_brainstorm` であることを確認する。
- [x] issue 本文の初期案を基点に、候補機能をカテゴリ別に広げる。
- [x] データ構造、原本保存、PDF/OCR、検索、閲覧、追加調査、Web UI の候補を整理する。
- [x] 採否未決のまま残すべき論点をまとめる。
- [x] ユーザー向け issue log を残す。

## 次に決めること

- タグ、フォルダ、用語集をどう役割分担するか。
- 原本のマスターテーブルを「ファイル単位」「資料単位」「版単位」のどこで持つか。
- PDF スキャンを、保管だけにするか、OCR まで進めるか。
- Web/HTML 画面の最小構成を、一覧・詳細・検索のどこまでにするか。
- 最初の MVP に含める機能をどこまで絞るか。

## 2026-07-11 follow-up: Issue #5

### 方針

Issue #5 では、ブレインストーミングの候補をそのまま並べず、アルファ開発で必須なものだけに絞る。特に「非 AI 検索」「原本保存」「Web での参照」という project の根に関わる要素を優先し、OCR や用語集のような拡張要素は後段へ送る。

### 作業項目

- [x] 既存の brainstorm 候補と MVP 叩き台を見直す。
- [x] アルファ段階で必須な要素と後回しにする要素を切り分ける。
- [x] アルファ開発のマイルストーンと完了条件を整理する。
- [x] ユーザー向け issue log を追加する。

### この時点での判断

- 必須要素は、原本保存、原本マスターテーブル、最小メタデータ、非 AI 検索、一覧/詳細画面、基本登録導線である。
- タグは残すが、フォルダ階層と用語集はアルファの必須から外す。
- PDF は取り込み対象に含めるが、scan program と OCR はアルファ完了条件に入れない。

## 2026-07-11 follow-up 2: Issue #5 サンプル原本収集

### 方針

alpha の議論だけでは開発に着手しづらいため、共有可能な fixture 原本を先に 3 件用意する。形式は HTML、PDF、画像とし、登録、検索、preview 導線の確認に使える最小セットにする。

### 作業項目

- [x] fixture 保存先を `main_artifact/fixtures/demo_programming_tech_library/` に追加する。
- [x] HTML、PDF、画像の 3 種類の原本サンプルを生成する。
- [x] サンプルを 3 つの alpha テーマへ対応づける index を作る。
- [x] ユーザー向け issue log を追加する。

### この時点での判断

- サンプルは外部配布物の収集ではなく、共有可能な synthetic fixture として repo 内で生成する。
- HTML は要求工学・仕様化、PDF はソフトウェア設計、画像はソフトウェアテスト・品質保証に対応させる。
- 登録や preview の検証では、`records/alpha_source_samples.json` を最初の参照 index として使える。

## 2026-07-11 follow-up 3: Issue #5 実検索ソース版

### 方針

synthetic fixture は維持したまま、実際に検索した外部ソースを別セットとして保存する。
plain text 化や OCR の検証では、実在ソースの方がノイズや前処理条件を把握しやすい。

### 作業項目

- [x] HTML、PDF、JPEG の実在ソースを検索して保存する。
- [x] URL、出典、用途を machine-readable な index にする。
- [x] issue log に provenance を残す。

### この時点での判断

- synthetic fixture と actual web source は役割が違うため、置換ではなく併存にする。
- issue #6 の text extraction 機能は、まずこの actual source セットを入力として扱う。
