# CAD確認・転記の基準作業を記録する — v1.16.0

記録機能・形式はv1.16.0を維持します。パッケージv1.17.0の[抽出接続](cad-workflow-extraction.md)では、同じ部品・定義であることを照合し、計測記録は変更しません。

## 何を記録できるか

CADで形状を確認し、帳票へ転記し、チェックする現在の作業を工程別に記録します。入力整備・正解付け・設定・説明・更新も記録し、時間と誤りの確認状況をJSONとMarkdownへまとめます。

**タイマーはCAD操作やExcel転記を実行する機能ではありません。** 作業者が実際の作業を行い、その時間と独立した確認結果を記録します。所要時間を推定で埋めたり、帳票の内容を自動採点したりする機能でもありません。

1記録につき、1人・1方法・固定した部品順を使います。別の作業者・繰返し・比較方法は別ファイルにします。同じ部品の繰返しを未見部品として数えません。実データ・実帳票の測定がない現状では、現場基準の測定は完了していません。

## 準備と記録の作成

リポジトリのルートで実行します。基準記録だけなら追加のCADライブラリーは不要です。既存STEP抽出を実行する研究スクリプトにはgeometry環境が必要です。

```bash
python -m pip install -e ".[geometry,test]"
research-workflow-baseline init output/manual-baseline.json \
  --contract fixtures/cad-workflow-contract/reference-contract.json \
  --cases fixtures/cad-workflow-contract/reference-cases.json \
  --operator observer-a \
  --tool "実際に使用するCADと版" \
  --workbook "実際の帳票名と版"
```

これは既知7入力を使う操作例です。顧客業務の実測には、対象部品・入力SHA-256・系列ID・独立した正解の出所を記録した別manifestを用意してください。全体数が不明なら`whole_count_truth: null`を保持します。CADのネイティブ形式等を手動で調べる場合も、この時間記録にSTEP変換は必要ありません。

`--tool`・`--workbook`を省いた記録は作成できますが、記録完了とはしません。`--operator`には匿名の作業者参照を使えます。業務定義と部品manifestの内容・ハッシュを記録へ保存し、後から別条件と混同することを防ぎます。CAD/帳票本体は読み込みません。

準備済みWSLでは`output/venv312/bin/research-workflow-baseline`、または`output/venv312/bin/python -m research_notes.workflow_baseline`を使えます。

## 工程をタイマーで測る

入力整備などの共通作業は部品IDなしで記録します。

```bash
research-workflow-baseline time output/manual-baseline.json \
  --phase input_preparation --evidence "入力ファイルと必要情報を整理した作業"
```

部品ごとの作業には`--case`でmanifest内のIDを指定します。

```bash
research-workflow-baseline time output/manual-baseline.json \
  --case single --phase cad_check --evidence "CADで径・位置・深さを確認した作業"
```

コマンドの開始後に実際の作業を行います。ターミナルへ戻り、Enterで工程を完了します。`p`で中断、`r`で再開、`q`またはCtrl+C/入力終了で未完了の時間を保存します。未完了保存は終了コード130です。同じ工程の続きは再度計測し、時間を合算します。中断中の時間だけを除外します。通常の確認・読み込み待ち等を、時間短縮のために中断扱いにしないでください。

| 区分 | 工程名 | 記録する作業 |
| --- | --- | --- |
| 共通 | input_preparation | 入力整備・必要情報の確認 |
| 共通 | truth_labeling | 独立した正解作成・確認 |
| 共通 | setup | 設定・準備 |
| 共通 | training | 説明・習熟 |
| 共通 | update | 更新・変更対応 |
| 部品 | input_check | 入力・部品・単位等の確認 |
| 手作業 | cad_open / cad_check | CAD/ファイルを開く、形状・寸法確認 |
| 抽出＋全件確認 | extract / review | 抽出処理、抽出結果を全件確認 |
| 部品 | transfer / final_check | 帳票へ転記、最終チェック |
| 部品 | correction / rerun | 訂正、再実行 |

比較用の抽出＋全件確認は、初期化時に`--method existing_extraction_with_full_review`を指定します。現在の手作業とは別ファイルにし、それぞれの準備も記録します。並行作業の時間の扱い、共通作業の配賦、測定順・習熟の影響は測定前に決めてください。今回のツールは能動計測時間の工程別合計を出し、人件費・設備稼働・ROIへ自動換算しません。

## ストップウォッチ値、対象なし、未測定

外部のストップウォッチで測った値も記録できます。

```text
research-workflow-baseline record output/manual-baseline.json --case single --phase cad_check --seconds <実測秒数> --evidence <測定記録の参照>
```

`--seconds`は秒単位で、有限の0〜604800秒です。`--unfinished`を付けると続きが必要な記録になります。完了済みの工程に同じ時間を再登録すると拒否します。訂正・再実行は該当工程へ記録します。

訂正などが発生しなかった場合も、理由付きで明示します。

```bash
research-workflow-baseline record output/manual-baseline.json \
  --case single --phase correction --not-needed --evidence "独立チェックで訂正なしと確認"
```

未記録は`null`、実測した0秒は数値0、対象なしは理由付きの`not_needed`として区別します。中断済みの時間を「対象なし」で消すことはできません。

## 誤りと正解の範囲を記録する

以下は独立した正解付き合成部品`single`を確認した後の記録形式です。**確認していない値を例のまま0にしないでください。** 項目数は実際に独立照合した帳票項目の数です。

```text
research-workflow-baseline quality output/manual-baseline.json --case single --truth-scope whole_part --truth-origin independent_recipe --truth-reference fixtures/hole-inventory/manifest.json#single --truth-hole-count 1 --checked-fields <確認項目数> --incorrect-fields <誤り項目数> --missed-features <見逃した特徴数> --false-complete <yesまたはno>
```

品質は独立レシピ、または独立した人の確認から記録します。認識器の自己出力を正解にしません。

- `whole_part`：必要な全体確認を行った記録。全体数の独立した正解が必要です。
- `selected_fields`：一部項目だけの確認。全体の見逃し数・誤った完了判定は未確認のままです。
- `unknown`：正解不明。誤り・見逃し・誤った完了判定を0件にしません。

フラグを省いた未確認値は`null`です。公開ブラケットの全体数は基準manifestで不明です。丸穴5・長孔6を、そのまま全体の正解として登録できません。新たに独立した人の全体確認を行った場合は、別の出所として記録します。本版は品質値の独立監査やCAD/帳票との自動照合を行いません。

## 集計と結果の読み方

```bash
research-workflow-baseline report output/manual-baseline.json \
  --output-dir output/manual-baseline-report
```

標準出力と`baseline-report.json`に同じ結果を出し、`baseline-report.md`へ工程別の表を保存します。全計画部品を分母に保持し、未知・未記録の部品を除外しません。

| 項目 | 意味 |
| --- | --- |
| known_active_seconds | 記録された時間の小計。未記録がある間は全体時間ではない |
| total_active_seconds | 共通作業と全部品の全工程が記録済みの場合だけ数値。未完了ならnull |
| error_counts.*.known_total | 独立確認として記録された値の小計。全体の誤り数とは限らない |
| error_counts.*.unknown_cases / total | 未確認部品数と、全件の件数。未確認が残る全件数はnull |
| baseline_record_complete | 時間・品質・利用ツール/帳票の記録が揃ったか。業務成功の判定ではない |
| record_kind | operator_observation：利用者の観測記録 / synthetic_control：ソフトウェア検証用の合成記録 |
| adoption_decision / time_saving_seconds | 常にnot_evaluated / null。採否・省力化は後続の同品質比較で評価 |

時間と誤りは利用者の入力に基づく観測です。記録完了でも誤りが存在し得ます。顧客合意済みとは表示しません。終了コード0は記録・集計処理の成功で、現場測定の完了を意味しません。入力・整合性・保存の失敗は2です。`time`には操作案内が出るため、機械連携には`report`のJSONを使ってください。

入力JSONはUTF-8、128000バイト以下、部品は1〜100件です。重複キーやNaN/Infinityを拒否します。既存の初期記録を上書きせず、更新時はロックと変更検知を使って保存します。外部通信は行いません。顧客データの共有や公開はこの記録機能に含めません。

## 研究用の再現

```bash
output/venv312/bin/python experiments/run_workflow_baseline_study.py \
  --output-dir output/workflow-baseline-study --repeats 2
```

合成した時間・誤りで集計を検証し、既存7入力の機械処理を別に測定します。合成値は現場実測として扱いません。[研究ノート](../notes/cad-workflow-baseline.md)と[検証記録](../results/cad-workflow-baseline/verification.json)を参照してください。
