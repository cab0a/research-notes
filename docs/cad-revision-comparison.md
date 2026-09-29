# STEP Revision Comparison — v1.2.0

## 日本語概要

新旧2つのSTEPを独立して読み込み、共通の視点・縮尺・座標基準で並べて表示できます。単位、体積、面積、面数、辺数、頂点数と、新版から旧版を引いた差を確認できます。入力は明示的なmm単位の単体ソリッドに限定します。変更箇所の自動検出・局所寸法差・確認レポート保存は今後の開発です。操作方法と制限を、英語本文の要約に続いて説明します。

---

## English Summary

Version 1.2 adds a local read-only comparison screen for two independently
imported STEP files. Each slot holds its own immutable geometry snapshot and
measured metrics. Both views share their camera, scale and coordinate origin.
Uploads, pair demos and stale-tab handling publish complete states atomically,
without modifying the dimension editor. The bounded importer admits explicit
SI millimetres, a single root, one valid solid and shell, and at most 24 faces.
No correspondence, alignment, change detection, local dimension extraction or
report export is claimed by this release.

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
3. 左右どちらかをドラッグすると両方が回転します。境界やプレビューの外へドラッグしても操作を継続できます。
4. **表示**で面と辺、**拡大率**で共通の倍率を選びます。**視点を戻す**で初期の視点・倍率へ戻ります。
5. **全体の測定値**で、新旧の値と差を確認します。**旧版と新版を入れ替え**で差の符号も反転します。
6. ファイルを選び直せば片方だけを置き換えられます。**旧版を閉じる**・**新版を閉じる**は指定した側だけを解除します。

### ファイルを用意せず試す

**サンプル2件を開く**で、12 × 10 × 4 mmの穴付き板を2つ生成し、それぞれ別のSTEPとして読み込みます。
旧版の穴半径は1 mm、新版は1.3 mmです。この寸法はサンプルの作成条件であり、比較エンジンの推定結果ではありません。

| 測定値 | 旧版 | 新版 | 差（新版 − 旧版） |
| --- | --- | --- | --- |
| 体積 mm³ | 467.433629 | 458.762834 | −8.670796 |
| 面積 mm² | 434.849556 | 438.053980 | +3.204425 |
| 面数 | 7 | 7 | 0 |
| 辺数 | 15 | 15 | 0 |
| 頂点数 | 10 | 10 | 0 |

## 対応範囲と表示の意味

| 項目 | v1.2.0の動作 |
| --- | --- |
| 入力 | 各2 MB以下。単一ルート・正常な単体ソリッド・シェル1つ・1〜24面 |
| 単位 | 単一の明示的なSIミリメートル宣言・単位コンテキストを要求。他単位は拒否 |
| 形状 | 編集候補の採用は不要。読込条件を満たす球なども表示可能 |
| 座標 | 元データの位置・向きを維持。2形状全体の境界を使い、同じ中心と縮尺で投影 |
| 描画 | 診断用の三角形・曲線サンプル。陰影は形状を見やすくするためで、変更箇所の色分けではない |
| 全体の測定 | 体積・面積・面数・辺数・頂点数。差が0でも形状一致と判定しない |
| 未読込の片側 | 空欄として表示し、差を計算しない |
| 読込失敗 | 正常に読み込めていた両側のデータを保持 |
| 状態の競合 | 古い比較状態からの読込・入替・解除を拒否し、最新状態を表示 |
| 寸法編集との関係 | 比較用データは独立。寸法編集の候補・確定形状・未確定変更に影響しない |
| ローカル処理 | 外部への送信・外部参照の取得なし。サーバー終了時に比較状態を破棄 |

同じサーバーを開いたタブ同士は比較データを共有します。自動位置合わせはないため、元データの座標が大きく離れている場合は形状が小さく見えます。
形状間の対応付け、変更箇所の判定、穴径などの局所寸法差、比較レポート保存は未実装です。

## Implementation and Verification

`RevisionComparison` stores detached, JSON-serializable read-only snapshots,
not the editor's transaction or inferred feature model. The existing bounded
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
python -m pytest tests/test_cad_web.py tests/test_operational_studies.py -k "not artifacts_reproduce" -q
```

The recorded local run passed 47 tests; five historical artifact-reproduction
cases were deselected. Controls cover independent real HTTP uploads, analytic
volumes and areas, swap/clear semantics, no inferred shape equality, preserved
translated coordinates, inspection without editable candidates, failed units,
malformed/oversized requests, stale revisions, atomic previews and editor
isolation. Existing editor and workspace-snapshot controls also passed.

Browser verification covers actual file selection, paired rendering, rotation
across the divider, reset, invalid-upload recovery, swap and tab conflicts.
See [verification evidence](../results/cad-revision-comparison/verification.json)
and the [comparison screen](../results/cad-revision-comparison/comparison.png)
and [metrics table](../results/cad-revision-comparison/metrics.png).

The [research and publishing plan](step-revision-comparison-plan.md) describes
the next stages. This release does not publish an Insights article or broaden
the frozen Python API 1.0 contract.
