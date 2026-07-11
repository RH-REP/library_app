# Plan

## 方針

Issue #3 は実装依頼ではなく、実運用を始めながらソフトウェアを汚さずに開発するための設計判断である。まず境界方針を文書化し、その後の実装 issue で保存先や画面を決められる状態にする。

## 作業項目

- [x] `main_artifact/goal.md` と `main_artifact/development_process.md` を読む。
- [x] 既存の assignment state を確認し、issue #3 の sub-artifact path が `sub_artifact/003_software_data_boundary` であることを確認する。
- [x] software、private repo、実データ保存場所の責務分離を整理する。
- [x] 実運用からソフトウェア改善へ戻す開発ループを整理する。
- [x] コミット可否とサンプルデータ化の基準を整理する。
- [x] ユーザー向け issue log を残す。
- [x] follow-up comment に基づき、プログラミング技術図書館を当面のテーマとして反映する。
- [x] private 開発中に個別データを commit し、配布時に除外する release boundary を整理する。
- [x] `git archive` 用の `.gitattributes` export-ignore を追加する。

## 次に決めること

- 実データの保存先を、ローカルディレクトリ、SQLite、専用 DB、別 private data repo のどれにするか。
- PDF や OCR テキストを Git 管理するか、ファイルストレージ管理にするか。
- 最小デモ用の synthetic fixture をどの範囲まで作るか。
- 実運用で使う config/env の名前と配置を決めるか。
- 配布を archive にするか、clean repository にするか。
