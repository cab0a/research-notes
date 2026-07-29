# Reproducibility

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
```

The [study index](studies.md) maps every command to its research note and main
artifacts.

## Fixed Fixture Refresh

The decoder-contract experiments can recreate their fixed inputs in a separate
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
the five artifacts, aggregates codec, syntax, metadata, recovery, and metadata
round-trip policy reports, then compares the stable CSV outputs with the
committed cross-platform references.

This matrix cannot be reproduced as a genuine cross-platform observation from
one local machine. A local `--platform-label` records provenance but does not
substitute for the five runner environments.

## Tests

```bash
python -m pytest
```

The 56 tests cover:

- Laplacian variance and Tenengrad behavior
- tiled and sliding-window aggregation
- optical blur kernels and deterministic transforms
- preprocessing, photometric, resize, and JPEG operations
- JPEG marker, quantization-table, syntax, and metadata parsing
- fixed-fixture hashes and decoded-pixel contracts
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
|   `-- malformed-jpeg-metadata/
|-- notes/
|   `-- *.md
|-- results/
|   |-- README.md
|   |-- *.csv
|   `-- *.png
|-- src/research_notes/
|-- tests/test_blur_metrics.py
|-- LICENSE
|-- README.md
`-- pyproject.toml
```

## Compatibility Boundary

The project does not promise identical decoded arrays for dependency versions,
codec builds, hardware paths, or runner images that are not recorded in the
committed manifests. Cross-platform findings are regression evidence for the
fixed corpus and pinned release matrix.
