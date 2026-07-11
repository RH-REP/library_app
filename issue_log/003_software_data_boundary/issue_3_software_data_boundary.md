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

## Follow-up: プログラミング技術図書館と配布時の個別データ除外

追加コメントで、当面のテーマを「プログラミングの技術」に関する図書館にし、現時点では個別データも commit して保存するが、配布できる状態になったときには個別データが抜けるようにしたい、という相談があった。

判断:

- 可能。
- ただし、個別データを含む private repository の Git history をそのまま公開してはいけない。
- ファイルを後で削除しても、過去の commit history から復元できるため。
- 配布は、private path を除外した release archive か、個別データを一度も含まない clean branch / clean repository で行う。

対応:

- `main_artifact/goal.md` に、当面のテーマと配布時の個別データ除外条件を追記した。
- `main_artifact/development_process.md` に、private commit と clean distribution の境界を追記した。
- `sub_artifact/003_software_data_boundary/artifact.md` に、private data commit を許容する条件と配布方法を追記した。
- `.gitattributes` を追加し、`private_data/**` などを `git archive` から除外する設定を入れた。

残課題:

- `private_data/programming_tech_library/` の具体的なディレクトリ構造を決める。
- `fixtures/demo_programming_tech_library/` の最小サンプルを作る。
- release archive 作成手順と private data 混入チェック手順を作る。

## Follow-up: main_artifact で Web app と個別データを先に分ける

追加コメントで、現段階では配布データのコンタミは大きな問題にせず、まず `main_artifact` の中で software 部分と個別データ部分を切り分けたい、ソフトウェアは Web app を想定する、という指示があった。

判断:

- 現段階では release の厳密な clean 化より、物理的な置き場の分離を優先してよい。
- first cut は `main_artifact/web_app/` `main_artifact/private_data/programming_tech_library/` `main_artifact/fixtures/demo_programming_tech_library/` にする。
- `web_app/` には UI、API、schema、設定テンプレートを置き、個別データは置かない。
- `private_data/` には実データを置き、`fixtures/` には共有可能な demo データを置く。

対応:

- `main_artifact/web_app_directory_plan.md` を追加した。
- `main_artifact/web_app/README.md` を追加した。
- `main_artifact/private_data/programming_tech_library/README.md` を追加した。
- `main_artifact/fixtures/demo_programming_tech_library/README.md` を追加した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` を更新した。
- `.gitignore` と `.gitattributes` を更新し、新しい `main_artifact` 配下の構成を tracked / export-ignore の両面で扱えるようにした。

残課題:

- `main_artifact/web_app/` の frontend/backend/shared の責務を決める。
- `main_artifact/private_data/programming_tech_library/` の最小ディレクトリを作る。
- `main_artifact/fixtures/demo_programming_tech_library/` の最小データを作る。
