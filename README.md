# Research Notes

## 日本語概要

このリポジトリは、画像処理に関する研究課題、文献調査、仮説、統制実験、結果、考察、制約を継続的に記録する研究ノートです。

研究テーマは、ぼけ評価と局所化、前処理や圧縮による評価値の変化、JPEGの復号・メタデータ・環境間互換性です。現在の研究では、正常・不正・曖昧なメタデータを持つ同じ合成画像に対し、保存・除去・正規化・拒否の方針を比較し、バイト保持、意味保持、厳格な検査、復号画素を分けて評価しています。

入力が同じなら同じ結果を生成するテストデータ、CSV・PNG成果物、固定した依存関係、テスト、5種類の環境を使った互換性検証を含みます。研究ごとの結果、再現手順、主張できる範囲は、以下の英語本文と個別ノートを参照してください。

---

Reproducible image-processing studies that connect a focused question to
source review, controlled experiments, committed evidence, interpretation,
and explicit claim boundaries.

## Overview

This repository records a sequence of related technical investigations rather
than a fixed algorithm showcase. Each published study includes a research
question, controlled inputs, versioned experiment code, CSV observations, PNG
figures, interpretation, and limitations.

The work starts with blur heuristics, then tests spatial aggregation,
preprocessing, optical and photometric effects, JPEG compression history,
decoder portability, metadata interpretation, malformed-metadata recovery,
and metadata round-trip policies. The current release is v0.14.0.

Unlike `vision-playground`, which compares image-processing methods as a stable
experiment suite, this repository preserves how questions, controls, evidence,
and claim boundaries evolve from one study to the next.

## Research Themes

| Theme | Studies | Central question |
| --- | --- | --- |
| Blur measurement and localization | v0.1.0–v0.4.0 | How do noise, spatial aggregation, and window geometry change Laplacian variance and Tenengrad responses? |
| Processing-pipeline sensitivity | v0.5.0–v0.8.0 | How do preprocessing, optical blur, photometric transforms, and JPEG history move scores and fixed calibration rules? |
| JPEG codec and metadata contracts | v0.9.0–v0.14.0 | Which byte, pixel, metadata, recovery, and sanitization behaviors remain stable across encoders, decoders, syntax variants, policies, and recorded CI environments? |

The [study index](docs/studies.md) maps all 14 releases to their questions,
representative findings, artifacts, commands, and complete notes.

## Representative Result

The v0.14.0 study applies four explicit metadata policies to the 21-fixture
v0.13.0 corpus after fixed Pillow or OpenCV re-encoding. It measures complete
input-envelope bytes, supported EXIF and ICC semantics, strict output
acceptance, the compressed JPEG core, and raw decoded pixels separately.

| Policy | Outputs per encoder | Strict accepted | Supported EXIF / ICC retained |
| --- | ---: | ---: | ---: |
| preserve | 19 / 21 | 5 / 19 | 2 / 2 |
| strip | 19 / 21 | 19 / 19 | 0 / 2 |
| normalize | 19 / 21 | 19 / 19 | 2 / 2 |
| reject | 5 / 21 | 5 / 5 | 2 / 2 |

![JPEG metadata round-trip policy contracts](results/jpeg_metadata_round_trip.png)

All 124 emitted local outputs retained the exact re-encoded JPEG core and raw
pixels of their policy-free control. Preserve also copied every available
controlled envelope, including rejected metadata: byte preservation is not
the same contract as validation or semantic correctness. These counts apply
only to the fixed synthetic corpus and pinned builds. The five-profile matrix
repeated all 840 observations with one behavior signature per contract and no
within-contract JPEG-byte or decoded-pixel hash variation.

## Claim Boundaries

- The studies use small, 8-bit synthetic images rather than a representative
  natural-image benchmark.
- Metric responses are relative to declared controls. They are not universal
  blur thresholds, perceptual scores, or proof that one metric is superior.
- The malformed-metadata corpus is not a fuzzer, vulnerability assessment,
  resource benchmark, or memory-safety proof.
- The metadata normalizer supports only EXIF Orientation and complete embedded
  ICC profiles; it is not a general-purpose metadata sanitizer.
- Cross-platform observations describe pinned wheels on recorded GitHub-hosted
  runner images. They do not guarantee identical behavior for other builds.
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

- Committed reference evidence: [`results/`](results/)
- Artifact catalog: [`results/README.md`](results/README.md)
- Fixed decoder inputs and declared references: [`fixtures/`](fixtures/)

## Key Features

- Fourteen published studies with explicit questions, controls, results, and
  limitations
- Programmatically generated blur, noise, window, preprocessing, optical, and
  photometric conditions
- Fixed JPEG fixtures for syntax, chroma sampling, color metadata, malformed
  metadata, trailing data, resource-policy controls, and round-trip policies
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
hashes, pairwise code-value differences, and cross-platform agreement.

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

The repository contains 56 tests covering blur metrics and models,
preprocessing and photometric transforms, JPEG parsing, fixed-fixture
contracts, experiment outputs, and cross-platform summary logic.

GitHub Actions runs the tests and regenerates the reference evidence on Ubuntu
with Python 3.12. Separate jobs record JPEG observations on Ubuntu x64 default
and scalar paths, Windows x64, macOS arm64, and macOS Intel x64 before
aggregating the combined reports.

## Compatibility

Python 3.11 or newer is required. Python 3.12 and the exact runtime versions in
`pyproject.toml` define the reference environment. Cross-platform conclusions
apply only to the runner images and bundled codec builds recorded in the
manifests.

## Roadmap

- Evaluate field-level retention policies for XMP, IPTC, EXIF thumbnails, and
  unknown APP data without claiming complete metadata semantics.
- Evaluate adaptive or multiscale aggregation without treating overlapping
  windows as independent evidence.
- Extend global point-spread-function controls to spatially varying defocus and
  non-uniform motion without treating synthetic labels as measured camera
  truth.
- Replicate selected controls on a traceable public image set with labels.

The roadmap is exploratory and does not represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
