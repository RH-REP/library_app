# Library Folder Structure Review

Issue #7 の依頼に対する、図書館データの実フォルダ構成レビューである。

参照した前提:

- Web app は `main_artifact/web_app/` に置く。
- 個別データは `main_artifact/private_data/programming_tech_library/` に寄せる。
- 共有可能な demo data は `main_artifact/fixtures/demo_programming_tech_library/` に分ける。
- UI は Explorer 型で、path、kind、tag、status を使って検索・絞り込みする。
- HTML / PDF / image は Python extractor で plain text 化する方針がある。

## 結論

ユーザー案の方向性はよい。特に、未処理の `input/`、原本置き場、整理済み text、
処理ログを分ける発想は実用的である。

ただし first cut では、`organized_data/` に text 抽出結果を直接置くのではなく、
次の 3 段階に分ける方が破綻しにくい。

1. 原本を保存する `raw_sources/`
2. 原本から機械的に抽出した `extracted_text/`
3. 整理AIや人間が内容単位にまとめた `organized_data/`

`raw_sources/` と `extracted_text/` は source ID で 1 対 1 に対応させる。
`organized_data/` は content または item ID で管理し、必要に応じて複数 source を参照する。

## 推奨 first cut

```text
main_artifact/private_data/programming_tech_library/
├── README.md
├── input/
│   └── inbox/
├── process_log.csv
├── raw_sources/
│   └── src_YYYYMMDD_NNN_short_slug/
│       ├── original/
│       │   └── original_file.ext
│       ├── source_manifest.json
│       └── attachments/
├── extracted_text/
│   └── src_YYYYMMDD_NNN_short_slug/
│       ├── plain_text.txt
│       └── extraction_record.json
├── organized_data/
│   └── item_YYYYMMDD_NNN_short_slug/
│       ├── index.md
│       ├── source_refs.json
│       └── notes.md
├── library_records/
│   ├── sources.csv
│   └── items.jsonl
├── research_requests/
└── review_queue/
```

### `input/`

ユーザーや調査Agentがファイルを置く未処理 dropbox とする。

ここでは分類しない。PDF、画像、HTML、CSV などが混在してよい。
整理AIが処理を開始したら、原本は `raw_sources/{source_id}/original/` へコピーまたは移動する。

実用ルール:

- `input/inbox/` は未処理だけを置く。
- 処理済みファイルを `input/` に残し続けない。
- 重複判定はファイル名ではなく sha256 で行う。

### `raw_sources/`

原本の保存場所である。ユーザー案の `raw_data/` に相当する。

既存文書では `raw_sources/` という名前が出ているため、この repository では
`raw_data/` より `raw_sources/` を推奨する。意味も「原本」に寄るため、
抽出結果や整理済み情報と混ざりにくい。

実用ルール:

- 原本は原則として変更しない。
- 1 source ごとに `src_YYYYMMDD_NNN_short_slug/` を作る。
- 元ファイル名は `source_manifest.json` に保存する。
- 同じ内容の再取り込みは `sha256` で検出する。

### `extracted_text/`

HTML / PDF / image から機械的に得た text を置く。

ここは「整理済み知識」ではなく「抽出結果」である。OCR ノイズ、PDF の読み順崩れ、
HTML の nav 混入が残る可能性があるため、`organized_data/` と分ける。

実用ルール:

- `raw_sources/{source_id}/` と同じ `source_id` を使う。
- 出力ファイル名は固定名にする。
- first cut の最小出力は `plain_text.txt` と `extraction_record.json` にする。
- status は `ok`、`needs_ocr`、`needs_review`、`failed` を最低限持つ。

### `organized_data/`

整理AIまたは人間が、source を読書・知識単位にまとめた結果を置く。

ここは source file 単位ではなく item/content 単位にする。1 冊の本に PDF、画像、
HTML メモが複数ある場合でも、1 つの item に集約できるためである。

実用ルール:

- `item_YYYYMMDD_NNN_short_slug/` を使う。
- `index.md` に整理済み本文または概要を置く。
- `source_refs.json` で参照元 source ID を列挙する。
- 手書きメモは `notes.md` に分ける。

### `library_records/`

UI、検索、import/export のための正規化レコードを置く。

最初は DB ではなく小さな file contract でよい。

推奨:

- `sources.csv`: 原本 source の一覧。
- `items.jsonl`: 整理済み item の一覧。

`process_log.csv` は処理履歴、`library_records/` は現在の正規化状態として分ける。
この分離をしないと、処理のやり直しや失敗ログが検索対象の正本に混ざる。

## `.library_skill` のレビュー

ユーザー案:

```text
.library_skill/
```

目的が「PDF、HTML などを text 変換する Python program」であれば、dot prefix は
少し危ない。

理由:

- hidden directory なので、人間や UI の Explorer から見落としやすい。
- Python package として import する名前に向かない。
- 配布や archive のときに「隠し内部ファイル」と誤解されやすい。

推奨は次のどちらかである。

### 案A: Web app の import utility として置く

```text
main_artifact/web_app/scripts/extractors/
├── html_to_text.py
├── pdf_to_text.py
├── image_ocr_to_text.py
└── common.py
```

Web app の取り込み機能として育てるなら、この置き方が自然である。

### 案B: 独立した library skill として置く

```text
main_artifact/library_skill/
├── README.md
├── extractors/
│   ├── html_to_text.py
│   ├── pdf_to_text.py
│   ├── image_ocr_to_text.py
│   └── common.py
└── schemas/
    └── extraction_record.schema.json
```

Agent や CLI が共通で使う補助 program として始めるなら、この置き方が分かりやすい。
dot prefix は使わず、見える名前にする。

## 命名規則

### ディレクトリ名

- 小文字英数字、ハイフン、アンダースコアだけを使う。
- 日本語タイトルや長い本名をそのまま path にしない。
- 日付は `YYYYMMDD` に統一する。
- source は `src_YYYYMMDD_NNN_short_slug` にする。
- item は `item_YYYYMMDD_NNN_short_slug` にする。

例:

```text
src_20260713_001_requirements_engineering_wikipedia
item_20260713_001_requirements_engineering
```

### ファイル名

原本は `original/` の下に保存し、元ファイル名をできるだけ残す。
派生物は固定名にする。

推奨する固定名:

```text
source_manifest.json
plain_text.txt
extraction_record.json
index.md
source_refs.json
notes.md
```

`file_A`、`file_B`、`raw_fileA` のような名前は避ける。後から見たときに役割が分からない。

## `process_log.csv` の最小 column

`process_log.csv` は append-only の処理履歴にする。

```csv
run_id,source_id,item_id,input_path,raw_path,text_path,media_type,sha256,extractor,status,started_at,finished_at,warnings
```

status の first cut:

```text
queued
raw_archived
extracted
needs_ocr
needs_review
organized
failed
skipped_duplicate
```

注意点:

- `process_log.csv` を唯一の正本にしない。
- 最新状態は `source_manifest.json`、`extraction_record.json`、`library_records/` にも残す。
- 失敗時も行を残し、空の `plain_text.txt` だけで成功扱いにしない。

## 処理フロー

```text
input/inbox/
  -> raw_sources/{source_id}/original/
  -> extracted_text/{source_id}/plain_text.txt
  -> organized_data/{item_id}/index.md
  -> library_records/sources.csv, items.jsonl
```

1. ユーザーまたは調査Agentが `input/inbox/` に原本を置く。
2. 整理AIが sha256、media type、source ID を決める。
3. 原本を `raw_sources/{source_id}/original/` に保存する。
4. Python extractor が `extracted_text/{source_id}/plain_text.txt` を作る。
5. 整理AIが内容を確認し、`organized_data/{item_id}/` にまとめる。
6. UI と検索用に `library_records/` を更新する。

## UI との対応

Explorer UI では、全部の実ファイルをそのまま表示するとノイズが多い。

優先して見せるもの:

- `organized_data/{item_id}/index.md`
- `library_records/items.jsonl`
- review が必要な `extracted_text/{source_id}/plain_text.txt`

通常は隠してよいもの:

- `raw_sources/{source_id}/original/`
- OCR 前の画像や PDF 原本
- `process_log.csv` の全履歴

UI の filter では、次の kind/status を使うと扱いやすい。

kind:

```text
item
source
text
record
request
note
```

status:

```text
queued
extracted
needs_review
organized
failed
```

## ユーザー案への実践コメント

良い点:

- `input/` を用意するのは正しい。人間と調査Agentの投入場所を固定できる。
- 原本と text を分ける方針は正しい。後で OCR や再抽出をやり直せる。
- `process_log.csv` を置く発想は正しい。整理AIの処理を追跡できる。

修正したい点:

- `.library_skill` は hidden directory なので、実装が見えにくくなる。
- `organized_data/{contents}/file_A` は名前が曖昧で、後から検索・UI表示しづらい。
- `raw_data` と `organized_data` を完全な同一フォルダ構成にすると、source 単位と知識 item 単位が混ざる。
- `process_log.csv` だけに現在状態を持たせると、再実行や失敗復旧が難しくなる。

first cut のおすすめ:

- 原本は `raw_sources/{source_id}/`。
- 抽出 text は `extracted_text/{source_id}/`。
- 整理済み知識は `organized_data/{item_id}/`。
- 関係は `source_refs.json` と `library_records/` で結ぶ。

## 次に決めること

このレビューを採用するなら、次 issue では次を実施するとよい。

1. `main_artifact/private_data/programming_tech_library/README.md` に first cut 構成を反映する。
2. 空ディレクトリを commit する必要がある場合だけ `.gitkeep` を置く。
3. `source_manifest.json` と `extraction_record.json` の最小 schema を決める。
4. `process_log.csv` の status と更新タイミングを extractor 実装に合わせて固定する。
