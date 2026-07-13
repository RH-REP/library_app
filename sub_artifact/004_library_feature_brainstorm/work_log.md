# Work Log

## 2026-07-11

- Issue #4 の本文を確認した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` を確認した。
- `.core_program/assignment_state.json` で issue #4 の正式な sub-artifact path が `sub_artifact/004_library_feature_brainstorm` になっていることを確認した。
- issue 本文に挙がっていたタグ、フォルダ構成、用語集、PDF scan program、html、原本の保存、原本のマスターテーブルを起点に、候補機能を広げた。
- 採否をまだ決めない前提で、データ構造、原本保存、検索、閲覧、Web UI、運用境界の観点から整理した。
- `issue_log/004_library_feature_brainstorm/issue_4_library_feature_brainstorm.md` を作成した。

## 2026-07-11 follow-up: Issue #5

- Issue #5 の本文を確認した。
- Issue #4 の brainstorm artifact から、アルファ開発で必須な要素だけを再抽出した。
- タグ、原本保存、原本マスターテーブル、最小メタデータ、非 AI 検索、一覧/詳細画面をアルファ必須候補として整理した。
- フォルダ階層、用語集、OCR、scan program、推薦や保存済み検索などは後回し候補として分離した。
- `artifact.md` にアルファ開発の必須要素、非必須要素、マイルストーン、アルファ完了条件を追記した。
- `issue_log/004_library_feature_brainstorm/issue_5_alpha_milestones.md` を作成した。

## 2026-07-11 follow-up 2: Issue #5

- Issue #5 の追加コメントを確認した。
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/` 配下に HTML、PDF、PNG のサンプル原本を追加した。
- `records/alpha_source_samples.json` を作成し、3 つのサンプルを alpha 開発テーマへ対応づけた。
- fixture README に `source_samples/` の用途を追記した。
- `artifact.md` にサンプル原本収集の follow-up を追記した。
- `issue_log/004_library_feature_brainstorm/issue_5_alpha_source_samples.md` を作成した。

## 2026-07-11 follow-up 3: Issue #5 実在ソース版

- ユーザーの追加コメントを確認した。
- synthetic fixture とは別に、実際に検索した HTML、PDF、画像を形式別の `source_samples/` 配下に保存した。
- `records/actual_web_source_samples.json` に URL、出典、取得日、用途を記録した。
- `artifact.md`、`sub_goal.md`、`plan.md` に actual source の追記を行った。
- `issue_log/004_library_feature_brainstorm/issue_5_actual_source_samples.md` を作成した。

## 2026-07-13 follow-up 4: Issue #5 自作 sample file 削除

- ユーザーの追加コメントを確認した。
- 自作側の synthetic HTML / PDF / image sample を削除した。
- `records/alpha_source_samples.json` を削除した。
- actual source sample と `records/actual_web_source_samples.json` は残した。
- fixture README と artifact を、現行 sample set が actual source 中心である内容へ更新した。
- `issue_log/004_library_feature_brainstorm/issue_5_remove_synthetic_source_samples.md` を作成した。

## 2026-07-13 follow-up 5: Issue #5 画像 sample 差し替え

- ユーザーの追加コメントを確認した。
- 画像 sample がプログラミング知見に関するものになるよう、ソフトウェア開発プロセス図へ差し替えた。
- 古いソフトウェアテスト大会の JPEG を削除した。
- `records/actual_web_source_samples.json` と関連 artifact / issue log の参照を更新した。
