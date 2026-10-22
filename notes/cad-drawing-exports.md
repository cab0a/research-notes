# 実CAD出力のSVG／DXFから編集可能CADを復元する

実験日: 2026-10-22。基点 `7d01eeaf4d8e12def0295bcd0fe2489ebf5b9bd8`。
版数1.17.0上の独立探索研究。既存のv1.15〜v1.24業務計画は変更しない。
[前回の寸法線研究](drawing-dimension-lines.md)からの続報。

**[結果HTML](../results/cad-drawing-exports/report.html)** で、入力DXFの描画、
FreeCAD出力SVG、復元・編集後STEPの3D、寸法差、保留理由を確認できる。
[閲覧・再現手順](../docs/cad-drawing-exports.md)も参照。

## Research Question

自作の単純なSVGプリミティブで成立した復元処理は、実際のCADエクスポーターが
出力した図面へ接続できるか。図面の寸法不足と、入出力形式の未対応を区別できるか。

「実CAD出力」はFreeCADを実行してTechDrawから出力したことを指す。
今回も自分たちで設計した少数の板形状であり、顧客から受領した図面や
未知部品のホールドアウト評価という意味ではない。

## Source Review / Method Selection

| 一次資料 | 確認したこと | 今回実行したこと |
|---|---|---|
| [FreeCAD 1.1.4公式配布](https://github.com/FreeCAD/FreeCAD/releases/tag/1.1.4) | Linux x86_64 AppImage、公式SHA-256 | ダウンロード・ハッシュ一致・展開、WSL2/offscreenで起動 |
| [TechDrawGui API](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDrawGui_API.md) | ページSVG出力API。資料自体は古く未網羅との注記あり | `exportPageAsSvg`で保存 |
| [TechDraw API](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/TechDraw_API.md) | ページDXF出力API | `writeDXFPage`で保存 |
| [公式の寸法テスト](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/src/Mod/TechDraw/TDTest/DrawViewDimensionTest.py) | DrawViewDimensionとReferences2Dの利用方法 | 自作マクロで外形・穴位置・径の寸法を作成 |
| [ezdxf DIMENSION仕様](https://ezdxf.readthedocs.io/en/stable/dxfentities/dimension.html) | 寸法種別、定義点、表示ブロックの関係 | ezdxf 1.4.4でDXFを読み、数値と形状を関連付け |
| [FreeCAD LICENSE](https://github.com/FreeCAD/FreeCAD/blob/1.1.4/LICENSE) / [ezdxf LICENSE](https://github.com/mozman/ezdxf/blob/v1.4.4/LICENSE) | FreeCADリポジトリのLGPL-2.1本文、ezdxfのMIT | ランタイムや第三者モデルをリポジトリへ再配布していない |

CADモデル・図面・空白テンプレートは今回の自作。
外部モデルや既存の規格図面、埋め込みフォントは含めない。
CADの実行環境は約821 MBのAppImage、展開後約2.8 GBで、無視対象のoutput/に置いた。
新規のPython依存は任意の `drawing` extraにezdxf 1.4.4を追加した。
既存の幾何カーネル、拘束・フィーチャーグラフ、STEP出力、穴再計測、HLRを再利用する。

A: VLM直接生成、B: 図面理解とCAD生成の分離との性能比較は実行していない。
今回もC: 非AIベクター方式であり、OCR、AI API、GPU、学習は使用しない。

## Controlled Experiment

[生成マクロ](../experiments/export_freecad_drawings.FCMacro)をFreeCADで実行した。
直接のPart.makeBox/円柱Booleanで作成した部品に、三面図と実際のTechDraw寸法を付けた。
書き出したSVG/DXFは加工せず[固定入力](../fixtures/cad-drawing-exports/README.md)へ保存した。
FreeCADネイティブ文書と元STEPはauthoring/evaluation側に分けた。

8文書設定×2形式で16ファイル。別途、同じDXFに誤った投影法を指定する対照1入力。
合計17入力を各2回実行した。形状の種類は無孔板と1穴板で、派生を独立部品数と数えない。

| ケース | CAD側で設定した内容 |
|---|---|
| plain | 40×30×8 mm、無孔、第三角法 |
| one | 同上、穴X12/Y10/径6 mm、貫通 |
| decimal | 52.5×37.25×6.5 mm、穴X17.5/Y13.25/径5.5 mm |
| scaled | oneと同じ部品、ページ縮尺1.5 |
| first | oneと同じ部品、第一角法 |
| no_x | 穴X位置の寸法を付けない |
| no_thru | 径の可視文字からTHRUを外す |
| tolerance | 幅寸法へ±0.1 mmを付ける |
| wrong_projection | oneの元DXFを使用し、人の投影法指定だけを意図的に変更 |

数値・縮尺はCAD作図側の設定であり、復元側のcontextへ渡さない。
人が与えるのはmm、形状クラス、投影法、3つのビューレイヤー対応。
座標系は左下基準、板の厚み方向Zという実験規約。
任意図面からのビュー自動認識や一意な形状解釈を主張しない。

復元子プロセスへの引数は図面・context・空の出力先のみ。
CAD生成後、評価側が元のFreeCAD STEPと別保存の設計値を読み込む。
APIと処理順の分離であり、OSのファイルアクセスを隔離するサンドボックスではない。
テストでは復元関数が外部ファイルを読まなくても動くことを確認する。

## 実出力で見つかった差

| 項目 | 実測した表現 | 今回の扱い |
|---|---|---|
| SVG外形 | rectでなくpath、matrix変換、継承スタイル | 前回の平坦SVG文法では未対応 |
| SVGの円 | Cコマンドによるベジェ曲線 | 円へ復元する正規化は未実装 |
| SVG寸法 | 文字・寸法線・三角矢印が別の変換付き要素 | 今回は表示と棚卸しまで。復元候補を生成しない |
| DXF外形 | LINE、同じ位置の重複稜線 | 4辺の矩形を確認し、一致する線だけを重複除去 |
| DXFの円 | CIRCLE | topの円と径寸法の定義点を対応付ける |
| DXF投影の一部 | 外形辺に重なるSPLINE（次数1/2を観測） | 正の重み・有限制御点で凸包が既存の1辺上に収まる場合だけ冗長と判断。一般スプラインを近似して捨てない |
| DXF寸法 | DIMENSIONの種別・定義点・数値と表示BLOCK | 数値と表示BLOCKの文字を照合し、定義点が外形頂点/穴中心に接続するか確認 |
| DXFの可視/隠れ | この出力では形状側に信頼できる線種区別がない | 宣言した板形状クラスの下で内側の全厚縦線を隠れ線相当として照合。可視性の正解とは扱わない |
| DXF文字コード | HEADERはANSI_1252だが±はUTF-8バイト | 今回のエクスポーター用に厳密UTF-8で読む。別エンコーディングは未対応 |
| DXFバージョン | 出力AC1014、ezdxf読込後AC1015 | ライブラリーの読込時変換を記録。入力ファイルは変更しない |

[解釈処理](../src/research_notes/cad_drawing_import.py)はDXFを小さな根拠付き中間表現へ変換し、
前回の幾何・寸法・投影・隠れ線照合へ接続する。
元のファイルSHA-256とDXFハンドルを根拠として保存する。
寸法値が無い場合に画面上の長さから補完しない。
レイヤー名は人のビュー対応にだけ使い、寸法レイヤー名や要素順は意味として利用しない。

SVGを保留したときに、対になるDXFや元CADを使って成功へ置き換えることはない。
DXFの表示にはezdxf、並べて確認する別表示にはFreeCADの元SVGを使う。
両者の線種や寸法の見え方は同じとは限らず、HTMLで切り替えられる。

## Evaluation

[結果JSON](../results/cad-drawing-exports/results.json)、
[CSV](../results/cad-drawing-exports/summary.csv)、
[検証記録](../results/cad-drawing-exports/verification.json)を保存。

| 対象 | 結果 |
|---|---|
| 復元対象DXF 5入力×2回 | 10/10で生成コード実行、有効な単一ソリッド、STEP再読込、寸法/形状/再投影/編集を通過 |
| DXF負例4入力×2回 | 8/8で想定した理由の保留。負例への候補出力0 |
| SVG 8入力×2回 | 16/16で形式未対応。SVG復元の成功は0 |
| 前回の寸法線パーサーを元SVGへ適用 | 全8出力で保留。最初の拒否理由はelement_id |
| 外形のSTEP実測最大誤差 | 2.000000023×10⁻⁷ mm、境界ボックス許容差を含む |
| 穴径・XY・貫通長の最大誤差 | 0 mm |
| 解析式との体積／表面積の最大差 | 1.273292582×10⁻¹¹ mm³ / 9.549694369×10⁻¹² mm² |
| FreeCAD正解STEPとの体積IoU | 全て1.0、材料の対称差0 mm³ |
| 実B-RepのHLR再投影サンプル最大残差 | 7.105427358×10⁻¹⁵ mm |
| 編集後 | 幅+5、厚さ+2、穴の径/Xを各+1 mm。10/10で有効。穴寸法差0、解析体積差最大2.546585165×10⁻¹¹ mm³ |

判定閾値は既存研究を維持: 寸法1e-6 mm、体積/面積差1e-5 mm³/mm²、
IoU≥1−1e-8、再投影サンプル距離≤0.02 mm。
製造上の合格公差ではない。再投影は線集合のサンプル評価で、可視性や連続曲線全域の証明ではない。

正解側はFreeCAD 1.1.4 / OCCT 7.8.1、復元側はcadquery-ocp 7.9.3.1.1。
別のCAD生成経路とOCCT版を用いたが、同じカーネル系列なので独立カーネル比較ではない。
体積IoUの計算自体も復元側のOCCTで行う。

全体テストは **1,401 passed / 357.12秒**。
新規35テストには固定17入力、縮尺/投影法/レイヤー名/要素順、誤った寸法値、
表示文字との不一致、定義点の断絶、内部線の欠落、未対応曲線、単位違い、
非表示レイヤー、不正DXF、数値contextの拒否、保留時の成果物不生成を含む。
ブラウザーでは元SVG/DXF表示、編集後3Dの回転、保留、空の絞り込みを確認した。

### 失敗と未対応

no_x: `hole_position_missing`、no_thru: `hole_extent_ambiguous`、
tolerance: `unsupported_annotation`、wrong_projection: `projection_layout_conflict`。
SVGは一律 `svg_export_graphics_unsupported`。
SVGの拒否を「曖昧さを正しく認識した成功」とは数えない。

初期調査では頂点APIの範囲外参照で作図マクロが停止した。実在する頂点を列挙して修正し、
最終入力8文書は全てFreeCADからの保存完了を確認した。
HTML表示では余白なしのDXF描画で文字端が欠けたため、表示側に余白を追加した。
CADの生成失敗と、表示の問題は別に扱った。

## Interpretation / Limitations

今回成立したのは、**実CADエクスポーターのDXFが保持する寸法の接続情報を再利用する経路**。
DXFの構造情報があるため、すべての文字と矢印を画像から再発見する必要はなかった。
SVGで失われた型情報をどう扱うかは、次の研究課題として残る。

制約: FreeCAD1.1.4の今回の出力、矩形板、分離したZ方向丸穴、
X/Y基準寸法、明示したTHRU、mm、宣言した三面対応。
一般のブロック挿入、輪郭、円弧、回転ビュー、連鎖寸法、共有穴位置、
公差/GD&T、断面・止まり穴、組立、未知ファミリー、他CAD、OCR、VLMは未評価。
CLIは小さな入力に制限しているが、任意のDXF/SVGを安全に扱うサービスを保証するものではない。
測定時間・人の修正時間・自動化率の業務評価も未実施。

## 次の優先順位

| 優先 | 次の実験 | 確かめたいこと |
|---|---|---|
| 1 | FreeCAD SVGの座標変換・path・回転文字を正規化 | 同じ図面のSVGとDXFで寸法と保留理由が一致するか。円近似の誤差も分ける |
| 2 | 別CADの許諾済みSVG/DXFを少数追加 | DIMENSION保持／分解済み表現、文字コード、レイヤー、縮尺の差。出力元ごとの対応表を作る |
| 3 | DXF表示BLOCKと意味情報のさらに厳密な照合 | 表示文字の上書き、線の隠蔽、寸法定義と描画の矛盾を誤採用しないか |
| 4 | 連鎖寸法・共通基準と寸法不足 | 解の不足・矛盾・複数解釈を区別する |
| 5 | 未調整の図面で評価を固定 | 開発用派生と評価データを分け、確認・修正工数も計測する |
| 6 | 同じ入力をPNG化してOCR／VLMと比較 | ベクター情報がない場合の追加価値、誤り、費用を共通基準で測る |

当面の到達点は、少数の許諾済み図面について「根拠付き候補・保留・人の確認事項」を
示し、寸法変更可能なCADとSTEPを保存して追試できること。
この独立研究の結果から、既存の業務ロードマップを自動的に書き換えない。
