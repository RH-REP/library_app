# Issue #3 Software/Data Boundary

## 依頼

ユーザーは、図書館システムを実運用しながら開発したいが、個別データがソフトウェアを汚染することを懸念している。

本文の要点:

- このソフトウェアは図書館を作る。
- 既存データや追加収集依頼を整理するシステムにしたい。
- 実運用しないと開発が進まない。
- しかし個別データが software に混入するのは避けたい。
- `software (upstream) -> fetch & switch repo to private_repo (個人利用)` のような運用を考えている。

## 判断

実運用と開発は分けずに連動させてよい。ただし、成果物の境界を分ける。

- software/upstream: 汎用ソフトウェア、schema、import/export 契約、fixture、テスト。
- private project repo: 個人利用の作業記録、設定例、判断メモ。
- private runtime data: 実データ、PDF、OCR 結果、個人メモ、収集依頼、cache、backup。

実データから分かった課題は、個別情報を除いた issue、fixture、schema、UI 要件へ変換して software 側へ戻す。

## 成果

- `sub_artifact/003_software_data_boundary/` を初期化した。
- `artifact.md` に software/data boundary の開発方針を整理した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` に、個別データを software 本体へ混入させない前提を追記した。

## 残課題

- 実データ保存先を決める。
- `.gitignore` と設定ファイルの具体案を決める。
- 最小 demo fixture を作る。
- data contract を文書化する。
