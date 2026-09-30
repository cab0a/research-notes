# STEP Hole Inventory — v1.8.0

## 日本語概要

STEPを1つ読み込み、対応範囲内の板について穴の数・径・位置・深さ・方向を一覧にします。画面のH1などを選択すると円筒面を強調し、CSVには測定値と判定状態を保存します。対象は座標軸に平行な長方形の板と、互いに離れたZ方向の円筒貫通穴・平底の止まり穴です。穴0個を確認した場合と、穴数を確定できない場合を区別します。英語本文の要約に続いて操作方法を示します。

---

## English Summary

The single-file inventory qualifies rectangular plates with separated Z-axis
cylindrical through holes or flat-bottom blind holes. Measured surfaces are
used to rebuild the material; symmetric volume and surface-area residuals must
pass before any whole-part count is reported. Unsupported geometry abstains;
intake failures are rejected. Both retain an unknown count rather than zero.
The local browser provides numbered geometry, row selection and CSV export.
The command line writes JSON, CSV and SVG without a browser. Measurements are
geometric evidence, not recovered CAD nominal dimensions, tolerances or history.

## 起動と操作

Python 3.12とgeometry依存を用意します。

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.cad_web
```

`http://127.0.0.1:8767/holes` を開きます。既存サーバーが起動中なら
`--port 8770` など空いているポートを指定してください。
準備済みのWSL環境では `output/venv312/bin/python` を利用できます。

1. **3穴サンプルを開く**で、ファイルを用意せず確認できます。
2. STEPを選び、**STEPを開く**で受け取ったファイルを読み込みます。
3. 判定状態と穴数を確認します。保留・拒否では穴数は不明です。
4. 図をドラッグして回転します。**確認する穴**または表のH番号を選ぶと、該当する円筒面と表の行を強調します。
5. **CSVを保存**で `hole-inventory.csv` を保存します。

H番号は各ファイル内のX/Y/開口Z順による表示用番号です。
別ファイルとの同一性を示しません。違う入力を開くと選択は全体に戻ります。
編集・新旧比較・穴一覧は別のデータ領域で、同じサーバーのタブ間では各領域を共有します。
終了時に状態を破棄します。STEPを外部へ送信したり、外部参照を取得したりしません。

## 座標とCSV

| 項目 | 意味 |
| --- | --- |
| diameter_mm | 円筒面から測った直径。単位mm |
| center_x_mm / center_y_mm | STEP内の座標系における円筒軸のX/Y |
| entry_z_mm | 円筒軸と開口平面の交点のZ。貫通穴では上面を選択 |
| depth_mm | 円筒面が板内で占めるZ方向の長さ |
| axis_x / axis_y / axis_z | 開口から穴の内部へ向かう単位ベクトル。上面は(0,0,-1)、下面は(0,0,1) |
| result_status | complete：一覧取得、unresolved：形状保留、rejected：読込拒否 |
| hole_count | completeのみ数値。保留・拒否では空欄 |
| source_sha256 | 判定した入力バイト列のSHA-256 |

CSVはUTF-8 BOM付きです。先頭データ行は `record_type=summary`、
続いて穴ごとの `record_type=hole` 行を保存します。穴0個でもsummary行を残します。
保留・拒否は理由を保存し、空の穴一覧を「穴なし」と扱いません。
利用者入力のファイル名等の数式先頭記号はエスケープします。
中心X/Yと開口Zは板の左下からの距離ではなく、元STEPの座標です。
板全体が移動している場合もその座標を維持し、原点への移動や自動位置合わせはしません。

## 対応範囲と保留

入力は2 MB以下、単一STEPルート、正常な単体ソリッド・シェル1つ・最大24面です。
単一の明示的なSIミリメートル宣言と単位コンテキストを要求します。
元の長方形の板の6外周平面がそれぞれ1面で、円筒穴が互いにも外周にも接触せず、
Z方向に開いている場合を扱います。止まり穴は平底で、再構成した材料が一致する必要があります。

突起・面分割・段付き穴・交差穴・外周に接する穴・斜めの穴・曲面部品・回転した板は保留します。
円筒面があるという理由だけで穴と数えません。1箇所でも全体を確定できなければ、
全体の穴数と一覧を保留します。段付き穴の一部だけを独立した穴として数える処理はありません。
今回の外部公開STEP6件は全て読込条件で拒否されました。

長さの判定許容差は `0.00001 mm`。材料差の閾値は
`max(0.0000001 mm³, 入力体積 × 0.00000001)`、面積差も同じ数値下限・相対率をmm²で用います。
入力の面・辺・頂点の許容差が長さの判定許容差を超える場合も保留します。
これらは形状判定の閾値で、図面の公差や測定精度の保証ではありません。

2 MB超・空入力は要求エラーとして前の一覧を保持します。
サイズ内の入力が読込拒否になった場合は、その入力名・理由・穴数不明を表示し、
前のファイルの穴を新しい入力の結果として残しません。
古い状態からの読込・CSV保存は拒否し、最新状態を取得します。
形状読込とメッシュ化は既存のローカル研究アプリ同様、ネイティブ処理を同一プロセスで実行し、
CPU・メモリの強制上限はありません。

## CLI and verification

```bash
python -m research_notes.hole_inventory fixtures/hole-inventory/sources/multiple_diameters.step --output-dir output/my-holes
python -m research_notes.hole_inventory_benchmark --output-dir output/hole-check --repeats 3
```

The installed alias is `research-hole-list`. CLI output contains `holes.csv`,
`inventory.json` and `holes.svg`; complete results exit 0, unresolved or rejected
results exit 2. Rejected SVG output is an explicit unknown-count placeholder.
The [fixed study](../notes/step-hole-inventory.md) includes independent recipes,
21 controls and the measured result record. Related local regression tests
passed 110 cases; this is not a new cross-platform verification claim.
Browser download byte/HTTP checks pass, but the in-app browser automation did
not produce a filesystem download event for the Blob CSV save. A normal-browser
filesystem save remains unverified in this record; CLI CSV output is verified.
