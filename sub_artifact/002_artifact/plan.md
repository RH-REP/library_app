# Plan

1. `main_artifact/goal.md` と `main_artifact/development_process.md` を読み、今回の位置づけを確認する。
2. `.tools/knowledge_web` の既存画面構成を確認する。
3. `sub_artifact/002_artifact/` を初期化する。
4. 静的 HTML のデモ画面を作成する。
5. 作業内容と確認事項を `artifact.md` と `issue_log/` に記録する。
6. HTML と git 差分を確認し、変更を commit/push して issue にコメントする。

## 実装方針

- 既存 `knowledge_web` の VS Code 風 2 ペイン構成を参照する。
- デモは単体 HTML とし、ブラウザで直接開けるようにする。
- 左ペイン幅はデスクトップで約 1/4 を基準にする。
- 検索、種別、タグ、状態のフィルターを用意する。
- Markdown はプレビュー、編集、分割表示を切り替えられるようにする。
