# Sub Goal: Issue #3 ソフトウェアと運用データの境界設計

## 目的

図書館システムを実運用しながら開発する前提で、個別データがソフトウェア本体に混入しない開発・運用方針を定める。

## 成果物

- `sub_artifact/003_software_data_boundary/artifact.md`
- `issue_log/003_software_data_boundary/issue_3_software_data_boundary.md`
- この sub-artifact の標準ファイル一式

## 範囲

- software/upstream、個人利用 private repo、実データ保存場所の責務を分ける。
- 実運用から見つかった課題を、個別データなしでソフトウェア改善へ戻す流れを定義する。
- コミットしてよいもの、コミットしてはいけないもの、サンプル化してよいものを整理する。

## 範囲外

- 実データ保存先、DB、OCR、バックアップ方式の確定。
- 具体的なアプリ実装。
- 個別データの収集、移行、匿名化作業そのもの。
