# Research Notes

## 日本語概要

このリポジトリは、画像処理とSTEP/B-repの調査、統制実験、結果、考察、制約を再現可能に記録します。

v0.22.0では13個の合成fixtureから複数DATA、complex entity、UTF-8、binary、ANCHOR、REFERENCE、SIGNATURE、ZIPを検証し、5件をaccept、4件をquarantine、4件をrejectにしました。閉じた四面体STEPとpreviewも保存します。限定構文の結果であり、EXPRESS・AP242適合、外部取得、署名検証、archive展開、幾何評価は主張しません。

合成データ、CSV・PNG、固定依存、109件のテスト、CIを備えます。詳細、再現手順、主張の境界は以下の英語本文と個別ノートに示します。

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
dependency-free STEP Part 21 and B-Rep analyzer from topology into advanced
exchange-structure boundaries. The current release is v0.22.0.

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

The [study index](docs/studies.md) maps all 22 releases to their questions,
representative findings, artifacts, commands, and complete notes.

## Representative Result

The v0.22.0 study recognizes selected advanced Part 21 exchange structures
without crossing unimplemented trust boundaries. Thirteen synthetic inputs
isolate supported syntax, external dependencies, resource limits, and
contradictory structure.

| Boundary | Decision | Evidence |
| --- | --- | --- |
| Single and repeated DATA | accept | One geometry-bearing section and two named schema-bound sections |
| Complex entity | accept | One subsuper record with three component records |
| UTF-8, binary, and ANCHOR | accept | Direct text, lexical binary validation, and one tagged anchor |
| External REFERENCE | quarantine | URI retained; retrieval not attempted |
| SIGNATURE | quarantine | Base64 retained; CMS verification not attempted |
| ZIP container | quarantine | Container recognized; archive not opened |
| Depth limit | quarantine | Aggregate nesting exceeds the configured budget |
| Contradictory or invalid structure | reject | Four isolated negative controls |

![Advanced Part 21 exchange structure boundaries](results/step_part21_exchange_boundaries.png)

All 13 observations match their declared decisions: five accept, four
quarantine, and four reject. The viewable tetrahedron control contains 74
entity instances and 97 local references; the v0.21.0 topology path still
resolves four faces, six edges, one shell, one solid, and no free edges. These
are controlled parser and topology results, not general STEP, EXPRESS, or
AP242 conformance and not evaluated geometric validity.

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
- The STEP parsers support only the committed structural subsets. Advanced
  syntax recognition does not validate an EXPRESS schema, resolve external
  resources, verify CMS signatures, open ZIP containers, evaluate trimmed
  geometry, or establish support for arbitrary STEP files.
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
The STEP studies commit generated Part 21 fixtures, structure and section
inventories, face-, edge-, shell-, and solid-level tables, and visual controls.

- Committed reference evidence: [`results/`](results/)
- Artifact catalog: [`results/README.md`](results/README.md)
- Fixed decoder inputs and declared references: [`fixtures/`](fixtures/)

## STEP Sample Gallery

The [STEP sample and preview catalog](docs/step-sample-catalog.md) links each
generated input to its manifest, purpose, expected route, and visual evidence.
The v0.22.0 geometry control is a committed closed tetrahedron STEP file rather
than a screenshot-only example.

![Closed tetrahedron geometry control](results/step_part21_geometry_control.png)

Preview images support inspection; CSV invariants and tests remain the
validation evidence.

## Key Features

- Twenty-two published studies with explicit questions, controls, results, and
  limitations
- Programmatically generated blur, noise, window, preprocessing, optical, and
  photometric conditions
- Fixed or deterministically generated JPEG fixtures for syntax, chroma
  sampling, color metadata, malformed metadata, trailing data, resource
  boundaries, and round-trip policies
- Dependency-free bounded parsing for controlled simple and advanced STEP Part
  21 structures, plus topology resolution for the geometry-bearing subset
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
physical-file parsing, section order, declared schema identifiers, external
trust boundaries, topology resolution, visual previews, and deferred schema
and geometry evaluation.

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

The repository contains 109 tests covering blur metrics and models,
preprocessing and photometric transforms, JPEG parsing, fixed-fixture
contracts, repeated and field-level metadata policies, resource-boundary
routing, bounded simple and advanced STEP parsing, B-Rep topology ownership and
incidence, experiment outputs, and cross-platform summary logic.

GitHub Actions runs the README Quick Start, checks its summary CSV and figure,
then runs the tests and regenerates the reference evidence on Ubuntu with
Python 3.12. Separate jobs record JPEG observations on Ubuntu x64 default and
scalar paths, Windows x64, macOS arm64, and macOS Intel x64 before aggregating
the combined reports.

## Compatibility

Python 3.11 or newer is required. Python 3.12 and the exact runtime versions in
`pyproject.toml` define the reference environment. Cross-platform conclusions
apply only to the runner images and bundled codec builds recorded in the
manifests. The v0.21.0 and v0.22.0 STEP layers have no geometry-kernel
dependency and do not claim compatibility beyond their controlled Part 21 and
topology subsets.

## Roadmap

The [STEP, B-Rep, and 3D intelligence roadmap](docs/brep-learning-roadmap.md)
moves from exchange syntax and schema semantics through evaluated geometry,
modeling operations, assemblies, interoperability, face-adjacency graphs,
feature recognition, AI-ready evidence, and an integrated analysis and
modeling tool. Geometry-kernel adoption remains an explicit capability,
distribution, and license checkpoint.

The roadmap is exploratory; only published releases represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
