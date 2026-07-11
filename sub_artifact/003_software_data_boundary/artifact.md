# Software/Data Boundary Development Policy

## 結論

この図書館システムは、実運用をしながら開発してよい。ただし、ソフトウェア本体と個別データを同じものとして扱わない。

推奨する境界は次の 3 層である。

| 層 | 役割 | Git に入れるか |
| --- | --- | --- |
| software/upstream | アプリ本体、スキーマ、import/export 契約、検索 UI、汎用ロジック | 入れる |
| private project repo | 個人利用の設定例、運用判断、ArtifactForge の作業記録 | 必要最小限だけ入れる |
| private runtime data | 実際の蔵書、PDF、OCR 結果、個人メモ、収集依頼、バックアップ | 原則入れない。private 開発中だけ例外可 |

実運用でしか分からないことは多いので、実データを使った観察は必要である。ただし、実データから見つかった課題は、そのままソフトウェアに貼り付けるのではなく、個別情報を除いた fixture、仕様、テスト、画面要件へ変換してから software 側に戻す。

## Follow-up: プログラミング技術図書館と private data commit

「プログラミングの技術」に関する図書館をテーマにし、現時点では個別データも commit して保存し、配布時には抜く、という進め方は可能である。

ただし重要な制約がある。Git では、ファイルを後から削除しても過去の commit history には残る。そのため、個別データを含む private repository の履歴をそのまま公開してはいけない。

配布方法は次のどちらかに分ける。

| 配布方法 | 可能か | 注意点 |
| --- | --- | --- |
| clean release archive | 可能 | `.gitattributes` の `export-ignore` で private path を除外して archive を作る |
| public Git repository | 可能 | 個別データを一度も含まない clean branch / clean repo から作る |
| private repo を途中で public 化 | 不可 | 削除済みファイルでも history から復元できる |

この repository では、private data を commit する場合の候補 path を次にする。

```text
private_data/programming_tech_library/
```

配布用の小さなサンプルは、別 path に分ける。

```text
fixtures/demo_programming_tech_library/
```

`private_data/**` は `.gitattributes` で `export-ignore` にした。これにより、`git archive` で release archive を作る場合は private data を除外できる。ただし、これは archive への除外であり、GitHub に公開された Git history から消す仕組みではない。

## Follow-up: 開発段階では main_artifact で先に切り分ける

追加コメントで、現段階では配布データへのコンタミは重大問題とせず、まず `main_artifact` の中で software 部分と個別データ部分を切り分けたい、ソフトウェアは Web app を想定する、という方針が示された。

この方針に合わせ、今の first cut は次にする。

```text
main_artifact/
├── web_app/
├── private_data/programming_tech_library/
└── fixtures/demo_programming_tech_library/
```

この段階では、release の完全自動化よりも「どこに何を置くか」を固定することを優先する。`web_app/` に UI と API を寄せ、`private_data/` に実データを寄せ、`fixtures/` に再現用の共有データを寄せる。

## リポジトリの考え方

現在の ArtifactForge プロジェクトでは、remote の意図は次の形でよい。

```text
origin    = ユーザー個人の project repo。作業成果を push する先。
upstream  = ArtifactForge または software template。fetch 専用。
```

将来、図書館アプリそのものが独立して大きくなる場合は、さらに次のように分けるとよい。

```text
libraly_software      = 汎用ソフトウェア本体
libraly_private_ops   = 個人利用の運用メモ、設定、デプロイ手順
libraly_data_private  = 実データを置く場合の完全 private な別領域
```

ただし、PDF、スキャン画像、大量 OCR テキスト、バックアップは Git に向かない。Git 管理するなら小さな設定や manifest までにし、実体はローカルディレクトリ、NAS、クラウドストレージ、DB などへ分ける。

## 配布用 software にコミットしてよいもの

- アプリケーションコード。
- DB schema、migration、validation rule。
- import/export の契約文書。
- UI の画面案、検索仕様、操作フロー。
- `config.example.yml` や `.env.example` のような設定テンプレート。
- 架空データまたは十分に匿名化した小さな demo fixture。
- 実運用から抽象化した issue、テストケース、再現手順。

## 配布用 software に入れないもの

- 実際の蔵書台帳、個人メモ、収集依頼、問い合わせ履歴。
- PDF、スキャン画像、OCR 生テキスト、購入履歴、貸借履歴。
- API key、cookie、token、ローカルパス、個人設定。
- 実データから自動生成された検索 index や cache。
- 復元可能なバックアップ一式。

書誌情報は境界が曖昧になりやすい。ISBN や公開書誌のように一般情報へ近いものでも、個人の蔵書リスト、分類、メモ、優先度、収集意図が混ざると private runtime data として扱う。

private 開発中にこれらを commit する場合は、repository 自体を private のまま保ち、配布時には clean release archive または clean repository を作る。

## 実運用から開発へ戻すループ

1. 実データは private runtime data に置いて運用する。
2. 使いながら、検索しづらい、分類しづらい、追加調査が詰まる、PDF が読みにくいなどの問題を観察する。
3. 問題を issue にするときは、個別の本名、PDF 内容、個人メモを削り、構造だけを書く。
4. 必要なら架空データで再現 fixture を作る。
5. software/upstream 側では、fixture、schema、UI、importer、検索ロジックを改善する。
6. private project repo で software 更新を取り込み、実データに対して再確認する。

このループなら、運用から学びながら、ソフトウェアには汎用化された知識だけを戻せる。

## 実装時の境界案

最初の実装では、次のような環境変数または設定を置くとよい。

```text
LIBRALY_DATA_ROOT=/absolute/path/to/private/library_data
```

software 側は `LIBRALY_DATA_ROOT` の下を読み書きするが、その中身は repository に入れない。repository には代わりに次を入れる。

```text
fixtures/demo_programming_tech_library/
config.example.yml
docs/data_contract.md
```

`fixtures/demo_programming_tech_library/` は架空の小さなデータだけにする。実データで起きた問題をテストしたい場合も、実名や本文を使わず、同じ構造を持つ架空データへ変換する。

## データ層の分け方

運用データは少なくとも次に分けると扱いやすい。

| データ層 | 内容 | software 側に置くもの |
| --- | --- | --- |
| raw_sources | PDF、画像、元 CSV、手入力前の資料 | 形式説明だけ |
| staging | 取り込み途中、OCR 結果、修正待ち | schema と validation |
| library_records | 正規化した蔵書・資料レコード | schema、sample fixture |
| search_index | 検索用 index、cache | 生成コードだけ |
| research_requests | 追加収集依頼、調査メモ | workflow 定義だけ |

実データ本体を入れず、形式・制約・生成手順だけを software 側に入れるのが基本である。

## この issue での決定

- 実運用しながら開発する方針で進めてよい。
- 当面のテーマは「プログラミングの技術」に関する図書館にする。
- private な開発段階では、個別データを commit して保存してよい。
- 現段階では、配布データへのコンタミよりも `main_artifact` 内の物理分離を優先する。
- ただし、個別データを含む Git history をそのまま公開・配布しない。
- 実データは配布用ソフトウェア本体の一部にしない。
- ソフトウェアには、コード、契約、schema、fixture、汎用化した要件だけを入れる。
- Web app 本体は `main_artifact/web_app/` に寄せる。
- 個別データは private runtime data として扱い、当面は `main_artifact/private_data/programming_tech_library/` に寄せる。
- 共有可能な最小データは `main_artifact/fixtures/demo_programming_tech_library/` に寄せる。
- 実運用で見つけた課題は、匿名化・抽象化して issue と fixture に変換してから実装する。
- 配布時は `.gitattributes` の `export-ignore` を使った archive、または個別データ履歴を含まない clean repository を作る。

## 次の推奨 issue

- `main_artifact/web_app/` の frontend/backend/shared の責務設計。
- `main_artifact/private_data/programming_tech_library/` の最小ディレクトリ作成。
- `main_artifact/fixtures/demo_programming_tech_library/` の最小サンプル作成。
- `docs/data_contract.md` の作成。
- 実データ取り込み前の `raw_sources -> staging -> library_records` の流れの設計。
