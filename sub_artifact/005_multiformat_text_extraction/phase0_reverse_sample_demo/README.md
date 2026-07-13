# Phase 0 Reverse Sample Demo

この directory は、Issue #6 の「完成品の実態がつかみにくい」という指摘に対する
Phase 0 の確認用 sub-artifact である。

先に 3 つの短い source text を作り、それを逆向きに HTML / PDF / JPG へ変換した。
そのうえで、将来 extractor が出すべき `plain_text.txt`、
`extraction_record.json`、`structured_text.json`、および
metadata header 付き `organized_examples/*/index.md` を置いた。

## 見る順序

1. `source_texts/` で元文章を見る。
2. `generated/` で HTML / PDF / JPG に変換された原本を見る。
3. `expected_extracted/` で extractor の期待出力を見る。
4. `organized_examples/` で metadata header 付きの整理済み item を見る。
5. `manifest.json` で対応関係を確認する。

## Sample Mapping

| source_id | generated source | expected extraction |
| --- | --- | --- |
| `requirements_note_html` | `generated/html/requirements_note.html` | `expected_extracted/requirements_note_html/` |
| `pdf_layout_note_pdf` | `generated/pdf/pdf_layout_note.pdf` | `expected_extracted/pdf_layout_note_pdf/` |
| `diagram_note_jpg` | `generated/image/diagram_note.jpg` | `expected_extracted/diagram_note_jpg/` |

## 確認コマンド

```sh
python3 sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generate_reverse_samples.py
python3 -m json.tool sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/manifest.json >/tmp/phase0_manifest_check.json
find sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/expected_extracted -name '*.json' -print -exec python3 -m json.tool {} \; >/tmp/phase0_expected_json_check.txt
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/pdf/pdf_layout_note.pdf
file sub_artifact/005_multiformat_text_extraction/phase0_reverse_sample_demo/generated/image/diagram_note.jpg
```

## 処理イメージ

HTML sample は、`nav` と `footer` を落として本文、見出し、箇条書きを
`body_text` として保存する想定である。

PDF sample は、text layer を持つ 2 段組文書として扱う。将来の extractor は
OCR に逃げる前に native text を確認し、座標で本文順序を作り、
caption を `caption_text` に分ける。

JPG sample は、OCR 候補だけで文章化しない。図中 label は `figure_text` に置き、
検索用には human review 済みの `diagram_transcription` を使う。

## metadata header contract

`organized_examples/*/index.md` は Issue #7 の metadata header contract に合わせ、
先頭に `収集日`、`収集URL`、`ファイルの要約`、`タグ` を置く。
`expected_extracted/*/plain_text.txt` には metadata header を付けない。
