# 別CAD・曖昧さ・未調整部品：閲覧と再現

[結果HTML](../results/drawing-generalization/report.html)を開くと、入力図面、
復元／寸法変更後の3D、寸法差、保留理由、上開き・下開き候補、断面を確認できます。
HTML内の描画にネットワーク接続は不要です。STEP等のリンクを使う場合は隣接フォルダーも必要です。
「未調整の部品」の例は入力選択欄の `holdout_`、別CADは `portability_` です。
3Dは左右ドラッグで手前の面が指示方向へ回り、上下ドラッグで下面側へも回転します。
モデル選択で寸法変更後を表示できます。HTML内でCADを再計算する機能ではありません。

## 固定入力で追試

Python 3.12.14 / cadquery-ocp 7.9.3.1.1 / ezdxf 1.4.4。
Windowsホスト上のWSL2 Ubuntu 26.04で実行しました。ネイティブWindowsは未評価です。
既存の `output/venv312` とOCCT基盤を再利用し、GPU・AI API・学習モデルは使用していません。
通常のセットアップは[共通手順](reproducibility.md)を参照してください。

以下はWSLシェルから、リポジトリのルートで実行します。出力先は未作成のディレクトリを指定します。

```bash
output/venv312/bin/python -m experiments.run_drawing_generalization \
  --output-dir output/drawing-generalization-replay --repeats 2
output/venv312/bin/python -m research_notes.drawing_generalization_report \
  output/drawing-generalization-replay
output/venv312/bin/python -m pytest -q \
  --junitxml=output/drawing-generalization-tests.xml
```

この追試にFreeCAD／LibreCAD本体は不要です。実行前後に150ソース・仕様ファイルの
SHA-256を確認します。将来の変更で不一致になった場合、元のコミットで再実行するか、
別実験として再固定してください。既存の凍結記録を書き換えて同じ評価と呼ばないでください。

## 1入力からCADを作る

```bash
output/venv312/bin/python -m research_notes.drawing_generalization \
  fixtures/drawing-generalization/development/inputs/bottom/drawing.svg \
  fixtures/drawing-generalization/development/inputs/bottom/context-svg.json \
  --output-dir output/bottom-reconstruction
output/venv312/bin/python output/bottom-reconstruction/candidate.py \
  output/bottom-reconstruction/candidate.step
```

線種を失ったDXFに、確認済み断面を追加する例：

```bash
output/venv312/bin/python -m research_notes.drawing_generalization \
  fixtures/drawing-generalization/development/inputs/section_bottom/drawing.dxf \
  fixtures/drawing-generalization/development/inputs/section_bottom/context-dxf.json \
  --section fixtures/drawing-generalization/development/inputs/section_bottom/section.svg \
  --output-dir output/section-reconstruction
```

保留の場合は `inference.json` だけを確認します。候補時に生成するPythonレシピの
`PARAMETERS` が編集対象です。`OPENING` は図面の根拠で選んだ開口方向です。
これは新しく構成した編集可能モデルであり、元作者の操作履歴の復元ではありません。

## CAD書き出しを再現する場合

実使用ツールはFreeCAD 1.1.4（内部OCCT 7.8.1）とLibreCAD 2.2.1.5（Qt 5.15.2）です。
ランタイムは `output/` に置き、配布対象外としています。

FreeCADは既存の公式AppImage展開版を使用しました。各仕様JSONを指定して実行します。
次は新しい出力先の例です。固定fixtureへのコピーは通常の追試では不要です。

```bash
QT_QPA_PLATFORM=offscreen \
RESEARCH_CAD_EXPORT="$PWD/output/new-holdout-export" \
RESEARCH_DRAWING_SPECS="$PWD/fixtures/drawing-generalization/holdout-specs.json" \
output/freecad-runtime/squashfs-root/AppRun \
  experiments/export_drawing_generalization.FCMacro
```

当初の順序は、開発入力生成 → 21開発テスト → `freeze_drawing_engine` →
holdoutのCAD出力 → `freeze_drawing_generalization` → 全入力評価、でした。
`engine-freeze.json` のUTC時刻とexport-log・結果の完了時刻を残しています。
準備／凍結スクリプトは既存成果物を作り直すための通常コマンドではありません。

LibreCADの実コマンドはケースごとの `export.log` とmanifestに保存しました。

```bash
QT_QPA_PLATFORM=xcb output/librecad-runtime/squashfs-root/AppRun \
  dxf2svg -r 1024x768 -o drawing.svg /absolute/path/to/source.dxf
```

この版は出力名に入力側ディレクトリを付けるため `-o` は相対ファイル名です。
`QT_QPA_PLATFORM=offscreen` は同梱プラグインがxcbのみのため起動失敗しました。
既存WSLg表示でxcbを使用するとCLI出力できました。WSLg／表示サーバーなしの
完全ヘッドレス環境やネイティブWindowsでの動作は確認していません。

## 出所・ライセンス・確認範囲

| 対象 | 一次情報と実行時の確認 |
|---|---|
| LibreCAD 2.2.1.5 | [公式リリース](https://github.com/LibreCAD/LibreCAD/releases/tag/v2.2.1.5)。GPLv2系。実バイナリを実行しSVG出力を観測 |
| dxf2svg実装 | [固定版CLIソース](https://raw.githubusercontent.com/LibreCAD/LibreCAD/v2.2.1.5/librecad/src/main/console_dxf2png.cpp)。ソースを調査、外部コードの転載なし |
| SVG書き出しの位置づけ | [LibreCADメニュー文書](https://docs.librecad.org/en/latest/ref/menu.html)。今回のCLI観測と一般的な機能説明を区別 |
| FreeCAD切断 | [1.1.4断面実装](https://raw.githubusercontent.com/FreeCAD/FreeCAD/1.1.4/src/Mod/TechDraw/App/DrawViewSection.cpp)を参照。今回実行したのはPart.slice＋TechDrawで、DrawViewSectionによる記号・ハッチング解釈ではない |

LibreCAD実使用AppImage SHA-256：
`0889296c62cd852df5ae6f559b840ec94a10b4e8514f0cbb04115e19fe74561f`。
公式URL、バージョン、コマンド、SVG入力hashは
[portability manifest](../fixtures/drawing-generalization/portability/manifest.json)に保存しています。
自作のコード・図面はリポジトリのPolyForm Noncommercial 1.0.0に従います。
外部バイナリ・学習データ・商用CAD出力は同梱していません。

[研究結果と次の実験](../notes/drawing-generalization.md) /
[全観測](../results/drawing-generalization/results.json) /
[実測テスト・リンク・hash検証](../results/drawing-generalization/verification.json)
