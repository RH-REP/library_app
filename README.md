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
初期化が終わったあとの issue #1 は通常の作業用には使わず、
Session_router の契約違反 bug report の受け皿としてだけ再利用してください。
bug report を投稿する必要があるときは、issue #1 を reopen してから投稿します。

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

## 利用（clone して使う側）

この repo を clone したフォルダで使う。clone 側では直さず、開発側で直してコミットし、clone 側の `update.command`（`git pull --ff-only`）で取り込む。エンジンの実行記録は `.gitignore` で除外してあるので、pull で消えたり書き換わったりしない。

- 正本: 開発側の `main_artifact/` `sub_artifact/` `issue_log/`（Git で追跡している成果物と作業記録）。clone 側にはその clone と、Git で追跡しないエンジンの実行記録を置く。
- 起動: clone 側の `start.command` をダブルクリック（静的なデモビューア `index.html` を開くだけ）。
- **Issue は issue_hub（別の repo。複数の app の Issue を外側から回す）で回す。この repo のエンジン（`.core_program/` の issue 取得・dispatch）は使わない**（2026-10-23 から。両方を動かすと同じ書き込みに2つのセッションが起動する）。エンジンは upstream の ArtifactForge から来るので消さずに残してある。issue_hub は、このエンジンが書いた目印（`codex-agent-v1`）も読んで番を決める。
- （使っていた頃の手順）エンジン（issue 取得・dispatch）は `start.command` からは起動しない。開発側で動かし、記録を clone 側に置くときは
  `python3 .core_program/app/01_fetch_issue/run_issue_queue.py --output <clone>/.core_program/app/01_fetch_issue/data/open_issues.json`
  や dispatch の `run_dir_base` でその場所を指す。既定のまま動かすと開発側に新しく作る（`.gitignore` 済み）。

### 改善のコメント（右上の !）

画面右上の「!」を押すと、今の画面 ID（`data-screen`）とコメントを書き込んだ GitHub の「新しい Issue」画面（`RH-REP/library_app`）が開く。中身を確かめてから GitHub で送る。この repo は公開なので、送った中身は公開される。そのため画面の写真は既定で付けない（選んだときだけ端末に保存し、本人が GitHub で添付する）。ボタンの部品は `feedback.js`（正本は issue_hub の `feedback/feedback.js`。直すときは正本を直して写し直す）。

### 置いてあるもの

| パス | 内容 |
|---|---|
| `start.command` | 起動口。この clone の `index.html`（デモビューア）を開く |
| `update.command` | `git pull --ff-only` で開発側のコミットを取り込む。実行記録は消さない |
| `.core_program/app/01_fetch_issue/data/open_issues.json` | issue 取得結果のスナップショット（`.gitignore` で除外） |
| `.core_program/app/02_dispatch_queue/data/visible_sessions/<日時>_<種別>/` | エージェント起動ごとの `prompt.md` と `launch.command`（`.gitignore` で除外） |
