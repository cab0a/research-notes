# OCCTを使う理由はあるか：SMLib・SolidCraft・ClassCADを含む基盤選定

調査・実測日：2026-10-19（日本時間）

最新の前提・計画は[STEPを必須にしないB-Rep認識の再調査](brep-native-recognition-strategy.md)を参照。ネイティブ履歴と既存の長孔計測・幾何差分まで対象を広げ、SolidCraft配布CLIの小例も追加確認した。以下は当時のSTEP比較として保持する。

現行版：v1.14.0。調査開始時のコミット：`a91a960dc5ac5687f6ad87557cf393e180524022`

追補：[認識機能の再利用調査](recognition-reuse-audit.md)により、既存認識器の評価をSMLib移植より先行させる。以下のカーネル実測は維持するが、丸穴・長孔の別カーネル実装を必須工程にはしない。

## 結論と、前回の調査から変わった点

**OCCTを使う意味は今もある。ただし、OCCTでなければ実現できないわけではない。既存STEPの検査・認識を当面の中心にして、SMLib系を実データで比較できる状態へ進める。汎用CAD全体の自作は優先順位を下げる。**

前回の[資料・ソース調査](smlib-usd-brep-investigation.md)から、今回は隔離環境で実行するところまで進めた。SMLib系の`SMLib`、NVIDIA公式Pythonパッケージ`usd-brep`、第三者の`smlibpy`、CAD製品`ClassCAD`を同一視しない。

| 判断 | 根拠と意味 |
| --- | --- |
| SMLib系は実際の代替候補になる | `smlibpy 0.3.5`は固定STEP 64件を読み込めた。ブラケットはOCCTと42面・体積がほぼ一致。単なる将来候補から、認識APIを試す候補へ進めてよい |
| OCCTの値を無条件に正解にしない | NURBS化した対照形状で、同じOCCTでも既定積分と精度を指定した積分の体積が違った。カーネル変更より前に計測条件を明確にする必要がある |
| 全面移行の根拠はまだない | 読み込めたことと、穴を正しく判定できたことは別。ねじ部品の経路間差、日本語名の保持、資源上限内で終わらない計測も残った |
| 汎用CADの機能は既存製品を先に検討する | SolidCraftはアプリ全体、ClassCADは履歴・拘束等を含むエンジン。この範囲をこの研究で一から広げ続ける理由は弱くなる |
| この研究は業務の確認に集中する | 穴情報・変更差分・根拠・判定保留・確認レポートを、受領したSTEPに対して再現可能にする。この品質は製品の存在だけでは保証されない |

製品については提供元の資料・固定ソースを確認した。**SolidCraft、SolidCore、ClassCAD自体は実行していない。** 比較表の機能は提供元が示す範囲であり、本研究での動作保証ではない。

## 1. そもそも何を自作し、何を借りるのか

現在の目的は「既存CADを置き換えること」より、「届いたSTEPから業務に必要な情報を取り出し、確認可能な形で返すこと」に置く。

| 層 | 役割 | このリポジトリでの扱い |
| --- | --- | --- |
| ファイルの受付 | Part 21、単位、外部参照、サイズや資源上限の確認 | 現行の受付条件を維持。ライブラリーで開けるかとは分ける |
| STEP変換 | 記述された面・辺・配置を計算可能な形状へ変換 | OCCTのSTEP reader、または別実装を使う |
| 幾何・位相 | 曲面、トリム境界、内外、距離、交差、Boolean | OCCTやSMLib等のカーネルを使う |
| 認識と説明 | 外周の円柱を穴と誤認しない、長孔の条件を確認、根拠と保留を返す | ここは引き続き研究・検証する |
| CADの設計操作 | スケッチ、拘束、履歴、再計算、組立、図面 | 汎用的な拡張は既存CAD/APIを先に検討 |
| 業務への接続 | 一括確認、CSV、帳票、改訂比較、DBへの接続 | 顧客の確認作業に合わせて開発する領域 |

STEP内の製品名や円の記述を列挙するだけなら、形状カーネルを使わない方法もある。しかし、円柱面は外側のボスや曲げにも存在する。貫通穴と断定するには、トリム、開口、隣接面、材料の内外、配置・単位を整合して調べる必要がある。これらを独自に作り直すより、カーネルの照会機能を使う意味がある。

**カーネルは必要な道具になり得るが、OCCTだけがその道具ではない。** また、穴を作るコマンドと、履歴のない受領STEPから穴を認識する処理は別である。

## 2. OCCTに残る具体的な価値と弱点

現在使っている`cadquery-ocp 7.9.3.1.1`について、基盤を継続する理由を「今まで使ったから」だけにはしない。

| OCCTを使う具体的な理由 | 注意する点 |
| --- | --- |
| STEPのroot転送、単位、STEPモデルと転送結果を扱う入口がある | 読込成功だけで完全な変換・属性保持を保証しない |
| 面の解析種別、トリム範囲、位置変換、面・辺・頂点を照会できる | NURBS化された円柱は解析円柱と同じ分岐にならない |
| 公差を指定したソリッドの内外判定がある | 大座標・小形状や境界近傍では、その呼び方と条件の検証が必要 |
| XDE経由で名前・色・組立等を扱う経路がある | 基本のSTEPControl reader/writerとは別の経路。属性別に保持を検証する |
| 既存の認識・保留・再出力の検証資産につながっている | 検証資産は移行の物差しになるが、OCCTの正しさを自動的に証明しない |

根拠：[STEPControl_Reader][occt-step-reader]、[BRepAdaptor_Surface][occt-surface]、[BRepClass3d_SolidClassifier][occt-classifier]、[STEP/XDEの公式ガイド][occt-step-guide]。ガイドには現行7.9系以外の内容もあるため、今回実行したAPIと、資料上の対応範囲は区別する。

配布条件にも差がある。OCCTはLGPL 2.1と追加例外、SMLibのNVIDIA公開コードはApache 2.0、`smlibpy`の独自部分はMIT、SolidCraftの固定版はMITまたはApache 2.0。製品・ホイールに含まれる依存物の条件は別途残る。SMLibの公開によって本リポジトリのライセンスやClassCAD製品の条件が変わるわけではない。[OCCT公式ライセンス][occt-license]、[追加例外][occt-exception]、[前回のライセンス整理](smlib-usd-brep-investigation.md#導入条件とライセンス)

### 今回見つかった、OCCT側の計測の課題

現行の[`signed_volume`と`surface_area_and_centroid`](../src/research_notes/brep_runtime.py)は、`BRepGProp`の既定の積分経路を使っている。今回はそれに加えて、適応Gauss積分と、NURBSの区間分割を有効にしたGauss–Kronrod積分を調べた。積分の相対精度と、形状を判定する長さ公差は別の設定である。[公式API定義][occt-gprop]

| 同じ元STEPをOCCTで計測（mm³） | 現行の既定積分 | Gauss–Kronrod、区間分割あり、`1e-9` |
| --- | ---: | ---: |
| `circle_spline` | 531.432055345 | 531.433629386 |
| `slot_spline` | 499.316239223 | 499.433629386 |
| 公開ブラケット | 7061.155301786 | 7061.155301786 |
| 公開ねじ部品 | 332.276264420 | 336.736286124 |
| u-blox SAM AP203 | 1309.883580907 | 1309.883820559 |

精度を指定した値も万能の真値とは呼ばない。複数の積分方法・精度段階での収束と、既知寸法の対照形状を一緒に確認する必要がある。**「OCCTと数値が違うので相手が間違い」と扱えないことは、この実験で確認できた。** 既存の穴認識結果を変更したという意味でもない。製品側の計測実装・合否条件は今回は変更していない。

## 3. SMLibを動かした結果

実行経路を分けた。

| 経路 | 今回実行したこと | 混同してはいけない点 |
| --- | --- | --- |
| NVIDIA公式`usd-brep 1.0.0` | 単純形状の作成、Boolean、面積・体積 | 前回確認した公式Python I/Oに直接STEP APIは見つかっていない。今回はこの経路でSTEPを読んでいない |
| AWVの`smlibpy 0.3.5` | 単純形状、直接STEP読込、解析面照会、再出力 | NVIDIA公式ラッパーとは別実装。STEP変換・カーネル修正・独自の計測積分を含む |
| OCCT/OCP | 同じ固定入力の読込・計測、再出力、精度を変えた計測 | 比較対象であり、既定計測を真値にはしない |

`smlibpy`の面の種別、円柱の半径・軸のAPIは、認識処理の移植を試す入口になる。ただし、今回移植したのは認識エンジンではない。独自積分は[shapes.py][smpy-shapes]から[measure.cpp][smpy-measure]へ進む経路を確認した。公式`usd-brep`の計測精度と一括りにしない。

### 単純形状6種類

箱、円柱、球、丸穴付き板、直線長孔付き板、両方を含む板を、それぞれのAPIで作った。体積・表面積の期待値は寸法から計算した式を使い、認識結果から逆算していない。

| 経路と計測設定 | 6形状中の最大体積相対誤差 | 最大面積相対誤差 |
| --- | ---: | ---: |
| OCCT、既定積分 | 2.27e-16以下 | 2.68e-16以下 |
| 公式`usd-brep`、`1e-3` | 4.87e-4 | 1.13e-3 |
| 公式`usd-brep`、`1e-9` | 5.19e-9 | 2.86e-4 |
| `smlibpy`、`1e-7` | 6.61e-16以下 | 1.72e-11以下 |
| `smlibpy`、`1e-9` | 4.85e-16以下 | 2.68e-13以下 |

この6形状では、公式版は精度指定を厳しくしても表面積が体積と同程度まで改善するとは限らなかった。全SMLib演算が不正確という主張には広げない。公式の[既知問題][nvidia-known]にも計測上の注意が記録されている。

### 固定STEP 64件の読込

既存の頑健性対照44件、数値条件12件、公開STEP 6件、認証済み板2件を使った。

| 読込経路 | 読込・計測完了 | その経路の形状有効判定 |
| --- | ---: | ---: |
| OCCT直接reader | 64 / 64 | 64 / 64 |
| `smlibpy`、`heal=False` | 64 / 64 | 64 / 64 |
| `smlibpy`、`heal=True` | 64 / 64 | 64 / 64 |

**これは本番の受付条件を通した結果ではない。** 各ネイティブreaderへ直接渡し、ファイルを計算可能な形へ変換できるかを調べたもの。単位・外部参照等の受付契約や、穴の認識結果の一致は評価していない。OCCTの有効判定とSMLib系のmanifold・正体積等の確認も同一条件ではない。

- ブラケット：両経路とも42面。体積はOCCT既定で7061.155301785680、`smlibpy`で7061.155301785560 mm³。円柱支持面は18面あったが、曲げや長孔の端部を含むため、18穴とは数えない。
- `heal`の有無で今回の集計値は同じだった。この標本で修復の優劣は判断できない。
- OCCT既定値との体積相対差が`1e-6`を超えた入力は8件、外接箱の座標差が`1e-4 mm`を超えた入力は4件。これは追加確認用の抽出条件であり、正誤の合否線ではない。上述の積分差も混ざる。
- 公開ねじ部品はOCCTが28面、`smlibpy`が34面。体積も異なり、計測法と変換された形状の差をさらに切り分ける必要がある。面の分割数だけでは破損と断定しない。

### 再出力と属性

6入力を両経路で書き、両経路で読み直す36観測は完了した。一方、精度を変えた追加計測15観測のうち、`smlibpy`で再出力したねじ部品をOCCTで計測する1観測はCPU 30秒の上限で終了した。**読込不能という結果ではなく、その複数計測を上限内で完了できなかったという結果**である。

ブラケットとSAM部品は、再出力後のOCCT既定体積に差があっても、区間分割を使った積分では元STEPに近づいた。「再出力で体積が変わった」と即断するのも危険である。ねじ部品の経路間差は未解決のまま残す。体積一致だけで局所形状やトリム境界の保持を保証することもしない。

日本語名`穴板_日本語`を持つ小さなSTEPでは、OCCT/XDEで名前を保持できた。`smlibpy`では入力時に文字化けし、出力は`?`へ置き換わった。**今回作ったUTF-8文字列を含むファイルの結果**であり、STEPの全ての文字列エンコーディングについての結論ではない。色の数値も記録したが、色空間の違いを正規化していないため、この実験で色の正誤は判定しない。

## 4. SolidCraft：CAD全体を借りる候補

対象はTangency Labsの[SolidCraft][solidcraft]。固定したのは**v0.15.0、`fa691707c224cae580c42201ed3a22d5e4b8c716`**。リリース公開は2026-10-17 15:55:08 UTC。[固定リリース][solidcraft-release]

スケッチ・拘束・履歴を持つパラメトリックCADで、デスクトップ・ブラウザー・CLI・MCPを提供する。Pythonの形状カーネルの差替え部品ではなく、設計操作を含めたアプリとして比較する対象である。[固定README][solidcraft-readme]

| 確認事項 | 基盤選定への意味 |
| --- | --- |
| 固定版のカーネルは`truck`系。独自のkernel境界を持つ | この版を「SMLib搭載CAD」とは呼ばない。[依存定義][solidcraft-kernel] |
| STEP入出力、寸法変更・再構築を扱う | 一般的なモデリング画面や編集操作を本研究で増やす前に、既存アプリで足りるか確認する価値がある |
| 固定版の文書ではSTEPの自由曲面offset・pcurveのみの辺に制限、組立入力はbodyへ平坦化 | 受領STEPや組立属性の扱いを、そのまま置き換えられるとは判断しない。[固定ROADMAP][solidcraft-roadmap] |
| 物理量は細かいテセレーションから計算する、と記載 | 本研究の厳しい数値比較と同じ計測経路とは限らない。同じ「体積」でも条件を揃える必要がある |

固定版の[参照試験文書][solidcraft-oracle]には82/82件、解析式61件・FreeCAD由来21件とある。ただし同じ版のREADMEは75/76件のままで、文書間に更新差があった。82/82は提供元の記録で、本研究で再実行した件数ではない。既定の体積・面積比較は相対`1e-3`等であり、受領STEPの穴認識精度の試験とも異なる。

### SMLib検討とSolidCoreは別に追う

[Issue #331][solidcraft-smlib-issue]にはSMLibの評価・段階導入案がある。そこにある速度比較や工数は提供元の報告・見積もりであり、本研究の実測には使わない。採用案があることと、固定版に搭載済みであることは別である。

さらに、関連する**[SolidCore][solidcore]**も確認した。SMLibのRust移植で、調査時に固定したコミットは`6bb8f514f5fd0afcfa5240afde5792aac6eb4b54`、crate版は0.0.1。固定README自身が、一連の処理を通して使える状態ではなく、primitive・Boolean・filletは未完成と説明する。Python bindingsやOCCT translatorsも移植対象外である。[固定README][solidcore-readme]

本研究でRustへ書き直す理由にはまだならない。独立した検証経路が育つ可能性として追い、実際のSTEP入口・認識API・必要な演算が揃った段階で再評価する。

## 5. ClassCAD：履歴・拘束も含むCADエンジンを借りる候補

**ClassCADはNVIDIA製品ではなく、AWV Informatik AGの製品である。** SMLibを幾何処理に使い、その上にパラメーター、履歴、参照、組立、拘束等を提供する。NVIDIAによるSMLibの公開と、ClassCAD全体の無償OSS化を混同しない。[公式の層構成][classcad-smlib]、[提供元の構成説明][classcad-architecture]

| 製品・公開物 | 位置付け | この研究での判断 |
| --- | --- | --- |
| `smlibpy` | Pythonから低水準の形状処理・STEPを使う第三者ライブラリー | 今回の隔離実測の対象。ClassCADエンジンのキーを使う製品APIとは分ける |
| ClassCAD | ヘッドレスCADエンジン。NativeとWASM | 履歴・組立・拘束を含む業務アプリを受託する場合に、購入する基盤の候補 |
| buerli / Buerligons | SDK / CADアプリ | 画面を持つ業務ツールで利用範囲を別途調査する対象 |
| classcad.ai / `classcad-ai` | エージェント向けスクリプト・レンダラー・MCP等 | 公開クライアントのMITと、動かすエンジンの製品条件を区別する |

`classcad-ai`は既定ブランチ`next`の`23e406652bf70e7bdb156aae1d4ddc4cb9ee75d8`を固定した。確認した`@classcad/script`、`@classcad/mcp`等にはMITライセンスがあるが、ルートの依存には別配布のClassCAD API 21.2.0がある。エージェント連携が公開されているだけで、エンジン自体の使用・再配布が無条件に許可されるとは読まない。[固定依存定義][classcad-ai-package]、[MCPのライセンス][classcad-ai-license]

### ローカル処理と商用配布の条件

提供元の2026-10-13の説明では、Freeは非商用等のWASM利用、Soloは個人商用・STEP出力、Businessは自社Native運用とPython/C#を含む。具体的な金額は公開ページから確認できず、記載しない。プランで技術的に使えることと、顧客へ機能を提供する契約は分けて確認する。[プラン説明][classcad-pricing]

2026-02-01付の利用条件には、有効なClassCADキー、社内商用利用の有償契約、外部へ機能を提供する場合の配布ライセンスが記載されている。キーには期限があり、通常サポートと個別契約の支援も区別される。これは調査時点の製品条件の要約で、料金・権利の確定は個別用途と適用契約による。[利用条件][classcad-license]

NativeはWindows/Linux上の自社環境で動かす構成があり、オフラインキーも申請による提供と説明されている。一方、通常起動時のキー取得や、規約上の診断データ送信の可能性は別に存在する。**形状処理がローカルであることだけを根拠に、外向き通信ゼロ・完全閉域対応済みとは説明しない。** キー更新、診断設定、依存物、AIを併用する場合の送信先まで含めて構成を確かめる必要がある。[Native資料][classcad-native]、[診断情報に関する条件][classcad-license]

今回はアカウント作成・認証・購入・エンジン起動をしていない。ClassCADを不採用と決めたのではなく、現時点の「受領STEPから穴一覧」のために製品依存を増やす必要性より、履歴・組立まで必要な案件での導入効果を重視する。

## 6. 使い分けの判断

次の表は本調査に基づく提案であり、全製品で同じ形状を実行した順位表ではない。

| やりたいこと | 第一候補 | 判断理由・次の確認 |
| --- | --- | --- |
| 受領STEPの穴一覧・差分・確認証拠 | 当面OCCT＋現在の認識処理 | 既存結果と受付契約を使い、計測条件の不備を先に詰める |
| 同じ認識を別カーネルで検証 | `smlibpy`の限定アダプター | STEP読込・解析面APIが使える。穴の真偽・保留・参照の同等性を試す |
| NVIDIAの基盤そのものを評価 | `usd-brep` / SMLib | 公式の演算と第三者の追加機能を分離した小さな再現例に使う |
| 汎用的なCAD画面・履歴編集を使う | SolidCraft等の既存CAD | アプリを自作する前に作業を再現。受領STEP・属性の制限は別途評価 |
| 拘束・組立・図面を持つ専用CADを納品 | ClassCAD等の製品API | 開発を省ける範囲と、商用・配布・閉域の費用条件を案件単位で比較 |
| ブラウザー向けRustカーネル | SolidCoreの進捗を追う | 現時点で本研究の実行基盤にはしない |

OCCTを使い続ける判断は暫定だが、単なる様子見ではない。次の比較で誤認識を減らせる、受領データを多く処理できる、必要な属性を保持できるなら、SMLib系へ切り替える理由になる。逆に、形状生成デモやライセンス名だけで移行を決めない。

## 7. 今後の進め方をどう変えるか

この節の実装順は[認識機能の再利用調査](recognition-reuse-audit.md)で修正した。まず既存認識器が必要な判定を提供できるか評価し、満たす部分は再利用する。以下のSMLib系アダプターは、不足や比較上の必要性が確認された場合の候補とする。

**カーネルの自作や、汎用CADの機能追加を研究の主軸にしない。受領データに対する確認の正しさと、実務の手間が減る範囲を測る。** これが今回の調査からの方針提案である。

| 順番 | 実施内容 | 終了条件と、その先の判断 |
| --- | --- | --- |
| 1 | 計測条件を独立した契約として定義 | 単位、長さ公差、積分精度、局所原点、収束、資源上限を記録。既知寸法のNURBS対照とねじ部品を評価し、未収束は確認へ返す |
| 2 | 認識が必要とする最小APIを切り出す | 面種別・隣接・ループ・材料内外・参照番号・公差の境界を決める。全OCCT APIを抽象化しようとしない |
| 3 | 丸穴・直線長孔だけSMLib系で並行評価 | ブラケットの既存5丸穴・6長孔に加え、ボス・止まり・段付き・開いた切欠き等で誤認識と保留を比較。全穴数の未確定は維持 |
| 4 | 実際に受領するSTEPを用途別に増やす | CAD由来、単位、組立、文字コード、NURBS、例外を分類。公開サンプルの件数を一般精度へ置き換えず、対象業務での自動化率を出す |
| 5 | 一括確認と人のレビューをつなぐ | 受付不可・認識済み・保留・計測未収束を分離し、必要な確認箇所をCSV・比較図・レポートで追えるようにする |
| 6 | 案件で必要な設計編集だけ既存CADと接続 | CAD内部は既存マクロ/API、外部確認は本研究の処理。履歴や組立が必要ならSolidCraft/ClassCAD等で先に作業を試す |

後続リリースの候補として、まず「計測条件と収束の説明」、次に「認識の最小境界と別経路の比較」を置く。これは提案であり、今回v1.15以降を実装・リリースしたものではない。

短期の成果物は「CADを何でも作れる」ではなく、例えば「この受領データ群のうち、条件を満たす穴を何件自動取得し、何件を理由付きで人へ返したか」とする。形状認識の価値をカーネル名から切り離して評価できる。

## 8. 証拠、再現方法、今回の限界

- [実測結果の要約](../results/cad-kernel-choice/summary.json) / [入力別CSV](../results/cad-kernel-choice/intake-matrix.csv)
- [出所・固定コミット・環境・ネイティブバイナリーのハッシュ](../results/cad-kernel-choice/sources.json)
- [実行条件・再現コマンド](../results/cad-kernel-choice/README.md)
- [隔離実測スクリプト](../experiments/run_cad_kernel_probe.py) / [要約・整合性確認](../experiments/summarize_cad_kernel_probe.py)

263タスク観測の内訳は、単純形状18、読込192、再出力36、追加精度15、属性2。追加精度の1件はCPU上限で終了したため、全件成功とはしない。成功という状態も計算処理の完了を示し、正解認識の認定ではない。

Linux/WSL、Python 3.12.14での記録であり、Windows Nativeや複数OSの配布試験ではない。隔離環境以外の依存、現行の認識ルール、既存STEP・正解データ、v1.14の結果は変更していない。

多くの対照形状はOCCTで作成され、公開データも限られる。独立したCATIA/NX/SOLIDWORKS由来の顧客データ群を代表しない。各タスクの保存は1回分で、同時実行・起動・異なる計測処理が混ざるため、処理秒数から製品間の速さの順位をつけない。今回の実験で穴認識の再実装、局所形状一致、PMIの保持、ネイティブCADの設計履歴復元を確認したとは主張しない。

[occt-step-reader]: https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/STEPControl/STEPControl_Reader.hxx
[occt-surface]: https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/BRepAdaptor/BRepAdaptor_Surface.hxx
[occt-classifier]: https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/BRepClass3d/BRepClass3d_SolidClassifier.hxx
[occt-step-guide]: https://occt3d.com/dev/doc/overview/html/occt_user_guides__step.html
[occt-gprop]: https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/src/BRepGProp/BRepGProp.hxx
[occt-license]: https://dev.opencascade.org/resources/licensing
[occt-exception]: https://github.com/Open-Cascade-SAS/OCCT/blob/V7_9_3/OCCT_LGPL_EXCEPTION.txt
[smpy-shapes]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/shapes.py
[smpy-measure]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/cpp/measure.cpp
[nvidia-known]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/KNOWN_ISSUES.md
[solidcraft]: https://github.com/tangency-labs/solidcraft
[solidcraft-release]: https://github.com/tangency-labs/solidcraft/releases/tag/v0.15.0
[solidcraft-readme]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/README.md
[solidcraft-kernel]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/crates/kernel/Cargo.toml
[solidcraft-roadmap]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/ROADMAP.md
[solidcraft-oracle]: https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/docs/oracle.md
[solidcraft-smlib-issue]: https://github.com/tangency-labs/solidcraft/issues/331
[solidcore]: https://github.com/tangency-labs/solidcore
[solidcore-readme]: https://github.com/tangency-labs/solidcore/blob/6bb8f514f5fd0afcfa5240afde5792aac6eb4b54/README.md
[classcad-smlib]: https://classcad.ch/docs/architecture/classcad_and_smlib/
[classcad-architecture]: https://classcad.ch/docs/architecture/
[classcad-native]: https://classcad.ch/docs/native/
[classcad-pricing]: https://awv-informatik.ch/blog/pricing/
[classcad-license]: https://awv-informatik.ch/license/
[classcad-ai-package]: https://github.com/awv-informatik/classcad-ai/blob/23e406652bf70e7bdb156aae1d4ddc4cb9ee75d8/package.json
[classcad-ai-license]: https://github.com/awv-informatik/classcad-ai/blob/23e406652bf70e7bdb156aae1d4ddc4cb9ee75d8/packages/mcp/LICENSE
