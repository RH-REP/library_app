# Artifact

Issue #2 の依頼に対して、HTML のデモ画面を作成した。

## 作成ファイル

- `main_artifact/web_app_directory_plan.md`
- `main_artifact/web_app/README.md`
- `main_artifact/web_app/index.html`
- `main_artifact/private_data/programming_tech_library/README.md`
- `main_artifact/fixtures/demo_programming_tech_library/README.md`
- `index.html`
- `sub_artifact/002_demo_screen_viewer/demo.html`
- `docs/index.html`
- `docs/main_artifact/web_app/index.html`
- `docs/sub_artifact/002_demo_screen_viewer/demo.html`
- `docs/main_artifact/web_app_directory_plan.md`
- `docs/main_artifact/web_app/README.md`
- `docs/main_artifact/private_data/programming_tech_library/README.md`
- `docs/main_artifact/fixtures/demo_programming_tech_library/README.md`

## デモ内容

- 左側にフォルダツリーを配置した。
- 左ペインの幅はデスクトップで約 1/4 を基準にした。
- フォルダツリー上部に検索、種別、タグ、状態、Markdown 限定のフィルターを配置した。
- 現在は `main_artifact/web_app_directory_plan.md`、`main_artifact/web_app/README.md`、`main_artifact/private_data/programming_tech_library/README.md`、`main_artifact/fixtures/demo_programming_tech_library/README.md` をツリーに出し、右側に表示する。
- デモ画面の正本は `main_artifact/web_app/index.html` に置いた。
- Markdown ファイルではプレビュー、編集、分割表示を切り替えられる。
- 編集内容はデモ内のメモリ上で保存できる。
- `main_artifact` の現在構想に沿って、Web app 本体、個別データ、fixture の README/plan をフォルダツリー内に表示し、右側 viewer で開ける。
- デモを HTTP 経由で開いた場合は、対応する `main_artifact/...` または `docs/main_artifact/...` の実ファイルを読み込む。直接ファイルとして開いた場合も同内容の fallback を表示する。
- GitHub Pages 用に `docs/` 配下へ公開コピーを置いた。
- Pages が有効になると `https://rh-rep.github.io/libraly_app/` から確認できる。
- repository top の `index.html` からも現在の demo viewer へ即時遷移できる。

## 参照した既存資料

- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/README.md`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/index.html`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/styles.css`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/app.js`

## 注意点

- この成果物は画面確認用の静的デモであり、実ファイルへの永続保存は行わない。
- 実装時は、既存 `.tools/knowledge_web/server.py` のようなローカルサーバ機能か、別の保存 API が必要になる。
- `docs/` 配下は GitHub Pages 公開用コピーなので、元の demo/readme を変更した場合は同期が必要。
- root の `index.html` は repository top 用の案内入口であり、現在は `main_artifact/web_app/index.html` へ遷移する。
- 旧 `main_artifact/lib/` は廃止し、viewer の参照先は現行の `web_app / private_data / fixtures` 構成へ移した。
- `sub_artifact/002_demo_screen_viewer/demo.html` は制作履歴として残し、実装の正本は `main_artifact/web_app/index.html` に置く。
