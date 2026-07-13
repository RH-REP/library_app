# Work Log

## 2026-07-10

- GitHub issue #2 の Worker v1 入力を受領した。
- `main_artifact/goal.md` と `main_artifact/development_process.md` を確認した。
- 参照先 `.tools/knowledge_web/README.md`、`index.html`、`styles.css`、`app.js` を確認した。
- `sub_artifact/002_demo_screen_viewer/` と `issue_log/002_demo_screen_viewer/` の元になる成果物を作成した。
- 静的 HTML デモ `demo.html` を作成した。
- 成果物説明を `artifact.md` と `issue_log/002_demo_screen_viewer/issue_2_demo_screen.md` に記録した。
- `node` で HTML 内の inline script 構文を確認した。
- `git diff --check` で whitespace エラーがないことを確認した。
- Playwright と in-app browser はこのセッションで利用できなかったため、ブラウザ実画面の自動確認は未実施。

## 2026-07-10 follow-up

- 追加コメント「main_artifact に lib フォルダを作り、その中の readme.md を viewer で見たい」を受領した。
- current assignment の generic path `sub_artifact/002_artifact` を `sub_artifact/002_demo_screen_viewer` に改名した。
- `issue_log/002_artifact` を `issue_log/002_demo_screen_viewer` に改名した。
- `.core_program/assignment_state.json` の issue #2 sub artifact path を更新した。
- `main_artifact/lib/readme.md` を追加した。
- `demo.html` を `main_artifact/lib/readme.md` のみを表示する構成に絞り、実際の lib 参照に合わせた。

## 2026-07-11 follow-up

- 追加コメント「GitHub で誰でも確認できる方法がよい」を受領した。
- GitHub Pages 用に `docs/` 配下へ demo viewer と `readme.md` の公開コピーを作成した。
- `docs/index.html` を追加し、Pages のルートから demo viewer へ遷移するようにした。

## 2026-07-11 follow-up 2

- 追加コメントで、`main_artifact/lib/` を廃止し、viewer の参照先を現行の `web_app / private_data / fixtures` 構成へ差し替える方針を受領した。
- `main_artifact/lib/readme.md` と `docs/main_artifact/lib/readme.md` を削除した。
- `demo.html` のツリー表示と fetch 先を、`main_artifact/web_app_directory_plan.md`、`main_artifact/web_app/README.md`、`main_artifact/private_data/programming_tech_library/README.md`、`main_artifact/fixtures/demo_programming_tech_library/README.md` へ差し替えた。
- Pages 公開用の `docs/main_artifact/...` コピーも新構成へ同期した。

## 2026-07-13 follow-up

- 追加コメント「デモ画面をmainで実装して」を受領した。
- `sub_artifact/002_demo_screen_viewer/demo.html` の内容を `main_artifact/web_app/index.html` に昇格した。
- `docs/main_artifact/web_app/index.html` を追加し、公開用コピーの正本も `main_artifact/web_app/` 起点に揃えた。
- `docs/index.html` の遷移先を `docs/main_artifact/web_app/index.html` へ変更した。
- `main_artifact/web_app/README.md` に暫定 entrypoint として `index.html` を使う旨を追記した。
