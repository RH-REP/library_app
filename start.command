#!/bin/zsh -f
# libraly_app（ArtifactForge の library_app プロジェクト）のデモビューアを開く。
# コードはこのフォルダ（開発側 repo の clone。直すのは開発側で、update.command で pull して取り込む）。
# エンジンの実行記録はこのフォルダの .core_program/app/*/data/。
# GitHub issue 駆動のエンジン本体（.core_program/app/*/*.py）はここからは起動しない（README 参照）。
set -u
USE_DIR="${0:A:h}"                                   # 利用側の clone
if [[ ! -f "$USE_DIR/index.html" ]]; then echo "見つかりません: $USE_DIR/index.html（update.command で取り込んでください）"; read; exit 1; fi
open "$USE_DIR/index.html"
