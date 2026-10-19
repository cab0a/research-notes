# STEPを必須にしないB-Rep認識：SMLib・SolidCraft・ClassCADの再調査

調査日：2026-10-19。製品の現行版はv1.14.0。この文書の版番号は今後の計画案で、実装済みのリリースではない。

**研究目的の更新：** 既存機能と実測の記録は維持し、以後のゴール・版の計画は[中小企業向けCAD周辺業務の自動化](sme-cad-automation-roadmap.md)を優先する。本書の20項目および後続100項目は、必要な不足が分かった際に選ぶ旧候補として扱う。

## 結論と、今回変更する前提

**目的は、B-Repから形状・寸法・関係を取り出すこと。STEPは受け渡し方法の一つとして残し、内部処理の必須形式にはしない。各基盤のオブジェクトやネイティブ文書にアクセスできる場合は、そのまま既存APIを使う。**

再調査すると、利用できる機能は「穴の一括認識APIがあるか」だけでは評価しきれなかった。特にSolidCraftには、選択した長孔の寸法取得、ネイティブ履歴の照会、2形状の差分領域の検出が既にある。ClassCADには、履歴・式・B-Rep要素を参照する公開APIがある。これらを改めて自作する必要はない。

一方、**履歴のない任意のB-Repから、穴・長孔・ポケット等を全て発見して意味と寸法を確定する機能**は、3者に共通する完成APIとしては確認できていない。存在しないという断定ではなく、公開範囲と実行範囲に限定した結果である。既存の選択・計測・認識を接続し、不足する探索、例外処理、対応付けに研究を絞る。

今回の基盤選定では、SMLib系を幾何照会・既存分析の候補、SolidCraftを履歴照会・長孔計測・差分処理の具体的な再利用候補、ClassCADを履歴を使ったCAD連携の候補とする。一つに全面移行する判断はまだ行わない。

## 1. 「認識できる」を4つに分ける

| 層 | 例 | 既存機能で取得できたら省ける処理 |
| --- | --- | --- |
| 保存済み情報の照会 | 平面・円柱の種類、半径、軸、頂点・辺・面 | 幾何表現の読み直し、基本的な形状分類 |
| 履歴・意味情報の照会 | HoleFeatureの径、押出距離、配列数、スケッチの長孔輪郭 | **記録されている情報を形状から推定し直す処理** |
| 履歴のない形状の推定 | 面群をまとめて貫通穴・長孔・ボス等と判定 | 専用の認識器が対応していれば、その認識器を再利用 |
| 形状間の対応・比較 | この穴とあの穴の対応、部分形状の一致、改訂差分 | 既存の参照追跡・距離・差分計算を利用し、不足する意味付けだけ追加 |

履歴の「穴を作った操作」と、現在の形状に残っている穴は同じとは限らない。後の埋め戻し、切断、抑制、パターン、結合等を確認してから、現在の特徴として一覧にする。円柱面の数も穴の数ではない。

また、`.solidcraft`やOFB等の形式を使うこと自体が、他社CADの元履歴を復元するわけではない。CATIA・NX・SOLIDWORKS等の独自ファイルを全て直接読めると確認した調査でもない。外部CADからの受け渡しにSTEP等が必要な場合は、それを入口として使える。

## 2. 固定した対象と確認の深さ

| 対象 | 固定版・出所 | 確認の深さ |
| --- | --- | --- |
| NVIDIA USD BRep / SMLib | 1.0.0、`c9c5979f04cea8c38213004d4f04df0dcfb40d05` | C++認識実装、公式Python公開範囲、前回の隔離実測を再利用 |
| AWV smlibpy | 0.3.5、`316514b421285ae5abdfe5ed24936bd24ed9dec1` | SMLibに追加されたPython分析処理。前回30タスクのうち、ネイティブ生成形状とSTEP由来形状を区別して再解釈 |
| SolidCraft | v0.15.0、`fa691707c224cae580c42201ed3a22d5e4b8c716` | カーネル・文書・IO等271ファイルの取得記録と関係実装の確認。**Linux配布CLIも実行** |
| ClassCAD | 公開APIパッケージ21.2.0、同梱文書・型定義 | OFB、Part/Solid API、SCGを調査。現行の公式ガイドも取得。**エンジン実行は未実施** |

SMLibのNVIDIA公開部分と、第三者のsmlibpy・ClassCADを混同しない。SolidCraftの固定版はtruckと独自処理を使い、SMLibバックエンドではない。SolidCore等の別プロジェクト・将来案は、この固定版の実装済み機能へ数えない。[SMLib公開版][nvidia-release]、[SolidCraftカーネル][sc-kernel]、[ClassCADとSMLibの関係][cc-architecture]

## 3. どこまで既存機能があるか

「未確認」は、公開面に専用APIを発見していない、または今回実行していない状態を示す。非公開実装まで含めた不存在の証明ではない。

| 対象 | SMLib本体／smlibpy | SolidCraft v0.15.0 | ClassCAD公開API |
| --- | --- | --- | --- |
| ネイティブの入口 | メモリ上のBrep/Part、SMLibのネイティブIO、USD BRep統合。ラッパーごとに入口が違う | 再評価後の`Body`、文書`.solidcraft`。保存キャッシュは別扱い | Part/Solidオブジェクト、OFB。IWPの読込もAPIに記載 |
| 曲線・曲面の種類とパラメーター | 種別・半径・軸等を照会。公式Pythonとsmlibpyの公開範囲は違う | `face_surface`で平面・円柱・円錐・球・トーラス、`edge_circle`で円弧情報 | B-Rep要素ID、種類別の位置照会。SCGには平面・円柱・円錐・球・円弧等の情報もある |
| NURBS等から解析形状を判定 | C++に平面・円錐/円柱相当・球・回転面・押出面、曲線の直線/円弧等。**未実測** | 点・法線をサンプリングして解析面を当てはめる既存処理がある。全域の厳密保証ではない | エンジン内部の自動昇格範囲は公開APIから未確認 |
| 位相・内外・形状検査 | 頂点/辺/ループ/面/領域、パラメーター分類、材料領域、関係照会等 | 辺・面・殻、`Body.contains`、validity、面の出所等。全情報をCLIが同じ深さで公開するわけではない | インデックスからB-Rep要素を参照。クライアント側への全ループ・隣接・評価器の公開範囲は要確認 |
| 作成済み履歴と寸法 | カーネルのB-Rep自体から元CADの設計履歴が復元されるわけではない | `document.inspect`、`timeline.inspect`。穴・押出・ねじ・配列等の定義を文書が保持 | Part APIの履歴、`getFeature`、`getExpression`、SCGのクラス/メンバー等 |
| 丸穴 | 円柱面等は照会可能。穴生成ツールはあるが、穴単位の一括認識とは別 | ネイティブHoleFeatureの径・位置・種類を照会可能。**実測済み**。履歴なし全自動一覧は未確認 | フィーチャー参照・式は取得可能。任意B-Repの穴一覧APIは未確認 |
| 直線長孔 | 円柱面・平面・凸凹等の材料はある。Slot生成は認識ではない | **選択した端の円柱面から幅・全長・両端中心を取得する処理がある。実測済み**。スケッチ輪郭の長孔判定もある | 円弧等の参照はある。長孔寸法の専用自動認識APIは未確認 |
| フィレット・曲げ | smlibpyにフィレット面の選択と曲げ分析。C++除去機能とも区別 | 作成履歴は保持。任意形状の加工フィレット/曲げ一覧は未確認 | 作成・更新・履歴のAPI。履歴のない面群からの意味付き一覧は未確認 |
| 勾配・連続性 | smlibpyに方向指定の勾配・アンダーカット・分割線分析 | `inspect.draft`、`inspect.continuity`等。G0/G1/G2のサンプル評価がある | 今回の公開APIで同等の専用分析は未確認 |
| 距離・接触・干渉 | `relationship_to`等 | `inspect.clearance`、`inspect.interference`等。精度/近似経路を区別 | カーネルにSMLibを使うことから、同じAPIを呼べるとまでは推定しない |
| 2形状の幾何差分 | 距離・交差等を利用可能。意味付き改訂一覧は別 | **`inspect.compare`で差の領域・偏差・参照面・着色。小例で実測済み**。メッシュとサンプルに基づく | 既知の参照追跡はある。任意2形状の差分領域APIは未確認 |
| 任意の部分形状の一致度 | 上記の幾何照会は材料になるが、完成した汎用一致度APIは未確認 | 差分処理はあるが、未知の位置・姿勢の局所形状検索とは異なる | 点から既存要素を選ぶAPIはあるが、部分形状同士の自動一致判定とは異なる |

根拠：[SMLib認識関数・実測の棚卸し](released-recognition-catalog.md)、[SolidCraftの曲面判定][sc-surface]・[面の当てはめ][sc-fitting]・[長孔計測][sc-measure]・[位相/内外照会][sc-body]・[連続性][sc-continuity]・[差分][sc-compare]、[ClassCADのPart API][cc-part]・[SCG型定義の配布物][cc-package]。

## 4. SMLib系：既存の幾何判定・分析を呼ぶ

### 使える機能と入口

既にB-Repがあれば、その面と辺を問い合わせればよい。smlibpyの`faces().cylinders()`や各面の半径・軸、辺の凸凹、`faces().fillets()`、`bends()`、`draft_analysis(direction)`、`parting_line(direction)`を再利用できる。これらのためにSTEPへ書き出して再読込する必然性はない。

前回の30タスクのうち、箱・丸穴板・長孔板・フィレット箱・曲げ板の**5形状22タスクはsmlibpy上で直接生成したPart**を入力している。残り8タスクは公開ブラケットとNURBS化した穴板をSTEPから読んだもの。形式に依存しない直接Partの分析例は既にある。今回はこの記録を再利用し、30タスクを新たに実行したとは扱わない。[観測コード](../experiments/run_recognition_builtin_probe.py)、[生の結果](../results/recognition-catalog/builtin-probe.json)

曲げ板では90°・内R2 mm・板厚2 mm・長さ40 mmの1曲げを取得した。一方、長孔板でもフィレット選択は1面を返す。これらを「加工フィレット一覧」「全ての曲げ」へ広げるには、意味・面群・例外の検証が必要になる。K-factor 0.44は入力値である。

### 作り直さずに確認すべき不足

NURBSの解析形状への認識は、既存の`SmBSplineSurface::CopyAndAddAnalytics`等を使う。円柱相当が`SmCone`で返る経路、トーラス自動認識の呼出分岐がコメントアウトされている点、公式Pythonの`Brep.copy()`では自動昇格しない点を引き継ぐ。必要ならC++既存関数への呼出しを検討し、別の曲面フィッティングを先に作らない。[既存実装][smlib-recovery]、[公式Python][smlib-python]

不足するのは、基本照会そのものより、複数の面を一つの穴・段付き穴・長孔等へまとめる処理と、開口・底・貫通性を確認する処理である。既存の意味付き認識器に適合する入力であれば、そちらを優先する。SMLibへ現在の認識器を移植することを必須工程にはしない。

## 5. SolidCraft：長孔計測・履歴・差分は具体的な流用候補

### APIを実際に呼んだ結果

公式v0.15.0のLinux tar.gzのSHA-256をGitHub配布メタデータと照合し、CLIだけを取り出してWSLで実行した。デスクトップ画面・MCP・外部サービスは使っていない。バイナリー等はリポジトリへ同梱していない。[配布版][sc-release]

| 小例 | 呼び出した既存機能 | 実際の結果 | 結果が示さないこと |
| --- | --- | --- | --- |
| 40×30×5 mmの板にφ6 mmの穴を作成し保存・再読込 | `document.inspect`、`timeline.inspect`、`model.faces` | HoleFeatureの径6、位置(10,10,5)、下向き方向、simple定義を取得。内壁は半径約3の**2円柱面** | 2穴ではない。履歴なし形状の穴自動発見ではない |
| 幅6 mm・両端中心距離14 mmの長孔スケッチ | プロファイルの`inspect.measure` | 幅6、中心距離14、全長20 mm | 3Dの貫通性や部品全体の長孔一覧ではない |
| 上記を板へ貫通切削し、文書保存・再読込後に端面を選択 | 面選択の`inspect.measure` | 幅約6、中心距離14、全長20 mm、両端中心(10,15,2.5)/(24,15,2.5) | 自動列挙・貫通長・開口の認定は別。返す中心は今回、板厚の中間位置 |
| 同じ原点に10×8×4 mmと12×8×4 mmの箱を作成 | `inspect.compare` | 最大偏差2 mm、全体体積差64 mm³、New側に1差分領域 | 領域体積は約63.970260 mm³で近似。自動位置合わせ・意味付き寸法差・部分形状検索ではない |

メタ情報2呼出しと6本のスクリプト、**計8回のCLI呼出しが終了コード0**。これは3つの小例の観測であり、8種類の形状認識の成功率ではない。コマンド一覧は392件で、これも認識種類数ではない。[観測JSON](../results/native-brep-recognition/solidcraft-observations.json)、[再現コード](../experiments/run_native_brep_probe.py)

長孔の既存処理`slot_from_faces`は、選択した半円柱と、同半径・平行軸のもう一方の半円柱、両側の平面を使う。部品内の全候補を発見・重複排除する処理とは異なり、長孔の切削と凸の長円形状をこの寸法だけで区別する契約でもない。面の角度範囲等にメッシュの点を使うため、任意の面分割・交差・精度での完全性は未確認。[面選択の入口][sc-selection]、[長孔の条件][sc-measure]

### 曲面の種類も既存処理で求められるが、厳密保証と区別する

`face_surface`は平面・円柱・円錐・球・トーラスを返す。直接の平面型の照会に加え、既存の`surf_of`が点と法線のサンプルに候補面を当てはめて検査する。`edge_circle`も25点で円弧を当てはめて確認する。これらを再実装する前に、対象データ・公差・誤認識を評価する。サンプルに一致したことを、任意曲面の全域での厳密な同一性と説明しない。[型と入口][sc-surface]、[当てはめの条件][sc-fitting]

`inspect.compare`は配置済みの2形状をメッシュ化し、面からの距離をサンプリングし、差の領域を求める。既存の差分検出を再利用できる一方、未知の姿勢の検索、加工形状の名前付け、対応した寸法の差は追加の研究になる。[実装][sc-compare]

### ネイティブB-Repキャッシュを、そのまま正本にしない

SolidCraftの独立したB-Repスキーマには、頂点・辺・面・向き付きループ、線・円弧・スプライン、解析面等がある。保存用`SCBREP03`エンベロープはこれらと履歴・面の出所等を保持する。ただし、提供元は**再評価が終わるまで暫定キャッシュであり、編集の正本ではない**と明示している。

特に手続き的な交線の保存は、1e-4 mmを目標とするサンプル検査付きのフィットを使う。サンプル間を含めた最大誤差の証明ではない。ハッシュが合う、ネイティブB-Repである、という理由だけで精密な認識・編集の根拠へ昇格させない。[ネイティブ形式の仕様][sc-native]、[キャッシュの読込][sc-cache]

今回保存した2文書は`document.json`と`container.json`だけを含み、B-Repキャッシュは含まれていなかった。再読込時に文書から形状を再構築した結果を問い合わせている。**SCBREP03の読戻し精度を今回実測したものではない**。

さらに、ネイティブ板金の一部の穿孔表現は、文書上の意味情報と計測補正として存在し、B-Repに全て切り込まれていない経路がある。文書上の特徴と、実体のB-Rep上の特徴の両方を記録する必要がある。[計測処理][sc-inspect]

## 6. ClassCAD：既存履歴を使う価値と、公開APIの境界

### 再利用できるもの

| 公開機能 | 使い道 | 誤解しない点 |
| --- | --- | --- |
| `common.load/save`のOFB、`common.recalc` | ネイティブ文書・形状を保った読込、保存、再評価の入口 | OFBの保存/読込モードにはグラフィックスだけを使う場合もある。解析用には形状と必要なオブジェクトがあることを確認 |
| Part API、`getFeature`、`getExpression` | 既知のフィーチャー、式・値を取得し、再推定を省く | `getFeature`は**名前から既存フィーチャーを探す**。未知の形状から穴を発見する関数ではない |
| `getBrepGeometryByIndex`、`getBrepGeometryIndex` | ソリッド/フィーチャー内の頂点・線・円弧・NURBS曲線・面を参照 | 要素IDが返ることと、任意の低水準カーネル関数を呼べることは別 |
| `getGeometryIds`、`getGeometryPositions` | 点や種類を与えた既存要素の選択・再取得 | 与えた点に合う要素を探す機能。任意部分形状の類似度や、対称候補の一意性の証明ではない |
| SCGの構造・メンバー・解析面情報 | クラス、式、操作ID、円柱の半径/軸等をクライアントで活用 | 表示メッシュと解析注記を含む。SCG全体を精密B-Repの完全な交換形式とみなさない |
| `part/assembly.calculateMassProperties` | 部品/組立の体積・重心を取得 | 座標系が対象に依存する。今回、精度の実測はしていない |

固定パッケージの[取得記録](../results/recognition-availability/sources.json)、[公式Part API][cc-part]、[Common API][cc-common]を根拠とする。

### 「ClassCADなら必ず履歴付き」とも言えない

公式ガイドは、Part APIが履歴付き、Solid APIが直接ソリッドを操作する方式と区別する。後者のB-Rep参照は自動追跡されず、EntityInjectionを一つの機能として扱う。**2026-10-19取得のガイドには、現時点のEntityInjectionは再計算されず、将来対応するとの記載もある。** APIに`recalc`があることだけで、全経路の再計算・参照追跡が成立するとは判断しない。[PartとSolidの比較][cc-part-solid]

このガイドは固定APIパッケージ21.2.0とは別の時点の資料である。記載の違いや将来追加の関数を、固定パッケージで動作確認した機能へ数えない。

ClassCAD内で元から保持するフィーチャー・スケッチ・配列・式を使う場合は、認識研究を省ける範囲がある。ただし、読み込んだ形状、直接Solid APIで組み立てた形状、元の設計履歴を持つ文書を別々に検証する。

### まだ足りない確認

公開APIで、履歴なしB-Repの穴・長孔・ポケットを一括認識する専用API、全ての隣接/ループをクライアントへ取り出す入口、未知の部分形状の一致度判定を確認できていない。SMLibが内部にあることを理由に、低水準APIが全てそのまま公開されるとは扱わない。

エンジンはキーと利用条件のある製品で、今回は未実行。Native版も用意されているが、実行形態・契約・必要なAPIが揃うと確認できた案件で採用を判断する。公開クライアントのライセンスだけで、エンジンまでNVIDIA公開版と同じ利用条件とみなさない。[実行形態][cc-intro]

## 7. 実装方針：形状を共通形式へ作り直す前に、結果をつなぐ

| 入力の状態 | 最初に使うもの | 追加研究する部分 |
| --- | --- | --- |
| 信頼できる履歴・寸法がある | SolidCraft/ClassCAD等の履歴・式・スケッチAPI | 現在の形状に残っているか、配列・抑制・後続変更、位置/単位/座標系 |
| 履歴はないが、既存分析が対応する | ネイティブB-Repの種別照会、長孔計測、フィレット・曲げ分析等 | 全候補の探索、重複統合、穴/ボスの区別、対応範囲・保留 |
| 既存の意味付き認識器が入力を受け取れる | その認識器の公開API | 寸法の定義、面の根拠、例外、精度、出力との接続 |
| どの既存処理も要件を満たさない | 上流修正・補助判定・別ライブラリーの順で検討 | **確認できた不足だけ**を実装する |

共有するのは、少なくとも特徴の種類・寸法・座標/単位・方向・参照面・出所・判定状態である。出所は「履歴から取得」「幾何から推定」「人が確認」を区別し、原形状の参照は基盤固有のまま保持する。全てのカーネルを模した大きな共通B-Repクラスを先に作る必要はない。

Quiddity 0.3.11には穴・長孔・段構成等の既存認識が収録されるが、**OCP/build123d系の別ライブラリー**である。SMLibのBrepやSolidCraftのBodyをそのまま入力できると確認したものではない。[配布機能の棚卸し](released-recognition-catalog.md#5-別枠配布済みquiddityの認識機能)

従って、前回の「同じSTEPをQuiddityへ入れることから始める」は唯一の先行工程にしない。OCP形状を使う経路では有力な評価候補として残し、ネイティブ入力側では既存APIを先に使う。形式変換が必要な認識器は、変換損失と実装費を含めて採否を決める。

既存OCCT経路も、稼働するSTEP入口・比較用・OCP系の認識器を使う経路として残す価値がある。全入力をOCCTへ寄せることも、SMLibへ移すことも今回の結論にはしない。カーネルの数そのものを増やすより、必要な認識が根拠付きで得られる最小構成を選ぶ。

## 8. v1.15.0からの計画案

長期の見通しは[100項目のロードマップと最初のゴール](brep-recognition-roadmap-100.md)へ拡張した。以下の20項目を引き継ぎ、v1.34相当を「対象を絞った認識・比較・確認・保存」の一区切りとする。100項目全ての完了を、利用開始の条件にはしない。

v1.15〜v1.19を直近の実装候補とする。v1.20以降は20段階先までの見通しであり、**評価済みの既存機能で完了できるものは接続と検証で済ませる**。不足がない認識処理を、版を進めるためだけに再実装しない。ClassCADの実行は必要な実行条件が揃う場合の分岐で、全工程の前提にはしない。

| 版（案） | 到達点 | 使う既存機能／残る研究 | 完了の目安 |
| --- | --- | --- | --- |
| **v1.15.0** | ネイティブB-Repの既存分析を使う入口 | SMLib系のPart、SolidCraft文書/Bodyを直接照会。ClassCADは利用可能APIに限定して接続可否を判断 | STEPを経由しない小例で、面種別・寸法・出所を取得できる |
| **v1.16.0** | 履歴にある形状情報の取得 | `timeline.inspect`、Part/式/スケッチの照会を利用。履歴の有無と現在の残存を区別 | 穴・長孔輪郭・押出/配列の既知情報を、推定扱いにせず一覧化 |
| **v1.17.0** | 既存の長孔・フィレット・曲げ分析の適合評価 | SolidCraft長孔計測、smlibpyの選択・曲げを実データと対照形状へ適用 | 有効/誤検出/未対応と、得られない項目を明示できる |
| **v1.18.0** | 履歴なし形状の認識経路を選定 | 対応する既存認識器を評価。OCP経路ではQuiddityも候補。ネイティブ経路では探索・統合等の不足だけ補う | 穴・長孔で、入力型・寸法・面根拠・保留を満たす経路が決まる |
| **v1.19.0** | 形式に依存しない特徴一覧と確認 | 既存画面/CSV/JSONへ接続。履歴由来・推定・保留を区別 | 同じ種類の特徴を、異なる入口でも出所付きで確認・保存できる |
| v1.20.0 | 解析形状を失った面への対応 | SMLib既存C++認識、SolidCraft既存当てはめを比較。公差・トリムを評価 | NURBS化で失う情報と、回復できる条件が分かる |
| v1.21.0 | 段付き穴・皿穴 | 履歴の種類/寸法、対応する既存認識を利用し、同軸段の対応だけ補助 | 各段の径・深さ・角度と、保留理由を表示 |
| v1.22.0 | ポケット・ボス | 既存認識器と履歴を利用し、凹凸・開閉・面群の境界を検証 | 対象を絞った寸法/位置の一覧。切欠き等との誤認を測れる |
| v1.23.0 | フィレット・面取りの意味付け | 面選択と既知のR/面取り定義を利用。曲げ/長孔端との重複を整理 | 面数と加工特徴数を区別し、半径等を根拠付きで表示 |
| v1.24.0 | 穴・長孔等の配列 | ネイティブ配列履歴、既存の配列認識を利用 | ピッチ・方向・数・欠損候補を区別 |
| v1.25.0 | 板厚・曲げの対象拡大 | 既存曲げ分析と板金意味情報を利用。認識条件を満たす形状に限定 | 板厚・角度・Rと、形状に存在しない文書上の表現を区別 |
| v1.26.0 | 連続性・方向依存の分析 | 既存G0/G1/G2、draft等を利用 | 公差・引抜方向・サンプル条件付きで結果を保存 |
| v1.27.0 | 複合・不完全形状の扱い | 既存の妥当性検査を使い、交差穴・面欠損・ねじ等の未対応を明示 | 無理に確定せず、部分結果と確認箇所を残せる |
| v1.28.0 | 同じ配置での部分形状対応 | 面種別・寸法・隣接・既存参照を利用し、穴群等の局所対応を研究 | 対応候補と未対応部分を返し、対称候補は保留 |
| v1.29.0 | 位置・向きが違う部分形状 | 利用可能な位置合わせ処理を評価し、剛体変換下の対応を検証 | 姿勢の違いと形状の違いを区別 |
| v1.30.0 | 面分割・表現差に耐える対応 | 既存解析形状判定と面群を利用。1対多/多対多の対応を研究 | 同じ形状の面分割差で誤った変更を出しにくくする |
| v1.31.0 | 改訂差分の検出 | SolidCraft等の既存幾何差分を利用評価。認識した局所特徴と結び付ける | 差の領域と参照面を示し、サンプル近似の条件も残す |
| v1.32.0 | 意味を持つ寸法差 | 対応済みの穴・段・長孔等のパラメーターを比較 | 径・位置・深さ等の旧値/新値/差を、曖昧さ付きで表示 |
| v1.33.0 | 複数部品と確認レポート | 既存のローカル確認・帳票処理へ認識結果を接続 | 部品ごとの取得範囲・保留・変更点をまとめて保存 |
| v1.34.0 | 対応範囲の固定と再現検証 | 採用した基盤/認識器の固定版で再評価 | 入力形式/履歴/形状/精度/実行条件ごとの対応表と再現例を公開 |

認識した特徴から編集・再計算する研究は別途判断する。履歴と対応する編集APIがある場合は流用できるが、認識成功だけで元の設計意図や編集可能な履歴が復元されたとはみなさない。

## 9. 今回の限界と証拠

今回追加した実行はSolidCraftの小例のみ。SMLib C++の解析形状認識、ClassCADエンジン、Quiddity認識処理、SCBREP03の精度検証は未実行である。任意データの精度・速度、Windowsネイティブ動作、全フィーチャーの網羅性を保証しない。

本リポジトリの現在の穴認識、保留、過去の数値、依存関係は変更していない。公開ブラケットの既存結果は丸穴5・長孔6を取得するが、全体穴数未確定のまま。今回のSolidCraft小例を、このブラケットでの成功と読み替えない。

- [実験方法・再現手順](../results/native-brep-recognition/README.md)
- [SolidCraftの生の観測](../results/native-brep-recognition/solidcraft-observations.json)
- [固定版・URL・取得ハッシュ・先行証拠の参照](../results/native-brep-recognition/sources.json)
- [検証記録](../results/native-brep-recognition/verification.json)

[nvidia-release]: https://github.com/NVIDIA-Omniverse/usd-brep/releases/tag/v1.0.0
[smlib-recovery]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmBSplineSurface.cpp
[smlib-python]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SmPyLib/stubs/usd_brep/__init__.pyi
[sc-release]: https://github.com/tangency-labs/solidcraft/releases/tag/v0.15.0
[sc-kernel]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/src/lib.rs
[sc-surface]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/src/surface_kind.rs
[sc-fitting]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/src/offset.rs
[sc-body]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/src/body.rs
[sc-continuity]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/src/continuity.rs
[sc-inspect]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/engine/src/cmd/inspect.rs
[sc-measure]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/engine/src/cmd/measure_shape.rs
[sc-selection]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/engine/src/cmd/measure_sel.rs
[sc-compare]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/engine/src/cmd/compare.rs
[sc-native]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/docs/native-brep.md
[sc-cache]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/io/src/design/native_cache.rs
[cc-architecture]: https://classcad.ch/docs/architecture/classcad_and_smlib/
[cc-part]: https://classcad.ch/docs/API/part/
[cc-common]: https://classcad.ch/docs/API/common/
[cc-package]: https://awvstatic.com/classcad/download/release/21.2.0/classcad-api-js-21.2.0.tgz
[cc-part-solid]: https://classcad.ch/docs/api-usage/classcadPartVsSolidApi/
[cc-intro]: https://classcad.ch/docs/
