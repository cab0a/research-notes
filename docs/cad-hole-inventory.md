# STEP Hole Inventory — v1.13.0

## 日本語概要

STEPを1つ読み込み、丸穴と直線状の貫通長孔を画面・Python API・CLI・CSVでまとめて扱います。公開ブラケットでは丸穴5か所と長孔6か所を確認できます。穴番号・内壁・表の行を選択すると、対応する面と行を強調します。確認した11か所は全穴数の保証ではなく、全体数は不明のままです。該当しない寸法は画面では「—」、CSVでは空欄にします。

v1.13では[数値判定の安定化](../notes/hole-numerical-stability.md)を追加しました。材料判定を部品の近くの座標で行い、既存の100万mm移動モデルを取得できるようにしました。出力座標と判定の許容差は維持します。STEP交換で円弧の角度や許容差などが変わる追加条件には見逃しが残り、人の確認へ返します。v1.12の段差・ポケット内の穴の保留と、面・辺・頂点の許容差の確認も維持します。


---

## English Summary

Public inspection combines the v1.9 circular-hole and v1.10 straight-slot
rules in one typed inventory. Version 1.12 adds conservative validation of
recessed round openings, opening faces and vertices. Version 1.13 translates
only the material classifier's private solid and samples into a per-solid
local frame, retaining output coordinates and all qualification gates. Qualified
plates retain complete inventories; public parts retain unknown whole counts.
See the [integration study](../notes/unified-hole-inventory.md),
[circular-hole evidence](../notes/public-step-hole-inventory.md) and
[slot evidence](../notes/bracket-slot-inventory.md).

## 起動と操作

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.cad_web
```

`http://127.0.0.1:8767/holes` を開きます。使用中なら `--port 8773` など空きポートを指定します。
準備済みWSL環境では `output/venv312/bin/python` を利用できます。

1. **3穴のサンプルを開く**、またはSTEPを選び **選択したSTEPを開く**。
2. 一覧取得・部分確認・保留・拒否と、全体の穴数が確定しているかを確認。
3. 図をドラッグして回転。H/S番号・内壁・表の行を選択すると、対応面と行を強調。番号マーカーはEnter/Spaceでも選択できます。
4. **判定結果と穴一覧をCSV保存**からダウンロード。

公開例は `fixtures/public-step-corpus/sources/build123d_bracket.step` です。
丸穴H1–H5と長孔S1–S6を表示します。長孔は幅4.5 mm・全長7.5 mm・貫通長3 mmです。全体の穴数は不明です。
H/S番号はファイル内の表示用で、別ファイルの穴の同一性を示しません。
編集・比較・穴一覧は別データ領域です。同じサーバーのタブ間では各領域を共有します。
STEPを外部へ送信せず、外部参照も取得しません。終了時に状態を破棄します。サーバー更新後はプロセスを再起動し、ブラウザーも再読込してください。

## 座標とCSV

| 項目 | 意味 |
| --- | --- |
| feature_type | circular_hole：丸穴、straight_slot：直線状長孔 |
| hole_type | through：丸穴貫通、blind：丸穴平底止まり、straight_through_slot：長孔貫通 |
| diameter_mm | 丸穴の径（mm）。長孔では空欄 |
| width_mm / length_mm | 長孔の幅・両端の半円を含む全長（mm）。丸穴では空欄 |
| long_axis_x / long_axis_y / long_axis_z | 長孔の長手方向の単位ベクトル。丸穴では空欄 |
| center_x_mm / center_y_mm / entry_z_mm | 表示用の開口中心X/Y/Z（mm） |
| depth_mm | 確認した穴壁の深さ・貫通長（mm） |
| axis_x / axis_y / axis_z | 選んだ開口から穴内部への単位ベクトル |
| solid_index | 入力内の部品番号。製品名や永続IDではない |
| result_status | complete：全体一覧、partial：部分確認、unresolved：保留、rejected：読込拒否 |
| hole_count | completeのみ数値。それ以外は空欄 |
| recognized_hole_count | 確認した丸穴と長孔の行数の合計。全体数とは区別 |
| recognized_circular_hole_count / recognized_slot_count | 丸穴・長孔の内訳 |
| inventory_version | 一覧形式のバージョン |
| source_sha256 | 読み込んだバイト列のSHA-256 |

表示・CSV・JSONはmmへ変換したSTEP座標を維持し、自動位置合わせはしません。材料判定用の内部コピーだけを、ソリッドごとの原点近傍へ平行移動します。入力形状や出力位置・面番号を変更しません。
部分確認では2開口中心の辞書順が大きい側を選び、板全体の確定では上面を選びます。
長孔の長手方向は半円中心の辞書順で決めます。方向の符号は加工方向の推定ではありません。
画面は小数点以下最大6桁に丸め、CSVには解析値を保持します。元CADの公称寸法・公差・設計履歴ではありません。

CSVはUTF-8 BOM付きです。既存19列の後に新しい9列を追加しました。ブラケットはsummary 1行＋丸穴5行＋長孔6行です。先頭summary行に判定と理由、続くhole行に各穴を保存します。
全体の穴0個を確定した場合は0、部分確認・保留・拒否は穴数を空欄にします。
候補0件を「穴なし」とは扱いません。ファイル名等の数式先頭記号をエスケープします。

## 対応範囲

画面と `--public` は2 MB以下、対応するSI・換算単位をmmへ変換します。
複数の単位コンテキストは実スケールが一致する場合に限ります。
複数部品を読み込み、局所検証は最大512面、プレビューは別途最大256面です。
プレビューだけ失敗しても測定値を保持します。

全体数を確定するのは、座標軸に平行な長方形の板と、互いに離れたZ方向の円筒貫通穴・
平底の止まり穴で、再構成した材料領域と面積が一致する場合です。
局所検証は一周した内向き円筒と両端の平面上の円形内周などを照合します。
長孔は両端が半円の直線状・一定幅の貫通形状に限り、2つの内周と4つの内壁を照合します。
曲がった長孔・分割円筒・段付き穴・交差穴・ねじ・複雑な止まり穴は対象外です。円形外周の開口面は段付き穴の段差と
区別せず保留するため、ワッシャーなども対象外です。他部品による穴のふさがりは確認しません。

局所検証の面・辺・頂点許容差上限は0.00001 mm、半径・深さがその100倍以下のものは保留します。丸穴では開口面の外周にある壁も調べ、周囲より奥にある開口を段差・ポケット内の穴として保留します。
板の再構成は従来の長さ許容差・体積差・面積差の条件を維持します。
判定閾値は測定精度保証ではありません。詳細は実験ノートと実測JSONを参照してください。長孔処理だけ失敗した場合は、確認済みの丸穴を保持し、長孔の保留理由を記録します。

2 MB超・空入力は要求エラーとして前の一覧を保持します。サイズ内の読込拒否は新入力の
名前・理由・穴数不明に置き換えます。古い画面状態からの要求を拒否します。
ネイティブ処理を同一プロセスで実行し、CPU・メモリの強制上限はありません。

v1.13で再評価した既存44形状では、STEP読込後の取得対象32個中32個を取得し、誤取得は0個でした。原点から100万mm離した既存モデルの丸穴・長孔2個も取得します。追加した遠方座標12形状では、作成直後24個中24個、STEP交換後24個中8個を取得しました。残る16個は円弧角度・許容差・開口証拠などの条件で保留します。合成モデルの固定評価であり、一般の製造部品に対する精度保証ではありません。別部品による開口のふさがりは、この一覧の対象外です。

材料判定では、浮動小数点の座標間隔が長さ許容差の1/16（0.000000625 mm）を超えるサンプルを保留します。局所座標への移動で、入力時点で失われた桁は回復できません。この間隔の条件も測定精度の保証ではありません。

## CLI and Python

```bash
python -m research_notes.hole_inventory fixtures/public-step-corpus/sources/build123d_bracket.step --public --output-dir output/bracket-unified
python -m research_notes.unified_hole_benchmark --output-dir output/unified-check --repeats 3
python -m research_notes.hole_robustness --output-dir output/hole-robustness-check --repeats 2
python -m research_notes.hole_numerical_stability --output-dir output/hole-numerical-stability-check --repeats 2
```

The installed alias is `research-hole-list`. Outputs are `holes.csv`,
`inventory.json` and `holes.svg`. Complete results exit 0; partial, unresolved
and rejected results exit 2, after writing outputs. A missing preview has a
placeholder SVG. Without `--public`, the strict plate importer retains its
24-face, single-root, explicit-mm limitations for baseline reproduction.
The bracket command exits 2 even though all 11 verified rows are saved.
Use `--public --circular-only` or Python `include_slots=False` to retain the
earlier circular-only measurement scope (not the old serialized schema/version).
The standalone v1.10 `research-slot-list` API/CLI is also retained.

```python
from pathlib import Path
from research_notes.hole_inventory import analyze_step, inventory_csv
source = Path("fixtures/public-step-corpus/sources/build123d_bracket.step")
result = analyze_step(source.read_bytes(), source.name, inspection=True)
Path("bracket-holes.csv").write_bytes(inventory_csv(result))
print(result["recognized_hole_count"], result["hole_count"])  # 11, None
```

`holes` now contains both feature types. `kind` retains `through`/`blind` for
circles and adds `straight_through_slot`. Diameter is `None` for slots; width,
length and `longitudinal_direction` are `None` for circles. Existing X/Y/entry-Z,
depth, `axis` and `faces` fields support the unified viewer. Slot rows retain
their entry/exit centres, wall/opening evidence and v1.10 dimensions.
`slot_scan` stores diagnostics. `recognized_hole_count` is the total row count,
with `recognized_circular_hole_count` and `recognized_slot_count` subtotals.

API, CLI and HTTP CSV bytes are compared in tests. The browser-saved CSV also
matches the benchmark bytes. See the [verification record](../results/unified-hole-inventory/verification.json).
