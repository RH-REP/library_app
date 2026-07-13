# ArtifactForge User Manual

ArtifactForge は、GitHub issue に書いた相談を起点に、AI agent と一緒に
制作目標、工程、個別成果物を育てていくための repository template です。

ArtifactForge 本体 repository は、engine/template の配布元です。
実際の project は、ユーザー自身の別 repository に保存します。
通常ユーザーが読む文書は、この `USER_MANUAL.md` と `README.md` だけで十分です。

## 1. ArtifactForge とは何か

ArtifactForge では、作りたいものを最初の issue に書きます。
AI agent はその内容を読み、次の project 用ファイルを作成・更新します。

- `main_artifact/`: 完成品または統合された主成果物と、その目標・工程を置く場所
- `main_artifact/goal.md`: 作りたいもの、目標、成功条件の正本
- `main_artifact/development_process.md`: 工程、レビュー点、次の作業の正本
- `sub_artifact/`: 主成果物を完成・改善するための中間成果物、部品、調査、試作、補助作業
- `issue_log/`: 人間が読める作業ログ、判断記録、レビュー記録
- `.core_program/`: 内部エンジン。通常ユーザーが直接編集しない場所

配布元の ArtifactForge には、個別 project の内容を push しません。
通常の作業は、必ずユーザー自身の repository に push します。

## 通常の開発プロセス
1. Issue に開発に関する提案・質問・調査を書く
2. GitHub issue を取り込んで queue / pending / archive を更新する
   ```sh
   python3 .core_program/app/01_fetch_issue/run_issue_queue.py
   ```
3. queue を Session_router / worker に dispatch する
   ```sh
   python3 .core_program/app/02_dispatch_queue/run_dispatch_queue.py
   ```
   `request_for_human/` や `human_wating/` の待機記録から適切な session を resume
   したいときは、こちらを使います。
   ```sh
   python3 .core_program/app/02_dispatch_queue/run_session_resume.py
   ```
4. 通常の project 開発では `.core_program/` を直接編集しない。更新が必要なときだけ `upstream/main` を取り込む。

## 2. clone/download 後の最初の設定

ArtifactForge の update をあとから取り込みたい場合は、download zip ではなく
`git clone` から始めるのがおすすめです。

最初の project repository 作成、remote 設定、first issue 投稿までをまとめて
行う場合は、次の初期化コマンドを使います。

```sh
python3 .core_program/app/00_initialize_project/init_project.py
```

実際に repository 作成や issue 投稿を行う前に確認したい場合は、dry-run を使います。
dry-run では、投稿予定の first issue title/body、remote 設定、実行予定コマンド、
実際には何も変更しないことが表示されます。

```sh
python3 .core_program/app/00_initialize_project/init_project.py --dry-run
```

このコマンドは、project repository 名、GitHub owner/org、公開範囲、README の
最初の3問と `option` の質問を聞き、GitHub repository を作成して `origin` に
設定し、最初の GitHub issue を投稿します。GitHub owner/org はログイン中の
`gh` ユーザーがデフォルトです。organization 配下に作りたい時だけ変更してください。
`option` の質問は空欄でも構いません。

初期化コマンドは、ArtifactForge 本体用の `.gitignore` をユーザー project 用に
調整し、`sub_artifact/` と `issue_log/` の中身を通常の Git 追跡対象にします。
`.core_program/` の queue、pending、archive、runtime state は引き続き追跡しません。

すでに `origin` / `upstream` / `.core_program/assignment_state.json` が揃っている
場合は初期化済みとして検出し、first issue の重複投稿はしません。やり直す必要が
ある時だけ `--force` を付けてください。

`<MY_APP_NAME>` は、自分の app/project の名前に置き換えてください。

```sh
cd /path/to/workspace
git clone <ARTIFACTFORGE_REPOSITORY_URL> <MY_APP_NAME>
cd <MY_APP_NAME>
```

clone 直後の `origin` は ArtifactForge 本体を指しています。
このまま作業すると、本体へ誤 push する危険があります。
まず本体 repository を `upstream` に名前変更します。

```sh
git remote rename origin upstream
git remote set-url --push upstream DISABLED
```

次に、GitHub などで自分用の空 repository を作ります。
その repository を `origin` として追加します。

```sh
git remote add origin <USER_PROJECT_REPOSITORY_URL>
git branch -M main
git remote -v
```

期待する形は次の通りです。

```text
origin    <USER_PROJECT_REPOSITORY_URL>      (fetch)
origin    <USER_PROJECT_REPOSITORY_URL>      (push)
upstream  <ARTIFACTFORGE_REPOSITORY_URL>     (fetch)
upstream  DISABLED                           (push)
```

download zip から始める場合は、展開した directory で Git repository を初期化します。

```sh
cd <MY_APP_NAME>
git init
git branch -M main
git remote add upstream <ARTIFACTFORGE_REPOSITORY_URL>
git remote set-url --push upstream DISABLED
git remote add origin <USER_PROJECT_REPOSITORY_URL>
git add .
git commit -m "Start project from ArtifactForge"
git push -u origin main
```

ただし、download zip には Git history がないため、あとで `upstream/main` を
merge しにくくなります。
ArtifactForge の更新を取り込みたい project では、clone から始めてください。

## 3. 自分の repository へ push する方法

通常の保存先は `origin` です。

```sh
git status
git push -u origin main
```

以後の通常作業でも、push 先は `origin` です。

```sh
git add <changed_files>
git commit -m "Update project artifact"
git push origin main
```

ArtifactForge 本体である `upstream` には push しません。

```sh
# 使わない
git push upstream main
```

### 個別 project データを保存する時の注意

ArtifactForge 本体 repository では、個別 project のデータが混ざらないように
`.gitignore` が強めに設定されています。

初期化コマンドを使ったユーザー project では、初回 push 前に `.gitignore` が
project 用に調整され、`sub_artifact/` と `issue_log/` は通常通り追加できます。

project データを保存する例:

```sh
git add main_artifact/goal.md
git add main_artifact/development_process.md
git add sub_artifact
git add issue_log
git commit -m "Add project artifact state"
git push origin main
```

どちらの場合も、push 先が `origin` であることを確認してください。

## 4. ArtifactForge 本体へ push しないための remote 設定

remote は次の考え方で分けます。

```text
origin    = ユーザー自身の project repository
upstream  = ArtifactForge 本体 repository。fetch-only
```

`upstream` の push URL は `DISABLED` にします。

```sh
git remote set-url --push upstream DISABLED
```

確認コマンド:

```sh
git remote -v
git remote get-url origin
git remote get-url upstream
git remote get-url --push upstream
```

`git remote get-url --push upstream` が `DISABLED` なら、ArtifactForge 本体へ
誤 push しにくい状態です。

## 5. `goal.md` の書き方

`main_artifact/goal.md` は、この project の制作目標の正本です。
最初は README の first issue テンプレートを GitHub issue に貼り付け、
AI agent に `goal.md` を作成してもらうのが基本です。
この最初の issue #1 は初期化用の入口で、初期化後は通常の作業には使わず、
Session_router の契約違反 bug report の受け皿としてだけ再利用します。
bug report を投稿する必要があるときは、issue #1 を reopen してから使います。

最初の issue で答える中心は3つです。

1. 何を作りたいですか？
2. 進め方の希望はありますか？
3. ゴールはなんですか？

`goal.md` には、最終的に次の内容が入ると扱いやすくなります。

- 制作目標
- 背景
- 成功条件
- 作る範囲
- 作らない範囲
- 参考資料
- 未確定事項

`main_artifact/.goal_template.md` は、AI agent 用のテンプレートです。
project 固有の内容は `.goal_template.md` に直接書き込まず、
`main_artifact/goal.md` に整理します。

## 6. issue を使った作業の流れ

ArtifactForge では、issue を作業の入口にします。

1. ユーザーが GitHub issue に相談や作業依頼を書く
2. AI agent が issue と `goal.md` を読む
3. 必要なら `development_process.md` を更新する
4. worker session が `sub_artifact/NNN_slug/` を作成・更新する
5. 判断や作業ログを `issue_log/` に残す
6. 次の issue fetch で pending 中の作業状態を確認する

実行時、ArtifactForge は人間との窓口を visible Session_router に集約します。
worker と subagent は通常 non-visible で動きます。権限、ログイン、判断待ちなど
人間の確認が必要な場合は、worker/subagent から直接ユーザーに聞かず、
Session_router 経由で確認します。
worker は作業完了時、変更を commit して `origin` へ push し、GitHub issue に
完了コメントを投稿します。

`sub_artifact/` は、成果物の単位です。
例:

```text
sub_artifact/
└── 001_report_outline/
    ├── sub_goal.md
    ├── plan.md
    ├── work_log.md
    ├── src/
    └── notes.md
```

`sub_artifact/NNN_slug/` の中身は自由な構成でよく、Markdown だけに限定しません。
必要なコード、テスト、データ、画像、生成物を置いて構いません。

`.core_program/` は router、queue、pending、assignment state などの内部状態を
扱います。通常ユーザーは直接編集しません。
人間が読むべき判断記録は、`.core_program/` ではなく `issue_log/` に残します。

## 7. ArtifactForge を更新したい時だけ upstream を取り込む方法

日常作業では `upstream` を触りません。
通常の project 開発では `.core_program/` を直接編集しません。ArtifactForge 本体の更新が必要な時だけ、明示的に取り込みます。
ArtifactForge 本体の template や engine を更新したい時だけ、明示的に取り込みます。

まず、作業中の変更が残っていないか確認します。

```sh
git status
```

単純に取り込む場合:

```sh
git fetch upstream
git merge upstream/main
git push origin main
```

より安全に確認する場合:

```sh
git switch -c update-artifactforge
git fetch upstream
git merge upstream/main
git status
```

内容を確認して問題なければ、`main` に戻して取り込みます。

```sh
git switch main
git merge update-artifactforge
git push origin main
```

更新時に conflict が出た場合は、ArtifactForge 本体の template 変更と、
自分の project 変更が同じ場所を触っています。
どちらを残すか判断してから解消してください。

## 8. よくある失敗と確認コマンド

### `origin` が ArtifactForge 本体を向いている

確認:

```sh
git remote -v
```

直し方:

```sh
git remote rename origin upstream
git remote set-url --push upstream DISABLED
git remote add origin <USER_PROJECT_REPOSITORY_URL>
```

### `upstream` に push できてしまう設定になっている

確認:

```sh
git remote get-url --push upstream
```

直し方:

```sh
git remote set-url --push upstream DISABLED
```

### `sub_artifact/` や `issue_log/` が `git status` に出ない

`.gitignore` の source repository guard により、個別 project データが
ignore されている可能性があります。

確認:

```sh
git check-ignore -v sub_artifact/001_example/plan.md
git check-ignore -v issue_log/001_example/work_log.md
```

初期化コマンドを使った場合は、`sub_artifact/*` と `issue_log/*` が
`.gitignore` から外れているはずです。手動セットアップの場合は、
`.gitignore` から次の2行を外してください。

```text
sub_artifact/*
issue_log/*
```

### GitHub で空ではない repository を作ってしまった

GitHub 側で README や `.gitignore` を先に作ると、初回 push で衝突することがあります。
できるだけ空 repository を作ってから `origin` に設定してください。

すでに作ってしまった場合は、状況を確認してから merge してください。

```sh
git fetch origin
git status
```

### いま作業している branch がわからない

確認:

```sh
git branch --show-current
git status --short
```

通常は `main` で作業します。

### 本体更新を取り込むべきか迷う

迷う場合は、まず fetch だけにしてください。
fetch だけなら local の作業内容は変わりません。

```sh
git fetch upstream
git log --oneline --decorate --max-count=10 upstream/main
```

merge するのは、ArtifactForge 本体の更新を自分の project に入れると決めてからです。
