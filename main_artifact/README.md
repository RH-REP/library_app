# main_artifact

`main_artifact/` は、完成品または統合された主成果物と、その目標・工程の正本を置く場所です。
この README は、このフォルダを開いた人・AI agent 向けの短い入口説明です。
通常ユーザーの必読文書は root の `README.md` と `USER_MANUAL.md` です。

ユーザーは、まず GitHub issue に「何を作りたいか」を書きます。
その issue を読んだ AI agent が、次の2つを作成・更新します。

1. `goal.md`
2. `development_process.md`

通常、ユーザーが最初からこの2ファイルを直接埋める必要はありません。
迷っている内容も issue に書いてください。

AI agent は、必要に応じて次のテンプレートを参照します。

1. `.goal_template.md`
2. `.development_process_template.md`

`goal.md` と `development_process.md` は個別 project のデータです。
ArtifactForge 本体の upstream に混ぜないでください。

現在の main_artifact 内の初期構成は次を想定します。

1. `web_app/`
2. `library_skill/`
3. `private_data/programming_tech_library/`
4. `fixtures/demo_programming_tech_library/`
5. `web_app_directory_plan.md`

`web_app/` は Web app 本体、`library_skill/` は HTML / PDF / image などを
plain text 化する補助 program と schema、`private_data/` は開発中の個別データ、
`fixtures/` は共有可能な demo データの置き場です。

`.core_program/` の queue、pending、router 診断、session 割り当て状態は
内部エンジン用です。制作目標や人間向けの判断記録はここか `issue_log/` に
残します。
