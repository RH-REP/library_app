# Issue #6 Phase 1 Contract Subagent Integration

## 依頼

ユーザーは、1 phase を機能単位の数に分けてサブエージェントに開発させ、
worker が integration と検証を行うよう依頼した。

この対応では Phase 1: Extraction contract 更新を対象にした。

## 分担

### Subagent A: Python contract helper

担当:

- `main_artifact/library_skill/extractors/common.py`

実施内容:

- `ExtractionRecord` に `layout_warnings` と `extraction_method` を追加した。
- `ExtractionResult` に `body_text`, `caption_text`, `figure_text`,
  `diagram_transcription` を追加した。
- `write_extraction_result()` が `plain_text.txt`,
  `extraction_record.json`, `structured_text.json` を出力するようにした。
- `figure_text` は低信頼 OCR 候補として扱い、default では `plain_text.txt` に混ぜない。

### Subagent B: schema / docs

担当:

- `main_artifact/library_skill/schemas/extraction_record.schema.json`
- `main_artifact/library_skill/schemas/structured_text.schema.json`
- `main_artifact/library_skill/extractors/README.md`
- `main_artifact/library_skill/README.md`

実施内容:

- `extraction_record.schema.json` に `extraction_method` と `layout_warnings` を追加した。
- `structured_text.schema.json` を追加した。
- Phase 1 の output file boundary を README に記録した。
- metadata header は `organized_data/{item_id}/index.md` にだけ置く方針を明記した。

## Worker integration

- Python helper と schema/docs の field が対応していることを確認した。
- README の `plain_text.txt` 説明を、実装に合わせて調整した。
- `plain_text.txt` は body / caption / diagram transcription の default 合成 text とし、
  `figure_text` は caller が明示した場合だけ混ぜる方針にした。

## 検証結果

- `python3 -m py_compile` で common helper と skeleton extractors を確認した。
- `python3 -m json.tool` で `extraction_record.schema.json` と
  `structured_text.schema.json` の JSON 構文を確認した。
- `write_extraction_result()` の一時出力で、`plain_text.txt`、
  `extraction_record.json`、`structured_text.json` が生成されることを確認した。
- default の `plain_text.txt` に `figure_text` が混ざらないことを確認した。
- `git diff --check` で空白エラーがないことを確認した。
