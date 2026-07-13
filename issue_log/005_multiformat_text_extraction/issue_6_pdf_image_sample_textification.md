# Issue #6 PDF / Image Sample Textification

## 依頼

ユーザーは、現在のサンプル PDF と画像を確認し、文字が散らばっている場合に
どのように文字化すべきか整理するよう依頼した。

## 確認した sample

- PDF:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_through_pictures_arxiv.pdf`
- image:
  `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/royce_final_model_waterfall.png`

## 確認方法

- `pdfinfo` で PDF metadata とページ数を確認した。
- `pdftoppm` で PDF 1-3 ページを PNG にレンダリングし、レイアウトを目視確認した。
- `pdftotext -layout` で PDF の text layer 抽出結果を確認した。
- Tesseract CLI で画像 OCR を確認した。
- 画像は 3 倍拡大、grayscale、autocontrast、二値化した版でも OCR を確認した。

## PDF の観察結果

- PDF は 3 ページの text PDF で、OCR に回す必要はない。
- ただし untagged PDF であり、論文レイアウトは 2 段組である。
- 1 ページ目は title / abstract / author / 図1 / 本文 / 許諾文 / arXiv 縦ラベルが混在する。
- 2 ページ目は左カラム本文、右カラム本文、図2、図3、caption が混在する。
- 3 ページ目は図4、参考文献、受理日が混在する。
- `pdftotext -layout` は文字を取れるが、図や右カラムの位置によって本文順序が崩れる。

## PDF の文字化方針

- PDF は OCR ではなく text layer extraction を基本にする。
- `pypdf` の単純抽出だけではなく、`PyMuPDF` または `pdfplumber` で座標付き word / block を取る。
- title / abstract / left column / right column / caption / references / header / footer を領域として分ける。
- 本文は column 内で top-to-bottom に並べ、左カラムから右カラムへ進める。
- 図キャプションは本文へ混ぜず、`caption_text` として別 field にする。
- 図内文字は first cut では必須にせず、必要な場合だけ optional figure OCR とする。
- arXiv の縦ラベル、許諾文、header / footer は検索本文の主 field から外す。

## 画像の観察結果

- 画像はソフトウェア開発プロセスの歴史的な図で、文字が小さく、箱と矢印が密集している。
- 通常 OCR では `SYSTEM REQUIREMENTS` など一部は拾えるが、誤読が多い。
- 3 倍拡大・二値化しても、`DESIGN`、`DOCUMENTATION` などの一部は改善するが、
  図全体を信頼できる文章にはできない。
- 矢印の向きや関係は OCR だけでは復元できない。

## 画像の文字化方針

- この画像は paragraph text ではなく diagram として扱う。
- OCR output を正式本文にせず、candidate text として保存する。
- 右上の rule box、右側の simplified waterfall、中央の iterative process、
  左側の document flow のように region を分ける。
- 各 region で crop OCR を試し、confidence が低い場合は human review に回す。
- 正式な検索用テキストは、次のような `diagram_transcription` にする。

```text
Diagram: Royce final model / software development process
Main concepts:
- System requirements
- Software requirements
- Preliminary program design
- Analysis
- Program design
- Coding
- Testing
- Operations
Notes:
- The diagram emphasizes documentation, planned testing, customer involvement,
  and feedback between design, coding, testing, and operations.
```

## 出力 contract への反映

追加したい field:

- `body_text`: PDF / HTML の主本文。
- `caption_text`: 図表キャプション。
- `figure_text`: 図内 OCR 候補。
- `diagram_transcription`: human reviewed diagram text。
- `layout_warnings`: 2 段組、縦ラベル、低信頼 OCR など。
- `extraction_method`: `text_layer`, `coordinate_blocks`, `ocr_candidate`,
  `manual_reviewed_diagram` など。

## 判断

- PDF sample は alpha で扱う。座標ベース抽出が必要である。
- image sample は alpha で「OCR baseline と diagram transcription の設計」まで扱う。
- image OCR の完全自動化は alpha 必須にしない。
