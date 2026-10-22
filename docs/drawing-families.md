# 部品形状拡張：結果を見る・再現する

**[結果HTMLを開く](../results/drawing-families/report.html)**

最初は「L字ブラケット / SVG」。例を切り替えると段付き軸、矩形ポケット、複数穴、保留例も確認できる。
入力図面の「表示」で三面図全体・正面・平面・右側面を選択する。
3Dはドラッグ/矢印キーで回転、ホイールで拡大縮小。「寸法変更後」へ切り替えて編集結果を見る。
寸法表は元の抽出値・正解・変更後の値を別列にする。

下の「寸法の根拠と、人が確認する条件」で寸法を選ぶと、その寸法が参照する形状上の端点と
パラメータ名を強調する。寸法線の描画位置そのものではない。
DXFの入力画像は同じCADページのSVGであると明記し、DXF復元にはそのSVGを渡していない。

HTML単体で閲覧・条件JSON保存が可能。STEP/Python/JSONへのリンクは隣接フォルダーも必要。
ブラウザー内でCAD再計算や数値の寸法編集はしない。

## Windows / WSLから開く

ブラウザーへ以下のファイルをドラッグ:

```text
\\wsl.localhost\Ubuntu\home\nakanishi\inefficiencylab\research-notes\results\drawing-families\report.html
```

アプリ内ブラウザー用のローカルHTTP配信はPowerShellで:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m http.server 8765 --bind 127.0.0.1
```

[閲覧URL](http://127.0.0.1:8765/results/drawing-families/report.html)。停止は起動端末でCtrl+C。
既に8765で配信していれば追加起動は不要。

## 固定入力から再実行

```bash
python -m pip install -e ".[geometry,drawing,test]"
python -m experiments.run_drawing_families --output-dir output/drawing-families-reproduction --repeats 2
python -m pytest tests/test_drawing_families.py -q
```

出力先は新規ディレクトリ。固定SVG/DXFを使うのでFreeCAD起動は不要。
標準実験は32入力×2回。再現対象は11組のCAD出力と10派生SVGで、原本を変更しない。

既存のWSL環境をPowerShellから使う場合:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m experiments.run_drawing_families --output-dir output/drawing-families-reproduction --repeats 2
```

## 1件の復元・編集

```bash
python -m research_notes.drawing_families fixtures/drawing-families/inputs/l_bracket/drawing.svg fixtures/drawing-families/inputs/l_bracket/context-svg.json --output-dir output/l-bracket
python output/l-bracket/candidate.py output/l-bracket/candidate.step
```

inference.jsonがwithheldならcandidate.pyは作らない。まず理由と入力寸法を確認する。
生成されたcandidate.pyのPARAMETERSを編集し、別名のSTEPへ再実行する。
DXFはdrawing.dxfとcontext-dxf.jsonへ置き換える。4ファミリー共通のCLI。

## 人の確認→JSON保存→再計算

1. HTMLで「正面・平面の取り違え / SVG」を選び、保留理由を読む。
2. 確認欄で正面をpath:0、平面をpath:17、右側面をpath:44、第三角法にする。
   これはこの固定入力の参照番号で、任意の図面に流用しない。
3. 「確認条件JSONを保存」を押す。3Dと数値はまだ更新されない。
4. ダウンロードしたJSONを作業場所へ置き、入力図面と一緒にCLIへ渡す。

```bash
python -m research_notes.drawing_families fixtures/drawing-families/variants/wrong_views/drawing.svg /path/to/wrong_views_svg-reviewed-context.json --output-dir output/reviewed
python output/reviewed/candidate.py output/reviewed/candidate.step
```

この操作を実ブラウザーで試し、[修正条件](../results/drawing-families/review-correction/context.json)と
[再生成STEP](../results/drawing-families/review-correction/regenerated/candidate.step)を保存した。
寸法値や正解STEPを追加入力したものではない。人の作業時間は測定していない。

## CAD原本の再作図

[前回のFreeCAD入手・環境記録](cad-drawing-exports.md)に従ってFreeCAD 1.1.4を用意する。
既存の隔離実行環境で実行したコマンド:

```bash
QT_QPA_PLATFORM=offscreen RESEARCH_CAD_EXPORT="$PWD/output/drawing-families-export-new" output/freecad-runtime/squashfs-root/AppRun experiments/export_drawing_families.FCMacro
python -m experiments.freeze_drawing_families output/drawing-families-export-new output/drawing-families-freeze-new
```

再作図STEPには日時等が入り得るため、原本のSHA-256一致は要求せず、設計値・形状で比較する。
固定入力の追試には上のrunnerを使う。freezeの任意出力先をrunnerへ渡すオプションはない。
派生対照の作成スクリプトexperiments/derive_drawing_family_controls.pyは、固定入力を作る開発用。
既存variantsへ上書きしない。新規checkoutでfreeze直後に実行する場合だけ使う。

原本は自作図面。FCStd、正解STEP、作図ログ、入力SHA-256を保持。
outline文字の生成にはmatplotlibに同梱されたDejaVu Sansを利用し、
[ライセンス](../fixtures/drawing-families/licenses/LICENSE_DEJAVU)を残す。外部顧客データは含めない。

## 保存物と検証

| 場所 | 内容 |
|---|---|
| fixtures/drawing-families/inputs | 未変更のCAD出力・人の非数値条件 |
| fixtures/drawing-families/variants | 派生SVGと条件、manifestに派生元 |
| fixtures/drawing-families/evaluation | 評価専用の設計値と編集前後の正解STEP |
| fixtures/drawing-families/baseline.json | 適応前の判定と旧コードハッシュ |
| 各結果/inference.json | 寸法・参照端点・パス/文字ID・保留理由 |
| 各結果/candidate.py, model.json | 編集可能な生成レシピ |
| 各結果/candidate.step, edited.step | 復元と編集後の出力 |
| results.json, summary.csv | 全64試行・11組の比較・依存版・閾値 |
| review-correction | ブラウザーで保存した条件とCLI再生成 |
| verification.json | テスト・原本・成果物・文書リンクの照合 |

HTMLのみ再生成:

```bash
python -m research_notes.drawing_family_report output/drawing-families-reproduction
```

固定成果物の監査（全テスト、ブラウザー確認、文書保存の後）:

```bash
python -m pytest -q --junitxml=output/drawing-families-tests.xml
python -m experiments.verify_drawing_families results/drawing-families --junit output/drawing-families-tests.xml
```

実行環境はUbuntu 26.04 / WSL2、Python3.12.14、cadquery-ocp7.9.3.1.1、ezdxf1.4.4。
正解作図はFreeCAD1.1.4 / OCCT7.8.1。Windowsネイティブ・別CAD・OCR・AI APIは未実行。
[研究ノートの成立条件と次の計画](../notes/drawing-families.md)を参照。
