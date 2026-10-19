# NVIDIA SMLib / USD BRep 調査と今後の開発方針

調査日：2026-10-19（日本時間）

本リポジトリの基準：v1.14.0、`3a00aeffdbd4d4f974e281a95d64a64dce1f8287`

調査の段階：公式資料・公開ソース・配布メタデータの確認。インストール、ビルド、形状計算、性能比較は未実施。

追補：その後、[OCCT・SMLib系の隔離実測とSolidCraft・ClassCADを含む基盤選定](cad-platform-selection.md)を実施した。本書は初回の資料調査として残す。以降の実測では`smlibpy`による固定STEP 64件の読込、OCCTの積分条件による差、日本語名の保持上の問題等を記録した。現時点の開発方針は追補を参照する。

## 調査結果からの提案

**SMLibの公開は、今後のCAD基盤選びを見直す十分な理由になる。ただし、今のOCCT基盤をすぐに置き換える根拠はまだない。まず別環境で比較評価する。**

現時点では次の方針を提案する。これは調査に基づく判断であり、採用決定や実測結果ではない。

| 方針 | このリポジトリでの動き方 |
| --- | --- |
| STEPから穴情報を取得する目的は維持 | 穴径・位置・長孔寸法、誤認識の抑制、保留の説明、確認用出力を継続する |
| OCCTを当面の基準にする | 既存の取得値、STEP入出力、v1.14の確認手順を残したまま比較する |
| SMLibの小規模な比較評価を追加 | 単純形状の生成・計測と、既存STEPの変換による情報の保持を別々に評価する |
| 汎用モデリング機能の自作を急がない | Boolean、フィレット、シェルなどは既存カーネルを先に調べ、独自実装の必要性を判断する |
| 価値を業務側へ置く | 「カーネルを呼べる」から、対象データで何を確認でき、何を人に返すかまで作り込む |

公開されたのは形状処理の基盤であり、受け取ったSTEPの穴をすべて数える完成済みの認識エンジンではない。カーネル変更で長孔・止まり穴・段付き穴の認識が自動的に解決するとは判断しない。

## 何が公開されたのか

NVIDIAの公開先は **`NVIDIA-Omniverse/usd-brep`**。USD BRepは、NURBSによるB-Repソリッドモデリングを扱うC++・Pythonライブラリーで、内部にSMLibを含む。[公式リポジトリ][upstream]、[変更履歴][changelog]

| 確認項目 | 一次情報で確認した内容 |
| --- | --- |
| 公開版 | USD BRep 1.0.0。変更履歴の日付は2026-10-08 |
| GitHub Release | [v1.0.0][release]の公開時刻は2026-10-09 02:41:48 UTC。変更履歴の日付とは区別する |
| 固定したソース | `c9c5979f04cea8c38213004d4f04df0dcfb40d05` |
| 構成 | SMLib本体、SM_API、USDとの連携層、pybind11によるPython公開層、例、テスト、GUI関連ツール |
| 確認したAPI群 | プリミティブ、Boolean、押出・回転・スイープ、フィレット、オフセット、ステッチング、修復、形状照会、テセレーション |
| 幾何と位相の照会 | 面・辺・頂点、境界ループ、近傍点、距離、面積・体積、ソリッド状態など |
| GPU | 確認した公式の導入要件にGPU・CUDA必須の記載はない。GPU高速化や既存処理より速いことは未検証 |
| 保守への参加 | 外部コードの貢献は現在受け付けず、Issue・不具合報告を受け付ける方針 |

構成・APIの根拠は[SM_APIの照会定義][queries]、[Python型定義][stubs]、[Python導入資料][python-doc]、[貢献方針][contributing]。関数が公開されていることと、対象データで正しい結果を得られることは分けて扱う。

## 最も重要な点：STEPとUSDと`.brep`は別の形式

この研究の入口はSTEPである。USD対応があるだけで、現在のSTEP処理をそのまま置き換えられるとは限らない。

| 形式・経路 | 公式v1.0.0の公開コードで確認した範囲 |
| --- | --- |
| OpenUSD | BRepの読込・保存。`usd_brep.usd`の公開APIがある |
| SMLib独自形式 | 単体BRepの`.smb`、部品コンテナーの`.smp`の読込など |
| OCCTの`.brep` | OCCT BRepファイルからUSDへの変換、およびUSDのBRep配列からOCCT ASCII `.brep`への出力 |
| STEP `.step` / `.stp` | 調べた公式のPython公開型定義・ファイルI/O・変換ツールでは、直接読み書きする公開APIを確認していない |
| CATIA / NX / SOLIDWORKSのネイティブ形式 | 今回、直接読込・設計履歴の復元を提供する根拠は確認していない |

根拠：[ファイルI/O][file-io]、[SM_APIの独自形式I/O][native-io]、[OCCT→USDツール][occt-import]、[USD→OCCT出力定義][occt-export]。

`OCCT_BREP_IMPORT`というディレクトリー名は、STEPリーダーの提供を意味しない。また、`SmSTEPSurface`はSTEP形式の曲面パラメーターを評価するラッパーであり、STEPファイル全体のリーダーの証拠ではない。[SmSTEPSurfaceの定義][step-surface]

### 別の有力候補：smlibpy

**`awv-informatik/smlibpy`はNVIDIA公式パッケージとは別のプロジェクト**である。調査時のPyPI版は0.3.5。タグ`v0.3.5`のソースを確認した。[配布情報][smlibpy-pypi]、[固定ソース][smlibpy-source]

| 項目 | 確認した事実と注意点 |
| --- | --- |
| STEP入出力 | Pythonの独自リーダー・解釈処理、SMLibの位相構築処理、AP214のライターがある。公式USD BRepにSTEP APIがあるという意味ではない |
| Python・OS | Python 3.10〜3.14向けにWindows、Linux、macOS用wheelが配布されている。導入成功は未確認 |
| カーネル | 公開SMLibを組み込み、一部のカーネルソースを修正したコピーで置換してビルドする |
| 注意する相違 | 公式USD BRepそのものと、修正付きsmlibpyを同じ実装として集計しない |
| 属性保持 | 読込時の単位・配置、出力後の名前・色・文字、アセンブリ構成などを実データで照合する必要がある |
| 成熟度 | 配布メタデータはAlpha。広い機能一覧を、本研究の試験を通過した機能と扱わない |

根拠：[STEPリーダー][smlibpy-reader]、[STEP取込][smlibpy-import]、[STEP出力][smlibpy-writer]、[ビルド定義][smlibpy-cmake]、[修正一覧][smlibpy-patches]。

ソース上、取込には無効形状を修復する経路がある。出力の文字列処理にはASCIIへの置換もある。形状が開けたという理由だけで、元の表現・属性を無変更で保持できたとは判断しない。修復前後と変換で失われる情報を記録する。

`Hole`や`CounterBoreHole`のような**形状を作る機能**と、既存STEPの中からその特徴を**認識する機能**も区別する。高機能なモデリングAPIだけで、受領データの穴一覧が完成するわけではない。

## 現在の実装との関係

本リポジトリは`cadquery-ocp==7.9.3.1.1`を使い、PythonからOCCTの型と演算を直接参照している。[依存定義](../pyproject.toml)

| 層 | 現在の処理 | SMLib採用時に確かめること |
| --- | --- | --- |
| STEPの事前確認 | 独自のPart 21検査、単位・外部参照・読込条件の扱い | 検査と出所の記録は保持できる。別の取込処理を呼んでも、この契約は自動では引き継がれない |
| 形状読込 | `STEPControl_Reader`による転送、単位をmmへ変換 | 直接STEPを読む実装を選ぶか、変換経路を挟むか。変換による面・辺・許容差の変化 |
| 丸穴・長孔の認識 | 解析的な支持面・曲線、開口、内壁、接続、面積、材料状態を照合 | 円筒の径・軸、円弧の角度、面・辺・頂点の許容差、材料内外判定を同じ意味で取得できるか |
| 数値判定 | 材料判定用の内部コピーを部品近傍へ移動 | SMLib側の許容差・座標精度・単位・角度の契約を別途確認する |
| 根拠の参照 | 入力内の面・辺番号、SHA-256、理由コード | 番号が変わる前提で出所を追う。OCPの面番号をSMLibの番号と同一視しない |
| 編集と出力 | 現在のOCP形状、再構成、STEP保存 | 編集対象の対応付け、変更範囲、出力後の形状・属性を再検証する |
| UI・帳票 | 確認した穴の行と、未確定の全体数を区別 | JSON/CSVの意味と保留の説明は共通化しやすい。ただし画面用データ生成の接続は必要 |

根拠：[読込](../src/research_notes/public_step.py)、[丸穴](../src/research_notes/public_hole_inventory.py)、[長孔](../src/research_notes/slot_inventory.py)、[材料判定](../src/research_notes/local_material.py)、[出力](../src/research_notes/step_writer_modes.py)。

したがって、依存パッケージを一つ入れ替える移行にはならない。一方で、穴一覧の出力契約、説明、正解付きサンプルは、カーネルをまたぐ比較の資産として使える。

## 公式に公開されている既知問題

以下はNVIDIAの[KNOWN_ISSUES.md][known-issues]にある問題の要約であり、このリポジトリで再現測定した結果ではない。

| 既知問題 | 本研究への影響 |
| --- | --- |
| 円を含むトリム面の面積・体積などに誤差。既定の`relative_accuracy=1e-3`で面積の相対誤差が約1.4%に達した記録 | 丸穴の検証に関係する。既定値の体積・面積を正解として使わず、精度指定を変えて解析解と比較する |
| フィレット削除が変更せず成功扱いになる | 成功フラグだけで編集完了にしない |
| 修復が失敗しても成功扱いになる場合や、周期面・シームの誤修復 | 修復後の形状・空洞・位相を再確認する。原入力を上書きしない |
| フィレット付近のテセレーションで三角形の向きが反転する場合 | 見た目だけでソリッドの向きや材料状態を判定しない |
| 不整合なUSD BRep配列で読込プロセスがクラッシュし得る | 将来の実行評価では子プロセス、時間・メモリ上限、入力検査を設ける |

精度指定を厳しくする回避策は公式に示されているが、「この値なら本研究の許容差を満たす」とは未確認である。面積・体積の相対精度指定と、現在の局所形状判定の長さ許容差`1e-5 mm`を同じ尺度で比較しない。

smlibpyは一部の不具合への修正を公開している。ただし、その修正結果も提供元の検証記録であり、当方での確認はこれからである。[smlibpyの修正記録][smlibpy-patches]

## 導入条件とライセンス

| 項目 | USD BRep公式配布で確認した内容 |
| --- | --- |
| Python wheel | 1.0.0はCPython 3.12専用。Windows x64、Linux x64・aarch64の3ファイル。macOS用wheelは見当たらない |
| Linuxのwheelタグ | `manylinux_2_34`。既存のWSL Python 3.12は評価候補になるが、実際のロード・同居は未確認 |
| Windowsの実行 | Visual C++ Redistributableが必要と記載 |
| ソースビルド | C++ツールチェーンと、Packmanが取得する依存物を使う。大きなテスト資産はGit LFS |
| OpenUSD | wheelは対応するランタイムを同梱。既存の`pxr`・別のOpenUSDとの同居は確認事項 |
| オフライン運用 | ローカルライブラリーとしての利用は検討可能。導入資材の事前取得と、通信なしの実行は別途検証する |

根拠：[Python導入資料][python-doc]、[固定版PyPIメタデータ][pypi-json]、[README][upstream]。GUIの起動やNVIDIAサービスへの接続を、この研究の必須構成にはしない。

SMLibを含むNVIDIA著作部分の基本ライセンスはApache 2.0。商用の組込みを検討できるが、配布時のライセンス・表示の保持、変更したファイルの通知、該当するNOTICE等の扱いがある。商標利用や製品保証まで付くものではない。[ライセンス本文][apache]

配布物全体を「Apache 2.0だけ」と扱わない。公式wheelのライセンス式にはOpenUSD等の条件も含まれる。対象版の[第三者通知][notices]と[PyPIメタデータ][pypi-json]を、実際に配布する構成ごとに確認する。

OCCTも公開ライセンスで提供されており、公式にはLGPL 2.1＋追加例外と記載されている。今回の比較軸は、単なる無償・有償の差ではなく、配布条件、機能、取込経路、正確さ、保守性である。[OCCT公式ライセンス説明][occt-license]

本リポジトリ自身のPolyForm Noncommercial／商用別契約の方針は、依存候補の公開によって変更されない。第三者のコードと当方の認識ロジック・評価・業務処理の権利を分けて扱う。[本プロジェクトの方針](../LICENSING.md)

## 比較評価では何を独立させるか

```text
試験A：既知の寸法パラメーター
       ├─ OCCTで独立に生成 → 計測
       └─ SMLibで独立に生成 → 計測
       → 形状演算・計測を比べる。解析解も使う。

試験B：同じSTEP → OCCTで読込 → .brep → USD → SMLib
       → 変換後の形状評価を比べる。STEP読込は共通であり、独立な読込検証ではない。

試験C：同じSTEP
       ├─ 現在の検査＋OCCT読込
       └─ 独立した検査用環境＋smlibpyのSTEP読込
       → 読込経路も比べる。両者の認識条件・修復・正解は別途記録する。
```

「二つの実装が一致した」は参考証拠であり、正解の証明ではない。共通の入力生成・変換・認識規則には共通の誤りが残り得る。反対に、面数や面番号が違うだけで形状が違うとも決めない。座標・単位・体積・局所寸法・境界と、許容差内での形状を照合する。

## 次に行う評価案

以下は未実施の提案。v1.15以降の版番号の変更や、製品基盤の移行は、この調査だけでは確定しない。

| 段階 | 内容 | 判断できる状態・記録するもの |
| --- | --- | --- |
| 1. 導入確認 | 既存環境と分離し、公式`usd-brep==1.0.0`を固定して導入。smlibpyは別環境にする | wheelのSHA-256、OS、Python、ロード成功、ローカル実行と依存・通知一覧 |
| 2. 小さな解析解 | 箱、円柱、丸穴付き板、直線状長孔を独立生成。精度指定も変える | 既知の径・位置・長さ、解析的な面積・体積との誤差。実行時間と失敗も保存 |
| 3. 既存STEPの取込比較 | 公開ブラケットと対象外形状、単位・配置の異なる入力を使い、変換経路を明示する | 元のSHA-256、修復の有無、変換前後、属性の保持。現行の丸穴5・長孔6は比較基準であり、未実施のSMLib結果ではない |
| 4. 固定回帰 | v1.14の69入力を再利用。幾何62入力、確定板2入力、拒否5入力を分ける | 誤取得・見逃し・保留・拒否・寸法差を別集計。遠方座標の既存の見逃しも正解から消さない |
| 5. 採用判断 | 改善点と導入・保守負担を用途ごとに評価 | OCCT継続／検証用併用／限定機能で採用／移行保留のいずれかを証拠付きで選ぶ |

入力と候補は子プロセス単位で実行し、クラッシュや時間超過も結果として保存する。許容差・成功条件は実行前に固定し、SMLib側の失敗に合わせて基準を緩めない。許容する違いを変更する場合は、業務上の理由と影響を別に記録する。

**認識の採用条件**は、対象範囲の取得値が正解と合い、対象外を誤って確定せず、不明な全体数を0件にせず、未対応形状と処理失敗を説明できること。性能や便利さが良くても、この条件を外さない。

## これまでの計画への影響

| 予定していた方向 | 調査後の提案 | 理由 |
| --- | --- | --- |
| 複数STEPの一括処理、Excel/CSV、業務システムとの接続 | 継続。カーネルに依存しない出力契約と例外処理を優先 | 受領データの確認・転記という目的は変わらない |
| 実部品で認識できる範囲を広げる | 継続しつつ、SMLibの比較評価を一度挟む | 変換と形状処理の別の実装を調べる価値がある |
| 止まり穴・段付き穴・変更箇所の認識 | データと正解を揃えて進める | カーネル公開だけでは認識条件・対応付けは提供されない |
| 部分形状の一致度・対応付け | 距離・近傍点などの道具を評価し、認識の正解と照合基準は別に設計する | 形状照会APIは使える可能性があるが、部分形状認識や学習済みモデルを提供する証拠ではない |
| フィレット削除・修復・汎用編集を大きく自作 | 既存APIの評価を先にする | 利用可能な演算を重複して実装する投資を抑えられる可能性がある |
| OpenUSD・Omniverse連携 | 必要な用途が出た段階で評価 | 現在の穴一覧・STEP比較の必須条件ではない |
| 顧客へ説明する価値 | 入力の適用可否、取得値の根拠、人の確認、帳票・業務連携へ重点を置く | 公開カーネル・汎用ラッパーとの差を、対象業務で作るという戦略上の判断 |

顧客ニーズや開発費削減を今回実測したわけではない。まず「対象のSTEPで、安全に何を自動化できるか」を測るという、従来の進め方は引き続き必要である。

## 未確認事項と再調査の条件

SMLib経由での穴認識率、OCCTに対する速度差、寸法の正確さ、メモリ、Windows/WSLの実行、既存Python環境との同居、STEPの属性保持は未確認。今回の調査結果を、そのまま採用実績や精度の宣伝に使わない。

公式版やsmlibpyの更新、STEP直接入出力の追加、既知問題の修正、外部貢献方針の変更があれば、このメモの固定版との差を再確認する。Issue数・スター数・第三者ベンチマークだけで採用しない。

参照したソースのURL・SHA-256、版・配布情報と調査範囲は[調査ソースの記録](../results/smlib-investigation/2026-10-19-sources.json)に保存する。上流コードの実行結果や性能ベンチマークの記録ではない。

[upstream]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/README.md
[changelog]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/CHANGELOG.md
[release]: https://github.com/NVIDIA-Omniverse/usd-brep/releases/tag/v1.0.0
[python-doc]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/docs/python.rst
[queries]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SM_API/inc/SmApiQueries.h
[stubs]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SmPyLib/stubs/usd_brep/__init__.pyi
[file-io]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SmPyLib/src/SmPyFileIo.cpp
[native-io]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SM_API/inc/SmApiImportExport.h
[occt-import]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/tools/occt_to_usd/occt_to_usd.cpp
[occt-export]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/OCCT_BREP_EXPORT/inc/OcctExport.h
[step-surface]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/inc/SmSTEPSurface.h
[known-issues]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/KNOWN_ISSUES.md
[contributing]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/CONTRIBUTING.md
[notices]: https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/THIRD_PARTY_NOTICES.md
[apache]: https://www.apache.org/licenses/LICENSE-2.0
[occt-license]: https://occt3d.com/dev/doc/overview/html/occt_public_license.html
[pypi-json]: https://pypi.org/pypi/usd-brep/1.0.0/json
[smlibpy-pypi]: https://pypi.org/project/smlibpy/0.3.5/
[smlibpy-source]: https://github.com/awv-informatik/smlibpy/tree/316514b421285ae5abdfe5ed24936bd24ed9dec1
[smlibpy-reader]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/step_reader.py
[smlibpy-import]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/step_import.py
[smlibpy-writer]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/step.py
[smlibpy-cmake]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/CMakeLists.txt
[smlibpy-patches]: https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/third_party/patches/README.md
