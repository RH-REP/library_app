# Work Log

## 2026-07-11

- Issue #3 の本文を確認した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` を確認した。
- `.core_program/assignment_state.json` で issue #3 の正式な sub-artifact path が `sub_artifact/003_software_data_boundary` になっていることを確認した。
- 実運用しながら開発するための software/data boundary を整理した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` に、個別データをソフトウェア本体へ混入させない前提を追記した。
- `issue_log/003_software_data_boundary/issue_3_software_data_boundary.md` を作成した。

## 2026-07-11 follow-up

- Issue #3 の追加コメントを確認した。
- 当面のテーマを「プログラミングの技術」に関する図書館として `main_artifact/goal.md` に反映した。
- private 開発中は個別データを commit してよいが、配布時には clean archive または clean repository から出す必要があることを整理した。
- `private_data/**` などを release archive から除外するため `.gitattributes` に `export-ignore` を追加した。
- `artifact.md` と issue log に follow-up 判断を追記した。
