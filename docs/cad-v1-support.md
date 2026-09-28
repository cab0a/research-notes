# CAD v1.0 Support and Release Contract

## 日本語概要

v1.0.0は、対応範囲を固定した研究用3D基盤です。STEPの読込・検査、候補の確認、対応形状の寸法変更、再計算、比較、STEP出力をPython APIと対話ターミナルで行えます。公開部品を何でも編集できるわけではありません。AI候補は未学習の合成20例で正解率70%であり、利用者の確認を必須にします。診断画面は面・辺と根拠を調べる閲覧画面です。詳細は英語本文に示します。

---

## English Summary

Version 1 stabilizes a deliberately bounded research workflow. This contract
separates supported operations, measured evidence, experimental assistance and
unsupported claims. The API envelope, method arguments, revision checks and
writer policies are frozen; arbitrary STEP compatibility, proprietary history
recovery and native process isolation are not promised. Actual platform reports
and release validation records qualify the tested runtime.

## Supported Workflow

| Operation | Supported scope | Limit or refusal |
| --- | --- | --- |
| STEP import | Bounded Part 21 syntax, explicit supported units, OCCT transfer, licensed fixed public corpus | No complete AP conformance; no external reference retrieval; NUL transport controls are outside the parser profile |
| Inspection | Source hash, units, interpreted product paths, topology, B-Rep validity, face/edge diagnostics, volume and area | Per-face failures and coverage limits remain visible; local IDs are not persistent identities |
| Reconstruction | Axis-aligned plate with qualified hole, blind hole, boss, pocket or rib candidates | No recovered CAD authoring history; complex public parts usually have no editable candidate |
| Editing | Explicit candidate confirmation, supported dimensions, revision token | Candidate scores never authorize changes; stale tokens fail |
| Recompute | Dependency graph, sketch constraints, assembly placement, atomic commit/abort/rollback | Ill-conditioned/local nonlinear solutions have known limits; no arbitrary assembly mate inference |
| Compare | Original/rebuilt measurements and topology, diagnostic SVG workspace | Comparison requires a committed state; browser snapshot is read-only |
| STEP preserve | Exact source bytes | Does not include edits |
| STEP canonical | Supported syntax with normalized trivia | Refuses unsupported anchor/reference/signature preservation cases |
| STEP reconstruct | Committed geometry with measured round-trip checks | No original history, metadata or persistent topology identity guarantee |
| AI assistance | Frozen, evidence-linked ranking and abstention | Synthetic holdout accuracy 14/20; 15 decisions, 13 correct; two high-confidence incorrect decisions |

## Try It

From the repository root, with Python 3.12 and the geometry extra installed:

```bash
python -m pip install -e ".[geometry]"
python examples/cad_workspace.py
python -m research_notes.cad_tool
```

The following commands open the fixed hole example. `candidates` lists the
current IDs; this fixture's `through_hole` candidate is 2.

```text
open fixtures/step-reconstruction/through_hole.step
candidates
select 2 --confirm
set feature radius 1.3
recompute
compare
workspace
export output/edited.step reconstruct
quit
```

The installed console commands are `research-cad`, `research-3d` and
`research-cad-release`. For an ordinary public part, start with `open PATH
--inspect-only`. A missing candidate is an explicit abstention. Use `export PATH
preserve` when retaining the original exchange bytes. Existing output files
require `--overwrite`.

## API Stability

Use `research_notes.cad_api.CadWorkspace`. Version 1 keeps the v0.87 method
signatures, result envelope, status/error vocabulary and opaque revision-token
policy. The [frozen contract](../fixtures/cad-contract-freeze/v1_contract.json)
is machine-readable. Native objects and private modules are not public API.
Diagnostic JSON data may grow additively. CSV columns belong to their versioned
study. Floating measurements use declared numerical tolerances; hashes,
classifications and source bytes remain exact.

## Resource and Platform Boundaries

| Resource | Reference worker budget |
| --- | ---: |
| Source bytes / entities / references / tokens | 2,000,000 / 20,000 / 100,000 / 250,000 |
| Workspace faces / edges / triangles | 256 / 512 / 60,000 |
| Model nodes / sketch entities / constraints | 64 / 32 / 128 |
| Estimated syntax-input memory admission | 256 MB |
| Worker elapsed deadline | 30 seconds, including process startup |

These counters qualify different stages, not a universal safe-file promise.
The resource study measures Python allocation peaks with `tracemalloc`; native
OCCT/NumPy allocations are excluded. Memory admission is an estimate, not an
RSS limit. Mesh triangle accounting follows native tessellation. Fuzz/resource
workers have process deadlines; interactive API calls do not have hard native
CPU/RAM isolation. Unsupported or untrusted production inputs need a separate
operating-system isolation policy.

The CAD matrix runs on Linux x64, Windows x64, macOS Intel and macOS arm64,
with Python 3.12 and pinned dependencies. The
[platform report](../results/cad_platform_reproducibility.html) records real
runner versions and a digest of runtime sources plus `pyproject.toml`.
It qualifies the tested corpus, not every OS/kernel combination.

## Accepted Limitations and Evidence

- STEP syntax, EXPRESS validation, AP interpretation, geometry transfer and
  successful editing are separate claims. The two native import routes share
  OCCT and do not establish cross-kernel equivalence.
- Part 21 section 5.2 allows ignored transport octets. The bounded parser
  explicitly refuses raw NUL rather than implementing every transport form.
- The v0.84/v0.85 studies retain reference errors and difficult solver cases.
  A passing contract can document a known failure, refusal or abstention.
- The v0.94 protocol was committed before predictions. Held-out construction
  families are synthetic; no industrial accuracy claim is made.
- The review study uses scripted interactions and a browser verification,
  with no recruited participants or productivity estimate.
- The wheel provides runtime modules and entry points. Research fixtures,
  licensed public sources and reports are supplied in the repository/source
  distribution, not bundled in the wheel. External comparison parsers are
  separately fetched at pinned commits. Research runners and benchmark/ranking
  commands require the editable Git checkout installation shown above. The
  isolated wheel check covers the CAD API workflow and console help, not
  repository-backed research runners.

The [claim map](../results/cad_claim_traceability.html),
[end-to-end report](../results/cad_end_to_end.html),
[release gate](../results/cad_stable_release.html) and
[validation record](../results/cad-release-validation.json) record the
evidence boundary. Reproduction commands are in
[Reproducibility](reproducibility.md). Project licensing remains
[PolyForm Noncommercial 1.0.0](../LICENSING.md); public STEP files retain their
[upstream notices](../fixtures/public-step-corpus/README.md).
