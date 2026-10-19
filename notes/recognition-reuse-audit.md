# 認識機能の再利用を先に確認する

確認日：2026-10-19。現行版v1.14.0の実装は変更しない。

最新の調査は[ネイティブB-Repの既存機能と今後の計画](brep-native-recognition-strategy.md)。STEP経由を必須にせず、保存済み履歴の取得・選択した長孔の計測・形状差分も再利用対象に含める。

追補：[公開された認識機能の棚卸し](released-recognition-catalog.md)で、SMLib本体の認識・分類、smlibpyが追加する曲げ・勾配等の機能、配布済みQuiddity 0.3.11の36機能群を整理した。既存smlibpy APIの30タスク観測も追加した。本書の初回確認を引き継ぎ、今後の判断には追補を用いる。

## 問いと結論

ユーザーの問いは「新しい基盤に認識機能が入っているなら、それを作り直す研究をするのではなく、利用した先へ進むべきではないか」である。

**既存の認識器の利用可能性を先に評価する。その結果が出るまで、SMLib上での丸穴・長孔認識の再実装を必須の開発工程にしない。** 前回は形状カーネルの比較に重心があり、「認識器を借りられるか」を独立した採用判断として十分に扱っていなかった。

SMLib公開版で確認した範囲では、受領形状から丸穴・長孔を発見し、穴単位の径・位置・貫通長一覧を返す完成した公開APIは見つかっていない。しかし、**認識機能が一切ないという説明も不正確**である。曲面の解析形状への認識や、第三者ラッパーのフィレット面認識は存在する。

## 何が提供されているか

| 確認対象 | 提供されている機能・調査結果 | 再利用の判断 |
| --- | --- | --- |
| NVIDIA SMLib / USD BRep 1.0.0 | 曲面・位相の照会に加え、C++の`SmBSplineSurface::CopyAndAddAnalytics`は条件を満たすB-splineを解析曲面等として扱う実装を持つ | この曲面認識を一から書く前に評価する。穴としての意味・貫通性を返す処理とは分ける |
| 同SMLibの`SmFeatureExecutive` | 呼び出す側が面・境界を指定したfeatureを除去・再構築する | 名前がFeatureでも、自動的に穴一覧を発見するAPIとは扱わない |
| smlibpy 0.3.5の`Hole`、`CounterBoreHole`等 | 指定寸法の切削用形状を作る関数 | 認識ではない。`parts.py`の実装で確認 |
| 同smlibpyの`fillet_faces` / `faces().fillets()` | 面の接線接続・曲率等を調べてフィレット面を選ぶ | 対応する認識処理を再利用する候補。対象形状での精度は別途評価 |
| 同smlibpyの丸穴・長孔一覧 | Python本体と公開APIを調べた範囲で、完成した自動一覧APIは見つかっていない | この不在だけを理由に自作へ進まず、独立した認識ライブラリーも調べる |
| ClassCAD API 21.2.0 | 公開APIパッケージ内の仕様・型定義に穴自動認識APIは見つかっていない | 非公開エンジンや個別提供機能まで「ない」とは断定しない。採用候補になった場合に提供範囲を確認する |
| SolidCraft v0.15.0 | 固定版のコマンド一覧には穴作成や計測等があるが、受領STEPの穴一覧認識コマンドは確認できない | 全実装を再実行して確認したものではない。既存設計履歴を読めることと、外来STEPの認識を分ける |

NVIDIAの曲面認識は、固定ソースでは平面・円錐（円柱を含む）・球・回転面・押出面等を試す。トーラス認識の分岐は無効化されている。Python公開層からそのまま使えることや、対象のNURBS形状を正しく認識できることは今回未検証であり、全形状に対する認識済み機能とはしない。

一次情報：

- [SMLibの解析曲面認識実装](https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/src/SmBSplineSurface.cpp)
- [SmFeatureExecutive：呼び出す側がfeatureを指定する仕様](https://github.com/NVIDIA-Omniverse/usd-brep/blob/c9c5979f04cea8c38213004d4f04df0dcfb40d05/source/SMLib/inc/SmFeatureExecutive.h)
- [smlibpyの穴作成実装](https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/parts.py)
- [smlibpyのフィレット認識・除去実装](https://github.com/awv-informatik/smlibpy/blob/316514b421285ae5abdfe5ed24936bd24ed9dec1/src/smlibpy/defeature.py)
- [ClassCAD API 21.2.0配布パッケージ](https://awvstatic.com/classcad/download/release/21.2.0/classcad-api-js-21.2.0.tgz)
- [SolidCraft固定版のコマンド一覧](https://github.com/tangency-labs/solidcraft/blob/fa691707c224cae580c42201ed3a22d5e4b8c716/docs/features.md)

## 独立した認識器も候補に入れる

**[Quiddity](https://github.com/pzfreo/quiddity)は、既存STEP/B-Repから工学的な特徴を認識する目的の公開ライブラリーであり、今回の目的に直接近い。** NVIDIAのSMLibやAWVのClassCADとは別プロジェクトである。

確認した固定ソースは`f035e9675c6c823eb23287e0e490c031d010afad`。`pyproject.toml`の版は`0.3.11.dev0`、Alpha、Apache-2.0。内部でbuild123d/OCPを使う。開発ブランチの機能と、配布済みバージョンの機能を同一視しない。[固定パッケージ定義](https://github.com/pzfreo/quiddity/blob/f035e9675c6c823eb23287e0e490c031d010afad/pyproject.toml)

固定版の[対応範囲](https://github.com/pzfreo/quiddity/blob/f035e9675c6c823eb23287e0e490c031d010afad/docs/capabilities.md)には`recognise_holes`と`recognise_slots`があり、穴の同軸円柱群、底の種類、段付き、長孔の形状等を扱うと記載されている。一方で、部分円柱、特定の中断形状、長孔の方向・閉鎖条件等の除外もある。機能名だけで本研究のブラケットを処理できるとは判断しない。

**今回はQuiddityをインストール・実行していない。** 既存検証を代替できたとの結果はまだない。この時点で自作研究がすべて不要になったとも判断しないが、利用評価より先に同じ認識器を別カーネルで作る理由はない。

## 次の工程を修正する

| 順番 | 実施すること | 結果に応じた動き方 |
| --- | --- | --- |
| 1 | 配布版・開発版・API・ライセンスを固定し、既存認識器を隔離評価する | ブラケット、既知寸法の丸穴・長孔、ボス・止まり穴・切欠き等を同じ入力で比較する |
| 2 | 認識の意味と対応範囲を比較する | 取得数だけでなく、位置・径・長さ、貫通/止まり、面の根拠、誤認識、保留、例外を確認する |
| 3 | 要件を満たす認識結果を既存の確認・帳票へつなぐ | 認識器の作り直しを避け、改訂比較、確認レポート、一括処理や業務連携へ進む |
| 4 | 満たさなかった条件だけ研究対象にする | 上流への修正、補助判定、独自拡張、別カーネル比較を不足ごとに選ぶ |

v1.15以降の計画には、まず「既存認識器の利用可能範囲の評価」を先行させる。計測条件の改善は評価に必要な範囲で進める。前回案の「SMLib系による丸穴認識・長孔認識の実装」は、比較で必要性が示された場合の選択肢へ下げる。

調査は公開ヘッダー・Pythonソース・パッケージ内文書と型定義の確認である。検索語に出ない機能や商用の個別機能の不存在を証明するものではない。358取得物と追加確認のURL・ハッシュは[出所記録](../results/recognition-availability/sources.json)に保存した。外部のソース本文・ClassCAD APIパッケージは再配布しない。既存の認識コード・依存・検証結果は変更していない。
