# Web App

このディレクトリは、図書館システムの Web app 本体を置く場所である。

当面は、次の単位で分ける想定にする。

```text
web_app/
├── frontend/
├── backend/
├── shared/
├── scripts/
├── tests/
└── config.example.yml
```

ここには UI、API、schema、設定テンプレートを置く。個別の蔵書データ、PDF、個人メモは置かない。

現時点のデモ画面は `index.html` に置く。`web_app/` 配下を今後本体実装へ育てる前提の暫定 entrypoint とする。

現在の `index.html` は、`source_data -> extracted_data -> organized_data` の
完成イメージを確認する単体 HTML である。`extracted_data` の中では
`raw_text -> extracted_text` の編集段階を同じ画面で確認でき、右側の raw pane で
各内容を編集して preview に反映できる。
`organized_data` には整理済みメモを追記でき、各 file の tag も画面上で追加・編集できる。
