# Organized Text Metadata Header Contract

Issue #7 の follow-up として、`organized_data/{item_id}/index.md` の冒頭に置く
metadata block の現状契約をまとめる。

## 対象

対象 file:

```text
main_artifact/private_data/programming_tech_library/organized_data/{item_id}/index.md
```

この file は、整理AIまたは人間が source を読んで、item/content 単位に整理した text の本文である。

## 必須 header

`index.md` の最初の行から、次の block を置く。

```text
""""""
収集日：YYYY-MM-DD
収集URL：https://example.com/source
ファイルの要約：1〜3文で内容を要約する。
タグ：tag1, tag2
""""""
```

## 必須項目

- `収集日`: source を収集した日。まずは `YYYY-MM-DD` に統一する。
- `収集URL`: 収集元 URL。local file だけの場合は `local:` prefix を使う。
- `ファイルの要約`: source または item の要約。first cut では 1〜3 文にする。
- `タグ`: comma-separated の短い分類語。

不明な値は空欄にせず `未確認` と書く。

## 役割

この header は、人間、整理AI、LLM が text file を開いた瞬間に文脈を理解するための表示用 metadata である。

ただし、機械処理の唯一の正本にはしない。次の structured data と同期して扱う。

- `source_refs.json`
- `library_records/items.jsonl`
- source manifest
- extraction record

## parse rule

- 先頭行が `""""""` なら metadata block として読む。
- 次の `""""""` までを header とする。
- header 内は `key：value` の 1 行 1 項目にする。
- value 内に `""""""` を入れない。
- header の後に 1 空行を置き、その後に Markdown 本文を書く。

## 現時点の判断

- YAML front matter ではなく、ユーザー指定に近い quoted block を採用する。
- 日本語 label を使い、人間が直接編集しやすい形式にする。
- 将来 parser を作る場合は、`収集日`、`収集URL`、`ファイルの要約`、`タグ` の 4 label を固定 key として扱う。
