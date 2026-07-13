# Sub Goal: Issue #7 図書館データのフォルダ構成レビュー

## 目的

`main_artifact/web_app/index.html` の Explorer 型 UI を前提に、図書館アプリで扱う
実データ、原本、抽出 text、整理済みデータ、処理ログのフォルダ構成を実践的に
レビューする。

## 成果物

- `sub_artifact/006_library_folder_structure/artifact.md`
- `sub_artifact/006_library_folder_structure/plan.md`
- `sub_artifact/006_library_folder_structure/work_log.md`
- `issue_log/006_library_folder_structure/issue_7_library_folder_structure_review.md`

## 範囲

- `input/`、原本保存先、抽出 text、整理済みデータ、処理ログの役割を分ける。
- フォルダ名とファイル名の命名規則を提案する。
- `.library_skill` 案を Python program として実用化する場合の置き場所をレビューする。
- UI の Explorer、検索、filter に載せやすいデータ単位を整理する。

## 範囲外

- 実際の extractor 実装。
- 既存サンプルファイルの移動。
- 空ディレクトリや `.gitkeep` による本体構成の確定。
- DB schema、API、画面実装の変更。
