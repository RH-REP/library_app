# Issue #2 Demo Screen

## 依頼

ユーザーは HTML のデモ画面作成を依頼した。参照先として `~/Desktop/programing/ai_base/my_knowledge/.tools` が指定された。

必要な画面要素:

- 左側にデフォルト 1/4 幅程度のフォルダツリー。
- フォルダツリー上部に検索とフィルター機能。
- 選択した項目を右側にビュー表示。
- Markdown の場合は表示と編集。

## 判断

- 既存 `.tools/knowledge_web` は VS Code 風の 2 ペイン構成で、今回の依頼に近い。
- 今回は ArtifactForge の成果物として確認しやすいように、外部サーバに依存しない静的 HTML にした。
- 実ファイル保存は要件に含まれていないため、編集保存はデモ内メモリに限定した。

## 成果

- `sub_artifact/002_demo_screen_viewer/demo.html` を作成した。
- 検索、フィルター、フォルダ開閉、ファイル選択、Markdown プレビュー、Markdown 編集、保存、キャンセルを実装した。

## Follow-up

追加コメントで、`main_artifact/lib/readme.md` を作り、viewer で実際に見られるようにしたいという依頼があった。

対応:

- `main_artifact/lib/readme.md` を追加した。
- demo viewer のツリーに `main_artifact/lib/readme.md` を追加した。
- 初期選択ファイルを `main_artifact/lib/readme.md` にした。
- HTTP 経由で開いた場合は実ファイルを fetch し、直接ファイルとして開いた場合は同じ内容の fallback を表示するようにした。
- generic path `sub_artifact/002_artifact` を `sub_artifact/002_demo_screen_viewer` に改名した。

## 残課題

- 実ファイルの読み込みと保存を行う場合はバックエンド API が必要。
- PDF や画像の実プレビューは、対象ファイルの配置場所と配信方法を決めてから実装する。
- 本格実装では、既存 `.tools/knowledge_web` の file index 生成とサーバ機能を流用するか判断する。
