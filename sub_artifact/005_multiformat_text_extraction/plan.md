# Plan

## 方針

Issue #6 は実装 request だが、本文が求めているのは「3 段階レビューで工程を示す」
ことである。したがって、この sub-artifact の first cut では、3 形式の text
extraction 機能を同一 pipeline として整理し、実装前に確認すべき contract を
決める。

## 作業項目

- [x] `main_artifact/goal.md` と `main_artifact/development_process.md` を読む。
- [x] issue #5 で集めた synthetic / actual source sample を確認する。
- [x] issue #6 を新規 sub-artifact として `005_multiformat_text_extraction` に切る。
- [x] HTML / PDF / image の各機能について、3 段階レビュー工程を定義する。
- [x] 共通出力 contract、入力 fixture、後回し範囲を定義する。
- [x] ユーザー向け issue log を残す。

## 実装前提

- HTML と PDF はまず text 抽出可能な入力を対象にする。
- image は OCR 前提であり、alpha では最も不確実性が高い。
- `sub_artifact/004_library_feature_brainstorm` で集めた sample は、ここでは入力 fixture
  として扱い、brainstorm artifact からは分離する。

## この時点での判断

- 実装順は HTML -> PDF -> image が妥当。
- HTML では tag 除去だけでなく、link text や heading の残し方を決める必要がある。
- PDF は text PDF と scanned PDF を同列に扱わず、first cut は text PDF を優先する。
- image は OCR 品質が支配的なため、review 1 で quality gate を先に決める必要がある。
