# Unified Circular-Hole and Slot Inventory — v1.11.0

## 日本語概要

v1.9の丸穴認識とv1.10の長孔認識を画面・Python API・CLI・CSVで統合しました。公開ブラケットでは丸穴5か所・長孔6か所を同じ一覧に表示します。丸穴の径と長孔の幅・全長、長手方向と貫通方向を区別します。番号・内壁・表の行を選択すると対応する形状と行を強調します。確認できた11か所は全体数の保証ではなく、全体数は不明のままです。既存の公開STEP6件を3回ずつ評価し、各入力で認識結果は同一でした。

---

## English Summary

This release connects the existing circle and slot recognizers to one typed
inventory. It changes integration and presentation, not geometry thresholds.
The public bracket yields five circle rows and six slot rows. All six existing
public inputs retain unknown whole counts; the other five yield no qualified
rows. These fixed inputs were used during development, not held out for accuracy
evaluation. [The guide](../docs/cad-hole-inventory.md) documents commands, fields,
coordinate conventions, exit codes and inherited limits.

## Recorded result

| Item | Result |
| --- | --- |
| Bracket circles | 4 × diameter 3.3 mm, 1 × diameter 32 mm |
| Bracket slots | 6 × width 4.5 mm, overall length 7.5 mm |
| Bracket through lengths | 3 mm for all 11 reported rows |
| Row identifiers | H1–H5 for circles, S1–S6 for slots |
| Slot long directions | Four along Y, two along X |
| Whole opening count | Unknown; never certified as a complete count of 11 |
| Bracket CSV | 1 summary + 5 circle + 6 slot rows |
| Fixed corpus | 6 inputs / 5 families; all import, all whole counts unknown |
| Repetitions | 3 per input, identical measurements and diagnostics |

The viewer colors circles amber and slots teal. Selecting a marker, wall or
table row highlights the corresponding wall faces and row. Slot selection
highlights its four walls, not the entire opening planes. Keyboard Enter/Space
selects a marker; dragging rotates without changing selection. The selected
dimensions and both direction vectors appear above the viewer. The table
scrolls horizontally on narrow screens.

Positions and dimensions retain the [v1.9 circle](public-step-hole-inventory.md)
and [v1.10 slot](bracket-slot-inventory.md) definitions. No inferred design
history, machining intent or new dimension-editing capability is claimed.

## Schema and compatibility

`analyze_step(..., inspection=True)` enables both recognizers by default.
The `holes` list now contains `feature_type=circular_hole` or `straight_slot`.
`recognized_hole_count` is the accepted row count, with explicit
`recognized_circular_hole_count` and `recognized_slot_count` subtotals.
Consumers that assumed every row had a numeric diameter must branch on type:
slot diameter is null, circle width/length/long axis are null. CSV uses blank
cells and the UI uses an em dash. Existing H IDs, circular dimensions and
common position/depth/axis/face fields remain; slots retain S IDs and evidence.
CSV keeps its original columns in order and appends new fields, including version.

`include_slots=False` or `--public --circular-only` retains the former
circular-only measurement scope. The old public-hole benchmark explicitly uses
that mode; frozen evidence and sources are not replaced. This does not restore
the old serialized schema byte for byte. Strict intake without `--public` and
the separate v1.10 slot API/CLI retain their scopes.

`complete` is exclusive to the existing whole-plate reconstruction certificate.
Accepted slots produce only `partial`. No recognized rows means `unresolved`,
not absence. A slot-scanner failure retains verified circles and its reason.
Preview failure preserves both types and CSV. Replacing an input clears previous
rows; stale tokens cannot download a newer inventory accidentally.

## Evidence and reproduction

```bash
python -m research_notes.unified_hole_benchmark --output-dir output/unified-check --repeats 3
python -m research_notes.hole_inventory fixtures/public-step-corpus/sources/build123d_bracket.step --public --output-dir output/bracket-unified
python -m pytest tests/test_unified_hole_inventory.py tests/test_slot_inventory.py tests/test_public_hole_inventory.py tests/test_hole_inventory.py -q
```

The bracket CLI exits 2 after saving partial results; only complete whole-plate
inventories exit 0. This existing exit-code policy is maintained.

- [Repeated results and runtime/code/source hashes](../results/unified-hole-inventory/results.json).
- [Unified bracket CSV](../results/unified-hole-inventory/csv/build123d_bracket.csv).
- [Numbered source projection](../results/unified-hole-inventory/bracket.svg).
- [Tests, browser checks and download verification](../results/unified-hole-inventory/verification.json).
- [Frozen source and license manifest](../fixtures/public-step-corpus/manifest.json).

Both feature types pass their separate boundary cross-checks. Adapted slot values
exactly match the standalone recognizer. Both checks use the same OCCT kernel as
recognition: internal agreement, not independent metrology. Sources and notices
are unchanged. No new public samples or wider recognition claims are added.

## Limits

Both recognizers' restrictions, the 2 MB input/512-face scan limits and separate
256-face preview limit apply. The 399-face EMMY sample is scanned without preview.
Native geometry calls remain in process without hard CPU/memory deadlines.
Obstruction by another assembly component is not checked. Combining the screen
does not add support for curved, split, tapered, stepped, threaded or complex
blind features. Wider robustness evaluation, additional public samples, batch
processing and Excel-native reports remain later milestones. This release
changes the research repository only.
