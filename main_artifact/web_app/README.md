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
