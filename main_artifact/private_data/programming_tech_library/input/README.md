# Input

未処理ファイルの投入場所である。

ユーザーや調査Agentは `inbox/` に PDF、画像、HTML、CSV などを置く。
整理AIまたは intake program が処理を開始したら、原本は `raw_sources/` へ移す。

`input/` は一時置き場であり、処理済みファイルを長期保存しない。
