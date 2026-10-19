# CAD kernel / platform choice — 2026-10-19

Japanese interpretation and proposed direction: [cad-platform-selection.md](../../notes/cad-platform-selection.md).

This is a bounded local pilot, not a product ranking or a hole-recognition
benchmark. SolidCraft, SolidCore and ClassCAD were source-reviewed only.
No ClassCAD account, key, engine activation or paid plan was used.

## Evidence

| File | Recorded scope |
| --- | --- |
| [summary.json](summary.json) | Derived counts, differences, integration comparison and Unicode name observations |
| [primitives.json](primitives.json) | 6 independently constructed shapes × 3 backends = 18 task observations; analytic volume/area expectations |
| [intake.json](intake.json) | 64 fixed STEP inputs × 3 reader modes = 192 observations |
| [intake-matrix.csv](intake-matrix.csv) | All input/reader rows, not just agreements |
| [roundtrip.json](roundtrip.json) | 6 inputs × 2 writers, then 2 readers per export = 36 observations |
| [roundtrip-archive.json](roundtrip-archive.json) | Original runtime paths, archived re-export paths, writer, input and byte hashes |
| [accuracy.json](accuracy.json) | 5 inputs × original and 2 exports = 15 OCCT integration tasks; 14 complete, one CPU-limit termination |
| [metadata.json](metadata.json) | Japanese-name box read/write through OCCT/XDE and smlibpy, 2 observations |
| [sources.json](sources.json) | Source snapshots, retrieval outcomes, package versions, installed native binary hashes and evidence digests |

All 263 observations are retained, including the incomplete measurement. `ok`
means the task completed; it is not a certification of geometry or recognition.
The one `process_failed` record has exit code `-24` (Linux SIGXCPU), for
`accuracy-build123d_screw-from-smlibpy`. Its multiple integration calls did not
complete within the CPU budget. The recorded payload has no partial results.
It is not counted as a STEP reader failure.

The 64 inputs comprise 44 robustness controls, 12 numerical controls, 6 public
STEP files and 2 certified plates. Public SAM AP203/AP214 are a paired part,
not independent designs. Most synthetic inputs originated in OCCT. These are
not a representative CATIA/NX/SOLIDWORKS customer population.

## Runtime and comparison conditions

- Linux/WSL x86_64, Python 3.12.14; OCCT via `cadquery-ocp==7.9.3.1.1`.
- Isolated environments: `usd-brep==1.0.0`, `smlibpy==0.3.5` (NumPy 2.4.6).
- Each native task runs in a new child: 4 GiB address-space limit, CPU soft/hard
  30/31 seconds, 40-second wall timeout, core dumps disabled. These are Linux
  resource limits, not measurements of peak memory.
- Two workers per group; BLAS/OpenMP thread count set to one. One recorded
  observation per task; exploratory runs were made before freezing this code.
  Timings include different work and process startup, so they are not a speed
  comparison.
- Intake uses direct native readers. Production Part 21, unit, reference and
  eligibility checks are bypassed for this experiment. Existing admission
  outcomes are not replaced by these reader results.
- OCCT uses BRepCheck; SMLib-derived validity is not an identical predicate.
  A validity flag alone cannot certify equivalent geometry.
- `smlibpy` includes patches, its own STEP conversion and custom integration.
  Its results are not attributed to an unmodified NVIDIA official API.
- Cylindrical supports are diagnostic surface records, not detected holes.
  No SMLib hole-recognition implementation was created.
- Relative volume difference `>1e-6` and bbox coordinate difference `>1e-4 mm`
  only select intake diagnostics against OCCT's default calculation. OCCT
  default integration is not ground truth. Integration epsilon is not a length
  tolerance. Matching volume/bounds does not prove matching local surfaces.
- The Unicode fixture uses OCCT/XDE's correct UTF-8 string constructor.
  Observations do not establish support for every STEP string encoding. Color
  values are recorded without judging equality across color spaces.

## Reproduce

Run on Linux/WSL from the repository root, after preparing the existing
Python 3.12 geometry environment. The commands below create separate research
environments; they do not add packages to the production environment.

```bash
output/venv312/bin/python -m venv output/kernel-comparison-2026-10-19/official-env
output/kernel-comparison-2026-10-19/official-env/bin/python -m pip install usd-brep==1.0.0
output/venv312/bin/python -m venv output/kernel-comparison-2026-10-19/smlibpy-env
output/kernel-comparison-2026-10-19/smlibpy-env/bin/python -m pip install smlibpy==0.3.5 numpy==2.4.6

output/venv312/bin/python experiments/run_cad_kernel_probe.py --group primitives
output/venv312/bin/python experiments/run_cad_kernel_probe.py --group intake
output/venv312/bin/python experiments/run_cad_kernel_probe.py --group roundtrip
output/venv312/bin/python experiments/run_cad_kernel_probe.py --group accuracy
output/venv312/bin/python experiments/run_cad_kernel_probe.py --group metadata
python3 experiments/summarize_cad_kernel_probe.py
```

`roundtrip` must precede `accuracy`. Interpreters can be overridden with
`--occt-python`, `--smlibpy-python` and `--usd-brep-python`. The probe defaults to
`primitives`, not all groups. For a separate exploratory output, use
`--output-dir output/cad-kernel-recheck`; the summarizer validates the committed
result directory by default. The production package must be available to the
OCCT interpreter, as in the existing editable geometry environment.

To validate the recorded results without rerunning native kernels:

```bash
python3 experiments/summarize_cad_kernel_probe.py
```

The summarizer checks task counts, process outcomes, source hashes, probe hash
and archived re-exports. On a clean checkout it resolves ignored intermediate
paths to the committed [archive](roundtrip-archive.json). A reproduction may
write timestamps or change native traversal ordering; byte-identical regenerated
STEP is not promised. Replacing the recorded run requires regenerating its
archive and provenance together. A changed failure or count should be examined,
not relabeled as agreement.

The source provenance includes one failed fetch for `docs/ROADMAP.md` (404).
The real SolidCraft `ROADMAP.md` at repository root was subsequently retrieved
and hashed. This failure is not evidence of a missing roadmap. Upstream source
text and package binaries are not vendored in this directory.

## Re-export attribution and licenses

Files in `roundtrip/` are **modified derivatives**, re-exported on 2026-10-19
with the backend named in each filename. They are not the original upstream
files and are not certified production replacements. Geometry-only OCCT exports
do not preserve document attributes. Input/writer/path mappings and hashes are
listed individually in [roundtrip-archive.json](roundtrip-archive.json).

| Re-export filename prefix (both `-occt.step` and `-smlibpy.step`) | Original and terms |
| --- | --- |
| `build123d_bracket`, `build123d_screw` | gumyr/build123d, commit `17999d509ea0b08a6b45cb9bf71f6a7c9cc5dbc1`; [Apache-2.0](../../fixtures/public-step-corpus/licenses/build123d/LICENSE) and [NOTICE](../../fixtures/public-step-corpus/licenses/build123d/NOTICE) |
| `ublox_sam_ap203` | u-blox/3D-Step-Models-Library, commit `ac8778fbdcb8faa7d722bc52877f9d17d557a330`; [original permission and disclaimer](../../fixtures/public-step-corpus/licenses/3D-Step-Models-Library/LICENSE.txt) |
| `circle_spline`, `slot_spline`, `single` | This repository's generated controls; [project licensing](../../LICENSING.md) |

Original source URLs and attribution are retained in the
[public corpus manifest](../../fixtures/public-step-corpus/manifest.json) and
[corpus README](../../fixtures/public-step-corpus/README.md). External asset
terms remain independent of this repository's license. Keep the matching notices
with redistributed derivatives; no upstream endorsement is implied.
`unicode-*.step` are newly authored box controls under this repository's terms.
