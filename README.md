# Research Notes

## 日本語概要

このリポジトリは、画像処理とSTEP/B-repの調査、統制実験、結果、考察、制約を再現可能に記録します。STEP研究は、仕様理解、Pythonパーサー、形状・位相・製品構成、モデリング、3D AI利用の順に進めます。

v0.23.0ではv0.21とv0.22の読み取り処理を一つのPart 21基盤へ統合しました。10個の合成fixtureでsource保持、位置情報、単純・複合entity、前方参照、構文異常、resource上限を検証し、5件をaccept、2件をquarantine、3件をrejectにしました。acceptした5件は元bytesを完全再構成し、閉じた四面体の74 entities・97 referencesと従来の位相解析も維持します。

合成データ、CSV・PNG、固定依存、117件のテスト、CIを備えます。完全なPart 21、EXPRESS・AP242適合、幾何妥当性、書き戻し互換性は主張しません。詳細は以下の英語本文に示します。

---

Reproducible image-processing and STEP/B-Rep studies that connect a focused
question to source review, controlled experiments, committed evidence,
interpretation, and explicit claim boundaries.

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
v0.23.0.

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

The [study index](docs/studies.md) maps all 23 releases to their questions,
representative findings, artifacts, commands, and complete notes.

## Representative Result

The v0.23.0 study replaces the separate v0.21 and v0.22 tokenizers and grammar
streams with one source-preserving parser. Ten synthetic inputs isolate exact
source retention, grammar forms, localized failures, and resource limits.

| Condition | Decision | Evidence |
| --- | --- | --- |
| Geometry integration control | accept | 74 entities and 97 references pass the unified parser and existing topology adapter |
| Whitespace and comments | accept | All trivia remains in the complete token stream |
| UTF-8 coordinates | accept | Character, byte, line, and column positions remain distinct and attributable |
| Simple, complex, and forward references | accept | One grammar constructs both record forms without requiring definition order |
| Nesting and token-length limits | quarantine | Explicit budgets stop work without classifying the input as malformed syntax |
| Missing delimiter, open comment, invalid UTF-8 | reject | Three isolated syntax or decoding failures |

![Unified Part 21 source model](results/step_part21_source_model.png)

All ten observations match their declared decisions: five accept, two
quarantine, and three reject. Every accepted fixture reconstructs its exact
UTF-8 bytes, producing 1,435 committed token rows. The viewable tetrahedron
still resolves four faces, six edges, one shell, one solid, and no free edges.
These are controlled source-model and topology results, not complete Part 21,
EXPRESS, or AP242 conformance and not evaluated geometric validity.

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
- The unified STEP source model supports only the committed structural subset.
  Exact source reconstruction does not establish full Part 21 edition
  coverage, validate an EXPRESS schema, resolve external resources, verify CMS
  signatures, open ZIP containers, evaluate trimmed geometry, or establish
  support for arbitrary STEP files.
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
tables, and one or more explanatory PNG figures. JPEG studies also write
fixture, codec, runtime, syntax, decoded-pixel, and pair-comparison manifests.
The STEP studies commit generated Part 21 fixtures, token and source-span
inventories, structure and section inventories, face-, edge-, shell-, and
solid-level tables, and visual controls.

- Committed reference evidence: [`results/`](results/)
- Artifact catalog: [`results/README.md`](results/README.md)
- Fixed decoder inputs and declared references: [`fixtures/`](fixtures/)

## STEP Sample Gallery

The [STEP sample and preview catalog](docs/step-sample-catalog.md) links each
generated input to its manifest, purpose, expected route, and visual evidence.
The v0.23.0 corpus retains a copy of the closed tetrahedron as an integration
control alongside syntax-only samples and their source-model diagram.

![Closed tetrahedron geometry control](results/step_part21_geometry_control.png)

Preview images support inspection; CSV invariants and tests remain the
validation evidence.

## Key Features

- Twenty-three published studies with explicit questions, controls, results, and
  limitations
- Programmatically generated blur, noise, window, preprocessing, optical, and
  photometric conditions
- Fixed or deterministically generated JPEG fixtures for syntax, chroma
  sampling, color metadata, malformed metadata, trailing data, resource
  boundaries, and round-trip policies
- One dependency-free, source-preserving Part 21 lexer and parser shared by
  the exchange-structure and topology studies, plus topology resolution for
  the geometry-bearing subset
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
resolution, visual previews, and deferred schema and geometry evaluation.

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

The repository contains 117 tests covering blur metrics and models,
preprocessing and photometric transforms, JPEG parsing, fixed-fixture
contracts, repeated and field-level metadata policies, resource-boundary
routing, the unified source-preserving Part 21 parser, bounded exchange
structures, B-Rep topology ownership and incidence, experiment outputs, and
cross-platform summary logic.

GitHub Actions runs the README Quick Start, checks its summary CSV and figure,
then runs the tests and regenerates the reference evidence on Ubuntu with
Python 3.12. Separate jobs record JPEG observations on Ubuntu x64 default and
scalar paths, Windows x64, macOS arm64, and macOS Intel x64 before aggregating
the combined reports.

## Compatibility

Python 3.11 or newer is required. Python 3.12 and the exact runtime versions in
`pyproject.toml` define the reference environment. Cross-platform conclusions
apply only to the runner images and bundled codec builds recorded in the
manifests. The v0.21.0 through v0.23.0 STEP layers have no geometry-kernel
dependency and do not claim compatibility beyond their controlled Part 21 and
topology subsets.

## Roadmap

The [STEP mastery, Python parser, and 3D tool roadmap](docs/brep-learning-roadmap.md)
makes specification knowledge and a source-preserving Python parser the
foundation. It proceeds through Part 21 grammar coverage, EXPRESS parsing and
validation, AP242 product semantics, B-Rep geometry, inspection, modeling,
interoperability, face-adjacency graphs, and AI-ready evidence. Geometry-kernel
adoption remains an explicit capability, distribution, and license checkpoint.

The roadmap is exploratory; only published releases represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
