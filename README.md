# Research Notes

## 日本語概要

このリポジトリは、画像処理とSTEP/B-repの調査・実験・結果・制約を再現可能に記録し、Pythonパーサー、モデリング、3D AI利用へ進みます。

v0.28.0では、STEP Part 21のDATA entityと参照出現をsource span付きの有向multigraphへ変換し、型検索、順・逆参照、到達性、孤立、循環、schema所有を14件の合成fixtureで検証します。11件受理・2件隔離・1件拒否となり、31 node、25 edge、89 query rowを記録します。

合成データ、CSV・JSON・PNG、160件のテスト、CIを備えます。結果は物理参照graphであり、AP242製品構成、B-rep意味論、外部resource解決、永続CAD identityは主張しません。詳細は英語本文に示します。

`v0.27.0`以前は各タグ同梱の条件、以後はPolyForm Noncommercial 1.0.0です。商用利用は別契約です。

---

Reproducible image-processing and STEP/B-Rep studies that connect a focused
question to source review, controlled experiments, committed evidence,
interpretation, and explicit claim boundaries.

The development branch after v0.27.0 is source-available for noncommercial
research, academic, educational, and personal experimental use. Commercial
use requires a separate written license. Tagged releases through v0.27.0
retain the license included with each tag; see [Licensing](LICENSING.md) for
the version boundary and inquiry process.

## Overview

This repository records a sequence of related technical investigations rather
than a fixed algorithm showcase. Each published study includes a research
question, controlled inputs, versioned experiment code, CSV observations, PNG
figures, interpretation, and limitations.

The work starts with blur heuristics, then tests spatial aggregation,
preprocessing, optical and photometric effects, JPEG compression history,
decoder portability, metadata interpretation, malformed-metadata recovery,
metadata round-trip policies, multi-generation policy drift, field-level
selective retention, and resource-bounded admission before evaluating extended
metadata-family coverage and digest-bound transform integrity before composing
those controls into explainable routing policies. The current track develops a
dependency-free STEP Part 21 parser foundation before advancing into EXPRESS,
application semantics, and evaluated B-Rep geometry. The current release is
v0.28.0.

Unlike `vision-playground`, which compares image-processing methods as a stable
experiment suite, this repository preserves how questions, controls, evidence,
and claim boundaries evolve from one study to the next.

## Research Themes

| Theme | Studies | Central question |
| --- | --- | --- |
| Blur measurement and localization | v0.1.0–v0.4.0 | How do noise, spatial aggregation, and window geometry change Laplacian variance and Tenengrad responses? |
| Processing-pipeline sensitivity | v0.5.0–v0.8.0 | How do preprocessing, optical blur, photometric transforms, and JPEG history move scores and fixed calibration rules? |
| JPEG codec and metadata contracts | v0.9.0–v0.20.0 | Which byte, pixel, metadata, recovery, sanitization, temporal, field-retention, resource-boundary, nested-relationship, transform-integrity, and composed-policy behaviors remain stable across encoders, decoders, syntax variants, policies, generations, and recorded CI environments? |
| STEP and B-Rep foundations | v0.21.0 onward | Which exchange-structure, schema, topology, geometry, validity, and modeling claims can be reproduced from controlled product-model data? |

The [study index](docs/studies.md) maps all 28 releases to their questions,
representative findings, artifacts, commands, and complete notes.

## Representative Result

The v0.28.0 study converts the source-preserving Part 21 model into a bounded
directed multigraph. Fourteen synthetic fixtures isolate source-ordered nodes,
reference occurrences, section and schema ownership, forward and reverse
queries, reachability, cycles, nonlocal targets, and explicit query limits.

| Condition | Observed state | Evidence |
| --- | --- | --- |
| Construction routes | explicit | 11 accept, two resource-budget quarantines, and one syntax rejection match their declarations |
| Source-linked graph | controlled | 31 nodes and 25 edge occurrences retain section ownership, parameter paths, and source spans |
| Target scope | explicit | Local entity, external entity, external value, schema constant, and unresolved references remain distinct |
| Queries | bounded | 86 complete, two partial, and one not-evaluated result preserve traversal boundaries |
| Semantic boundary | physical only | Root-relative orphans and cycles do not imply AP242, assembly, B-Rep, or geometry meaning |

![Generic STEP graph evidence](results/step_graph.png)

All 14 construction observations match their declared routes. The graph keeps
repeated, unresolved, external, and constant reference occurrences without
inventing local nodes or retrieving resources. It is not an AP242 product
graph, assembly interpretation, B-Rep graph, or geometry dependency graph.

## Claim Boundaries

- The studies use small, 8-bit synthetic images rather than a representative
  natural-image benchmark.
- Metric responses are relative to declared controls. They are not universal
  blur thresholds, perceptual scores, or proof that one metric is superior.
- The malformed-metadata corpus is not a fuzzer, vulnerability assessment,
  resource benchmark, or memory-safety proof.
- The metadata normalizer supports only EXIF Orientation and complete embedded
  ICC profiles; it is not a general-purpose metadata sanitizer.
- The field-level parser supports twelve controlled fields and two layouts.
  It is not a general EXIF, XMP, ICC, IPTC, or privacy sanitizer.
- The resource-boundary auditor receives an already resident byte string and
  bounds only its declared header and metadata work. It does not bound file
  reads, decoder pixels, process memory, wall-clock time, or exploitability.
- The metadata-coverage parser recognizes only the synthetic EXIF, XMP, IPTC
  IIM, Photoshop IRB, and maker-note structures used by v0.18.0. It is not a
  complete metadata implementation.
- The transform-integrity record is a project-specific unsigned digest
  assertion. Matching bindings are not authenticated provenance.
- The composition engine returns decisions and optional bytes; it does not
  enforce quarantine storage, access control, retention, or operator review.
- The observed generation-3 pixel fixed point applies only to one small
  synthetic image, quality 75, 4:4:4 sampling, and the pinned builds. It is not
  a convergence guarantee or losslessness claim.
- Cross-platform observations describe pinned wheels on recorded GitHub-hosted
  runner images. They do not guarantee identical behavior for other builds.
- The STEP conformance layer supports only the committed 34-fixture subset.
  It is not an ISO certification suite, complete Wirth Syntax Notation
  coverage, EXPRESS validation, external-resource resolver, CMS verifier, or
  proof of support for arbitrary STEP files.
- The EXPRESS resolver supports a controlled ASCII declaration subset and
  direct imports from schemas in the same document. It does not implement
  complete visibility, transitive re-export, external schema loading,
  expression typing, constraint evaluation, or executable rule behavior.
- The Part 21-to-EXPRESS validator covers a controlled internal mapping and
  selected values. Complex instances remain quarantined after structural
  checks; constants, value instances, complete assignment compatibility,
  rules, and application semantics remain deferred.
- The generic STEP graph contains physical local and nonlocal reference
  occurrences. Zero indegree, isolation, reachability, cycles, and
  root-relative orphans do not establish application meaning.
- STEP face and edge indices are analysis-local. They are not persistent CAD
  identities across export, editing, Boolean operations, or healing.
- Known pattern identities, matched references, and synthetic calibration
  anchors are controls that are usually unavailable in blind inspection.

Each [complete research note](notes/) records additional limitations for its
own experiment.

## Quick Start

Python 3.11 or newer is required. The reference environment uses Python 3.12
and the exact dependency versions in `pyproject.toml`.

```bash
git clone https://github.com/cab0a/research-notes.git
cd research-notes
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python experiments/run_laplacian_variance.py --output-dir output/quickstart
```

Review:

- `output/quickstart/laplacian_variance.png`
- `output/quickstart/laplacian_variance_summary.csv`

This smallest study shows both the expected blur response and the noise
confound.

## Generated Artifacts

Each study writes observation-level or trial-level CSV files, compact summary
tables, and one or more explanatory PNG figures. The v0.28.0 graph study also
writes a deterministic versioned JSON record. JPEG studies write
fixture, codec, runtime, syntax, decoded-pixel, and pair-comparison manifests.
The STEP studies commit generated Part 21 and EXPRESS fixtures, token and
source-span inventories, structure, section, declaration, face-, edge-, shell-,
and solid-level tables, and visual controls.

- Committed reference evidence: [`results/`](results/)
- Artifact catalog: [`results/README.md`](results/README.md)
- Fixed decoder inputs and declared references: [`fixtures/`](fixtures/)

## STEP and EXPRESS Sample Gallery

The [STEP sample and preview catalog](docs/step-sample-catalog.md) links each
generated input to its manifest, purpose, expected route, and visual evidence.
The catalog includes the v0.24.0 Part 21 conformance corpus, the v0.25.0 and
v0.26.0 EXPRESS corpora, the paired v0.27.0 STEP/EXPRESS validation corpus,
and the v0.28.0 physical-reference graph corpus.
Syntax-only samples use source and relationship figures rather than fabricated
geometry previews.

![Closed tetrahedron geometry control](results/step_part21_geometry_control.png)

Preview images support inspection; CSV invariants and tests remain the
validation evidence.

## Key Features

- Twenty-eight published studies with explicit questions, controls, results, and
  limitations
- Programmatically generated blur, noise, window, preprocessing, optical, and
  photometric conditions
- Fixed or deterministically generated JPEG fixtures for syntax, chroma
  sampling, color metadata, malformed metadata, trailing data, resource
  boundaries, and round-trip policies
- One dependency-free, source-preserving Part 21 lexer and parser shared by
  the exchange-structure and topology studies, plus topology resolution for
  the geometry-bearing subset
- Edition-aware Part 21 conformance observations and isolated comparisons with
  two pinned public Python parsers
- A source-preserving EXPRESS lexer and parser plus bounded symbol, direct
  import, type-alias, aggregate-bound, and inheritance resolution
- Staged binding from Part 21 DATA sections and parameters to controlled
  EXPRESS schemas, entities, attributes, value domains, and inheritance order
- A deterministic Part 21 directed multigraph with stable local node IDs,
  source-linked reference occurrences, bounded traversal, cycle detection,
  and versioned JSON output
- Observation-level CSV files alongside summaries and figures from the same
  runs
- Deterministic seeds, pinned runtime dependencies, hashed fixtures, and
  committed reference evidence
- A five-profile CI matrix for decoded-pixel and metadata-recovery contracts
- Unit tests and CI regeneration checks against committed CSV and fixture data

## Research Workflow

```text
Research Question
    -> Source Review
    -> Method Selection
    -> Controlled Experiment
    -> Evaluation
    -> Interpretation
    -> Limitations
    -> Documentation
```

The experiment-specific evidence is organized in three layers:

1. `notes/` contains the complete research record.
2. `experiments/` and `src/research_notes/` contain the executable method.
3. `results/` and `fixtures/` contain committed evidence and fixed inputs.

## Evaluation Methodology

Each study declares the variable being changed, the controls held fixed, the
observation count, the aggregation policy, and the claim boundary. Decoder
studies separate file structure, array-interface validity, exact decoded
hashes, pairwise code-value differences, metadata admission, and
cross-platform agreement. The STEP studies separate container recognition,
physical-file parsing, exact source retention, source coordinates, section
order, declared schema identifiers, external trust boundaries, topology
resolution, visual previews, EXPRESS declaration parsing, semantic graph
states, DATA-schema binding, attribute-level parameter validation, and deferred
expression, application, and geometry evaluation. Physical-reference graph
queries preserve repeated occurrences and nonlocal target scopes while keeping
AP242 product meaning and B-Rep meaning outside the graph contract.

Measurements are interpreted inside each controlled design. Detailed results
for every release are collected in [`docs/studies.md`](docs/studies.md), while
the notes preserve hypotheses, source references, failure modes, and
experiment-specific limitations.

## Reproducibility

Install test dependencies and run the suite:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Every experiment can be run independently. The complete command list,
deterministic controls, fixture-refresh commands, CI aggregation design, and
repository layout are documented in
[`docs/reproducibility.md`](docs/reproducibility.md).

## Development and Testing

The repository contains 160 tests covering blur metrics and models,
preprocessing and photometric transforms, JPEG parsing, fixed-fixture
contracts, repeated and field-level metadata policies, resource-boundary
routing, the unified source-preserving Part 21 parser, edition and
conformance-class checks, bounded exchange structures, B-Rep topology
ownership and incidence, EXPRESS tokenization, declaration models, resource
limits, symbol tables, direct imports, type aliases, aggregate bounds,
inheritance, redeclarations, inverse links, experiment outputs, and
schema-bound Part 21 parameters, occurrence-reference compatibility, staged
validation boundaries, source-linked graph construction, bounded queries,
versioned JSON records, experiment outputs, and cross-platform summary logic.

GitHub Actions runs the README Quick Start, checks its summary CSV and figure,
then runs the tests and regenerates the reference evidence on Ubuntu with
Python 3.12. Separate jobs record JPEG observations on Ubuntu x64 default and
scalar paths, Windows x64, macOS arm64, and macOS Intel x64 before aggregating
the combined reports.

## Compatibility

Python 3.11 or newer is required. Python 3.12 and the exact runtime versions in
`pyproject.toml` define the reference environment. Cross-platform conclusions
apply only to the runner images and bundled codec builds recorded in the
manifests. The v0.21.0 through v0.28.0 STEP and EXPRESS layers have no
geometry-kernel dependency and do not claim compatibility beyond their
controlled Part 21, topology, and ASCII EXPRESS subsets.

## Roadmap

The [STEP mastery, Python parser, and 3D tool roadmap](docs/brep-learning-roadmap.md)
makes specification knowledge and a source-preserving Python parser the
foundation. v0.28.0 exposes the physical Part 21 reference graph and bounded
queries. The roadmap next proceeds through AP242 product semantics, B-Rep
geometry, inspection, modeling, STEP round trips,
feature recognition, and evidence-backed parametric reconstruction. v0.40.0
starts new parameter-driven construction, v0.44.0 targets import-edit-export
round trips, and v0.55.0 begins STEP-to-feature reconstruction candidates.
Geometry-kernel adoption remains an explicit capability, distribution, and
license checkpoint.

The roadmap is exploratory; only published releases represent completed work.

## License

The repository state after the v0.27.0 tag, including future releases, is
licensed under the
[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use requires a
separate written license from the copyright holder. To discuss commercial
licensing, [open a GitHub issue](https://github.com/cab0a/research-notes/issues/new)
with `Commercial licensing inquiry` in the title and do not include
confidential information.

Tagged releases through v0.27.0 retain the license included with each tag;
the [v0.27.0 license](https://github.com/cab0a/research-notes/blob/v0.27.0/LICENSE)
records the final historical boundary. Third-party material retains its own
terms. The complete version boundary and summary are documented in
[Licensing](LICENSING.md).
