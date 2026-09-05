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

## Follow-up: raw_text pipeline sample 統合版

追加依頼により、Issue #6 の Phase 0 sample と static viewer を統合した。

更新したファイル:

- `main_artifact/web_app/index.html`
- `docs/main_artifact/web_app/index.html`
- `sub_artifact/006_library_folder_structure/viewer_demo.html`
- `docs/sub_artifact/006_library_folder_structure/viewer_demo.html`

統合後の viewer では、次を同じ画面で辿れる。

- `raw_text`: source text から作る検索・確認用の一次 text
- `extracted_text`: `raw_text` から作る処理 metadata と structured text
- `organized item`: metadata header 付きの整理済み item

PDF と JPG は HTML 内に preview 用 data URI として埋め込み、GitHub Pages 用 mirror でも
単体で確認できるようにした。

追加フィードバックを受け、`source_texts/` の段階を viewer から外し、
pipeline を `raw_text -> extracted_text -> organized item` に変更した。
右側の raw pane には `Save edit` と `Reset` を追加し、HTML 内メモリ上で編集を
preview に反映できるようにした。

さらに追加フィードバックを受け、organized item へ整理済みメモを追記する `Add memo` と、
tag を追加・編集する tag editor / `Apply tags` を追加した。

## Follow-up: source_data / extracted_data / organized_data への整理

追加フィードバックを受け、逆変換 sample 由来の見せ方を主軸から外し、
現在の正規用語を次の 3 層に整理した。

- `source_data`: PDF、JPG、HTML などの原本。
- `extracted_data`: OCR や parser で text 化した状態。`raw_text` と `extracted_text` はこの中の編集段階。
- `organized_data`: 意味単位に分割し、metadata、tag、整理済みメモを持つ状態。

あわせて、static viewer の仮想 path、private data の実フォルダ、template、README を
`source_data -> extracted_data -> organized_data` に更新した。
