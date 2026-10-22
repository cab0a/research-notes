# 交差形状・穴種・寸法表記：閲覧と実行

[結果HTML](../results/drawing-machining/report.html)を開き、例を選びます。
図面の三面切替、3Dの回転、復元／寸法変更後の比較、STEP・Python・モデルJSONの保存ができます。
寸法公差は元図面の公称値・偏差・寸法IDとして別表に表示します。
HTMLは保存済み結果を表示するもので、ブラウザー内でCADを再計算しません。
図面・3Dは埋め込み済みです。ダウンロードには隣接フォルダーも必要です。

今回はユーザー指定により、テストコード追加・テストスイート実行をしていません。
以下は復元実験を再実行するコマンドで、pytestコマンドは追加していません。

## 環境

Windowsホスト＋WSL2 Ubuntu 26.04、Python 3.12.14、cadquery-ocp 7.9.3.1.1、ezdxf 1.4.4。
作者側はFreeCAD 1.1.4（内部OCCT 7.8.1）。ネイティブWindowsは未評価。
既存の `output/venv312` を使用し、追加の依存関係・GPU・AI APIはありません。

以下はリポジトリルートのWSLシェルで実行します。出力先には未作成のフォルダーを指定します。

## 保存済みの20入力を実行

```bash
output/venv312/bin/python -m experiments.run_drawing_machining \
  --output-dir output/drawing-machining-replay
output/venv312/bin/python -m research_notes.drawing_machining_report \
  output/drawing-machining-replay
```

作者側FreeCADの起動は不要です。各入力を1回実行し、寸法・B-Rep・STEP・元形状・編集後を記録します。
同じ開発入力の追試であり、新しい未調整部品の評価にはなりません。
実行記録の `tests.executed=false` はテストスイート未実行を示し、CAD実験を実行していないという意味ではありません。

## 座ぐり付き貫通穴を復元

```bash
output/venv312/bin/python -m research_notes.drawing_machining \
  fixtures/drawing-machining/inputs/counterbore/drawing.svg \
  fixtures/drawing-machining/inputs/counterbore/context-svg.json \
  --output-dir output/counterbore-reconstruction
output/venv312/bin/python output/counterbore-reconstruction/candidate.py \
  output/counterbore-reconstruction/candidate.step
```

`candidate.py` の `PARAMETERS` を編集して別のSTEPへ出力できます。
モデルは `pocket`、`bore`、`counterbore` の形状要素を持ちます。
`bore` の `extent` は `through` / `blind`、止まり穴には `depth` と `entry` があります。
`counterbore` は貫通する小径と、`counter_diameter` / `counter_depth` を持つ大径の1段構成です。

| 軸 | 位置u | 位置v | positive側からの進入 |
|---|---|---|---|
| z | X | Y | 上面Z=板厚 |
| x | Y | Z | 右面X=板幅 |
| y | X | Z | 奥側Y=板奥行（今回の実行例にはない） |

## 公差・数量・連鎖の記録

`toleranced_bore` の `model.json` には公称値に加え、元図面の公差が入ります。

```json
{
  "nominal_mm": 10.0,
  "deviations_mm": {"lower": -0.1, "upper": 0.2},
  "source_text": "10 +0.2/-0.1 DEPTH 8"
}
```

公差は元図面に対するメタデータです。Pythonで径を変更しても、公差の妥当性を自動で判断・更新しません。
STEPへ公差PMIを出力する実装もありません。
`bindings` の寸法IDをたどると、連鎖で位置を得た経路や、数量指示を共有する穴を確認できます。
寸法値の直入力をcontextに追加して復元する仕組みではありません。

保留時は `inference.json` の `reason_code` と `detail` を確認します。
深さが不明なら `hole_extent_ambiguous`、数量が違えば `quantity_conflict`、H7等は `unsupported_annotation` です。
複数の加工方向が残る場合は `direction_ambiguous`。推測で候補STEPを出しません。

## 作者側の再出力

```bash
QT_QPA_PLATFORM=offscreen \
RESEARCH_CAD_EXPORT="$PWD/output/machining-authoring-replay" \
RESEARCH_DRAWING_SPECS="$PWD/fixtures/drawing-machining/authoring-specs.json" \
output/freecad-runtime/squashfs-root/AppRun \
  experiments/export_drawing_machining.FCMacro
```

通常の追試でfixtureを再作成する必要はありません。`prepare_` / `freeze_` は元入力の作成記録です。
作者側仕様・FCStd・正解STEPは評価専用で、復元ワーカーへ渡していません。
自作コード・入力はリポジトリのPolyForm Noncommercial 1.0.0に従います。
外部データセット・実行バイナリは同梱していません。

[研究結果・制限・次の候補](../notes/drawing-machining.md)
