# Reproducibility

## 日本語概要

本書は、37件の研究ノートの合成画像・合成STEP・合成EXPRESS、固定した実験条件、CSV・JSON・図、実行環境を再現する手順を定義します。画像・JPEG・メタデータ・STEP・EXPRESS・AP242、形状計算核、面・辺・輪郭線・外殻・立体、許容差付き縫合に加え、辺使用回数、頂点リンク、接触次元、重複、横断交差の検証と互換性境界をまとめています。

現在と今後の公開版には研究・教育・個人的実験向けのPolyForm Noncommercial License 1.0.0を適用し、商用利用には書面による別ライセンスが必要です。過去版の事実は`LICENSING.md`に分離しています。

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
python -m pip install -e ".[comparison,geometry,test]"
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
python experiments/run_step_graph_queries.py
python experiments/run_ap242_product_paths.py
python experiments/run_ap242_assembly.py
python experiments/run_geometry_kernel_selection.py
python experiments/run_evaluated_face_geometry.py
python experiments/run_edge_curve_evaluation.py
python experiments/run_wire_trimming_evaluation.py
python experiments/run_shell_solid_validity.py
python experiments/run_tolerance_sewing_healing.py
python experiments/run_manifold_self_intersection.py
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

python experiments/run_step_graph_queries.py \
  --fixture-dir output/fixtures/step-graph-queries \
  --output-dir output/step-graph-queries \
  --refresh-fixtures

python experiments/run_ap242_product_paths.py \
  --fixture-dir output/fixtures/ap242-product-paths \
  --output-dir output/ap242-product-paths \
  --refresh-fixtures

python experiments/run_ap242_assembly.py \
  --fixture-dir output/fixtures/ap242-assemblies \
  --output-dir output/ap242-assemblies \
  --refresh-fixtures

python experiments/run_geometry_kernel_selection.py \
  --fixture-dir output/fixtures/geometry-kernel-selection \
  --output-dir output/geometry-kernel-selection \
  --refresh-fixtures

python experiments/run_evaluated_face_geometry.py \
  --fixture-dir output/fixtures/evaluated-face-geometry \
  --output-dir output/evaluated-face-geometry \
  --refresh-fixtures

python experiments/run_edge_curve_evaluation.py \
  --fixture-dir output/fixtures/edge-curve-evaluation \
  --output-dir output/edge-curve-evaluation \
  --refresh-fixtures

python experiments/run_wire_trimming_evaluation.py \
  --fixture-dir output/fixtures/wire-trimming-evaluation \
  --output-dir output/wire-trimming-evaluation \
  --refresh-fixtures

python experiments/run_shell_solid_validity.py \
  --fixture-dir output/fixtures/shell-solid-validity \
  --output-dir output/shell-solid-validity \
  --refresh-fixtures

python experiments/run_tolerance_sewing_healing.py \
  --fixture-dir output/fixtures/tolerance-sewing-healing \
  --output-dir output/tolerance-sewing-healing \
  --refresh-fixtures

python experiments/run_manifold_self_intersection.py \
  --fixture-dir output/fixtures/manifold-self-intersection \
  --output-dir output/manifold-self-intersection \
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
- The v0.31 OCCT box fixture normalizes only the generated timestamp and
  process counter. Repeated generation must otherwise remain byte-identical,
  and the manifest records its exact hash and generator versions.
- The v0.32 analytic-face fixture narrowly normalizes the same header and
  process fields plus three writer-generated compound occurrence numbers.
  Independent formulas define plane and cylinder truth, while the fixture
  manifest binds the normalized bytes to the pinned backend versions.
- The v0.33 edge-curve fixture applies the same narrow normalization to one
  plane, one partial cylinder, and one full cylinder. Independent formulas
  define boundary types, lengths, parameter spans, and UV paths; the fixture
  retains the explicit STEP edge-curve, surface-curve, p-curve, and seam
  representations.
- The v0.34 wire-trimming fixture applies the same narrow normalization to two
  planar frames, one full cylinder, and one natural sphere. Independent
  formulas define material area, centroid, restricted UV bounds, and signed
  loop areas. Connection order, point classification, seams, pole degeneracy,
  and stage-specific kernel flags are observed separately.
- The v0.35 shell/solid corpus applies the narrow header normalization to seven
  separate STEP files. Independent controls define V/E/F, face components,
  edge incidence, closure, orientability, Euler characteristic, and analytic
  volume magnitude. Generic analyzer, shell-specific status, signed volume,
  and STEP reorientation or shell splitting remain separate observations.
- The v0.36 tolerance/sewing corpus generates ten normalized STEP samples from
  three gap controls, selected sewn outputs, orientation controls, and one
  rejected tolerance-cap output. The in-memory operation log is authoritative
  for repair effects because STEP re-import may normalize local tolerance and
  validity state.
- The v0.37 manifoldness/intersection corpus generates 12 normalized STEP
  samples for vertex-link topology, single-argument edge/face interference, and
  geometric relationship controls. Independent topology and measure
  expectations remain separate from checker, minimum-distance, Boolean common-
  part, section, and STEP-stage observations. The checker cases aggregate two
  independent edges or faces; they do not generate one self-crossing
  parametric curve or supporting surface.
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
- The v0.28 corpus generates 14 exact STEP files with independent hashes and
  retains stable graph-local IDs, source-linked reference occurrences, target
  scopes, traversal roots, graph budgets, query limits, and versioned JSON.
- The v0.29 corpus generates 14 exact STEP files with independent hashes and
  retains product paths, source-linked semantic roles, direct representation
  items, geometric context, assigned units, diagnostics, work budgets, and
  versioned JSON.
- The v0.30 corpus generates 17 exact STEP files with independent hashes and
  retains occurrence identities, child-to-parent and root-relative matrices,
  source-linked semantic roles, normalized length units, diagnostics, work
  budgets, and versioned JSON.
- CI compares regenerated CSV, JSON, and fixture data with committed references.

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

The 255 tests cover:

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
- stable Part 21 graph nodes, repeated reference edges, nested parameter paths,
  nonlocal target scopes, forward and reverse traversal, query-relative
  orphans, strongly connected components, graph limits, and deterministic JSON
- controlled AP242 product-definition, shape-definition, representation,
  context, direct-item, placement, and assigned-unit paths with exact physical
  edge provenance and explicit schema, subset, invalidity, and work boundaries
- controlled AP242 definition reuse, occurrence identity, child-to-parent
  transform direction, rigid rotation, nested matrix composition,
  conversion-based length units, semantic cycles, and work boundaries
- geometry-backend gate selection, wrapper-versus-kernel identity, narrow OCCT
  writer normalization, headless box construction and STEP round trip, unique
  topology preservation, parser disagreement, and installed-package inventory
- independent plane and cylinder area, centroid, UV, point, normal, frame, and
  radius truth; constructed and STEP-imported face evaluation; reversed
  orientation; tolerance-stage separation; and deterministic fixture bytes
- line and circle edge truth, p-curves, parameter spans, oriented uses,
  periodic seams, ordered wire traversal, planar holes, face reversal,
  sphere-pole degeneracy, and point classification
- shell and solid incidence, components, closure, orientability, Euler,
  signed-volume gates, shell-specific status, and translator normalization
- requested-versus-stored sewing tolerance, per-subshape inventories,
  orientation repair, rejected tolerance caps, and geometry-preservation checks
- vertex-link components and degrees, edge-versus-vertex nonmanifold controls,
  single-argument edge/edge, edge/face, and face/face interference, geometric
  contact dimension, common-part measures, section lengths, and STEP-stage
  preservation
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
|   |-- ap242-assemblies/
|   |-- ap242-product-paths/
|   |-- geometry-kernel-selection/
|   |-- evaluated-face-geometry/
|   |-- manifold-self-intersection/
|   |-- step-graph-queries/
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
|   |-- *.json
|   `-- *.png
|-- src/research_notes/
|-- tests/
|-- LICENSE
|-- LICENSING.md
|-- README.md
`-- pyproject.toml
```

## Compatibility Boundary

The project does not promise identical decoded arrays for dependency versions,
codec builds, hardware paths, or runner images that are not recorded in the
committed manifests. Cross-platform findings are regression evidence for the
fixed corpus and pinned release matrix. The STEP parsers remain independent of
the optional geometry backend and promise only the controlled subsets
documented by v0.21.0 through v0.30.0. v0.31.0 adds one pinned Linux x64 OCCT
box round trip, v0.32.0 evaluates three analytic faces, v0.33.0 evaluates
controlled line and circle edges, p-curves, parameter ranges, and one seam,
and v0.34.0 evaluates outer and inner wires, face reversal, periodic seams,
and sphere-pole degeneracy. v0.35.0 evaluates seven shell and solid validity
conditions, v0.36.0 evaluates controlled sewing, local tolerance changes, and
orientation repair, and v0.37.0 evaluates bounded polyhedral vertex links and
shape-pair relationship dimensions on the same route. None implies complete ISO
10303-21, EXPRESS, or AP242 conformance, cross-platform kernel portability,
redistribution permission, or general trimmed-face, spline, curved-shell
manifoldness, self-intersection, general repair, manufacturing tolerance, or
design-intent recovery.
