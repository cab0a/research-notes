# Research Notes

## 日本語概要

このリポジトリは、画像処理とSTEP/B-repに関する研究課題、文献調査、仮説、統制実験、結果、考察、制約を継続的に記録する研究ノートです。

研究テーマは、ぼけ評価、前処理や圧縮による評価値の変化、JPEGの復号・metadata・環境間互換性、STEP Part 21とB-rep位相です。v0.21.0ではOpen CASCADEに依存せず、6個の合成STEP fixtureから面・辺・シェル・立体を解決します。閉じた四面体は4面・6辺・1シェル・1立体・自由辺0、1面を除いた四面体は自由辺3となり、未解決参照をquarantine、重複entity IDをrejectにしました。これは限定構文の位相検査であり、一般的なSTEP適合性や正確な幾何評価を主張しません。

入力が同じなら同じ結果を生成するテストデータ、CSV・PNG成果物、固定した依存関係、テスト、5種類の環境を使った互換性検証を含みます。研究ごとの結果、再現手順、主張できる範囲は、以下の英語本文と個別ノートを参照してください。

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
those controls into explainable routing policies. The current track begins a
dependency-free STEP Part 21 and B-Rep topology analyzer. The current release
is v0.21.0.

Unlike `vision-playground`, which compares image-processing methods as a stable
experiment suite, this repository preserves how questions, controls, evidence,
and claim boundaries evolve from one study to the next.

## Research Themes

| Theme | Studies | Central question |
| --- | --- | --- |
| Blur measurement and localization | v0.1.0–v0.4.0 | How do noise, spatial aggregation, and window geometry change Laplacian variance and Tenengrad responses? |
| Processing-pipeline sensitivity | v0.5.0–v0.8.0 | How do preprocessing, optical blur, photometric transforms, and JPEG history move scores and fixed calibration rules? |
| JPEG codec and metadata contracts | v0.9.0–v0.20.0 | Which byte, pixel, metadata, recovery, sanitization, temporal, field-retention, resource-boundary, nested-relationship, transform-integrity, and composed-policy behaviors remain stable across encoders, decoders, syntax variants, policies, generations, and recorded CI environments? |
| STEP and B-Rep foundations | v0.21.0 onward | Which file, topology, geometry, validity, and modeling claims can be reproduced from controlled product-model data? |

The [study index](docs/studies.md) maps all 21 releases to their questions,
representative findings, artifacts, commands, and complete notes.

## Representative Result

The v0.21.0 study resolves selected Part 21 entity relationships into face,
edge, shell, and solid inventories. Six synthetic inputs isolate closure,
disconnected ownership, surface declarations, missing references, and
duplicate identifiers.

| Fixture | Decision | Faces | Edges | Shells | Solids | Free edges |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `closed_tetrahedron` | accept | 4 | 6 | 1 | 1 | 0 |
| `open_tetrahedron` | accept | 3 | 6 | 1 | 0 | 3 |
| `two_closed_solids` | accept | 8 | 12 | 2 | 2 | 0 |
| `surface_catalog` | accept | 6 | 18 | 1 | 0 | 18 |
| `unresolved_reference` | quarantine | 0 | 0 | 0 | 0 | 0 |
| `duplicate_entity_id` | reject | 0 | 0 | 0 | 0 | 0 |

![STEP and B-Rep topology inspection](results/step_brep_topology.png)

All observations match their declared counts and decisions. The accepted
surface catalog classifies plane, cylinder, cone, sphere, torus, and B-spline
declarations. These are controlled topology and declaration results, not
general STEP conformance or evaluated geometric validity.

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
- The STEP parser supports only the committed simple-entity subset. It does not
  validate an EXPRESS schema, evaluate trimmed geometry, or establish support
  for arbitrary STEP files.
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
The STEP study commits generated Part 21 fixtures and face-, edge-, shell-, and
solid-level tables.

- Committed reference evidence: [`results/`](results/)
- Artifact catalog: [`results/README.md`](results/README.md)
- Fixed decoder inputs and declared references: [`fixtures/`](fixtures/)

## Key Features

- Twenty-one published studies with explicit questions, controls, results, and
  limitations
- Programmatically generated blur, noise, window, preprocessing, optical, and
  photometric conditions
- Fixed or deterministically generated JPEG fixtures for syntax, chroma
  sampling, color metadata, malformed metadata, trailing data, resource
  boundaries, and round-trip policies
- Dependency-free bounded parsing and topology resolution for a controlled
  synthetic STEP Part 21 subset
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
cross-platform agreement. The STEP study separates physical-file parsing,
declared schema identifiers, topology resolution, and deferred geometry
evaluation.

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

The repository contains 101 tests covering blur metrics and models,
preprocessing and photometric transforms, JPEG parsing, fixed-fixture
contracts, repeated and field-level metadata policies, resource-boundary
routing, bounded STEP parsing, B-Rep topology ownership and incidence,
experiment outputs, and cross-platform summary logic.

GitHub Actions runs the README Quick Start, checks its summary CSV and figure,
then runs the tests and regenerates the reference evidence on Ubuntu with
Python 3.12. Separate jobs record JPEG observations on Ubuntu x64 default and
scalar paths, Windows x64, macOS arm64, and macOS Intel x64 before aggregating
the combined reports.

## Compatibility

Python 3.11 or newer is required. Python 3.12 and the exact runtime versions in
`pyproject.toml` define the reference environment. Cross-platform conclusions
apply only to the runner images and bundled codec builds recorded in the
manifests. The v0.21.0 STEP topology layer has no geometry-kernel dependency
and does not claim compatibility with STEP constructs outside its controlled
subset.

## Roadmap

The [B-Rep learning and modeling roadmap](docs/brep-learning-roadmap.md) moves
from v0.21.0 topology inspection through evaluated geometry, modeling
operators, topology history, tolerance and healing, feature recognition,
assemblies, and cross-kernel portability. Geometry-kernel adoption is an
explicit dependency and license checkpoint rather than an implicit transitive
dependency.

The roadmap is exploratory; only published releases represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
