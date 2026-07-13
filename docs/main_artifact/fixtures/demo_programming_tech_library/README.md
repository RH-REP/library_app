# Demo Programming Tech Library Data

このディレクトリは、共有可能な demo 用データの置き場である。

想定する内訳:

```text
demo_programming_tech_library/
├── records/
├── snippets/
├── source_samples/
└── search_cases/
```

ここには架空データ、十分に匿名化したデータ、再現用の最小データだけを置く。

`source_samples/` には、alpha 開発や importer/preview 検証で使う HTML、PDF、画像などの代表的な原本サンプルを置く。

現時点では、実際に取得した外部ソース snapshot だけを残す。

- `actual/` 配下: issue #5 の follow-up で実際に検索して保存した外部ソースの snapshot

`records/actual_web_source_samples.json` は actual source の provenance 付き index
として扱う。以前作成した synthetic fixture と `records/alpha_source_samples.json` は
issue #5 の follow-up により削除した。
