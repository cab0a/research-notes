# 実CADのSVG／DXF: 結果を見る・再現する

最新のSVG対応と形式間比較は[こちら](cad-svg-dxf.md)。以下は初回の再現手順。

**[結果HTMLを開く](../results/cad-drawing-exports/report.html)**

ブラウザーで開けば、図面、3D、数値、保留理由をオフラインで閲覧できる。
STEP/Python/JSONのダウンロードには、隣のケースフォルダーも必要。
GitHubのソース表示では3D操作は動かないため、ローカルのHTMLを開く。

Windowsのこのチェックアウトでは次のファイルをブラウザーへドラッグできる。

```text
\\wsl.localhost\Ubuntu\home\nakanishi\inefficiencylab\research-notes\results\cad-drawing-exports\report.html
```

アプリ内ブラウザーでは、PowerShellから閲覧サーバーを起動する。

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m http.server 8765 --bind 127.0.0.1
```

[ローカル閲覧URL](http://127.0.0.1:8765/results/cad-drawing-exports/report.html)を開く。
localhost限定の静的表示。CADの再計算APIではない。終了は起動端末でCtrl+C。

## 閲覧方法

1. 確認する例を選ぶ。最初は「1穴プレート / DXF」。
2. 左の表示を「入力DXFの描画」と「同じCADページの出力SVG」で切り替える。
3. 図面を拡大し、スクロールして寸法を見る。
4. 右の3Dをドラッグ・ホイール・矢印キーで操作。復元直後／寸法変更後を選ぶ。
5. 下の寸法表、再投影、DXFハンドルを含む対応根拠を確認する。
6. SVGの例や負例を選ぶと、モデルの代わりに未対応・保留理由を表示する。

図面は画像としてHTMLへ埋め込む。3Dは保存STEPの実際の三角形。
ブラウザーで自由に寸法入力して再生成する機能は含まない。
画面でモデルを編集後に切り替えても、寸法照合表は復元直後の値。

## 固定入力からの追試（FreeCAD不要）

```bash
python -m pip install -e ".[geometry,drawing,test]"
python -m experiments.run_cad_drawing_exports --output-dir output/cad-export-reproduction --repeats 2
python -m pytest tests/test_cad_drawing_exports.py tests/test_drawing_dimensions.py tests/test_drawing_to_cad.py -q
```

PowerShellから既存環境で:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m experiments.run_cad_drawing_exports --output-dir output/cad-export-reproduction --repeats 2
```

出力先は新規または空のフォルダー。既存候補の混入を防ぐため再使用は拒否する。
`--case one_dxf --repeats 1`で1例のみ。
「全対照が予定どおり」の終了コード0には、SVGの形式未対応も含まれる。
復元成功数はresults.jsonのsummary.by_formatで別に確認する。

1図面を読む場合:

```bash
python -m research_notes.cad_drawing_import fixtures/cad-drawing-exports/inputs/one/drawing.dxf fixtures/cad-drawing-exports/inputs/one/context.json --output-dir output/cad-drawing-single
python output/cad-drawing-single/candidate.py output/cad-drawing-single/candidate.step
```

先にinference.jsonのstatusを確認。保留の場合はcandidate.py/model.jsonを生成しない。
生成PythonのPARAMETERSを編集して、新しいSTEP名で実行すれば寸法変更できる。
元作者の履歴を復元したものではなく、今回推定した形状の編集用レシピ。

HTMLだけを再生成:

```bash
python -m research_notes.cad_drawing_report output/cad-export-reproduction
```

## CADからの入力生成を再現する場合

通常の追試では不要。生成はFreeCAD GUIのTechDrawを使用し、復元とは別の段階。
[FreeCAD 1.1.4公式配布](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4)から
`FreeCAD_1.1.4-Linux-x86_64-py311.AppImage`を取得した。
公式のSHA-256ファイルとの一致を確認した値:

```text
f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434
```

AppImageをoutput/freecad-runtime/FreeCAD.AppImageとして保存・展開済みの場合、
リポジトリのWSLシェルから実行する。

```bash
QT_QPA_PLATFORM=offscreen RESEARCH_CAD_EXPORT="$PWD/output/freecad-export-new" output/freecad-runtime/squashfs-root/AppRun experiments/export_freecad_drawings.FCMacro
python -m experiments.freeze_freecad_drawings output/freecad-export-new output/cad-fixtures-reproduction
```

RESEARCH_CAD_EXPORTは**未作成**フォルダーを指定。
マクロはモデル・図面・寸法を作り、SVG/DXF/STEP/FCStdとexport-log.jsonを保存して終了する。
エラー時はerror.txtを確認。アプリ終了コードだけで成功判定せず、
export-log.jsonの8件と全出力の存在を確認する。
GUIイベント待ち時間は今回の環境で確認した値で、遅い環境では調整が必要になる場合がある。

freezeは原本をコピーし、入力ハッシュ、context、評価用設計値・解析式を整理する。
元CAD/STEPは復元子プロセスへ渡さない。
STEPの日時・CAD文書メタデータ等で再生成時のバイト列は変わり得る。
通常の評価はコミットした原本ハッシュで固定する。

実測環境はWindowsホストのUbuntu26.04/WSL2。
FreeCAD1.1.4/内蔵OCCT7.8.1、復元Python3.12.14/cadquery-ocp7.9.3.1.1/ezdxf1.4.4。
ネイティブWindows、他CAD、GPU/AI/OCRは未実行。
全体テストの既存依存は[再現規約](reproducibility.md)を参照。

[研究ノート](../notes/cad-drawing-exports.md)、
[固定入力の出所](../fixtures/cad-drawing-exports/README.md)、
[検証記録](../results/cad-drawing-exports/verification.json)に結果と制約を保存した。
