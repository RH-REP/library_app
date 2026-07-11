# ArtifactForge

ArtifactForge は、GitHub issue に書いた相談から `goal.md` と
`development_process.md` を AI agent と一緒に作り、制作作業を進めるための
リポジトリです。

clone 後に自分の repository として使う手順は [USER_MANUAL.md](USER_MANUAL.md) を参照してください。
通常ユーザーが読む文書は、この `README.md` と `USER_MANUAL.md` だけで十分です。

## 最初にすること

コマンドで新しい project repository の作成、remote 設定、最初の issue 投稿まで
進める場合:

```sh
python3 .core_program/app/00_initialize_project/init_project.py
```

実際に作成・投稿する前に内容だけ確認する場合:

```sh
python3 .core_program/app/00_initialize_project/init_project.py --dry-run
```

ダウンロード後、最初の GitHub issue に「このアーティファクトで何を作りたいか」
を書いてください。

下のテンプレートを issue に貼り付け、まず3つだけ埋めれば十分です。
オプションは空欄でも構いません。AI agent が質問しながら
`main_artifact/goal.md` と `main_artifact/development_process.md` を整理します。

```md
# 作りたいアーティファクト

## 何を作りたいですか？

例: 文書、調査レポート、申請書、Webアプリ、分析資料、創作物、運用手順など。

ここに書いてください:

## 進め方の希望はありますか？

例: まず相談したい、先に調査したい、目次から作りたい、小さく分けたい、レビューを挟みたい、など。

ここに書いてください:

## ゴールはなんですか？

成功条件、品質、使える状態、提出先、読者、利用者などを書いてください。

ここに書いてください:

---

## option: なぜ作りたいですか？

背景、困っていること、目的、使う場面など。

ここに書いてください:

## option: すでにある材料はありますか？

既存ファイル、URL、メモ、PDF、画像、過去の issue、参考資料など。

ここに書いてください:

## option: 作業で避けたいことはありますか？

やらないでほしいこと、まだ決めたくないこと、触ってほしくない範囲など。

ここに書いてください:

---

## AI agent 向けコメント

この issue は、この ArtifactForge project の最初の相談です。

まず、この issue の回答から次の2ファイルを作成または更新してください。

- `main_artifact/goal.md`
- `main_artifact/development_process.md`

作成時は、必要に応じて次のテンプレートを参照してください。

- `main_artifact/.goal_template.md`
- `main_artifact/.development_process_template.md`

ユーザーの回答が不足している場合は、推測で確定せず、仮置きの内容と確認事項を分けてください。
最初から細かく作り込みすぎず、次にユーザーが判断しやすい工程にしてください。
```

## ファイルの役割

- `main_artifact/.goal_template.md`: `goal.md` 作成用の AI agent テンプレート
- `main_artifact/.development_process_template.md`: `development_process.md` 作成用の AI agent テンプレート
- `main_artifact/`: 完成品または統合された主成果物と、その目標・工程を置く場所
- `main_artifact/goal.md`: AI agent が最初の issue から作る制作目標。個別 project のデータです
- `main_artifact/development_process.md`: AI agent が最初の issue から作る工程。個別 project のデータです
- `sub_artifact/`: 主成果物を完成・改善するための中間成果物、部品、調査、試作、補助作業の場所
- `issue_log/`: issue ごとの判断や作業記録を残す場所
- `.core_program/`: 内部エンジン用。通常は直接編集しません
