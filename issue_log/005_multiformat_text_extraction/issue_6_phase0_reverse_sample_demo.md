# Issue #6 Phase 0 Reverse Sample Demo

## 背景

Issue #6 の追加コメントで、現状の実装工程だけでは完成品の実態がつかみにくいと
指摘された。そこで Phase 0 に戻り、元文章から HTML / PDF / JPG を逆生成し、
将来の処理結果まで見える確認用 sub-artifact を作成した。

## 追加した場所

- `sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/`

## 構成

- `source_texts/`: 逆生成前の元文章 3 件。
- `generated/html/`: HTML 原本 sample。
- `generated/pdf/`: text-layer PDF 原本 sample。
- `generated/image/`: 図表 JPG 原本 sample。
- `expected_extracted/`: extractor が作るべき期待出力。
- `organized_examples/`: metadata header 付きの整理済み item 例。
- `manifest.json`: source text、生成原本、期待出力、整理例の対応表。
- `generate_reverse_samples.py`: 生成物を再作成する deterministic script。

## 確認観点

- HTML は navigation / footer を落とし、本文・見出し・箇条書きを `body_text` にする。
- PDF は OCR へ逃がす前に native text layer を確認し、2 段組と caption を分離する。
- JPG は OCR candidate を `figure_text` に残し、検索用には
  human review 済み `diagram_transcription` を使う。
- `plain_text.txt` には metadata header を付けない。
- metadata header は `organized_examples/*/index.md` の冒頭だけに付ける。

## 手元確認コマンド

```sh
python3 sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generate_reverse_samples.py
python3 -m py_compile sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generate_reverse_samples.py
find sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo -name '*.json' -print -exec python3 -m json.tool {} \;
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/pdf/pdf_layout_note.pdf
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/image/diagram_note.jpg
pdftotext sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/pdf/pdf_layout_note.pdf -
```
