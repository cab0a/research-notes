# 寸法線からのCAD復元: 保存結果

**[report.htmlをローカルブラウザーで開く](report.html)**。
図面、回転できる生成3D、寸法変更後、数値の照合、再投影と保留理由を確認できる。
外部CDN・外部API・追加ダウンロードなし。HTMLだけで表示でき、STEP等は隣のフォルダーから取得する。
開けない場合のローカルHTTPコマンドは[閲覧・再現ガイド](../../docs/drawing-dimension-lines.md)を参照。

| ファイル | 内容 |
|---|---|
| [results.json](results.json) | 20入力×2回。復元対象8/8、理由を含む保留12/12、誤確定0。環境・実装/入力ハッシュと全観測 |
| [summary.csv](summary.csv) | 入力別の期待/観測状態、理由、対照としての合否 |
| [verification.json](verification.json) | テスト、実行コマンド、整合性、ブラウザー確認、未実施項目 |
| 各ケースの`input.svg` / `context.json` | 実際に読んだ図面と人の事前指定 |
| 各ケースの`inference.json` | 寸法線・矢印・補助線・可視数値・円の対応、候補または保留理由 |
| 候補ケースの`candidate.py` / `model.json` / `candidate.step` | 生成して実行した編集用レシピ、既存FeatureModel、STEP |
| `edited.py` / `edited.step` | 明示した寸法変更を実行した結果 |
| `comparison.json` / `preview.json` | 評価用正解と観測の比較、実際のB-RepのHLRと表示用メッシュ。表示メッシュは精度評価に使わない |

8/8は開発用の限定合成入力での結果。任意の実務図面、OCR、未知部品での復元率ではない。
第一角法/第三角法やID変更は同じファミリーの派生で、反復も独立した部品ではない。
同一OCCTのIoU=1.0と別カーネルの独立検証を混同しない。
公差・半径・連鎖等の未対応入力も、無理に値へ変換せず保留として残す。

解釈と次の研究は[研究ノート](../../notes/drawing-dimension-lines.md)、
入力の出所は[fixtures README](../../fixtures/drawing-dimensions/README.md)を参照。
