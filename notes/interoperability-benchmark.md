# Parser, Importer and Geometry Interoperability Benchmark

## 日本語概要

v0.90.0では、固定した11サンプルを3種類のパーサーで比較し、形状を扱う7サンプルを2種類の読込経路で比較しました。構文の判定は9件で一致し、2件で分かれました。形状の体積・面積・位相数・境界寸法は7件とも許容範囲内で一致しました。同じOCCTを使う2経路なので、異なる幾何エンジン間の一致を意味しません。詳細は英語本文に示します。

---

## English Summary

Which observations agree across independently implemented syntax parsers,
different transfer interfaces and eligible geometry arithmetic routes? Eleven
hash-pinned sources separate syntax, supplied-schema validity, application
semantics, geometry and attributes. Agreement is never used as majority-vote truth.

## Fixed Inputs and Routes

Inputs include three authored named/colored shapes, the licensed CadQuery
assembly, build123d bracket, u-blox SAM AP203/AP214 files, an invalid exponent,
an edition-3 anchor, and two controlled EXPRESS scalar cases. The
[input manifest](../fixtures/interoperability-benchmark/inputs.json) records source
and sidecar hashes, parser commits, eligibility and expected syntax outcomes.
Public sources retain their original bytes and [upstream licenses](../fixtures/public-step-corpus/README.md).

| Layer | Routes | Scope |
| --- | --- | --- |
| Syntax | Repository Part 21 parser; steputils; IfcOpenShell step-file-parser | 11 sources; external parsers have fixed commits |
| Schema | Repository bounded EXPRESS validator with two supplied sidecars | One valid and one invalid scalar case; no full public AP schemas |
| Semantics | Repository explicit AP profiles | Resolved subset, partial or unsupported; not recovered design history |
| Import | STEPControl geometry transfer; STEPCAF/XCAF transfer | Seven geometry sources, explicit millimetre normalization |
| Geometry | Native GProp; signed tetrahedral integration over a mesh | Three eligible single closed solids; same OCCT tessellator |
| Attributes | XCAF free-root names and color table | STEPControl route does not expose these fields |

IfcOpenShell's parser is invoked in `with_tree=False` validation mode. It returns
no entity tree/count; this is explicitly recorded. This is the standalone
step-file-parser, not IfcOpenShell's IFC geometry engine. External processes have
a 30-second timeout; missing dependencies, adapter faults and timeouts are
reported as errors, not syntactic rejections. Tracked changes or wrong commits
in the pinned parser checkouts prevent the benchmark from running.

## Observations

| Control or comparison | Result |
| --- | --- |
| Syntax outcomes | 9 agreements and 2 disagreements among 11 sources |
| Invalid real exponent | Repository and IfcOpenShell parser reject; steputils accepts |
| Edition-3 anchor | Repository accepts; both pinned external parsers reject |
| Invalid scalar type | All syntax routes accept; supplied EXPRESS validation rejects |
| Seven native geometry comparisons | All match declared volume/area/count/bounds invariants |
| Named box attributes | XCAF observes `Controlled Box` and RGB approximately (0.85, 0.15, 0.10) |
| Mesh volume vs GProp: box | Relative difference about 1.5e-16 |
| Mesh volume vs GProp: through-hole | Relative difference about 5.02e-5 (0.0050%) |
| Mesh volume vs GProp: bracket | Relative difference about 3.32e-4 (0.0332%) |

Mesh comparisons pass the declared 0.1% relative volume budget. Freeform shells
and multi-solid compounds are explicitly ineligible for this single-solid
integrator. Approximation differences remain numeric evidence rather than being
rounded to zero or equated with parser failure.

Native comparisons require matching unique vertex/edge/face/shell/solid counts,
volume and area within `max(1e-6, 1e-6 * reference)`, and bounds within 1e-4 mm.
Tolerance differences are recorded separately. Authored analytic truth checks
the 24 mm³ / 52 mm² box and the upstream cube-plus-cylinder assembly volume
`1000 + 250*pi` mm³. These anchors avoid relying exclusively on mutual agreement.

## Boundaries

STEPControl and STEPCAF both use OCCT 7.9.3, via cadquery-ocp 7.9.3.1.1. Their
agreement covers two transfer interfaces, not two independent geometry kernels.
Mesh integration has independent arithmetic but shares OCCT's tessellation.
Matching counts and aggregate measurements do not prove pointwise equivalence,
correct assembly identity or complete attribute binding. Previously recorded
SAM trim inconsistencies remain outside these aggregate gates.

The reference execution uses Python 3.12.14 on Linux/WSL x86_64. Exact versions,
kernel information and dependency pins are in the generated
[environment record](../results/interoperability_benchmark_environment.json).
It describes one execution; v0.91 cross-platform validation remains future work.
The benchmark reports supported subsets, not complete STEP/AP conformance.

## Reproduce and Primary Sources

After installing `.[comparison,geometry,test]` and checking out the pinned
parsers as described in [reproducibility](../docs/reproducibility.md), execution
is offline:

```bash
python experiments/run_interoperability_benchmark.py
python -m research_notes.integrated_tool
```

At the `3d>` prompt, run `benchmark interop`.

- [CSV](../results/interoperability_benchmark.csv)
- [Detailed route observations](../results/interoperability_benchmark_evidence.json)
- [HTML report](../results/interoperability_benchmark.html)
- [steputils at the tested commit](https://github.com/mozman/steputils/tree/547860b349a36cf24c564d6c87ffd8f60484f6fb)
- [IfcOpenShell step-file-parser at the tested commit](https://github.com/IfcOpenShell/step-file-parser/tree/9400d243d880dace57490949d74ab1932ce99a09)
- [OCCT STEP transfer documentation](https://github.com/Open-Cascade-SAS/OCCT/wiki/step/efce7e8822af84fda44c206f469eba56ee0907d4)
- [Benchmark implementation](../src/research_notes/interoperability_benchmark.py)
