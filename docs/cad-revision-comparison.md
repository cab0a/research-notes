# STEP Revision Comparison — v1.5.0

## 日本語概要

新旧2つのSTEPを並べ、穴付き板の変更候補・追加・削除・判定保留を色分けできます。対応する穴径・穴中心X/Y・板厚の旧値・新値・差を表示し、比較図・寸法差・比較条件・保留理由を1つのHTMLへ保存します。対象は同じ座標系の長方形の板とZ方向の貫通穴です。曖昧な穴の対応を確定したことにはせず、元CADの設計寸法や履歴も推定しません。操作方法と制限を、英語本文の要約に続いて説明します。

---

## English Summary

Version 1.5 completes the bounded revision workflow: independently import two
STEP files, classify corresponding plate and hole faces, measure diameter,
position and thickness changes, and download a self-contained HTML report.
The engine qualifies rectangular plates with separated Z-axis through holes
using measured surfaces and reconstructed material. Shared-position anchors
precede conservative mutual-singleton matching; ambiguity remains unresolved.
Both views share their camera and scale. Reports preserve comparison diagrams,
all matched dimensions, source hashes, conditions and abstention reasons.
This is geometric evidence within a restricted grammar, not recovered design
history, arbitrary STEP correspondence or automatic alignment.

## 起動と操作

Python 3.12とgeometry依存を用意したリポジトリで起動します。

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.cad_web
```

`http://127.0.0.1:8767/revisions` を開くか、寸法編集画面の**新旧STEP比較**を押します。
準備済みのWSL環境では `output/venv312/bin/python -m research_notes.cad_web` で起動できます。
別のサーバーが起動中なら `--port 8768` など、空いているポートを指定してください。

1. **旧版ファイル**を選択し、**旧版を開く**を押します。
2. **新版ファイル**を選択し、**新版を開く**を押します。新版を先に開くこともできます。
3. 左右どちらかをドラッグすると両方が回転します。**表示**で面と辺、**拡大率**で共通倍率を選び、**視点を戻す**で初期状態へ戻します。
4. 色と穴ラベルを確認します。**確認箇所**または結果表の箇所名を選ぶと、その対応面を強調し、寸法表を絞り込みます。
5. **変更箇所と寸法差**で、旧値・新値・差（新版 − 旧版）と根拠を読みます。**許容差内の寸法も表示**で変更されていない対応寸法も確認できます。
6. **確認レポートを保存**で `step-comparison.html` をダウンロードします。現在の視点の比較図と、全ての対応寸法・保留箇所・比較条件が入ります。画面上で絞り込んだ箇所や変更寸法だけに限定しません。
7. **旧版と新版を入れ替え**で差の符号と追加・削除を反転できます。ファイルの再選択で片側だけを置換し、**旧版を閉じる**・**新版を閉じる**で指定側を解除できます。

### ファイルを用意せず試す

**サンプル**を選び、**サンプル2件を開く**を押します。旧版は12 × 10 × 4 mmの板です。新旧それぞれを別のSTEPへ出力し、読込後の形状だけを判定します。サンプルの作成パラメーターや正解ラベルを判定処理へ渡しません。

| サンプル | 測定・判定される内容 |
| --- | --- |
| 穴径の変更 | 穴径2.0 → 2.6 mm、差 +0.6 mm |
| 穴位置の変更 | 中心X 6.0 → 7.5 mm、Y 5.0 → 5.5 mm。体積は同じでも移動を検出 |
| 板厚の変更 | 板厚4.0 → 5.0 mm、差 +1.0 mm。側面と穴の貫通長さも変更候補 |
| 穴の追加 | 既存穴を対応付け、残った新版の穴を追加候補として緑で表示 |
| 穴の削除 | 既存穴を対応付け、残った旧版の穴を削除候補として赤で表示 |
| 対応が曖昧な穴 | 新旧各2穴の候補が競合。紫で保留し、穴の寸法差を生成しない |

## 対応範囲と表示の意味

| 項目 | v1.5.0の動作 |
| --- | --- |
| 入力 | 各2 MB以下。単一ルート・正常な単体ソリッド・シェル1つ・1〜24面 |
| 単位 | 単一の明示的なSIミリメートル宣言・単位コンテキストを要求。他単位は拒否 |
| 表示可能な形状 | 編集候補の採用は不要。読込条件を満たす球なども表示可能。局所比較は保留 |
| 局所比較の形状 | 軸に平行な6平面の長方形の板。穴なし、または互いに離れたZ方向の円筒貫通穴 |
| 座標の比較条件 | 新旧のXY外周とZ下端が許容差内で一致。異なる場合は全体を保留 |
| 座標 | 元データの位置・向きを維持。2形状全体の境界を使い、同じ中心と縮尺で投影 |
| 描画 | 面全体を分類して色分け。黄は変更候補、緑は追加候補、赤は削除候補、紫は保留、灰青は許容差内。変更した材料領域の厳密な境界ではない |
| 測定寸法 | 対応する穴径・共通座標系の穴中心X/Y・上下平面間の板厚。元CADの公称寸法・公差ではない |
| 全体の測定 | 体積・面積・面数・辺数・頂点数。差が0でも形状一致と判定しない |
| 未読込の片側 | 空欄として表示し、差を計算しない |
| 読込失敗 | 正常に読み込めていた両側のデータを保持 |
| 状態の競合 | 古い比較状態からの読込・入替・解除・レポート保存を拒否し、最新状態を表示 |
| 寸法編集との関係 | 比較用データは独立。寸法編集の候補・確定形状・未確定変更に影響しない |
| ローカル処理 | 外部への送信・外部参照の取得なし。サーバー終了時に比較状態を破棄 |

同じサーバーを開いたタブ同士は比較データを共有します。自動位置合わせはないため、元データの座標が大きく離れている場合は形状が小さく見えます。

### 対応付けと保留

平面・円筒面から測った寸法で板と穴を再構成し、読込形状との双方向の材料差と面積差を確認します。長さの比較許容差は `0.00001 mm`。材料差の閾値は `max(0.0000001 mm³, 体積 × 0.00000001)`、面積差の閾値も同じ相対率・数値下限をmm²で用います。入力形状の面・辺・頂点の許容差が長さの比較許容差を超える場合は保留します。

穴はまず中心が同位置の一意な組を対応付けます。残った穴は、板のXY最大寸法の25%以内（サンプルでは3 mm）で、旧→新・新→旧の両方向に候補が1つの場合だけ対応候補にします。両側に穴が残れば、複数候補や大きな移動と増減を区別できないため保留します。一方だけに残った穴は追加・削除候補です。穴ラベルH1などは各ファイル内の表示用番号です。

候補が一意でも、設計者が実際に行った操作を証明するものではありません。穴の入替や同位置での削除・再作成は履歴なしでは区別できません。回転・移動した板、外形変更、面の分割・結合、止まり穴、交差する穴、外周に接する穴、段差・曲面部品は今回の局所判定範囲外です。

### HTMLレポート

比較図は保存時の視点・拡大率・辺表示を反映した静的SVGです。保存後の視点変更はできません。寸法表、面の対応、根拠、保留理由、ファイル名・SHA-256・単位、ソフトウェア版、作成時刻、許容差、検索距離、形状照合の実測残差も含みます。CSS・図・結果データはHTML内に保存し、実行スクリプト・外部参照・サーバーへの要求は含みません。通常のブラウザでファイルを開いて閲覧する形式です。

## Implementation and Verification

`RevisionComparison` stores detached, JSON-serializable read-only snapshots,
not the editor's transaction or inferred feature model. `describe_plate`
qualifies measured descriptors, and `compare_revisions` computes the full
analysis before either slot and its revision token are published. The existing bounded
`read_step_input` importer checks units and solid limits before the shared
`shape_snapshot` tessellation routine. Temporary uploads are removed after
snapshot creation. A failed second demo import cannot replace the first slot.
Filenames are labels; neither filenames nor browser requests choose a server
filesystem path. Host, Origin, request-token and body-budget checks cover the
new endpoints as well as the existing editor.

Native imports and tessellation remain in-process without a hard native CPU or
memory limit. Renderer triangle limits are checked after meshing. These are
the existing local research application's constraints, not a hardened upload
service or a general-purpose STEP viewer.

```bash
python -m pytest tests/test_revision_detection.py tests/test_cad_web.py tests/test_operational_studies.py -k "not artifacts_reproduce" -q
```

The recorded local run passed 78 tests; five historical artifact-reproduction
cases were deselected. Independently constructed and separately exported STEP
controls cover diameter, equal-volume movement, thickness, addition/deletion,
ambiguous and distant holes, changed construction order, near-tolerance changes,
combined diameter/movement, translated plates and unsupported geometry. HTTP
controls cover report bytes/headers, missing inputs, invalid cameras, stale
requests and atomic rollback of matching failures. Existing upload, editor and
workspace-snapshot controls also passed. This is a local regression run, not a
general accuracy benchmark or new cross-platform result.

Current browser verification covers all six demos, classified rendering, region
selection, dimension filtering, rotation across the divider, reset and actual
HTML downloads. See the [current record](../results/cad-revision-workflow/verification.json),
[comparison screen](../results/cad-revision-workflow/comparison.png),
[dimension table](../results/cad-revision-workflow/dimensions.png), and downloaded
[diameter report](../results/cad-revision-workflow/diameter-report.html) and
[unresolved report](../results/cad-revision-workflow/ambiguous-report.html).
The browser automation environment blocks direct `file:` navigation, so visual
verification of the saved HTML opened as a local file remains unverified; the
downloaded bytes were checked for diagrams, metadata and absence of external
dependencies. The [v1.2 browser record](../results/cad-revision-comparison/verification.json)
is preserved separately and covers the original upload and stale-tab workflow.

The [research and publishing plan](step-revision-comparison-plan.md) describes
the next stages. This release does not publish an Insights article or broaden
the frozen Python API 1.0 contract.
