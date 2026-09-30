# STEP Hole Inventory — v1.9.0

## 日本語概要

STEPを1つ読み込み、板全体の穴一覧または局所検証した円形貫通穴の径・開口位置・深さ・軸方向を表示します。v1.9では公開STEP6件を読める検査用経路を穴一覧画面に接続し、ブラケットから5個の円形穴を取得しました。部分確認では全体の穴数は不明とします。英語本文の要約に続いて操作方法と制限を示します。

v1.10で追加した長孔認識は、別の[Python API・専用CLI](../notes/bracket-slot-inventory.md)を使用します。この画面と丸穴CSVへの統合は次段階です。

---

## English Summary

The UI uses inspection intake with supported unit conversion, multiple roots
and solids. Qualified plates retain complete inventories; other parts can
return locally verified circular through holes with unknown whole counts.
The original strict CLI intake remains available without `--public`.
The v1.10 [slot research API/CLI](../notes/bracket-slot-inventory.md) is separate;
the circular-hole screen and CSV described here keep their v1.9 scope.
The [new study](../notes/public-step-hole-inventory.md) records six unchanged
sources; [v1.8](../notes/step-hole-inventory.md) remains historical evidence.

## 起動と操作

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.cad_web
```

`http://127.0.0.1:8767/holes` を開きます。使用中なら `--port 8772` など空きポートを指定します。
準備済みWSL環境では `output/venv312/bin/python` を利用できます。

1. **3穴のサンプルを開く**、またはSTEPを選び **選択したSTEPを開く**。
2. 一覧取得・部分確認・保留・拒否と、全体の穴数が確定しているかを確認。
3. 図をドラッグして回転。H番号を選ぶと対応面と表の行を強調。
4. **判定結果と穴一覧をCSV保存**からダウンロード。

公開例は `fixtures/public-step-corpus/sources/build123d_bracket.step` です。
円形貫通穴5個が表示され、全体の穴数は不明です。底面の長穴は含みません。
H番号はファイル内の表示用で、別ファイルの穴の同一性を示しません。
編集・比較・穴一覧は別データ領域です。同じサーバーのタブ間では各領域を共有します。
STEPを外部へ送信せず、外部参照も取得しません。終了時に状態を破棄します。

## 座標とCSV

| 項目 | 意味 |
| --- | --- |
| diameter_mm | 円筒面の直径（mm） |
| center_x_mm / center_y_mm / entry_z_mm | 表示用の開口中心X/Y/Z（mm） |
| depth_mm | 確認した円筒壁の軸方向の長さ（mm） |
| axis_x / axis_y / axis_z | 選んだ開口から穴内部への単位ベクトル |
| solid_index | 入力内の部品番号。製品名や永続IDではない |
| result_status | complete：全体一覧、partial：部分確認、unresolved：保留、rejected：読込拒否 |
| hole_count | completeのみ数値。それ以外は空欄 |
| recognized_hole_count | 確認した穴の行数。全体数と区別する |
| source_sha256 | 読み込んだバイト列のSHA-256 |

mmへ変換したSTEP座標を維持し、原点への移動・自動位置合わせはしません。
部分確認では2開口中心の辞書順が大きい側を選び、板全体の確定では上面を選びます。
加工方向の推定や、元CADの公称寸法・公差・設計履歴ではありません。

CSVはUTF-8 BOM付きです。先頭summary行に判定と理由、続くhole行に各穴を保存します。
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
長穴・分割円筒・段付き穴・交差穴・ねじは対象外です。円形外周の開口面は段付き穴の段差と
区別せず保留するため、ワッシャーなども対象外です。他部品による穴のふさがりは確認しません。

局所検証の面・辺許容差上限は0.00001 mm、半径・深さがその100倍以下のものは保留します。
板の再構成は従来の長さ許容差・体積差・面積差の条件を維持します。
判定閾値は測定精度保証ではありません。詳細は実験ノートと実測JSONを参照してください。

2 MB超・空入力は要求エラーとして前の一覧を保持します。サイズ内の読込拒否は新入力の
名前・理由・穴数不明に置き換えます。古い画面状態からの要求を拒否します。
ネイティブ処理を同一プロセスで実行し、CPU・メモリの強制上限はありません。

## CLI and Python

```bash
python -m research_notes.hole_inventory fixtures/public-step-corpus/sources/build123d_bracket.step --public --output-dir output/bracket-holes
python -m research_notes.public_hole_benchmark --output-dir output/public-holes --repeats 3
```

The installed alias is `research-hole-list`. Outputs are `holes.csv`,
`inventory.json` and `holes.svg`. Complete results exit 0; partial, unresolved
and rejected results exit 2, after writing outputs. A missing preview has a
placeholder SVG. Without `--public`, the strict plate importer retains its
24-face, single-root, explicit-mm limitations for baseline reproduction.

```python
from pathlib import Path
from research_notes.hole_inventory import analyze_step, inventory_csv
source = Path("fixtures/public-step-corpus/sources/build123d_bracket.step")
result = analyze_step(source.read_bytes(), source.name, inspection=True)
Path("bracket-holes.csv").write_bytes(inventory_csv(result))
print(result["recognized_hole_count"], result["hole_count"])  # 5, None
```

HTTP CSV bytes and CLI output are verified. Browser automation verifies upload,
partial rows and selection. Filesystem creation after the browser Blob download
remains unverified; the UI only reports that a download was initiated.
