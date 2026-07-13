# Three-Review Implementation Process: Multiformat Text Extraction

Issue #6 の次実装では、extractor を一気に作らず、3 段階レビュー方式で進める。
各レビューは、次の実装へ進んでよいかを判断する gate として扱う。

## 3 段階レビューの全体像

```text
Phase 0-2
  -> Review 1: Contract Review
Phase 3-5
  -> Review 2: Extractor Output Review
Phase 6-7
  -> Review 3: Organized Data Review
```

レビューの目的:

- Review 1:
  実装前に contract と保存境界を固める。
- Review 2:
  実サンプルの抽出結果が検索に渡せる品質か確認する。
- Review 3:
  `organized_data/` と metadata header が、参照・検索・UI へ渡せる形か確認する。

## 参照する既存契約

- `sub_artifact/006_library_folder_structure/metadata_header_contract.md`
- `main_artifact/private_data/programming_tech_library/extracted_text/README.md`
- `main_artifact/private_data/programming_tech_library/organized_data/README.md`
- `main_artifact/library_skill/extractors/common.py`
- `main_artifact/library_skill/schemas/extraction_record.schema.json`

## 前提

- extractor の一次出力は `extracted_text/{source_id}/` に置く。
- 整理済み知識は `organized_data/{item_id}/` に置く。
- `plain_text.txt` の冒頭には metadata header を付けない。
- metadata header は `organized_data/{item_id}/index.md` の先頭だけに置く。
- `index.md` の metadata header は表示用であり、機械処理の唯一の正本にしない。
- 機械処理用 metadata は `extraction_record.json`、`source_refs.json`、
  `library_records/items.jsonl`、source manifest と同期する。

## Phase 0: 環境と依存の固定

目的:
Python extractor を実装する前に、実行環境で使える parser / OCR / PDF tool を確認する。

作業:

- Python 依存を確認する。
  `beautifulsoup4`, `lxml`, `pypdf`, `pdfplumber`, `PyMuPDF`, `Pillow`, `pytesseract`
- CLI 依存を確認する。
  `pdfinfo`, `pdftoppm`, `pdftotext`, `tesseract`
- Tesseract の language pack を確認する。
  first cut は `eng`、必要が出た時点で `jpn` を追加する。
- sample 3 件を Python から読めることを確認する。

完了条件:

- 不足 dependency が明示されている。
- 実装前に、HTML / PDF / image のどれを先に動かせるか判断できる。

## Phase 1: Extraction contract 更新

目的:
`plain_text` だけでは PDF の caption や画像の図表転記を扱いきれないため、
共通 contract を拡張する。

更新対象:

- `main_artifact/library_skill/extractors/common.py`
- `main_artifact/library_skill/schemas/extraction_record.schema.json`
- `main_artifact/library_skill/schemas/structured_text.schema.json`
- `main_artifact/library_skill/extractors/README.md`

追加する候補 field:

- `body_text`: HTML / PDF の主本文。
- `caption_text`: 図表キャプション。
- `figure_text`: 図内 OCR 候補。
- `diagram_transcription`: human reviewed の図表転記。
- `layout_warnings`: 2 段組、縦ラベル、図混在、低信頼 OCR など。
- `extraction_method`: `text_layer`, `coordinate_blocks`, `ocr_candidate`,
  `manual_reviewed_diagram` など。

出力方針:

- `plain_text.txt` は検索投入用の合成 text として残す。
- `extraction_record.json` に source、status、method、warnings などの machine metadata を残す。
- `structured_text.json` に body / caption / figure / diagram transcription の field を残す。
- 図表 OCR の低信頼 text は `plain_text.txt` に無条件で混ぜない。

完了条件:

- extractor 本体が未実装でも、拡張 contract の schema と dataclass が一致している。
- 旧 contract の `plain_text.txt` / `extraction_record.json` は壊さない。
- 追加出力の `structured_text.json` は schema で検証できる。

## Phase 2: metadata header adapter

目的:
Issue #7 の `organized_data/{item_id}/index.md` 冒頭 metadata header を、
extractor 後段の organizer で生成できるようにする。

metadata header 形式:

```text
""""""
収集日：YYYY-MM-DD
収集URL：https://example.com/source
ファイルの要約：1〜3文で内容を要約する。
タグ：tag1, tag2
""""""
```

実装方針:

- `render_metadata_header()` のような小さな helper を用意する。
- 不明な値は空欄にせず `未確認` にする。
- local file だけの場合は `収集URL` に `local:` prefix を使う。
- `タグ` は comma-separated の短い語にする。
- header の後に 1 空行を置いて Markdown 本文を始める。
- parser を作る場合は、`収集日`、`収集URL`、`ファイルの要約`、`タグ` を固定 key とする。

注意:

- この header は `extracted_text/{source_id}/plain_text.txt` には付けない。
- header は `organized_data/{item_id}/index.md` のための表示用 metadata である。
- 同じ情報を `source_refs.json` と `library_records/items.jsonl` にも保持する。

完了条件:

- `_template/index.md` と同じ形式の header を生成できる。
- header と structured metadata の同期方針が README に書かれている。

## Review 1: Contract Review

対象:

- `ExtractionResult` / `ExtractionRecord`
- `extraction_record.schema.json`
- `structured_text.schema.json`
- `plain_text.txt` / `extraction_record.json` の出力 contract
- `structured_text.json` の出力 contract
- `metadata_header_contract.md` との接続
- `extracted_text/` と `organized_data/` の境界

確認観点:

- `plain_text.txt` に metadata header を付けない判断が守られているか。
- `organized_data/{item_id}/index.md` にだけ metadata header を付ける設計になっているか。
- `body_text`, `caption_text`, `figure_text`, `diagram_transcription`,
  `layout_warnings`, `extraction_method` が必要十分か。
- 低信頼 OCR を `plain_text.txt` に無条件で混ぜない設計になっているか。
- `未確認` と `local:` prefix の扱いが metadata header adapter に入っているか。

レビュー成果物:

- contract 差分
- schema 差分
- サンプル `extraction_record.json`
- サンプル `structured_text.json`
- サンプル metadata header

通過条件:

- user または reviewer が、contract と保存境界に同意している。
- Phase 3-5 の形式別 extractor を実装しても後戻りが少ない状態である。

## Phase 3: HTML extractor first cut

目的:
HTML snapshot から検索に使える主本文を取り出す。

実装順:

1. Beautiful Soup + `lxml` parser で HTML を読む。
2. `script`, `style`, `noscript`, `nav`, `footer`, `aside` を除去する。
3. `title`, `h1-h3`, `p`, `li` を優先して `body_text` にする。
4. link text は残すが、navigation の link 群は落とす。
5. `plain_text.txt` は `body_text` 中心に生成する。
6. `requirements_engineering_wikipedia.html` で expected keyword を確認する。

完了条件:

- HTML sample 1 件で `status=ok` の extraction result が出る。
- navigation が本文より多く残らない。

## Phase 4: PDF coordinate extraction first cut

目的:
2 段組 PDF から本文、caption、図内候補を混ぜずに抽出する。

実装順:

1. text layer の有無を確認する。
2. `pypdf` で単純抽出を baseline として保存する。
3. `pdfplumber` または `PyMuPDF` で word / block 座標を取得する。
4. ページごとに header / footer / left column / right column / caption region を分ける。
5. column 内は top-to-bottom、left-to-right に並べる。
6. 図キャプションは `caption_text` に分離する。
7. arXiv 縦ラベル、許諾文、図内 OCR 候補は `layout_warnings` または別 field に回す。

完了条件:

- `software_through_pictures_arxiv.pdf` で本文順序が大きく崩れない。
- caption が本文に無制御に混ざらない。
- OCR に逃がさず `status=ok` または `needs_review` を返せる。

## Phase 5: Image OCR candidate と diagram transcription

目的:
図表画像を「文章 OCR」としてではなく、図表として検索可能にする。

実装順:

1. Pillow で画像を開く。
2. grayscale / autocontrast / upscale / threshold の前処理候補を作る。
3. Tesseract で OCR candidate を得る。
4. confidence が低い場合は `status=needs_review` にする。
5. region 単位の OCR を試せる構造にする。
6. human reviewed の `diagram_transcription` を受け取れるようにする。

完了条件:

- `royce_final_model_waterfall.png` で OCR candidate と warning が残る。
- 正式な検索用 text は `diagram_transcription` 優先にできる。
- 矢印や関係は OCR だけで復元しない前提が明示されている。

## Review 2: Extractor Output Review

対象:

- HTML extractor first cut の出力
- PDF coordinate extraction first cut の出力
- Image OCR candidate と diagram transcription の出力
- `plain_text.txt`
- `extraction_record.json`

確認観点:

- HTML は navigation や footer が本文より多く残っていないか。
- PDF は 2 段組の本文順序が大きく崩れていないか。
- PDF の caption が本文へ無制御に混ざっていないか。
- PDF の図内 OCR 候補が本文と別 field になっているか。
- 画像 OCR は低信頼の場合に `needs_review` になるか。
- `diagram_transcription` は検索用 text として読める粒度か。
- warnings が、後で人間が判断できる内容になっているか。

レビュー成果物:

- HTML sample の抽出結果
- PDF sample の抽出結果
- image sample の OCR candidate
- image sample の diagram transcription
- 形式別の warning 一覧

通過条件:

- HTML と PDF は検索に投入できる baseline text になっている。
- image は完全自動 OCR ではなく、review 前提の diagram text として扱える。
- Phase 6 の organized data bridge に渡す入力が揃っている。

## Phase 6: organized_data bridge

目的:
抽出結果を、人間や整理AIが読む `organized_data/{item_id}/index.md` に変換する。

実装順:

1. extraction result を読み込む。
2. source manifest または extraction record から収集日と収集URLを取る。
3. summary と tags を organizer が作る。
4. metadata header を生成する。
5. header の後に Markdown 本文を置く。
6. `source_refs.json` に元 source ID を列挙する。
7. `library_records/items.jsonl` と同期する。

完了条件:

- `organized_data/{item_id}/index.md` の先頭に metadata header がある。
- `source_refs.json` で元 source を辿れる。
- header だけを機械処理の正本にしていない。

## Phase 7: 回帰確認

確認項目:

- HTML / PDF / image 各 sample で extractor が終了する。
- `plain_text.txt`、`extraction_record.json`、`structured_text.json` が生成される。
- PDF は body と caption が分離される。
- image は低信頼 OCR を `needs_review` として扱える。
- organized index は metadata header contract に合っている。
- 不明値は `未確認` として出力される。

完了条件:

- extractor の first cut と organized data bridge の境界が維持されている。
- 次に UI / search index へ渡すデータ形が説明できる。

## Review 3: Organized Data Review

対象:

- `organized_data/{item_id}/index.md`
- `organized_data/{item_id}/source_refs.json`
- `library_records/items.jsonl`
- metadata header
- search / UI に渡す最終的な text

確認観点:

- `index.md` の先頭が metadata header contract に合っているか。
- 必須項目 `収集日`, `収集URL`, `ファイルの要約`, `タグ` があるか。
- 不明値が空欄ではなく `未確認` になっているか。
- local source の URL が `local:` prefix になっているか。
- `source_refs.json` で元 source を辿れるか。
- metadata header と structured data が矛盾していないか。
- PDF caption や image diagram transcription が、読み物として自然に整理されているか。

レビュー成果物:

- サンプル `organized_data/{item_id}/index.md`
- サンプル `source_refs.json`
- サンプル `items.jsonl`
- 回帰確認結果

通過条件:

- ユーザーが organized item を読んで文脈を理解できる。
- 非 AI 検索に渡す text と metadata が揃っている。
- 次工程の UI / search index 実装に進める。

## 実装順まとめ

1. Phase 0: 環境と依存の固定
2. Phase 1: Extraction contract 更新
3. Phase 2: metadata header adapter
4. Review 1: Contract Review
5. Phase 3: HTML extractor first cut
6. Phase 4: PDF coordinate extraction first cut
7. Phase 5: Image OCR candidate と diagram transcription
8. Review 2: Extractor Output Review
9. Phase 6: organized_data bridge
10. Phase 7: 回帰確認
11. Review 3: Organized Data Review
