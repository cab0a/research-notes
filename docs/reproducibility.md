# Reproducibility

## 日本語概要

本書は、27件の研究ノートの合成画像・合成STEP・合成EXPRESS、固定した実験条件、CSV、図、実行環境を再現する手順を定義します。最小実験と全実験の実行方法、固定fixtureの更新、決定論の範囲、metadata方針・resource上限・STEP位相・交換構造・統合source model・版別構文適合性・EXPRESS schema model・semantic graph・STEP instance検証を含む検証、互換性境界をまとめています。

環境構築と検証コマンドは以下の英語本文を参照してください。

---

## English Summary

This guide defines the reference environment, smallest runnable study,
complete experiment suite, deterministic controls, cross-platform matrix, and
compatibility boundary for reproducing the committed research evidence.

## Environment

Python 3.11 or newer is required. Python 3.12 and the exact runtime dependency
versions in `pyproject.toml` define the reference environment.

```bash
git clone https://github.com/cab0a/research-notes.git
cd research-notes
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Smallest Experiment

```bash
python experiments/run_laplacian_variance.py --output-dir output/quickstart
```

This writes:

- `output/quickstart/laplacian_variance_summary.csv`
- `output/quickstart/laplacian_variance.png`

## Part 21 Comparison Setup

The v0.24.0 differential experiment uses two independent public parsers at
exact commits. They are comparison inputs and are not vendored or imported by
the `research_notes` package. From a clean repository checkout, run:

```bash
python -m pip install -e ".[comparison,test]"
mkdir -p external
git clone https://github.com/mozman/steputils.git external/steputils
git -C external/steputils checkout 547860b349a36cf24c564d6c87ffd8f60484f6fb
git clone https://github.com/IfcOpenShell/step-file-parser.git \
  external/ifcopenshell_step_file_parser
git -C external/ifcopenshell_step_file_parser checkout \
  9400d243d880dace57490949d74ab1932ce99a09
```

The experiment verifies both `HEAD` values before collecting observations.
The external checkouts remain ignored by Git. Their repository URLs,
revisions, licenses, and comparison roles are committed in
`results/step_part21_parser_manifest.csv`.

## Complete Experiment Set

Each script can use its default `results/` destination or an explicit
`--output-dir` when a separate comparison directory is needed.

```bash
python experiments/run_laplacian_variance.py
python experiments/run_focus_metric_comparison.py
python experiments/run_local_blur_evaluation.py
python experiments/run_window_geometry_evaluation.py
python experiments/run_preprocessing_sensitivity.py
python experiments/run_optical_blur_models.py
python experiments/run_photometric_recompression.py
python experiments/run_jpeg_compression_history.py
python experiments/run_jpeg_codec_portability.py
python experiments/run_cross_platform_codec_contracts.py
python experiments/run_advanced_jpeg_syntax.py
python experiments/run_color_metadata_interpretation.py
python experiments/run_malformed_metadata_recovery.py
python experiments/run_metadata_round_trip.py
python experiments/run_metadata_generation_drift.py
python experiments/run_field_level_metadata_provenance.py
python experiments/run_resource_bounded_metadata.py
python experiments/run_metadata_family_coverage.py
python experiments/run_transform_integrity.py
python experiments/run_policy_composition.py
python experiments/run_step_brep_topology.py
python experiments/run_step_exchange_structure.py
python experiments/run_step_part21_source_model.py
python experiments/run_step_part21_conformance.py
python experiments/run_express_schema_model.py
python experiments/run_express_symbol_resolution.py
python experiments/run_step_express_validation.py
```

The [study index](studies.md) maps every command to its research note and main
artifacts.

## Fixed Fixture Refresh

The fixed-input experiments can recreate their fixture corpora in a separate
directory. CI uses this mode and compares the generated directories with the
committed fixtures.

```bash
python experiments/run_cross_platform_codec_contracts.py \
  --fixture-dir output/fixtures/jpeg-decoder-contracts \
  --output-dir output/jpeg-decoder-contracts \
  --platform-label linux-x64-reference \
  --refresh-fixtures

python experiments/run_advanced_jpeg_syntax.py \
  --fixture-dir output/fixtures/advanced-jpeg-syntax \
  --output-dir output/advanced-jpeg-syntax \
  --platform-label linux-x64-reference \
  --refresh-fixtures

python experiments/run_color_metadata_interpretation.py \
  --fixture-dir output/fixtures/color-metadata-contracts \
  --output-dir output/color-metadata-contracts \
  --platform-label linux-x64-reference \
  --refresh-fixtures

python experiments/run_malformed_metadata_recovery.py \
  --fixture-dir output/fixtures/malformed-jpeg-metadata \
  --output-dir output/malformed-jpeg-metadata \
  --platform-label linux-x64-reference \
  --refresh-fixtures

python experiments/run_step_brep_topology.py \
  --fixture-dir output/fixtures/step-brep-topology \
  --output-dir output/step-brep-topology \
  --refresh-fixtures

python experiments/run_step_exchange_structure.py \
  --fixture-dir output/fixtures/step-part21-exchange \
  --output-dir output/step-part21-exchange \
  --refresh-fixtures

python experiments/run_step_part21_source_model.py \
  --fixture-dir output/fixtures/step-part21-source-model \
  --output-dir output/step-part21-source-model \
  --refresh-fixtures

python experiments/run_step_part21_conformance.py \
  --fixture-dir output/fixtures/step-part21-conformance \
  --output-dir output/step-part21-conformance \
  --refresh-fixtures

python experiments/run_express_schema_model.py \
  --fixture-dir output/fixtures/express-schema-model \
  --output-dir output/express-schema-model \
  --refresh-fixtures

python experiments/run_express_symbol_resolution.py \
  --fixture-dir output/fixtures/express-symbol-resolution \
  --output-dir output/express-symbol-resolution \
  --refresh-fixtures

python experiments/run_step_express_validation.py \
  --fixture-dir output/fixtures/step-express-validation \
  --output-dir output/step-express-validation \
  --refresh-fixtures
```

## Deterministic Controls

- Synthetic source images are generated in code.
- Repeated-noise studies use fixed random seeds.
- Runtime dependencies are pinned in `pyproject.toml`.
- Fixed JPEG streams and lossless reference decodes are committed under
  `fixtures/`.
- Fixture manifests record hashes and declared structural relationships.
- Observation and summary CSV files are generated from the same experiment
  run as their PNG figures.
- Resource-boundary fixtures are generated in memory from fixed bytes and
  exercise exact-limit and limit-plus-one relations without external data.
- Metadata-coverage fixtures generate EXIF thumbnail, Extended XMP, IPTC IIM,
  and maker-note relationships entirely in memory.
- Transform-integrity fixtures generate inherited, renewed, stale, missing,
  malformed, duplicate, and tampered unsigned assertions in memory.
- Policy-composition fixtures evaluate nine controlled conditions under four
  explicit profiles and serialize every ordered decision trace.
- STEP fixtures generate exact Part 21 bytes for closed, open, disconnected,
  surface-catalog, unresolved-reference, and duplicate-identifier conditions.
- The STEP fixture manifest records exact byte lengths, SHA-256 hashes,
  expected routing decisions, topology counts, and free-edge counts.
- Advanced Part 21 fixtures isolate named and repeated DATA sections, complex
  entities, direct UTF-8, binary values, anchors, external references,
  signatures, invalid structures, nesting, and ZIP container recognition.
- The geometry-bearing Part 21 control is committed with a preview generated
  from its declared synthetic tetrahedron coordinates.
- The unified Part 21 corpus preserves raw token spellings, comments,
  whitespace, character and UTF-8 byte positions, localized failures, and
  explicit nesting and token-length limits.
- The v0.23 geometry control is byte-identical to the v0.21 closed tetrahedron,
  so one shape tests the shared parser and the existing topology adapter.
- The v0.24 corpus generates 34 exact edition, lexical, section, declaration,
  signature, and ZIP inputs with SHA-256 hashes and expected reason codes.
- External parser comparisons run each fixture in an isolated child process
  against two exact public repository revisions; parser acceptance is never
  used as the conformance oracle.
- The v0.25 corpus generates 40 exact ASCII EXPRESS sources with SHA-256
  hashes, expected routes, explicit parser limits, and no external schema or
  data dependency.
- Accepted EXPRESS sources reconstruct exactly; inventory and coverage tables
  preserve the boundary between parsed declarations, opaque expression or
  algorithm envelopes, and deferred semantic stages.
- The v0.26 corpus generates 38 exact ASCII EXPRESS sources and preserves
  stable symbol IDs, every reference candidate, type-alias and inheritance
  graph states, aggregate-bound provenance, and semantic resource limits.
- The v0.27 corpus generates 40 exact STEP/EXPRESS pairs with independent
  hashes and retains stage, DATA-schema, instance, parameter, diagnostic, and
  resource-limit evidence.
- CI compares regenerated CSV and fixture data with committed references.

PNG files are checked for successful generation. CSV and fixture comparisons
carry the deterministic equality contract because rendering metadata can vary
between plotting environments.

## Cross-Platform Matrix

GitHub Actions records JPEG decoder observations with Python 3.12 on five
profiles:

1. Ubuntu x64 with the default SIMD path
2. Ubuntu x64 with `JSIMD_FORCENONE=1`
3. Windows x64
4. macOS arm64
5. macOS Intel x64

Each profile uploads its observation tables. A separate Ubuntu job downloads
the five artifacts, aggregates codec, syntax, metadata, recovery, metadata
round-trip, multi-generation policy, field-level retention, and
resource-boundary, metadata-family coverage, transform-integrity, and composed-policy reports. Existing
stable CSV outputs are compared with committed cross-platform references;
the v0.18 through v0.20 aggregates validate all fixture contracts during the
workflow.

For the resource-boundary study, the aggregate requires 24 fixture contracts
and five observations per contract. It checks decision, reason-code, issue,
work-counter, and fixture-hash multiplicity. Runtime manifests remain
provenance records rather than byte-stable contracts because hosted runner
image identifiers can change independently of the controlled result.

This matrix cannot be reproduced as a genuine cross-platform observation from
one local machine. A local `--platform-label` records provenance but does not
substitute for the five runner environments.

## Tests

```bash
python -m pytest
```

The 140 tests cover:

- Laplacian variance and Tenengrad behavior
- tiled and sliding-window aggregation
- optical blur kernels and deterministic transforms
- preprocessing, photometric, resize, and JPEG operations
- JPEG marker, quantization-table, syntax, and metadata parsing
- fixed-fixture hashes and decoded-pixel contracts
- repeated preserve, normalize, and strip policy relationships
- field-level metadata extraction and selective-retention relationships
- exact-limit, over-limit, syntax, and framing decisions for bounded metadata
  admission
- complete, reordered, missing, duplicate, orphaned, and out-of-bounds nested
  metadata relationships
- image-core, normalized-metadata, and decoded-pixel digest bindings across
  inherited, renewed, stale, missing, malformed, and duplicate assertions
- ordered resource, coverage, opacity, integrity, and retention traces across
  four explicit policy profiles
- bounded Part 21 tokenization, resource decisions, broken references,
  duplicate identifiers, topology ownership, edge incidence, face adjacency,
  and declared surface parameters
- advanced exchange section order, repeated DATA bindings, complex entities,
  direct UTF-8 and binary values, anchors, inert external references,
  unverified signatures, ZIP recognition, and parser limits
- exact Part 21 source reconstruction, trivia retention, character and UTF-8
  byte spans, simple and subsuper records, forward references, localized
  syntax diagnostics, and source-model resource limits
- Part 21 edition floors, implementation levels, conformance classes, legacy
  string controls, direct UTF-8, strict real and occurrence syntax, bounded ZIP
  intake, and deterministic conformance fixtures
- EXPRESS trivia and token coordinates, exact source reconstruction, bounded
  lexical failures, schema and interface declarations, aliases, aggregates,
  selects, enumerations, inheritance, explicit, derived, and inverse
  attributes, constants, and algorithm envelopes
- deterministic EXPRESS fixture routes, inventory counts, source hashes,
  resource limits, and explicit deferred semantic states
- case-insensitive EXPRESS symbols, direct `USE` and `REFERENCE` imports,
  aliases, select members, aggregate bounds, inheritance diamonds and cycles,
  qualified redeclarations, inverse links, and explicit ambiguous or
  invalid-kind references
- schema-bound Part 21 DATA sections, internal inheritance parameter order,
  optional and derived markers, scalar and aggregate values, select wrappers,
  forward and subtype-compatible occurrence references, and explicit complex-
  mapping deferral
- experiment output schemas
- cross-platform summary and aggregation logic

## Repository Layout

```text
.
|-- .github/workflows/ci.yml
|-- docs/
|   |-- reproducibility.md
|   `-- studies.md
|-- experiments/
|   |-- run_*.py
|   `-- summarize_*.py
|-- fixtures/
|   |-- advanced-jpeg-syntax/
|   |-- color-metadata-contracts/
|   |-- jpeg-decoder-contracts/
|   |-- malformed-jpeg-metadata/
|   |-- express-schema-model/
|   |-- express-symbol-resolution/
|   |-- step-express-validation/
|   |-- step-part21-source-model/
|   |-- step-part21-conformance/
|   |-- step-part21-exchange/
|   `-- step-brep-topology/
|-- notes/
|   `-- *.md
|-- results/
|   |-- README.md
|   |-- *.csv
|   `-- *.png
|-- src/research_notes/
|-- tests/
|-- LICENSE
|-- README.md
`-- pyproject.toml
```

## Compatibility Boundary

The project does not promise identical decoded arrays for dependency versions,
codec builds, hardware paths, or runner images that are not recorded in the
committed manifests. Cross-platform findings are regression evidence for the
fixed corpus and pinned release matrix. The STEP parsers have no geometry-
kernel dependency and promise only the controlled subsets documented by
v0.21.0 through v0.27.0. They do not imply complete ISO 10303-21, EXPRESS, or
AP242 conformance and do not authorize external resource retrieval, signature
trust, archive extraction, semantic execution, or evaluated geometry claims.
