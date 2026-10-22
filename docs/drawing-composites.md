# 複合形状の2D→CAD：閲覧と再現

[結果HTML](../results/drawing-composites/report.html)を開き、例を選びます。
入力図面と3Dを並べ、復元直後／寸法変更後を切り替えられます。
3Dはドラッグ・矢印キーで回転、ホイールで拡大縮小。下面のポケットも回転して確認できます。
図面・3D・表はHTMLに埋め込み済みで、表示に外部通信は不要です。
STEP等の保存リンクには隣接フォルダーも必要です。HTML内ではCADを再計算しません。

## 環境

WindowsホストのWSL2 Ubuntu 26.04、Python 3.12.14、cadquery-ocp 7.9.3.1.1、ezdxf 1.4.4。
既存の `output/venv312` を利用。GPU、AI API、新規の大規模依存なし。
ネイティブWindowsの実行は未評価です。[共通セットアップ](reproducibility.md)を参照。

以下はWSLシェルからリポジトリのルートで実行します。出力先は未作成のディレクトリにします。

## 固定入力をまとめて追試

```bash
output/venv312/bin/python -m experiments.run_drawing_composites \
  --output-dir output/drawing-composites-replay --repeats 2
output/venv312/bin/python -m research_notes.drawing_composite_report \
  output/drawing-composites-replay
output/venv312/bin/python -m pytest tests/test_drawing_composites.py -q
```

通常の追試にFreeCAD／LibreCAD本体は不要です。旧研究の150ファイルと今回の凍結記録を照合します。
将来ソースが変わった場合は該当コミットで再現するか、別実験として固定してください。
凍結記録を上書きして同じ未調整評価と扱わないでください。
任意出力先で作るHTMLの研究ノートへのリンクは、`output/<name>` または `results/<name>` の深さを想定しています。
LibreCAD別経路は主評価と別なので、通常の追試先ではPNGへのリンクを表示しません。

## ポケット＋穴を1入力から復元

```bash
output/venv312/bin/python -m research_notes.drawing_composites \
  fixtures/drawing-composites/development/inputs/pocket_hole/drawing.svg \
  fixtures/drawing-composites/development/inputs/pocket_hole/context-svg.json \
  --output-dir output/composite-one
output/venv312/bin/python output/composite-one/candidate.py \
  output/composite-one/candidate.step
```

`candidate.py` の `PARAMETERS` に板寸法と `features` を保存しています。
各形状の位置・幅・深さ・径を変更し、別のSTEPへ保存できます。
これは元CADの操作履歴を取得したものではなく、図面から新たに構成した編集可能モデルです。
対応外の重なり・深さ・種類は生成時にも検査します。

## 文字対応を確認して再計算

HTMLで「寸法文字を選択して再計算①／②」を選び、寸法線と文字を見て選択JSONを保存できます。
「操作した人」を選び、開始→文字ID選択→保存すると操作記録も出せます。
この時間には環境準備・CAD計算を含みません。今回保存した記録はエージェントによる操作確認です。

保存済みの実操作JSONで追試する例：

```bash
output/venv312/bin/python -m research_notes.drawing_composites \
  fixtures/drawing-composites/controls/review_pocket_4/drawing.svg \
  fixtures/drawing-composites/controls/review_pocket_4/context.json \
  --review fixtures/drawing-composites/controls/review_pocket_4/review.json \
  --output-dir output/composite-reviewed
output/venv312/bin/python output/composite-reviewed/candidate.py \
  output/composite-reviewed/candidate.step
```

選択JSONは元図面のSHA-256と寸法ID→文字IDだけを含みます。数値は渡しません。
別ファイルや対象外ID、数値の上書きは拒否し、図形・寸法の整合性を再検査します。
保留時は `inference.json` の理由を確認します。候補STEPは作りません。

## CADの作者側出力を再現する場合

FreeCAD 1.1.4（内部OCCT 7.8.1）、公式AppImageの既存展開版を使用しました。
作者側マクロは従来の `export_drawing_families.FCMacro` の共通TechDraw出力を再利用します。
元仕様と編集後仕様から、別々にFreeCAD形状・STEPを作成します。

```bash
QT_QPA_PLATFORM=offscreen \
RESEARCH_CAD_EXPORT="$PWD/output/composite-authoring-replay" \
RESEARCH_DRAWING_SPECS="$PWD/fixtures/drawing-composites/holdout-specs.json" \
output/freecad-runtime/squashfs-root/AppRun \
  experiments/export_drawing_composites.FCMacro
```

元実験は、開発入力生成→開発24テスト→`freeze_composite_engine`→未調整CAD生成→
`freeze_drawing_composites`→32入力を2回評価、の順です。
作者マクロ、準備／凍結スクリプトは出所の記録であり、通常の追試で固定fixtureを再作成しません。
STEPやFCStdは時刻等でバイト一致しない場合があるため、生成し直したものは別出力として評価します。

## LibreCADの追加診断

```bash
output/venv312/bin/python -m experiments.probe_librecad_drawing_render \
  --runtime output/librecad-runtime/squashfs-root/AppRun \
  --output-dir output/librecad-render-replay
```

LibreCAD 2.2.1.5（Qt 5.15.2）、WSLgのxcbでPNGとSVGを出力。
PNGの寸法文字が見えない観測を保存したもので、OCR・3D復元はしていません。
完全ヘッドレス・別環境での再現や原因特定は未確認。
CLIログの `LC_CrashHandler installed` は登録メッセージで、今回の終了コードは0です。
ソフトウェアの出所とライセンスは[前研究の記録](drawing-generalization.md#出所ライセンス確認範囲)を継承します。
自作コード・図面はPolyForm Noncommercial 1.0.0。外部ランタイム・学習データは配布しません。

[研究結果と次の計画](../notes/drawing-composites.md) /
[全結果](../results/drawing-composites/results.json) /
[検証記録](../results/drawing-composites/verification.json)
