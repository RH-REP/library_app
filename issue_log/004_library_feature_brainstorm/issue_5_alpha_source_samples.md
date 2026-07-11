# Issue #5 Alpha Source Samples

## 依頼

ユーザーは、開発のためにサンプルを集め、HTML、PDF、画像の 3 種類の原本を一度保存するよう依頼した。

対応づける項目:

- 何を作るか明確にする / 要求工学・仕様化 / 要件定義、ユースケース、ユーザーストーリー、契約による設計
- 変更しやすく設計する / ソフトウェア設計 / モジュール化、SOLID原則、依存性逆転、リファクタリング
- 正しさを継続的に確認する / ソフトウェアテスト・品質保証 / 単体テスト、TDD、コードレビュー、CI、静的解析

## 判断

- 共有可能で repo に保存しやすい synthetic fixture として生成する。
- 保存場所は `main_artifact/fixtures/demo_programming_tech_library/` 配下に寄せる。
- 3 形式を登録、検索、preview 検証の最初の原本セットとして扱う。

## 成果

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/html/requirements_engineering_overview.html`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_design_principles.pdf`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/software_quality_practices.png`
- `main_artifact/fixtures/demo_programming_tech_library/records/alpha_source_samples.json`

## 使い道

- 原本マスターテーブルの最初の登録対象
- HTML/PDF/画像 preview の確認
- source type ごとの検索・一覧導線の確認
- alpha 開発の fixture index

## 次の候補 issue

- `alpha_source_samples.json` を前提にした原本マスターテーブル schema を作る。
- 3 種類の原本を登録できる最小フローを作る。
- source type ごとの一覧/詳細 UI の差分を決める。

## 2026-07-11 追加対応: 実検索ソース版

ユーザーの follow-up に合わせて、synthetic fixture とは別に、実際に検索して取得した
外部ソース版も保存した。

追加したもの:

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/html/requirements_engineering_wikipedia.html`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/pdf/software_through_pictures_arxiv.pdf`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/image/software_testing_wikipedia.jpg`
- `main_artifact/fixtures/demo_programming_tech_library/records/actual_web_source_samples.json`

判断:

- 共有しやすい synthetic fixture は残す。
- 一方で、HTML/PDF/image の実在ソースを別セットで保存し、plain text 化や OCR の
  前処理検証に使えるようにする。
- URL、出典、取得日は `actual_web_source_samples.json` に寄せる。
