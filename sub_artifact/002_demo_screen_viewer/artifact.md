# Artifact

Issue #2 の依頼に対して、HTML のデモ画面を作成した。

## 作成ファイル

- `main_artifact/lib/readme.md`
- `sub_artifact/002_demo_screen_viewer/demo.html`

## デモ内容

- 左側にフォルダツリーを配置した。
- 左ペインの幅はデスクトップで約 1/4 を基準にした。
- フォルダツリー上部に検索、種別、タグ、状態、Markdown 限定のフィルターを配置した。
- 選択したファイルを右側に表示する。
- Markdown ファイルではプレビュー、編集、分割表示を切り替えられる。
- 編集内容はデモ内のメモリ上で保存できる。
- `main_artifact/lib/readme.md` をフォルダツリー内に表示し、右側 viewer で開ける。
- デモを HTTP 経由で開いた場合は `../../main_artifact/lib/readme.md` から実ファイルを読み込む。直接ファイルとして開いた場合も同内容の fallback を表示する。

## 参照した既存資料

- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/README.md`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/index.html`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/styles.css`
- `~/Desktop/programing/ai_base/my_knowledge/.tools/knowledge_web/app.js`

## 注意点

- この成果物は画面確認用の静的デモであり、実ファイルへの永続保存は行わない。
- 実装時は、既存 `.tools/knowledge_web/server.py` のようなローカルサーバ機能か、別の保存 API が必要になる。
