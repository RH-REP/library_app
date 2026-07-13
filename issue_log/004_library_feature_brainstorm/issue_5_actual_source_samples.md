# Issue #5 Actual Source Samples

## 依頼

ユーザーは、前回の synthetic fixture ではなく、実際に検索して取得したサンプルを保存し、
URL や出典も md で簡易に残すよう依頼した。

## 方針

- 実在ソースは形式別に `source_samples/html/`、`source_samples/pdf/`、
  `source_samples/image/` に保存する。
- provenance は JSON index とこの issue log の両方に残す。

## 保存したソース

### 1. HTML

- ローカル保存先:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/html/requirements_engineering_wikipedia.html`
- URL:
  `https://en.wikipedia.org/wiki/Requirements_engineering`
- 出典:
  Wikipedia
- 用途:
  HTML から plain text へ落とす際に、本文だけでなく site chrome や link text が混ざる
  実在ページの挙動を確認する。

### 2. PDF

- ローカル保存先:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_through_pictures_arxiv.pdf`
- URL:
  `https://arxiv.org/pdf/2403.08085.pdf`
- 出典:
  arXiv
- タイトル:
  `Lessons from a Pioneering Software Engineering Environment: Design Principles of Software through Pictures`
- 用途:
  text PDF から plain text を抽出する first cut の入力として使う。

### 3. Image

- ローカル保存先:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/royce_final_model_waterfall.png`
- URL:
  `https://upload.wikimedia.org/wikipedia/commons/d/de/1970_Royce_Managing_the_Development_of_Large_Software_Systems_Fig10.PNG`
- 出典:
  Wikimedia Commons / Wikipedia
- タイトル:
  `Royce final model - Waterfall model`
- 用途:
  image-to-plain-text / OCR 導線で、ソフトウェア開発プロセスの図表画像を扱う
  最低限の入力として使う。

## 補足

- source list の machine-readable 版は
  `main_artifact/fixtures/demo_programming_tech_library/records/actual_web_source_samples.json`
  に保存した。
- これで issue #6 の HTML/PDF/image -> plain text 機能の入力セットが揃った。

## 2026-07-13 更新

ユーザーの follow-up により、自作側の synthetic sample file は削除した。
現行の sample set は、この actual source set だけである。

## 2026-07-13 更新 2

ユーザーの follow-up により、画像サンプルをプログラミング知見に直接関係する
ソフトウェア開発プロセス図へ差し替えた。
古いソフトウェアテスト大会の写真は、知見抽出用の画像サンプルとして弱いため削除した。
