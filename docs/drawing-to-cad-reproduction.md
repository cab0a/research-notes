# 2D図面→編集可能CAD: 初回実験の再現

この手順は独立した探索研究で、リリース機能の追加ではない。
[研究ノート](../notes/drawing-to-parametric-cad.md)に先行技術比較、仮定、結果、限界を示す。
以下はリポジトリルートで実行する。外部AI APIや学習データの取得は不要。

## 環境

実測環境はWindowsホスト上のUbuntu/WSL2、Python3.12.14、
`cadquery-ocp==7.9.3.1.1`、research-notes 1.17.0。
追加のGPU、CadQueryパッケージ本体、build123d、OCR、SMLib、モデル重みは使用していない。
依存は既存のpyproject.tomlのまま。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[geometry,test]"
```

既存の全テストを再現する場合は比較パーサー依存も必要。
`python -m pip install -e ".[comparison,geometry,test]"`と
[既存の比較環境の手順](reproducibility.md)を参照。
今回使用した既存venvは`output/venv312`。このパス自体は配布しない。

Windowsネイティブでは、依存が用意できれば同じPythonコマンドを使用する構成だが、
**今回実行したのはWSL2だけ**であり、ネイティブWindowsの動作確認とはしない。
PowerShellから既存WSL環境で追試したコマンド:

```powershell
wsl.exe -d Ubuntu --cd /home/nakanishi/inefficiencylab/research-notes output/venv312/bin/python experiments/run_drawing_to_cad.py --output-dir output/drawing-reproduction --repeats 2
```

`/home/nakanishi/...`は検証時の絶対パス。他の環境では自分のチェックアウトへ置き換える。
セットアップ後、下記の幾何実験はネットワークを必要としない。

## まず1部品を生成する

`output/drawing-single`は未作成または空のディレクトリにする。
過去の候補が保留結果に混ざることを避けるため、空でない出力先は拒否する。

```bash
python -m research_notes.drawing_to_cad \
  fixtures/drawing-to-cad/inputs/one_third.svg \
  fixtures/drawing-to-cad/inputs/one_third.context.json \
  --output-dir output/drawing-single
python output/drawing-single/candidate.py output/drawing-single/candidate.step
```

PowerShellでは行継続を避けて1行ずつ実行できる:

```powershell
python -m research_notes.drawing_to_cad fixtures/drawing-to-cad/inputs/one_third.svg fixtures/drawing-to-cad/inputs/one_third.context.json --output-dir output/drawing-single
python output/drawing-single/candidate.py output/drawing-single/candidate.step
```

`inference.json`に`status: candidate`、抽出寸法と根拠を保存する。
`model.json`は既存FeatureModel形式、`candidate.py`は実行可能な設計レシピ。
SVGの専用記法を読む実験であり、一般のSVGや画像へそのまま置き換えることはできない。

寸法を変えるには`candidate.py`の`PARAMETERS`を編集し、別名のSTEPへ再生成する:

```bash
python output/drawing-single/candidate.py output/drawing-single/edited.step
```

同名STEPの上書きは既存writerが拒否する。
STEPは静的形状で、寸法編集にはPython/JSONの設計表現を保持する。
モデルのJSON読込には既存`deterministic_recompute.model_from_dict`を利用できる。

保留例:

```bash
python -m research_notes.drawing_to_cad \
  fixtures/drawing-to-cad/inputs/ambiguous_extent.svg \
  fixtures/drawing-to-cad/inputs/ambiguous_extent.context.json \
  --output-dir output/drawing-withheld
```

`status: withheld`、`reason_code: hole_extent_ambiguous`となり、
CADコードとモデルは作らない。解釈CLIは正常に保留を記録した場合も終了コード0。
利用側は終了コードだけで成功とせず、必ずstatusを確認する。

## 固定13入力の生成・再投影・評価

```bash
python experiments/run_drawing_to_cad.py --output-dir output/drawing-reproduction --repeats 2
python -m pytest tests/test_drawing_to_cad.py -q
```

通常実験の終了コードは、全ての対照が想定通りなら0。
生成対象6件、保留対象7件を各2回実行し、JSON/CSVと各部品の成果物を保存する。
runnerは自分の出力ファイルを更新するため、追試ではコミット済みresultsを出力先にしない。
1部品に絞る場合は`--case one_third --repeats 1`を追加する。

生成ワーカーへ渡すのはSVG、context、空の作業ディレクトリのみ。
正解は`fixtures/drawing-to-cad/evaluation/`から評価側が別に読む。
評価は既存穴認識・幾何計測・Boolean差分と、実際のB-RepへのHLRを利用する。
部品座標の位置合わせや縮尺の最適化は行わない。

## 意図的に失敗する編集対象の反例

```bash
python experiments/run_drawing_to_cad.py \
  --output-dir output/drawing-order-failure \
  --case two_third --repeats 1 --edit-target sequence_first
```

**期待する終了コードは1**。元形状は一致するが、注記の配列順で編集する穴が変わる。
結果の`initial_reconstruction_passed`はtrue、`failure_stage`は`edit_evaluation`、
編集後の穴寸法差は1 mm、体積差は約31.4159265 mm³になる。
通常の`--edit-target leftmost`はX最小/Y最小の穴を双方で選び、この反例を切り分ける。
どちらも一般のフィーチャー対応を解決したものではない。

## 入力の再生成と出所調査は別の操作

追試に入力の再生成は不要。固定manifestのハッシュを使う。
フィクスチャ生成元は`experiments/build_drawing_cad_fixtures.py`。
実行すると入力と正解を再生成するため、通常の追試とは分ける。
STEPヘッダーの日付等によりバイトハッシュが変わりうるので、
既存manifestとの同一性と幾何的な同一性を混同しない。

先行研究のソースを再確認する場合だけネットワークを使用する。
以下のクローン先はGitの追跡対象外。コードを取り込んだり推論を実行したりはしない。

```bash
mkdir -p output/drawing-cad-sources
git clone https://github.com/AdityaJoglekar/Ortho2CAD output/drawing-cad-sources/Ortho2CAD
git -C output/drawing-cad-sources/Ortho2CAD checkout 546efb1facc4066e7904aacd259c9dd140c1e2ba
git clone https://github.com/lllssc/Drawing2CAD output/drawing-cad-sources/Drawing2CAD
git -C output/drawing-cad-sources/Drawing2CAD checkout 073711716abf4a8a9d8eb559acf636dc92aa6b3b
git clone https://github.com/huggingface/cadgenbench output/drawing-cad-sources/cadgenbench
git -C output/drawing-cad-sources/cadgenbench checkout 33304cf771fc5639144b1df9611e347251052cf8
python experiments/collect_drawing_cad_sources.py --date 2026-10-22 --output output/drawing-source-review.json
```

collectorの`--date`は調査日を記録するだけで、Webを過去の状態へ戻さない。
公開メタデータへのHTTP成功は、重みやデータ本体の取得・実行・利用許諾の確認とは別。
将来の401/404や変更も調査結果として記録する。

## 評価と未実施項目

閾値は寸法10⁻⁶ mm、体積/面積10⁻⁵ mm³/mm²、同一カーネルIoU ≥ 1−10⁻⁸、
サンプル再投影残差0.02 mm。固定合成条件の閾値であり、製造公差の推奨値ではない。

28件の追加テストは、正常/保留、第一角法/第三角法、正解の隔離、JSON履歴、
生成コード、実際の再投影、編集対象と古い出力の拒否を検査する。
[検証記録](../results/drawing-to-cad/verification.json)に全テスト結果を残す。
未実施はAI推論/学習、公開データ本体の評価、任意実務図面、OCR、
ネイティブWindows、異なるCADカーネル、GPU性能とAPI費用の比較である。
