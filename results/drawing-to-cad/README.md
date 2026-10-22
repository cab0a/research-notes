# Drawing to parametric CAD — committed observations

2026-10-22、Windowsホスト上のUbuntu/WSL2、Python3.12.14、OCP7.9.3.1.1。
AI利用なし、API呼出しなし、外部データの再配布なし。

| 成果物 | 内容 |
|---|---|
| [results.json](results.json) / [summary.csv](summary.csv) | 固定13入力を各2回。候補6件は生成・再読込・寸法/形状・再投影・編集評価を通過。負例7件は理由付き保留 |
| 各ケースの`inference.json` | 可視注記/幾何からの値、根拠、人の事前指定、状態/保留理由 |
| 候補ケースの`candidate.py`、`model.json`、`candidate.step` | 実行したCADレシピ、既存FeatureModel、生成STEP。元のCAD履歴ではない |
| `edited.py`、`edited-parameters.json`、`edited.step` | 対象を明示して寸法を変更した候補 |
| `reprojection.json`、2件の`comparison.png` | 実際のB-RepのOCCT HLRと、SVGの比較。サンプル点による距離評価 |
| [initial-edit-order-failure.json](initial-edit-order-failure.json) | 初回、元形状一致でも「先頭の穴」の違いで編集比較に失敗した観測。初回コードのハッシュも保持 |
| [order-target-counterexample/results.json](order-target-counterexample/results.json) | 現在のコードでも配列順指定の失敗を再現。期待終了コード1、編集寸法差1 mm/体積差10π mm³ |
| [source-review.json](source-review.json) | 論文/公開コード/配布メタデータの確認。実行結果や重み本体の取得を意味しない |
| [verification.json](verification.json) | 実行コマンド、テスト、入力/実装ハッシュ、既存計画を変更していないことの確認 |

生成ワーカーはSVGとcontextだけを受け取り、評価側が別途正解を読む。
同一カーネルのIoU=1.0、開発用合成条件での6/6という結果は、
実務図面の精度、元設計履歴の復元、AIの優位性を示すものではない。
第一角法/第三角法と縮尺の派生は同一ファミリーとして扱う。

元図面の入力をそのまま描き直した絵ではなく、生成・再読込したSTEPを再投影している。
ただし再投影距離は可視/隠線を合わせたサンプル線集合の比較で、
厳密な連続曲線の一致証明や可視性分類の評価ではない。

外部ソースのクローン・HTMLキャッシュ・テストログは`output/`に置きGit追跡しない。
自作図面と成果物の由来は[fixtures README](../../fixtures/drawing-to-cad/README.md)、
解釈と限界は[研究ノート](../../notes/drawing-to-parametric-cad.md)、
コマンドは[再現ガイド](../../docs/drawing-to-cad-reproduction.md)を参照。
