# 既存の穴認識を業務項目へ接続する — v1.17.0

## 今回できること

既存のSTEP読込・丸穴/長孔認識を1回実行し、[v1.15の業務定義](cad-workflow-contract.md)の17項目へ接続します。値と一緒に、入力SHA-256、単位、部品数・面数等の観測、実行条件、元の抽出結果の参照先を保存します。

**値が取得できたことと、そのまま業務へ採用できることは別です。** 本版は情報の接続を行い、業務の適用可否・完了・採否は判定しません。必須項目との対応から確認を説明する工程はv1.18、既存帳票への実出力はv1.19の計画です。

今回接続した経路は`research_notes.hole_inventory.analyze_step`です。既存のOCCT経路を使い、新しい認識器・追加の依存ライブラリー・カーネル移行はありません。SMLib/SolidCraft/ClassCADのネイティブ入力は今回未接続で、必要な案件条件に応じて追加を検討します。

## 実行する

リポジトリのルートで実行します。

```bash
python -m pip install -e ".[geometry,test]"
research-workflow-extract fixtures/public-step-corpus/sources/build123d_bracket.step \
  --contract fixtures/cad-workflow-contract/reference-contract.json \
  --part-reference bracket-check \
  --output-dir output/workflow-extraction
```

準備済みWSLでは`output/venv312/bin/research-workflow-extract`、または`output/venv312/bin/python -m research_notes.workflow_extraction`を使えます。標準出力と`workflow-extraction.json`に同じJSONを出力します。

`--part-reference`は利用者が指定する参照名です。元CADの図番を抽出した値ではありません。省いた場合は未提供として保持し、ファイル名から品番を推測しません。

入力は空でない2 MB以下のSTEPバイト列です。既存の検査用読込、丸穴＋長孔、プレビューなしという固定設定を使います。寸法・座標は既存経路のmm出力を維持し、この接続処理で位置合わせ・座標の中心化・形状修復を追加しません。外部のCAD製品の起動や外部サービスへの送信は行いません。

## JSONの読み方

| 項目 | 内容 |
| --- | --- |
| source | 入力のハッシュ、バイト数、表示用ファイル名。formatは受付経路の形式で、読込成功はinventory.statusで確認 |
| route | 呼び出した既存API、版、固定オプション、Python/OS/パッケージ/OCP、選択した実装6ファイルのSHA-256 |
| contract / contract_sha256 | 業務定義の内容と正規化JSONのハッシュ |
| inventory / inventory_sha256 | 既存APIの結果をJSONとして保持したものと、そのハッシュ |
| input_observations | 単位コンテキスト、変換倍率、ルート数、ソリッド数・面数・境界・許容差等。未読込なら不明 |
| summary / features | 業務項目へ接続した値・状態・単位・出所 |
| baseline_binding | 任意の基準記録との部品ID・入力ハッシュによる照合。未指定ならnull |
| timing | 既存抽出APIの呼出時間だけ。人の確認・転記・準備時間ではない |

実装ハッシュは選択した6ファイルの記録で、全依存コードや環境の完全な再現保証ではありません。

各項目には`value`、`availability`、`unit`、`provenance`があります。

| availability | 意味 |
| --- | --- |
| present | 既存の観測結果または明示した利用者入力に値がある。自動採用の許可ではない |
| unknown | 全体数や所属などが不明 |
| not_applicable | 長孔の丸穴径、丸穴の幅・全長・長手方向など、形状種別として非該当 |
| not_provided | 利用者が部品参照を指定していない |

例えば、公開ブラケットの最初の長孔の幅は次のように記録します。

```json
{
  "value": 4.5,
  "availability": "present",
  "unit": "mm",
  "provenance": {
    "paths": ["/inventory/holes/5/width_mm"],
    "operation": "copy"
  }
}
```

参照先は同じJSON内のJSON Pointerです。径・深さ等は元の値をコピーし、開口中心XYZは3項目をベクトルへまとめます。従来の板解析にソリッド番号がない場合は、測定済みのソリッド数が1である場合だけ1を導出し、その根拠を記録します。複数ソリッドで所属が記録されていなければ不明とします。

部品数が2である観測を取得しても、この版では業務定義の「単体ソリッド」という条件へ適合したとは判定しません。`contract_conformance`・`business_completion`・`adoption_decision`は常に`not_evaluated`、`customer_approved`はfalseです。

## 基準測定の記録へ結び付ける

[v1.16の記録機能](cad-workflow-baseline.md)で、抽出＋全件確認のセッションを作成できます。

```bash
research-workflow-baseline init output/extraction-session.json \
  --contract fixtures/cad-workflow-contract/reference-contract.json \
  --cases fixtures/cad-workflow-extraction/manifest.json \
  --method existing_extraction_with_full_review \
  --operator observer-a --tool "research_notes.hole_inventory.analyze_step 1.14.0"

research-workflow-extract fixtures/public-step-corpus/sources/build123d_bracket.step \
  --contract fixtures/cad-workflow-contract/reference-contract.json \
  --baseline-session output/extraction-session.json --case public_bracket \
  --output-dir output/bracket-extraction
```

これは研究用入力の操作例です。記録した業務定義と入力ハッシュを照合し、別部品の取り違えを拒否します。手作業側のセッションを抽出側として使うことも拒否します。**基準記録は変更せず、抽出秒数を人の作業時間や品質確認として自動登録しません。** 実帳票・利用者の測定は引き続き必要です。

## Python API

```python
from pathlib import Path
from research_notes.workflow_contract import read_contract
from research_notes.workflow_extraction import extract_step

contract = read_contract(Path("fixtures/cad-workflow-contract/reference-contract.json"))
source = Path("fixtures/public-step-corpus/sources/build123d_bracket.step")
report = extract_step(source.read_bytes(), contract, file_name=source.name)
print(report["summary"]["recognized_hole_count"]["value"])  # 11
print(report["summary"]["whole_hole_count"]["value"])       # None
print(report["features"][5]["fields"]["width_mm"]["value"]) # 4.5
```

公開ブラケットの11行は丸穴5・長孔6という部分結果です。部品全体の穴数は不明のままで、0行の未解析入力も0穴へ置き換えません。寸法は幾何からの取得値で、公称寸法・加工公差・材質・ねじ指示の推定ではありません。H/S番号と参照面は入力内の参照で、ファイルをまたぐ永続IDではありません。

終了コード0は構造化された接続結果を作成できたことを示し、`inventory.status=rejected`も含みます。CAD読込成功・業務完了とは別です。定義・入力容量・記録との不一致・ファイル処理等の接続エラーは2です。既存の認識条件・穴一覧のJSON/CSVは変更していません。

## 検証の再現

```bash
output/venv312/bin/python experiments/run_workflow_extraction_study.py \
  --output-dir output/workflow-extraction-study --repeats 2
```

[研究ノート](../notes/cad-workflow-extraction.md)・[結果](../results/cad-workflow-extraction/results.json)・[テスト/配布確認](../results/cad-workflow-extraction/verification.json)を参照してください。
