# Issue #7 Static Viewer Demo

## 依頼

既存の viewer demo と、Issue #7 で整理してきた folder structure / metadata header contract を
組み合わせ、完成品をイメージできる静的HTMLを作るよう依頼された。

動的アプリではなく、静的HTMLでよいという指定だった。

## 実施内容

- `sub_artifact/006_library_folder_structure/viewer_demo.html` を作成した。
- GitHub Pages 確認用に `docs/sub_artifact/006_library_folder_structure/viewer_demo.html` を追加した。
- 既存 viewer demo の Explorer、filter、preview、raw text 表示の構成を踏襲した。
- `raw_sources`、`extracted_text`、`organized_data`、`library_records`、`process_log` の例を同一画面に載せた。
- `organized_data/{item_id}/index.md` の metadata block を panel 表示し、raw Markdown も同時に見られるようにした。

## 判断

- backend や保存処理は入れない。
- HTML 内に demo data を埋め込み、単体で開ける prototype にする。
- 完成品イメージでは、整理済み item を主表示にし、raw source と extracted text は source pipeline と tree で辿れる形にする。
