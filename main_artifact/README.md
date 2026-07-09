# main_artifact

`main_artifact/` は、このプロジェクトの制作目標と工程を置く場所です。

ユーザーは、まず GitHub issue に「何を作りたいか」を書きます。
その issue を読んだ AI agent が、次の2つを整理・更新します。

1. `goal.md`
2. `development_process.md`

通常、ユーザーが最初からこの2ファイルを直接埋める必要はありません。
迷っている内容も issue に書いてください。

`.core_program/` の queue、pending、router 診断、session 割り当て状態は
内部エンジン用です。制作目標や人間向けの判断記録はここか `issue_log/` に
残します。
