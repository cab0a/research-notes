# CAD業務・評価定義の確認 — v1.15.0

## 今回使えるもの

「受領した単体部品の穴情報を既存帳票へ転記する」研究用の基準仕様と、その定義をチェックするPython API・CLIを追加しました。

**確認するのは業務・評価の定義です。CADの自動化可否や、顧客への導入採否を判定するコマンドではありません。** 実際のExcelへの転記、顧客の帳票列の設定、作業時間測定は後続工程です。既存の穴一覧機能は引き続き利用できます。

```bash
python -m pip install -e ".[geometry,test]"
research-workflow-contract fixtures/cad-workflow-contract/reference-contract.json \
  --output-dir output/workflow-definition
```

準備済みWSL環境では、次でも実行できます。

```bash
output/venv312/bin/python -m research_notes.workflow_contract \
  fixtures/cad-workflow-contract/reference-contract.json \
  --output-dir output/workflow-definition
```

標準出力と`output/workflow-definition/contract-review.json`に同じ結果を出力します。終了コード0は基準定義の確認成功、2は定義不足・不整合・読込失敗です。CADの認識成功率や業務完了を示す終了コードではありません。

## 結果の読み方

| 項目 | 基準定義の確認に成功した場合 |
| --- | --- |
| definition_valid | true：この版の基準定義に整合 |
| definition_state | research_definition_fixed |
| customer_approved | false：顧客が合意したとは判断しない |
| performance_measured | false：性能・作業時間は測っていない |
| adoption_decision | not_evaluated：採否は未評価 |
| issues | 定義不整合の場所・コード・日本語の説明 |
| contract_sha256 | 順序・整形に依存しない正規化JSONのSHA-256 |

```python
from pathlib import Path
from research_notes.workflow_contract import read_contract, review_contract

definition = read_contract(Path("fixtures/cad-workflow-contract/reference-contract.json"))
report = review_contract(definition)
print(report["definition_valid"], report["adoption_decision"])
# True not_evaluated
```

この版は任意の顧客仕様を承認する汎用契約システムではありません。対象業務と座標・完全性・正解の定義を基準仕様として固定します。顧客側の条件が異なる場合は、それを記録して適用範囲を再設計する必要があります。

## 固定した基準

| 内容 | 定義 |
| --- | --- |
| 入力単位 | 一つのソリッドからなる部品。複数部品の混同を避ける |
| 認識の対象 | 円形貫通穴・円形平底止まり穴・両端半円の直線貫通長孔 |
| 座標 | 入力モデルの原点・座標を維持し、長さはmm。自動位置合わせはしない |
| 位置 | 選択した開口中心XYZ。板厚中央や両端中点とは区別 |
| 方向 | 開口から内部への単位方向。実際の工具方向の認定ではない |
| 長孔 | 幅・半円端を含む全長・長手方向。丸穴径とは別欄 |
| 深さ | 確認した穴壁の軸方向深さ/貫通長。公称加工深さ・ドリル先端ではない |
| 全体数 | 全体確認が成立した場合だけ数値。確認済み行数とは分ける |
| 非該当と不明 | 長孔に丸穴径を要求しない。一方、必要な値が未取得なら人の確認が必要 |
| 外部情報 | 品番・材質・公差・ねじ指示等を形から推測しない。利用者等の出所を記録 |
| 正解 | 独立した設計レシピまたは独立した人の確認。認識器の自己出力・相互一致だけでは正解にしない |

17項目の定義は[基準JSON](../fixtures/cad-workflow-contract/reference-contract.json)に記載しています。「必須」は業務が完成したと言うための条件であり、v1.15で全列の転記を実装したという意味ではありません。

## 研究用の採否基準

固定した正解付き評価セットで、自動確定値の誤り0、誤った業務完了判定0、必要な特徴の見逃し0を研究用の基準値とします。寸法照合は1e-6 mm以内です。これは既知レシピとの数値比較条件で、製造公差・測定精度・未知部品の無誤り保証ではありません。

工数は同じ品質条件で比較し、総時間の差が0分より大きいことを要求する基準です。20回という値は繰り返し利用の**試算条件**で、測定件数・導入効果ではありません。

比較する各方法について、初期準備・設定・説明、実行、確認、訂正、再実行、更新を記録します。例えば、手作業の総時間は「手作業側の準備＋回数×一件の手作業＋更新」、自動化側は「自動化側の準備＋回数×実行/確認/訂正/再実行＋更新」です。初期準備を片方だけに計上しません。

実際の帳票・列対応・座標基準・品質/時間目標・データ利用条件は、すべて顧客との合意待ちとして保持します。研究用基準に整合していても、顧客案件の採用や性能達成を表示しません。

## 再現する

```bash
output/venv312/bin/python experiments/run_workflow_contract_study.py \
  --output-dir output/workflow-definition-study --repeats 2
```

11種類の不適切な定義と、7入力の既存穴一覧を確認します。STEPの認識条件を変更した研究ではありません。結果の解釈は[研究ノート](../notes/cad-workflow-definition.md)と[検証記録](../results/cad-workflow-contract/verification.json)を参照してください。

入力JSONはUTF-8、128000バイト以下。重複キー・NaN/Infinity・型の違い・未定義項目・必要な定義の欠落を拒否します。定義チェックは、任意のプログラムや外部参照を実行しません。
