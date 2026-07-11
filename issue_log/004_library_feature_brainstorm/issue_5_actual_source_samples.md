# Issue #5 Actual Source Samples

## 依頼

ユーザーは、前回の synthetic fixture ではなく、実際に検索して取得したサンプルを保存し、
URL や出典も md で簡易に残すよう依頼した。

## 方針

- synthetic fixture は demo / shareable fixture として残す。
- 実在ソースは別セットとして `source_samples/actual/` に保存する。
- provenance は JSON index とこの issue log の両方に残す。

## 保存したソース

### 1. HTML

- ローカル保存先:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/html/requirements_engineering_wikipedia.html`
- URL:
  `https://en.wikipedia.org/wiki/Requirements_engineering`
- 出典:
  Wikipedia
- 用途:
  HTML から plain text へ落とす際に、本文だけでなく site chrome や link text が混ざる
  実在ページの挙動を確認する。

### 2. PDF

- ローカル保存先:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/pdf/software_through_pictures_arxiv.pdf`
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
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/image/software_testing_wikipedia.jpg`
- URL:
  `https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/TestingCup-Polish-Championship-in-Software-Testing-Katowice-2016.jpg/1280px-TestingCup-Polish-Championship-in-Software-Testing-Katowice-2016.jpg`
- 出典:
  Wikipedia Commons
- 用途:
  image-to-plain-text / OCR 導線で、実在 JPEG を扱う最低限の入力として使う。

## 補足

- source list の machine-readable 版は
  `main_artifact/fixtures/demo_programming_tech_library/records/actual_web_source_samples.json`
  に保存した。
- これで issue #6 の HTML/PDF/image -> plain text 機能の入力セットが揃った。
