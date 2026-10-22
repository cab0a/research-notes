# 寸法線からのCAD復元: 結果を見る・追試する

**保存済み結果: [report.html](../results/drawing-dimensions/report.html)**

ローカルファイルとしてブラウザーで開ける。HTMLには図面・3D・数値を埋め込んでいるため、
閲覧だけならPythonやOCCT、通信は不要。STEP等のダウンロードには隣のケースフォルダーも保持する。
GitHubのソース表示ではJavaScriptによる回転は動かないため、ローカルで開く。

## Windowsで開く

エクスプローラーで次のファイルをブラウザーへドラッグするか、ブラウザーの「ファイルを開く」で指定する。

```text
\\wsl.localhost\Ubuntu\home\nakanishi\inefficiencylab\research-notes\results\drawing-dimensions\report.html
```

検証時のフォルダー名であり、別のチェックアウトでは自分のパスに置き換える。
アプリ内ブラウザー等でファイルを直接開けない場合は、ローカルHTTPサーバーも使える。
PowerShellで実行:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m http.server 8765 --bind 127.0.0.1
```

ブラウザーで以下を開く。

```text
http://127.0.0.1:8765/results/drawing-dimensions/report.html
```

サーバーは閲覧用で、CADの再計算を実行するAPIではない。終了は起動した端末でCtrl+C。
別のPCではポートとPythonパスを調整する。

## HTMLでできること

1. 「確認する例」で部品または負例を選択。
2. 入力図面を平面/正面/右側面/全体へ切り替え、必要なら拡大。
3. 3Dをドラッグ、ホイール、矢印キーで操作。「視点リセット」で戻せる。
4. 「寸法変更後」で実験時に再生成したモデルへ切り替え。同じ視点を維持する。
5. 復元直後の寸法表、再投影、抽出根拠、STEP/Python/JSONを確認。
6. 「保留」に絞り、生成しなかった理由と次の確認を読む。

ブラウザー内の寸法入力・再計算は未実装。HTMLは保存した観測結果の表示。
正解モデルを保留例の代わりに表示することもない。

## 実験の再実行

依存は既存のまま、Python3.11以上と`geometry`/`test`オプション。
実測はWindowsホストのUbuntu/WSL2、Python3.12.14、cadquery-ocp7.9.3.1.1。
ネイティブWindowsは未実行。GPU・AI API・OCR・外部モデルの重みは使用しない。

```bash
python -m pip install -e ".[geometry,test]"
python -m experiments.run_drawing_dimension_lines --output-dir output/dimension-reproduction --repeats 2
python -m pytest tests/test_drawing_dimensions.py tests/test_drawing_to_cad.py -q
```

PowerShellから既存環境で実行する場合:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python -m experiments.run_drawing_dimension_lines --output-dir output/dimension-reproduction --repeats 2
```

出力先は未作成または空のフォルダーにする。古い候補を保留結果と混ぜないため、再利用を拒否する。
再実行する場合は別の出力先を選ぶ。`--case one_third --repeats 1`で1部品だけ確認できる。
通常は全ての対照が想定どおりなら終了コード0。保留例も、想定した理由と一致すれば対照として合格する。
候補生成の成功と、想定どおり保留したことは別々に集計する。

出力先の`report.html`に同じ形式のHTMLを生成する。
既存結果からHTMLだけ作り直すコマンド:

```bash
python -m research_notes.drawing_dimension_report output/dimension-reproduction
```

全体テストの比較依存は[既存の再現手順](reproducibility.md)を参照。

## 1部品の解釈とSTEP生成

```bash
python -m research_notes.drawing_dimensions fixtures/drawing-dimensions/inputs/one_third.svg fixtures/drawing-dimensions/inputs/one_third.context.json --output-dir output/dimension-single
python output/dimension-single/candidate.py output/dimension-single/candidate.step
```

解釈CLIは保留を正常に記録した場合も終了コード0。`inference.json`のstatusを確認してから
生成コードを実行する。保留なら`candidate.py`と`model.json`は作らない。
寸法変更は生成Pythonの`PARAMETERS`を編集し、別名のSTEPへ再実行する。
既存STEPの上書きは拒否する。

## 固定入力と評価

通常の追試では入力の再生成は不要。
`fixtures/drawing-dimensions/manifest.json`の入力ハッシュを検証してから実行する。
正解STEPと設計値は`evaluation/`に隔離し、復元ワーカーには渡さない。
生成元を確認する場合は以下を読む。

- [入力生成処理](../experiments/build_drawing_dimension_fixtures.py)
- [図面解釈](../src/research_notes/drawing_dimensions.py)
- [実験・評価](../experiments/run_drawing_dimension_lines.py)
- [HTML生成](../src/research_notes/drawing_dimension_report.py)

生成スクリプトは`python -m experiments.build_drawing_dimension_fixtures`で実行できるが、
固定入力・評価用STEPを更新する操作である。STEPヘッダーが変わるとバイトハッシュも変わる。

実測・失敗理由・条件・今後の計画は[研究ノート](../notes/drawing-dimension-lines.md)、
実行確認は[verification.json](../results/drawing-dimensions/verification.json)に保存。
