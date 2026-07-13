# Library Records

UI、検索、import/export のための正規化レコードを置く場所である。

first cut では、source 一覧を `sources.csv`、item の例を `items.example.jsonl` に置く。
実データの正本化が始まったら `items.jsonl` または DB へ移行する。

`organized_data/{item_id}/index.md` の冒頭 metadata block に入れる
`収集日`、`収集URL`、`ファイルの要約`、`タグ` は、検索や UI で使えるように
item record 側にも同期する。
