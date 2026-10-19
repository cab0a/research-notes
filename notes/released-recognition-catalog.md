# 公開された認識機能の棚卸しと、再利用後に進む研究

調査・実行日：2026-10-19。現行製品版はv1.14.0のまま。

## この調査で先に決めること

**既にある認識機能を調べ、必要な結果を得られるものは利用する。独自実装や別カーネルへの移植は、その調査で不足が分かった部分に限定する。**

今回の主対象はNVIDIAが公開したSMLib / USD BRep 1.0.0。第三者のsmlibpy、ClassCAD、SolidCraft、独立した認識ライブラリーQuiddityを別枠に整理した。「形状処理ができる」「認識処理が存在する」「こちらのSTEPで必要な結果を得られる」は区別する。

今回完了したのは、公開実装・APIの棚卸し、既存smlibpy APIの小さな動作確認、配布済み認識ライブラリーの機能一覧確認と、それに基づく次工程の選定である。新しい認識器や移行版を実装したものではない。

## 対象版と確認の深さ

| 対象 | 固定した版 | 今回の確認 |
| --- | --- | --- |
| NVIDIA SMLib / USD BRep | 1.0.0、`c9c5979f04cea8c38213004d4f04df0dcfb40d05` | C++ヘッダー、関係する実装、公式Python型定義・バインディング |
| AWV smlibpy | 0.3.5、`316514b421285ae5abdfe5ed24936bd24ed9dec1` | Python本体の実装、公開API、隔離環境で既存APIを30回呼び出し |
| ClassCAD | 公開APIパッケージ21.2.0 | 同梱文書・型定義。非公開エンジンは未実行 |
| SolidCraft | v0.15.0、`fa691707c224cae580c42201ed3a22d5e4b8c716` | 固定版のコマンド一覧・構成。アプリ自体は未実行 |
| Quiddity | **配布済み0.3.11** | PyPI wheelのSHA-256、METADATA、同梱capabilities.json、公開export。認識処理は未実行 |

Quiddityは前回の調査では開発ソースのみ確認していた。今回は2026-10-15配布の`quiddity-0.3.11-py3-none-any.whl`を直接調べた。タグ`quiddity-v0.3.11`が指すソースは`f035e9675c6c823eb23287e0e490c031d010afad`で、そちらのpyproject.tomlは`0.3.11.dev0`を記載しているが、**実際のwheelのMETADATAは0.3.11**。版の判断には配布物を用い、Webの最新版だけから収録機能を推定していない。[配布記録][quiddity-pypi]、[固定ソース][quiddity-project]

## 1. SMLib本体に入っている認識・分類

「平面として既に保存されている面を照会すること」と、「NURBSから平面だと認識すること」を分ける。また、次の幾何学的な認識は、穴・ポケットといった加工形状の意味付けとは異なる。

| 認識・分類対象 | 関数・実装の入口 | 入っているもの／出力 | 利用時の条件・今回の確認状態 |
| --- | --- | --- | --- |
| NURBSの平面認識 | `SmPlane::IsNurbSurfacePlane`、`SmBSplineSurface::CopyAndAddAnalytics` | 条件を満たすB-splineを解析平面へ変換 | C++実装を確認。対象STEPでの成功範囲は未実測 |
| NURBSの円柱・円錐認識 | `SmCone::IsNurbSurfaceCone` | 円柱相当を含め、円錐としての解析表現へ変換 | この経路では円柱も`SmCone`。専用Cylinder型が返る前提にしない。未実測 |
| NURBSの球面認識 | `SmSphere::IsNurbSurfaceSphere` | 球面としての解析表現 | C++の有効な分岐を確認。未実測 |
| NURBSの回転面認識 | `SmSurfOfRevolution::IsNurbSurfaceSurfOfRevolution` | 回転面としての表現 | 回転形状を説明するもので、元CADの操作履歴を復元する機能ではない。未実測 |
| NURBSの押出面認識 | `SmSurfOfExtrusion::IsNurbSurfaceSurfOfExtrusion` | 押出面としての表現 | 対象曲面が条件を満たす場合。元スケッチ・寸法拘束の復元ではない。未実測 |
| NURBSのトーラス認識 | 同`CopyAndAddAnalytics`内 | 関連するコードはあるが、呼出分岐がコメントアウト | **この自動認識経路の利用可能機能には数えない**。既存トーラス型の照会とは別 |
| 曲線の直線性 | `SmBSplineCurve::IsLine`、`SmCurve::IsLine` | 公差・サンプル数等の条件に基づく直線性と線の位置・方向 | C++実装を確認。全てのNURBS曲線を厳密に解析形状へ変換する機能とはしない |
| 曲線の円弧性 | `SmCurve::IsArc` | 円弧としての中心・基準軸・半径・角度範囲 | C++に公差・サンプル数を用いた判定実装がある。公式Pythonにこの判定全体を公開した関数は確認していない。未実測 |
| NURBS曲線の円への認識 | `SmCircle::IsNurbCurveCircle` | 条件を満たす曲線から`SmCircle`を作る | 固定実装は有理2次曲線等の条件を確認し、円弧判定を利用する。任意のスプラインの円近似を保証しない。未実測 |
| 楕円表現が円かの判定 | `SmEllipse::IsCircle` | 2方向の半径が許容範囲で等しいか | 既存の楕円表現の判定。任意NURBSから楕円を発見する機能とは別。未実測 |
| 曲線・曲面の平面性 | `Curve.is_planar`、`Surface.is_planar`、C++の`IsOnPlane`等 | 平面上にあるか、指定平面との関係 | 公式Pythonにも平面性の問い合わせがある。穴単位の分類ではない |
| トリム内・辺内の位置分類 | `Face.classify_uv`、`Edge.classify_parameter` | パラメーター位置が面内・境界・外側等のどこか | 公式Pythonに公開。材料の内外や「貫通穴」を単独で決めるものではない |
| 3D点の位相的な所在 | C++の`SmBrep::Point3DClassify` | 点が属するregion・face・edge・vertex等 | C++のAPIを確認。公式Pythonの単純な同名公開関数は確認していない |
| ソリッド同士の位置関係 | `SmApiBrepRelationship`、`Brep.relationship_to` | 分離・接触・交差・包含と距離 | 公式Pythonにも公開。局所的な加工形状の一致・類似度とは別 |
| 材料領域・空洞領域の集計 | `material_census`、`is_manifold_solid` | 領域数・有効性を扱う検査用情報 | 穴の数や径を一覧化する認識器ではない |

曲面認識の中心となる[CopyAndAddAnalytics実装][surface-recovery]、[平面認識][plane-recovery]、[円錐認識][cone-recovery]、[直線性判定][curve-recovery]、[円弧性判定][arc-recovery]、[円への認識][circle-recovery]、[照会API][queries]、[公式Pythonの公開範囲][python-stubs]を確認した。

### C++にある機能が、そのまま公式Pythonにあるわけではない

公式Pythonの`Brep.copy()`は、明示的にNURBSから解析曲面への昇格を行わず、表現を保持する。このコピーを呼ぶだけで上表の認識が動くとは扱わない。今回調べた公開Python型定義には、`CopyAndAddAnalytics`全体に相当する一括関数は見つかっていない。[Pythonコピー仕様][python-stubs]、[バインディング][python-bindings]

必要になった場合は、C++実装への既存の入口が使えるかを先に確認する。その機能を新たなフィッティング実装で置き換える計画にはしない。公差設定、失敗時の扱い、変換前後のトリム・境界の保持を確認することが研究対象になる。

## 2. smlibpyが追加している認識・分析

以下はNVIDIAの公式Pythonそのものではなく、**第三者ラッパーsmlibpyの追加機能**である。

| 認識・分析対象 | 既存API | 得られるもの | 再利用時の限界 |
| --- | --- | --- | --- |
| 面・辺の幾何種別 | `Face.geom_type`、`Edge.geom_type`、`faces().cylinders()`等 | 平面・円柱・円錐・球・トーラス・NURBS、直線・円弧等の種別 | 保存された表現の照会。円柱面数は穴数ではない |
| フィレット面 | `faces().fillets()`、`fillet_faces()` | 接線接続や曲率等から選択した面 | 面集合の選択であり、加工上のフィレット単位・設計履歴の認定ではない |
| 板金の曲げ | `part.bends()` | 曲げ角度・内側半径・板厚・軸方向の長さ・軸 | 同軸の内外円柱面の組と板厚等を使う。一般の曲がった部品を全て認識するわけではない |
| 抜き勾配・アンダーカット | `part.draft_analysis(direction)` | 面ごとの角度範囲とpositive / insufficient / vertical / undercut | 引抜方向・閾値を与える分類。金型全体の成立性やスライド機構を決めるものではない |
| パーティングライン | `part.parting_line(direction)` | 指定方向で表面の向きが切り替わる境界のwire群 | 方向依存の幾何分析。最適な金型分割や加工計画を自動決定しない |
| 辺の凸・凹・滑らかさ | `Edge.convexity`、`edges().convex()/concave()` | convex / concave / smooth等 | 境界状態や公差に依存する局所分類 |
| ソリッド間の関係 | `relationship_to`等 | 分離・接触・交差・包含 | 比較や検査の材料。部品名・形状の意味や一致度を自動推定しない |

根拠：[フィレット選択実装][smpy-defeature]、[曲げ検出実装][smpy-sheetmetal]、[勾配・分割線実装][smpy-draft]、[種別・凸凹の実装][smpy-shapes]、[公開API][smpy-api]。

### 認識と取り違えやすい機能

| 機能名 | 実際の役割 |
| --- | --- |
| `Hole`、`CounterBoreHole`、`CounterSinkHole` | 寸法を与えて切削用形状を作る。既存形状から穴を探す処理ではない |
| `Slot`、`ArcSlot` | 長孔等の輪郭を作る。受領STEPの長孔認識ではない |
| `remove_faces` / `SmFeatureExecutive` | 呼出側が選んだ面・境界を除去し、周囲を再構築する。自動的に全ての穴を発見しない |
| `remove_fillets` | フィレット選択を利用した除去・再構築まで含む。**認識と編集の複合処理**として区別する |
| `unfold` / `flat_pattern` | 条件を満たす曲げを使って展開する。元の加工条件やK-factorをSTEPから推定するわけではない |
| MCP / 自然言語操作 | 既存関数をエージェントから呼ぶ入口。新たな形状認識方式が内蔵されている証拠にはしない |

## 3. 丸穴・長孔・加工形状の完成認識器は入っているか

NVIDIA公開版、smlibpy、ClassCAD公開API、SolidCraft固定版コマンドで確認した範囲では、次の**意味を持つ一覧認識API**は見つかっていない。

| 欲しい結果 | SMLib系で確認できた関連機能 | 未確認の部分 |
| --- | --- | --- |
| 丸穴・貫通/止まり・径・位置・深さ | 円柱面、境界、距離、材料領域等の照会 | 穴単位への統合、開口・底・貫通性の判定と一覧 |
| 長孔・幅・全長・方向・貫通長 | 円柱面・平面・凸凹・接続の照会 | 一つの長孔としての統合と寸法一覧 |
| 段付き穴・皿穴・ねじ穴 | 対応する形状を生成する機能、円錐等の照会 | 受領形状からの種類・段構成・ねじ仕様の自動認識 |
| ポケット・ボス・リブ・面取り・穴パターン | 面の選択・生成・除去・計測 | 加工形状としての一括認識結果 |
| 部分形状の一致度・変更箇所の意味付け | 距離・交差・位置関係・曲面の照会 | 任意の部分形状の対応付けや意味付きの差分判定 |

これは公開された範囲での調査結果である。ClassCADの非公開実装・個別提供機能、SMLibを使った別製品に存在しないと証明したものではない。[公開面の追加調査](recognition-reuse-audit.md)の出所記録も引き継ぐ。

## 4. 既存APIを実際に呼んだ結果

新しい認識器を作らず、既存smlibpy APIをLinux/WSLの隔離環境で呼んだ。7入力で面種別・凸凹、フィレット、曲げ、勾配を確認し、2入力でパーティングラインも確認した。**30タスクとも処理は完了したが、認識精度100%という意味ではない。**

| 入力 | 円柱面の数 | フィレット選択の面数 | 曲げ検出数 | 読み取り方 |
| --- | ---: | ---: | ---: | --- |
| 箱 | 0 | 0 | 0 | 対照としての観測 |
| 丸穴付き板 | 1 | 0 | 0 | 円周の辺は2本。2穴ではない |
| 直線長孔付き板 | 3 | 1 | 0 | Boolean後の面分割がある。円柱面・フィレット面を長孔の数に置き換えない |
| 四隅をR2で丸めた箱 | 4 | 4 | 0 | 作成した4つの丸み面を選択できた |
| 90°に曲げた板 | 2 | 2 | 1 | 角度90°、内側半径2 mm、板厚2 mm、長さ40 mmを取得 |
| 公開ブラケット | 18 | 13 | 0 | 13面を13個の加工フィレットと断定しない。曲げ0も、幾何的に曲がっていないことの証明ではない |
| NURBS化した丸穴付き板 | 0 | 0 | 0 | 9面ともbspline。今回の読込・選択では解析円柱に自動変換されなかった |

長孔付き板には設計上のフィレット操作を加えていないが、既存フィレット選択は1面を返した。接線接続した曲面を拾う選択処理と、加工形状としての分類を区別する必要がある。曲げ板でも曲げ面とフィレット選択が重なり得るため、各APIの件数を足して総特徴数にしない。

曲げAPIのK-factorは既定の**入力値0.44**で、材料・加工条件を推定したものではない。ブラケットでは曲げ検出の必要条件である内外の円柱面の組を確認できておらず、取得0件を欠陥や全体の曲げ数へ読み替えない。

勾配は+Z・最小角度1°を指定した。箱でも底面はundercut、上面はpositive、側面はverticalに分類される。この一方向の分類だけで「金型で作れない」と判断しない。パーティングラインのwireは箱で1本、丸穴付き板で2本だったが、wire数は穴数ではない。

これは対象を絞った呼出確認であり、精度・再現性・製造要件の適合を網羅する試験ではない。[生の観測結果](../results/recognition-catalog/builtin-probe.json)、[入力別CSV](../results/recognition-catalog/builtin-matrix.csv)

## 5. 別枠：配布済みQuiddityの認識機能

QuiddityはSMLibに付属する機能ではない。**既存B-Repから意味のある形状情報を認識するための別ライブラリー**で、内部ではbuild123d/OCPを使う。認識機能を再利用する目的なら、こちらを直接評価する理由がある。

0.3.11のwheel内の公開契約には、次の**36機能群**が収録されていた。APIが同梱されていることを確認したもので、こちらのデータで動作・精度を保証した件数ではない。

| 分類 | 同梱されている機能群のID |
| --- | --- |
| 穴・穴配列（4） | `holes`、`countersinks`、`double-d-bores`、`hole-patterns` |
| 長孔・長孔配列（4） | `slots`、`oriented-slots`、`slot-patterns`、`oriented-slot-patterns` |
| 凹部・空洞（2） | `section-recesses`、`interior-voids` |
| ボス・パッド・リブ（5） | `bosses`、`polygonal-bosses`、`rectangular-pads`、`gusset-ribs`、`gusset-rib-patterns` |
| 段差・面レベル（8） | `angled-steps`、`circular-blind-steps`、`face-levels`、`oblique-through-steps`、`paired-ramp-steps`、`risers`、`through-steps`、`turned-steps` |
| 丸み・面取り（4） | `blends`、`fillets`、`chamfers`、`oriented-chamfers` |
| 溝・平取り（2） | `grooves`、`flats` |
| 素材・薄肉・板金（4） | `plates`、`polygonal-stock`、`thin-wall-bodies`、`sheet-metal-bodies` |
| 自由曲面・反復形状（3） | `freeform-surfaces`、`circular-face-patterns`、`repeating-radial-profiles` |

36には、加工形状だけでなく、素材情報・面の情報・認識済みの特徴から求めるパターンも含まれる。「36種類の加工を任意のSTEPから完全認識する」とは説明しない。

今回の目的に特に近い出力は以下。

| API | 配布物で確認した出力項目の例 | 次に確認する条件 |
| --- | --- | --- |
| `recognise_holes` | `HoleRecord`のdiameter / location / axis / depth / bottom / cbore / csink等 | 深さ・位置の基準、貫通性、段の意味、面分割、交差穴、保留との対応 |
| `recognise_slots` | `Slot`のwidth / length / long_axis / end_radius / corner_radius / 深さ方向の範囲等 | 全長の定義、半円端、方向制約、貫通、開いた切欠きや橋の除外 |
| `recognise_countersinks` | major_diameter / drill_diameter / included_angle / depth / location / axis | 穴との関連付け、外側円錐との区別 |
| `recognise_hole_patterns` | 円周・直線・矩形・格子状の配列 | 入力が既に認識した穴であること、欠損・重複・曖昧さ |

**Quiddityの認識処理は今回実行していない。** wheelをZIPとして読み、同梱契約と公開exportを照合した。[収録一覧とハッシュ](../results/recognition-catalog/quiddity-0.3.11-inventory.json)、[提供元の対応範囲][quiddity-capabilities]

Apache-2.0、Python 3.11以上3.15未満、build123d・NumPy・SciPyへの依存を配布物で確認した。各形状の制限と依存条件は別途残り、本リポジトリのライセンスを変更するものではない。認識結果からSTEPを編集・再出力する処理まで、自動で提供されるとは扱わない。

## 6. 調査結果から選ぶ次の工程

**次に進むのは、配布済み認識器が本研究の要求をどこまで満たすかの利用評価である。SMLibへの移植から始めない。**

| 順番 | 対象と実施内容 | 判断と、その先 |
| --- | --- | --- |
| 1 | Quiddity 0.3.11を隔離し、穴・長孔の既存APIを同じSTEPで実行する | ブラケット、既知寸法、ボス・止まり穴・切欠き・面分割等について、数・寸法・意味・面の根拠を比較する |
| 2 | 受付・座標・単位・出力の定義・例外の扱いを確認する | 既存の「保留」を失わず利用できるか判断。単純な件数一致や、表面積一致だけで採用しない |
| 3 | 条件を満たす認識結果を既存の確認画面・帳票・改訂比較へ接続する | 認識器の作り直しを省き、複数STEP処理・業務への出力・確認時間の短縮へ進む |
| 条件付き | NURBSに必要な認識が不足した場合、SMLib既存の解析曲面認識を評価する | まず既存C++機能への入口・公差・トリム保持を確認。不足だけを補う |
| 別用途 | 板金や金型分析の具体的な相談がある場合、smlibpyのbends / draft_analysis等を利用評価する | 形状と条件を絞り、既存機能の結果を確認・帳票へ使う。現行の穴業務の必須工程にはしない |

採用できた場合に独自研究として残すのは、対象データでの不足、曖昧な対応、人へ返す説明、改訂差分や業務連携である。採用できない条件が分かった場合も、直ちに全面自作へ戻さず、上流修正・補助判定・代替品を不足ごとに選ぶ。

従来のv1.15以降の長期案は、この利用評価で範囲が決まってから組み直す。今回の棚卸しをもってv1.15以降の製品機能が完成した、あるいはQuiddity採用が決まったとはしない。

## 証拠と再現方法

- [方法・再現コマンド](../results/recognition-catalog/README.md)
- [認識APIの動作確認](../experiments/run_recognition_builtin_probe.py)
- [配布物の読取スクリプト](../experiments/inspect_recognition_distribution.py)
- [出所・固定版・実装・配布物のハッシュ](../results/recognition-catalog/sources.json)
- [整合性・対照条件の確認](../results/recognition-catalog/verification.json)

未確認という判定は、公開API・固定ソースで確認できなかったという意味に限定する。商用の非公開機能や将来版の不存在を断定しない。今回、ClassCAD・SolidCraft・Quiddityの形状認識や、SMLib C++の解析曲面昇格を実行してはいない。外部のソース本文・wheel・APIパッケージはリポジトリへ再配布しない。

[surface-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmBSplineSurface.cpp
[plane-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmPlane.cpp
[cone-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmCone.cpp
[curve-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmBSplineCurve.cpp
[arc-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmCurve.cpp
[circle-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmCircle.cpp
[queries]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SM_API/inc/SmApiQueries.h
[python-stubs]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SmPyLib/stubs/usd_brep/__init__.pyi
[python-bindings]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SmPyLib/src/SmPyBorrowedGeometry.cpp
[smpy-defeature]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/defeature.py
[smpy-sheetmetal]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/sheetmetal.py
[smpy-draft]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/draft.py
[smpy-shapes]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/shapes.py
[smpy-api]: https://smlibpy.classcad.ch/docs/api/
[quiddity-pypi]: https://pypi.org/project/quiddity/0.3.11/
[quiddity-project]: https://github.com/pzfreo/quiddity/blob/f035e9675c6c823eb23287e0e490c031d010afad/pyproject.toml
[quiddity-capabilities]: https://github.com/pzfreo/quiddity/blob/f035e9675c6c823eb23287e0e490c031d010afad/docs/capabilities.md
