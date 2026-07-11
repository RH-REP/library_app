# Multiformat Text Extraction

Issue #6 の依頼に対して、HTML、PDF、image を plain text 化する機能群を
新規 sub-artifact として切り出し、実装前の first cut 計画を整理する。

## 依頼の解釈

今回すぐに最終実装まで進めるよりも先に、

- どの入力を対象にするか
- どの形で plain text を出すか
- どの段階で何をレビューするか

を明確にした方が、3 段階レビューの project 進行と整合する。

## 入力として使う sample

入力 fixture は issue #5 で集めた 2 系統を使う。

- synthetic fixture:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/`
- actual source sample:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/`

実装初期の確認では、actual source の方を優先する。

理由:

- HTML は site chrome を含む実在ページの方が tag 除去条件を確認しやすい。
- PDF は text PDF として抽出可否を確認しやすい。
- image は OCR の難しさを synthetic より把握しやすい。

## 共通出力 contract

3 形式とも、first cut では次の共通 contract を目指す。

- 入力ごとに 1 つの extracted text を得る。
- 文字コードは UTF-8。
- 原本 path と extractor 種別を metadata に残す。
- 明らかに抽出不能な場合は空文字ではなく `failed` 状態を返す。
- 後段の検索と LLM 処理が読めるよう、出力は line-oriented plain text を基本にする。

### first cut の出力単位

- 原本:
  HTML / PDF / image
- 派生物:
  `plain_text.txt`
- metadata:
  `extraction_record.json`

## 機能1: HTML -> plain text

### 目的

HTML から、検索と要約に使える本文テキストを取り出す。

### first cut の対象

- text/html の静的ページ
- title, heading, paragraph, list, link text

### first cut で後回し

- JavaScript 実行後 DOM
- site-wide navigation の高度除去
- table の構造保持

### レビュー1: Extraction Contract Review

確認事項:

- 何を本文として残すか。
- heading と list をどの程度改行で保つか。
- link URL を残すか、link text のみ残すか。

完了条件:

- HTML extractor の入出力 contract が 1 ページで説明できる。

### レビュー2: Fixture Extraction Review

確認事項:

- `requirements_engineering_wikipedia.html` を使ったとき、nav や脚注で本文が埋もれないか。
- 改行と空白正規化で読める text になるか。

完了条件:

- sample 1 件で抽出結果を見て、不要ノイズと必要情報の境界がわかる。

### レビュー3: Search / LLM Integration Review

確認事項:

- この text を検索 index に入れて困らないか。
- LLM へ渡したとき、見出しと本文の関係が崩れていないか。

完了条件:

- 検索と LLM の両方で再利用可能な最低形になっている。

## 機能2: PDF -> plain text

### 目的

PDF から検索可能な plain text を取り出す。

### first cut の対象

- 文字埋め込み済み text PDF
- ページ順に抽出できる PDF

### first cut で後回し

- scanned PDF の OCR
- 複雑な段組み復元
- 図表構造の再構成

### レビュー1: Extraction Contract Review

確認事項:

- text PDF と scanned PDF をどう判別するか。
- ページ区切りを text 上でどう表すか。
- header/footer を残すか除去するか。

完了条件:

- PDF extractor の対象範囲と非対象範囲が曖昧でない。

### レビュー2: Fixture Extraction Review

確認事項:

- `software_through_pictures_arxiv.pdf` から、タイトル・本文・改ページの扱いを確認できるか。
- 抽出結果に連結崩れや文字化けがないか。

完了条件:

- 少なくとも 1 件の text PDF で検索投入に耐える text を得られる。

### レビュー3: Search / LLM Integration Review

確認事項:

- PDF 由来であることを metadata として残す必要があるか。
- 段落崩れが後段要約に与える影響は許容範囲か。

完了条件:

- text PDF の extractor を alpha 範囲として確定できる。

## 機能3: Image -> plain text

### 目的

画像を OCR し、plain text として扱えるようにする。

### first cut の対象

- 文字が比較的大きく、解像度が十分な画像
- JPEG / PNG

### first cut で後回し

- 手書き文字
- 複数言語混在の高精度 OCR
- レイアウト保持

### レビュー1: Extraction Contract Review

確認事項:

- OCR エンジンの候補と要求精度をどう置くか。
- 日本語と英語を同時に扱うか。
- 失敗時の扱いをどうするか。

完了条件:

- OCR を alpha に含めるか、placeholder に留めるかを判断できる。

### レビュー2: Fixture Extraction Review

確認事項:

- `software_testing_wikipedia.jpg` のような実在画像で、文字抽出対象として妥当か。
- OCR 向きの image sample を追加で集める必要があるか。

完了条件:

- 画像 OCR の実装前に、fixture 不足か実装不足かを切り分けられる。

### レビュー3: Search / LLM Integration Review

確認事項:

- OCR 誤認識が検索や要約でどの程度許容されるか。
- image OCR を alpha 完了条件に含めるか、beta へ送るか。

完了条件:

- image extractor の project 内優先順位が決まる。

## 実装順

1. HTML extractor
2. PDF extractor
3. image OCR extractor

この順にする理由は、構造の単純さと不確実性の低さである。

## 次の実装 issue 候補

- HTML extractor の入出力 contract を fixture 付きで固定する。
- text PDF extractor の first cut を 1 本作る。
- image OCR を alpha に入れるか見送るかを判定する。
- extracted text の保存先と metadata schema を決める。
