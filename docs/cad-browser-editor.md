# CAD Browser Editor — v1.5.0

## 日本語概要

ローカルのブラウザ画面から、STEP読込、再構成候補の確認・採用、寸法入力、再計算、変更前後の比較、STEP保存を行えます。穴付き板のサンプルは画面のボタンで生成して読み込めます。別途サンプルファイルを用意する必要はありません。対応範囲と検証方法は英語本文に示します。

v1.5.0の[新旧STEP比較](cad-revision-comparison.md)画面では、独立した2ファイルについて、穴付き板の変更候補・寸法差を確認し、HTMLレポートへ保存できます。以下はv1.1.0で追加した寸法編集機能のガイドです。

---

## English Summary

Version 1.1 adds a local single-workspace HTTP adapter and a Japanese browser
editor over the frozen `CadWorkspace` API. A generated hole plate can be loaded,
explicitly selected, dimension-edited, recomputed, compared and downloaded.
The Python API version remains 1.0.0. No new geometry family or assembly editor
is claimed by this release. The Japanese operation guide follows; implementation
boundaries and verification are documented below.

## 操作ガイド

### 起動

Python 3.12とgeometry依存を用意したリポジトリで実行します。

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.cad_web
```

インストール後は `research-cad-web` でも起動できます。表示された
`http://127.0.0.1:8767` をブラウザで開きます。
`--open-browser` を付けるとブラウザも開きます。
ポートが使用中なら `--port 8768` などを指定します。終了はターミナルで `Ctrl+C`。

準備済みのWSL環境では、WSLターミナルでリポジトリへ移動して起動できます。

```bash
output/venv312/bin/python -m research_notes.cad_web
```

### 穴半径を変更する

1. **穴付き板のサンプルを開く**を押します。
2. 再構成候補から**貫通穴（切削）**を選び、確認のチェックを入れて**候補を採用**を押します。
3. **半径**を `1` から `1.3` に変更し、**寸法変更を準備**を押します。
4. **再計算して確定**を押します。
5. **比較を更新**で、読込時と確定形状を同じ視点・縮尺で並べます。
6. **STEPを保存**を押します。`through_hole-edited.step` がブラウザのダウンロード先へ保存されます。

板は12 × 10 × 4 mmです。穴半径1.3 mmでは、体積が約467.433629から458.762834 mm³に変わります。
半径30 mmなど成立しない変更は確定されません。診断を確認し、寸法を修正するか**入力・未確定の変更を取り消す**を押してください。

読込・候補パネルは次の操作へ進むと折りたたまれます。別のファイルや候補を選ぶ場合は見出しをクリックして開けます。原点座標は寸法欄の詳細から変更できます。

### 対応範囲

| 項目 | v1.1.0の動作 |
| --- | --- |
| 読込 | ファイル選択、または生成した穴付き板。入力は2 MB以下 |
| 編集 | v1の対応候補に含まれる寸法。候補の明示的な確認が必要 |
| 再計算 | 全体が成立したときだけ確定。失敗時は最後の正常な形状を保持 |
| 比較 | 読込時と確定形状の3D表示、体積・面積・面数・辺数 |
| 保存 | 確定形状を再構成STEPとしてダウンロード。未確定の変更があると拒否 |
| 操作の競合 | 古い状態からの編集・再計算・保存を拒否し、最新状態を表示 |
| セッション | サーバー1つにつき1つの作業状態。タブ間で共有。再起動すると失われる |

任意のSTEPを編集したり、元の設計履歴を復元したりする機能ではありません。
形状の描画は診断用です。面・辺の番号は変更後も同じ要素を指すとは限りません。
APIで生成する従来のHTMLは引き続き閲覧用スナップショットです。
編集画面はPythonサーバーの起動中に利用します。詳細は[既存のAPI対応範囲](cad-v1-support.md)を参照してください。

## Implementation and Boundaries

The editor calls the existing confirmed selection, staged edit, atomic
recompute, comparison and reconstruct-export operations. Batch changes and
preview generation run against copied session containers before publication.
A failed upload, invalid batch or failed preview retains the previous session.
Failed geometric recomputation retains the committed shape and exposes attempt
diagnostics. Revision checks also cover source replacement and download, so a
stale tab cannot export a silently changed revision.

The stdlib server binds only to `127.0.0.1`. It validates Host/Origin and a
per-process request token, serializes workspace access, caps upload/JSON bodies,
and never interprets uploaded filenames as server filesystem paths. Temporary
files belong to the session. Assets are local and included in the wheel; there
is no CDN or external data upload. Native geometry calls still run in-process
without a hard CPU or native-memory limit. This is a local research editor,
not a multi-user hosted service.

## Verification

Run the HTTP regression tests with the geometry and test extras installed:

```bash
python -m pytest tests/test_cad_web.py -q
```

These controls exercise the real HTTP server: source upload and candidate
confirmation, radius editing, pending-state export refusal, recomputation,
analytic volume and exported STEP reimport, invalid-dimension recovery, stale
revisions, atomic batch/preview failures, and request-origin/body boundaries.
The CAD platform workflow also runs these controls on its four OS targets.

Browser verification uses the visible sample → candidate → radius 1.3 → stage
→ recompute → compare → download flow, with invalid radius and rollback checks.
See the [recorded browser result](../results/cad-browser-editor/verification.json)
and [screen capture](../results/cad-browser-editor/editor.png).

The v1.0 platform/release artifacts remain historical evidence of that tagged
runtime. Its release gates intentionally do not certify a changed v1.1 runtime.
The new editor has its own tests and browser evidence; a new test count does
not expand the geometric support boundary.
