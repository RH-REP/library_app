# Multiformat Text Extraction

Issue #6 の follow-up として、HTML / PDF / OCR を Python program で扱う前提に
切り替え、必要な skill set と実装工程を具体化する。

## 今回の依頼

- HTML のハンドリングを Python で行いたい。
- PDF の取り扱いを Python で行いたい。
- OCR まわりの Python skill set を先に把握したい。
- 実装工程を、実際に着手できる粒度まで細かくしたい。

## 入力として使う sample

実装と検証では、issue #5 で保存した actual source sample を主に使う。

- HTML:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/html/requirements_engineering_wikipedia.html`
- PDF:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_through_pictures_arxiv.pdf`
- image:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/royce_final_model_waterfall.png`

以前の synthetic fixture は issue #5 の follow-up で削除済みである。
実装初期の確認では actual source を使う。

## 2026-07-13 follow-up: PDF / image sample visual review

Issue #6 の追加コメントで、現在の PDF と画像 sample を実際に確認し、
文字が散らばっている場合にどう文字化するかを整理するよう依頼された。

確認した sample:

- PDF:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_through_pictures_arxiv.pdf`
- image:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/royce_final_model_waterfall.png`

確認結果:

- PDF は 3 ページの text PDF であり、OCR に回す必要はない。
- PDF は untagged で、2 段組、図、図キャプション、ヘッダー、フッター、
  arXiv の縦向きラベルが混在する。
- `pdftotext -layout` では本文自体は取れるが、図キャプションや右カラムが
  本文途中に混ざるため、そのまま検索用本文にすると読み順が崩れる。
- 画像は 900x503 のソフトウェア開発プロセス図で、箱、矢印、点線境界、
  小さいラベルが多い。
- Tesseract CLI で原本と 3 倍拡大・二値化版を試したが、通常 OCR では誤読が多く、
  図全体を文章として復元する用途には不十分である。

この sample に対する判断:

- PDF は「本文抽出」として扱う。ただし、単純なページ全文連結ではなく、
  座標情報を使って title / abstract / left column / right column / caption /
  reference を分ける。
- PDF 内の図中テキストは、本文とは別の optional figure OCR として扱う。
  first cut では図キャプションを主に取り、図内ラベル OCR は metadata warning 付きにする。
- 画像は「通常文書」ではなく「図表」として扱う。
  OCR 結果をそのまま本文にせず、図表タイトル、領域、ノード、関係を構造化した
  diagram transcription にする。
- 画像 OCR は automatic final text ではなく、human review 前提の candidate text として扱う。

推奨する出力分解:

- `body_text`: PDF の本文、または HTML の本文。
- `caption_text`: 図表キャプション。
- `figure_text`: 図内ラベルや OCR 候補。検索対象にする場合も本文とは別 field。
- `diagram_transcription`: 画像 sample のような図表を、人間が確認できる構造化テキスト。
- `layout_warnings`: 2 段組、縦ラベル、図混在、低信頼 OCR などの注意。
- `extraction_method`: `text_layer`, `coordinate_blocks`, `ocr_candidate`, `manual_reviewed_diagram`
  などを明示する。

PDF の文字化方針:

1. まず text layer の有無とページ数を確認する。
2. `pypdf` の単純抽出だけで終わらせず、`PyMuPDF` または `pdfplumber` の
   word / block 座標を使う。
3. ページ上部の title block、header、footer、左カラム、右カラム、figure caption を
   region として分ける。
4. 各カラム内は top-to-bottom、left-to-right で並べる。
5. 図キャプションは本文途中に混ぜず、`caption_text` として残す。
6. arXiv の縦向きラベルや許諾文は `layout_warnings` または低優先 metadata に回す。

画像の文字化方針:

1. 原本画像を grayscale / autocontrast / upscale した OCR candidate を作る。
2. 画像全体 OCR は参考値に留め、箱単位や領域単位で crop して OCR する。
3. 右側の simplified waterfall、中央の iterative model、左側の document flow、
   右上の rule box など、領域ごとに分ける。
4. OCR confidence が低い場合は、図表の意味を人間が確認した
   `diagram_transcription` を正式な検索用テキストにする。
5. 矢印の順序は OCR では取れないため、ノード列と関係を別フィールドにする。

この follow-up により、image OCR は alpha 必須実装ではなく、
「OCR candidate を出し、必要なら人間レビュー済み diagram transcription を保存できる」
ところまでを alpha の現実的な範囲とする。

## 共通出力 contract

3 形式とも、first cut では次の共通 contract を持つ。

- 入力 1 件につき 1 件の extracted text を出力する。
- 文字コードは UTF-8 に統一する。
- 原本 path、media type、extractor 名、status を metadata に残す。
- 抽出不能時は空文字ではなく `failed` を返す。
- 後段の検索と LLM 処理の両方で扱いやすいよう、line-oriented plain text を基本にする。

### first cut の出力単位

- 派生 text:
  `plain_text.txt`
- metadata:
  `extraction_record.json`

### metadata の最低項目

- `source_path`
- `media_type`
- `extractor`
- `status`
- `warnings`
- `ocr_used`
- `language_hint`

## Python skill set

### 共通基盤

first cut で最低限必要になる skill set は次の通り。

- `pathlib` で原本と出力先を扱う。
- `json` で metadata を保存する。
- `dataclasses` または `typing` で共通 record を定義する。
- `logging` で抽出失敗理由を残す。
- `pytest` で fixture 単位の回帰確認を行う。

この層では、各 extractor が別実装でも同じ出力 contract を返すことが重要である。

### HTML handling

推奨 stack:

- `beautifulsoup4`
- `lxml`

必要な skill set:

- 壊れた HTML を parser で受け止める。
- `script` `style` `nav` `footer` などの不要要素を除去する。
- heading / paragraph / list / link text をどう plain text に落とすか決める。
- 連続空白、改行、注釈ノイズを正規化する。

採用理由:

- Beautiful Soup は `get_text()`、CSS selector 系、tag 除去で first cut を作りやすい。
- `lxml.html` は `drop_tree()` `drop_tag()` `text_content()` があり、本文整形を一段細かく制御しやすい。
- first cut では Beautiful Soup を主操作系、`lxml` を parser backend と補助操作系にするのが妥当。

### PDF handling

推奨 stack:

- `pypdf`
- `PyMuPDF`
- `pdfplumber`

必要な skill set:

- text PDF と scanned PDF を切り分ける。
- ページごとに text を抜き、ページ境界を残す。
- header / footer / 改ページの扱いを決める。
- 抽出結果が sparse すぎる場合の fallback を用意する。
- 2 段組や図が混ざる PDF では、座標付き block / word を使って読み順を作る。

採用理由:

- `pypdf` は pure Python で導入しやすく、`page.extract_text()` の first cut が作りやすい。
- `PyMuPDF` は `page.get_text()` と block / word 単位の取得があり、読み順崩れや位置情報確認に向く。
- `pdfplumber` は word / table / crop 操作を使って、2 段組や余白ノイズの処理を確認しやすい。
- PDF は 1 本のライブラリで完全統一するより、`pypdf` を標準経路、`PyMuPDF` を fallback / 検証経路にした方が現実的である。

### OCR / image handling

推奨 stack:

- `Pillow`
- `pytesseract`
- `Tesseract OCR`

必要な skill set:

- 画像を grayscale 化し、必要に応じて二値化する。
- OCR 実行前に解像度と文字サイズの向きを確認する。
- `jpn` / `eng` など言語 pack の有無を確認する。
- OCR 失敗時に「前処理不足」か「画像品質不足」かを切り分ける。

採用理由:

- `pytesseract` は Python から Tesseract を呼ぶ最短経路である。
- `pytesseract` は `image_to_string()`、`get_languages()`、timeout 指定を持ち、first cut の wrapper として十分である。
- Tesseract 本体は Python package ではなく外部 binary なので、環境確認工程を最初に置く必要がある。

### scanned PDF の OCR

推奨 stack:

- `ocrmypdf`

必要な skill set:

- PDF を OCR 対象として再保存し、検索可能な text layer を付与する。
- text PDF の経路と scanned PDF の経路を分ける。
- OCR 後 PDF から再度 text 抽出する二段構成を理解する。

採用理由:

- scanned PDF を `pypdf` だけで扱うのは不十分である。
- OCRmyPDF は Tesseract を使って検索可能 PDF を作るため、PDF OCR の責務分離がしやすい。

## 推奨アーキテクチャ

first cut では、1 本の巨大 script よりも共通 contract を返す 3 系統の extractor に分ける。

- `html_extractor`
- `pdf_extractor`
- `image_ocr_extractor`
- scanned PDF 用に `pdf_ocr_bridge`

各 extractor は、最終的に同じ `ExtractionRecord` を返す。

## 2026-07-13 follow-up: implementation phases and metadata header

ユーザーの確認により、実装前に工程を次の粒度へ切ることにした。
詳細は `implementation_phases.md` に分けた。

取り込んだ追加契約:

- `sub_artifact/006_library_folder_structure/metadata_header_contract.md`
- `organized_data/{item_id}/index.md` の冒頭 metadata header
- 必須 header fields: `収集日`, `収集URL`, `ファイルの要約`, `タグ`
- 不明値は空欄にせず `未確認`
- local file だけの場合は `local:` prefix

重要な境界:

- `extracted_text/{source_id}/plain_text.txt` には metadata header を付けない。
- metadata header は `organized_data/{item_id}/index.md` にだけ付ける。
- extractor は `plain_text.txt` と `extraction_record.json` を作る。
- organizer は extraction result を読んで、metadata header 付き `index.md` と
  `source_refs.json` を作る。
- metadata header は表示用であり、機械処理の唯一の正本にはしない。
  `source_refs.json`、`library_records/items.jsonl`、source manifest、
  `extraction_record.json` と同期する。

工程の切り方:

1. 環境と依存の固定
2. `ExtractionResult` / `ExtractionRecord` contract 更新
3. metadata header adapter
4. HTML extractor first cut
5. PDF coordinate extraction first cut
6. Image OCR candidate と diagram transcription
7. organized_data bridge
8. 回帰確認

## 2026-07-13 follow-up: program skeleton

Issue #7 で、Python extractor の置き場は
`main_artifact/library_skill/extractors/` と整理された。

今回、その構成に合わせて、まず置くべき program の雛形を作成した。

- `main_artifact/library_skill/extractors/common.py`
- `main_artifact/library_skill/extractors/html_to_text.py`
- `main_artifact/library_skill/extractors/pdf_to_text.py`
- `main_artifact/library_skill/extractors/image_ocr_to_text.py`

細部実装はまだ入れていない。各 extractor は同じ入口 `extract(source_path, source_id,
language_hint)` を持ち、現時点では contract に合う `failed` result を返す。

後続 issue では、この雛形に対して次の順で実装を入れる。

1. `html_to_text.py` に Beautiful Soup / lxml ベースの処理を入れる。
2. `pdf_to_text.py` に pypdf / PyMuPDF ベースの処理を入れる。
3. `image_ocr_to_text.py` に Pillow / pytesseract ベースの処理を入れる。
4. 必要になった時点で scanned PDF 用 bridge を追加する。

## 具体的な実装工程

### 工程0: 環境確認

実装前に先に潰すべき項目:

- Python 仮想環境を作る。
- `beautifulsoup4` `lxml` `pypdf` `PyMuPDF` `Pillow` `pytesseract` を install する。
- `tesseract --version` が通るか確認する。
- `pytesseract.get_languages()` で `eng` と必要なら `jpn` が見えるか確認する。
- fixture 3 件を Python から開けるか確認する。

完了条件:

- HTML / PDF / image のサンプルを同一環境で読み込める。
- OCR が Python から呼べるかどうかが着手前に判定できる。

### 工程1: 共通 contract と CLI 骨組み

作るもの:

- `ExtractionRecord` の dataclass
- `plain_text.txt` と `extraction_record.json` の保存関数
- 単一ファイルを処理する CLI entrypoint

ここで決めること:

- status を `ok` `failed` `needs_ocr` のどれにするか
- warning の粒度
- 文字コードと改行正規化

完了条件:

- extractor 本体が未完成でも、共通出力の雛形が固定される。

### 工程2: HTML extractor first cut

実装順:

1. HTML を Beautiful Soup + `lxml` parser で読む。
2. `script` `style` `noscript` を除去する。
3. `nav` `footer` `aside` は first cut では blacklist 方式で落とす。
4. `title`, `h1-h3`, `p`, `li`, `a` の text を優先して連結する。
5. `get_text()` と空白正規化で plain text を作る。
6. `requirements_engineering_wikipedia.html` でノイズ確認を行う。

レビュー観点:

- 本文より nav が多く残っていないか
- 見出しが潰れていないか
- link text だけで意味が崩れていないか

完了条件:

- actual HTML 1 件で、検索投入しても大崩れしない text を得る。

### 工程3: PDF extractor first cut

実装順:

1. `pypdf.PdfReader` でページを開く。
2. 各ページに対して `extract_text()` を実行する。
3. ページ境界を明示して text を連結する。
4. 抽出文字数が極端に少ない場合は `needs_ocr` を返す。
5. 読み順が崩れる場合のみ `PyMuPDF` で block 単位抽出を試す。
6. `software_through_pictures_arxiv.pdf` で title / body / page break を確認する。

レビュー観点:

- text PDF として読めているか
- 改ページの扱いが後段検索で邪魔にならないか
- header / footer の重複ノイズが大きすぎないか

完了条件:

- actual PDF 1 件で、OCR に逃がさず baseline text を得る。

### 工程4: Image OCR extractor first cut

実装順:

1. `Pillow` で画像を開く。
2. 必要なら grayscale 化だけ先に入れる。
3. `pytesseract.image_to_string()` で text を取る。
4. `lang="eng"` から始め、必要が見えたら `jpn+eng` に広げる。
5. `royce_final_model_waterfall.png` で OCR 可能性を確認する。
6. 明確に品質不足なら warning を付けて alpha の責務範囲外へ出す。

レビュー観点:

- 文字が連結崩れしすぎていないか
- 英語ページでも OCR ノイズが過大でないか
- 前処理で改善する問題か、原本品質の問題か

完了条件:

- image OCR を alpha 必須にするか beta 送りにするか判断できる。

### 工程5: scanned PDF OCR bridge

HTML / text PDF と違い、scanned PDF は別経路にする。

実装順:

1. PDF extractor が `needs_ocr` を返したら scanned 候補として扱う。
2. OCRmyPDF で OCR 済み PDF を生成する。
3. 生成後 PDF に対して再度 PDF extractor をかける。
4. OCR を通した fact を metadata に残す。

完了条件:

- text PDF と scanned PDF が同じ実装で混線しない。

### 工程6: 検証と回帰確認

最低限の検証:

- HTML / PDF / image 各 1 件で `plain_text.txt` が生成される。
- `extraction_record.json` に status と warning が入る。
- fixture に対して expected keyword を数個ずつ確認する。
- 失敗ケースで空ファイルではなく `failed` または `needs_ocr` になる。

## アルファ段階の最低構成

まず完成扱いにしてよい最小構成は次の通り。

1. HTML extractor が actual HTML 1 件で安定する。
2. text PDF extractor が actual PDF 1 件で安定する。
3. image OCR は baseline の可否判断まで行う。
4. scanned PDF OCR は bridge 設計までを alpha の必須範囲とし、実装は次 issue でもよい。

この整理なら、先に「検索に渡せる plain text 化の中核」を作り、OCR の重い論点を後ろに回せる。

## 次の実装 issue 候補

- HTML extractor の Python first cut を 1 本作る。
- text PDF extractor の baseline を作る。
- `ExtractionRecord` と出力 directory contract を固定する。
- OCR 環境確認 script を先に作る。
- scanned PDF を alpha に含めるか独立 issue に切るか判断する。

## 調査メモ

今回の具体化で参照した一次情報:

- Beautiful Soup documentation:
  https://beautiful-soup-4.readthedocs.io/en/latest/
- lxml HTML documentation:
  https://lxml.de/lxmlhtml.html
- pypdf text extraction:
  https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- PyMuPDF recipes:
  https://pymupdf.readthedocs.io/en/latest/recipes-text.html
- pytesseract README:
  https://github.com/madmaze/pytesseract
- Tesseract user manual:
  https://tesseract-ocr.github.io/tessdoc/
- OCRmyPDF API:
  https://ocrmypdf.readthedocs.io/en/latest/api.html
