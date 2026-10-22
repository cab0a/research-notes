# SVGとDXFの一致検証: 結果を見る・再現する

**[最新の結果HTML](../results/cad-svg-dxf/report.html)**

最初は「1穴プレート / SVG」を表示する。
「確認する例」で同じ名前のSVGとDXFを切り替え、図面・3D・寸法差を確認できる。
3Dはドラッグ、ホイール、矢印キーで操作し、「寸法変更後」も選べる。
下の「同じ図面のSVGとDXF」に抽出値の差、復元／編集後の体積IoUを表示する。
負例ではSTEPを表示せず、保留理由を表示する。

HTML単体でオフライン閲覧可能。ダウンロード用STEP/Python/JSONは隣のフォルダーも必要。
HTML内で寸法入力・CAD再計算はしない。3D切替後も寸法表は復元直後の値。

Windowsでは以下をブラウザーへドラッグできる。

```text
\\wsl.localhost\Ubuntu\home\nakanishi\inefficiencylab\research-notes\results\cad-svg-dxf\report.html
```

アプリ内ブラウザーで開く場合、PowerShellで:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m http.server 8765 --bind 127.0.0.1
```

[閲覧URL](http://127.0.0.1:8765/results/cad-svg-dxf/report.html)。終了は起動端末でCtrl+C。

## 固定入力から追試

```bash
python -m pip install -e ".[geometry,drawing,test]"
python -m experiments.run_cad_svg_pairs --output-dir output/cad-svg-reproduction --repeats 2
python -m pytest tests/test_cad_svg_pairs.py -q
```

既存WSL環境をPowerShellから使う場合:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m experiments.run_cad_svg_pairs --output-dir output/cad-svg-reproduction --repeats 2
```

出力先は新規／空に限る。1組だけなら
`--case one_svg --case one_dxf --repeats 1` を付ける。
ペア評価のため両形式を指定する。

入力は前回のFreeCAD原本をハッシュ照合して使用。FreeCADのインストール・再出力は不要。
SVG復元プロセスへ渡すのはSVGと人の選択contextのみ。
DXF・正解STEP・設計値はSVG復元に渡さない。
結果は36試行の観測と9組の比較。反復数は独立標本数ではない。

## SVGを1件だけ復元

```bash
python -m research_notes.cad_svg_import fixtures/cad-drawing-exports/inputs/one/drawing.svg fixtures/cad-svg-dxf/one_svg.json --output-dir output/svg-single
python output/svg-single/candidate.py output/svg-single/candidate.step
```

まずinference.jsonのstatusを確認する。withheldならcandidate.py/model.jsonは作らない。
candidate.pyのPARAMETERSを編集し、別名のSTEPへ実行すると寸法変更できる。
例では40×30×8 mm、穴X12/Y10/径6 mmを抽出する。これらの値はcontextには含めない。

DXF単独は[前回のCLI](cad-drawing-exports.md)を利用する。
前回のcad_drawing_importのSVG保留動作は歴史的な比較用に保持し、
新SVG処理はcad_svg_importとして追加した。

## 出力と根拠

| 保存物 | 内容 |
|---|---|
| results.json / summary.csv | 各形式・各反復の成否、保留理由、計測値、環境・ソースハッシュ |
| pairs.csv | SVG対DXFの寸法差、復元／編集後IoU、保留理由の一致判定 |
| 各例/inference.json | 抽出寸法、SVGパス／文字／矢印参照、変換後の根拠、元曲線 |
| 各例/candidate.py / model.json | 編集可能な再生成レシピ。元の設計履歴ではない |
| 各例/candidate.step / edited.step | 復元・編集後のソリッド |
| 各例/comparison.json / preview.json | 正解照合、再投影、3D表示用メッシュ |
| report.html | 通信不要の閲覧画面 |

HTMLのみ再生成:

```bash
python -m research_notes.cad_svg_report output/cad-svg-reproduction
```

固定成果物とテスト実行記録の照合（HTMLの手動確認後）:

```bash
python -m pytest -q --junitxml=output/cad-svg-tests.xml
python -m experiments.verify_cad_svg_pairs results/cad-svg-dxf --junit output/cad-svg-tests.xml
```

## 成立条件

人が用紙単位、形状クラス、投影法、図面グループ、3つの外形パスを指定する。
パス参照はDrawingContent内での0始まりpath要素番号で、原本を変えたら選び直す。
選択スクリプトを別の新規フォルダーへ再実行することもできる。

```bash
python -m experiments.prepare_cad_svg_pairs output/svg-context-reproduction
```

この出力内の相対パスはfixtures配下で使う前提。入力ハッシュ・contextの再確認用であり、
別ディレクトリのmanifestをそのまま標準ランナーへ渡す機能はない。

任意のSVG／曲線に対応した変換器ではない。
円の4区間ベジェ近似、限定した寸法線とXMLテキスト、矩形板のみ。
詳細な閾値・未対応・今後の研究は[研究ノート](../notes/cad-svg-dxf.md)を参照。

実測: Ubuntu26.04/WSL2（Windowsホスト）、Python3.12.14、
cadquery-ocp7.9.3.1.1、ezdxf1.4.4。ネイティブWindowsは未実行。
元FreeCADの出所・ライセンス・再作図手順は[前回](cad-drawing-exports.md)に保存。
