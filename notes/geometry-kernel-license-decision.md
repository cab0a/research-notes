# Geometry Kernel and License Decision

## 日本語概要

本研究は、STEPの仕様理解とPython解析器を保ったまま、面・辺・シェル・立体の幾何評価へ進むための形状計算核を選定します。8候補をSTEP交換、解析的B-rep、モデリング、Python利用、画面なし実行、再現可能な導入の6条件で比較し、`cadquery-ocp`経由のOpen CASCADE Technologyを、再配布しない任意の研究用依存として限定採用しました。10 × 20 × 30の合成箱はSTEP往復後も1立体・6面・12辺・8頂点を保ちました。ただし、Python結合部のApache-2.0とOpen CASCADE本体のLGPL-2.1追加例外は別の条件であり、導入物の標準ライセンス一覧から本体の告知文を確認できなかったため、バイナリ再配布は別途監査するまで対象外です。詳細、疑問点、出典は英語本文に示します。

---

## English Summary

This study selects CadQuery OCP and Open CASCADE Technology (OCCT) as an
optional, bounded research backend for evaluated geometry. It does not replace
the project's kernel-free Part 21 and EXPRESS layers. A headless synthetic box
retains one solid, six faces, twelve unique edges, and eight unique vertices
after an OCCT STEP write/read round trip. The Apache-2.0 binding and the
LGPL-2.1-with-additional-exception native kernel are separate license layers.
No third-party wheel or native library is committed, and binary redistribution
remains outside the selected scope until a separate compliance audit is
completed.

## Research Question

Which geometry-kernel route gives this Python research project a reproducible
path from parsed STEP records to evaluated analytic B-Rep geometry and later
modeling, while keeping license layers, package cost, provenance, and claim
boundaries explicit?

## Background

The project already parses a controlled Part 21 and EXPRESS subset, builds
source-linked reference graphs, and resolves selected AP242 product and
assembly paths. Those layers explain what the exchange file declares. They do
not numerically evaluate a trimmed surface, calculate an area, classify kernel
topology, test a B-Rep, or execute a modeling operation.

A geometry kernel supplies those operations, but it cannot establish that the
project's source interpretation is correct. The architecture therefore keeps
two evidence paths:

```text
Part 21 bytes -> source-preserving parser -> schema and semantic provenance
Part 21 bytes -> optional geometry kernel -> evaluated shape and modeling evidence
```

Agreement can strengthen a controlled claim. Disagreement must remain visible
rather than being silently resolved in favor of either path.

## Selection Requirements

The v0.31.0 comparison uses six technical gates:

1. Direct STEP exchange support.
2. Analytic B-Rep access rather than triangle meshes alone.
3. Construction and modeling operations.
4. A usable Python API.
5. Headless execution suitable for CI.
6. A pinned pip installation for the reference environment.

License identification, independent-kernel status, package footprint, and
redistribution questions are recorded separately. Passing technical gates is
not a license conclusion.

## Candidate Review

| Candidate route | Result | Main boundary |
| --- | --- | --- |
| CadQuery OCP with OCCT | Selected for bounded research | The Apache wrapper does not replace the native OCCT license; redistribution needs a separate audit |
| pythonocc-core with OCCT | Alternate route to the same kernel | Documented reference installation uses Conda rather than this project's pinned pip path |
| FreeCAD Python runtime | Application-runtime reference | Broad application dependency rather than the minimal library route |
| Gmsh OpenCASCADE API | Meshing reference | Valuable STEP and mesh workflow, not the selected direct face-inspection layer |
| CGAL | Computational-geometry reference | No project-qualified direct STEP-to-analytic-B-Rep Python route |
| Truck | Watch candidate | Independent Apache-2.0 B-Rep direction, but no maintained Python route and no official Linux support claim in the reviewed user book |
| Manifold | Mesh complement | Apache-2.0 Python route for manifold triangle meshes, not an analytic STEP B-Rep replacement |
| Parasolid | Commercial reference only | Commercial SDK without a publicly reproducible Python/pip reference route in this study |

The complete gate matrix and direct source links are committed in
[`geometry_kernel_candidates.csv`](../results/geometry_kernel_candidates.csv).
Only CadQuery OCP satisfies all six reference-environment gates. This is a
project decision under declared requirements, not a claim that it is the best
kernel for every application.

## License Stack

The selected route has distinct layers:

| Layer | Recorded terms | v0.31.0 treatment |
| --- | --- | --- |
| This repository | PolyForm Noncommercial 1.0.0 | Research, academic, educational, and personal experimental use; commercial use requires a separate written repository license |
| `cadquery-ocp` Python distribution | Apache-2.0 package metadata and wrapper license | Installed only as an optional experiment dependency |
| OCCT native libraries reached through the wrapper | LGPL-2.1 with the OCCT additional exception, according to the official OCCT licensing page | Used for the controlled local/CI probe; not committed or redistributed by this repository |
| VTK dependency pulled by the pinned wheel | BSD package metadata | Included in the installed-package inventory even though the probe does not use visualization |

The repository's commercial license, if obtained, would not override any
third-party obligation. Conversely, a permissive wrapper license does not
relicense the native libraries it loads.

The installed reference audit found one Apache license file for
`cadquery-ocp`, no license file for `cadquery-ocp-proxy`, and one BSD license
file for VTK through the standard Python distribution file records. That
inventory did not surface an OCCT LGPL notice. This is an observation about
the installed artifacts and audit method, not a finding of noncompliance. It
is sufficient reason for this project not to package or redistribute those
binaries without a dedicated legal and technical review.

## Controlled Experiment

The experiment performs these headless steps with pinned
`cadquery-ocp==7.9.3.1.1`:

1. Construct a 10 × 20 × 30 box with `BRepPrimAPI_MakeBox`.
2. Count unique solids, faces, edges, and vertices with indexed shape maps.
3. Run `BRepCheck_Analyzer` on the constructed shape.
4. Write STEP with `STEPControl_Writer`.
5. Normalize only the generated timestamp and process counter.
6. Read the committed bytes with `STEPControl_Reader`.
7. Repeat the unique topology counts and kernel validity check.
8. Submit the same bytes to the project's independent Part 21 parser.
9. Inventory distribution versions, declared licenses, recorded file sizes,
   requirements, and standard license-file paths without absolute paths.

The inventory excludes the zero-byte `REQUESTED` installer marker because pip
adds it according to direct-versus-transitive installation history rather than
third-party wheel payload content.

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_geometry_kernel_selection.py
```

All STEP bytes are generated by the experiment. No company, customer, or
third-party CAD model is used.

## Results

| Observation | Result |
| --- | --- |
| Compared candidates | 8 |
| Routes passing all six technical gates | 1 |
| Selected route | `cadquery-ocp` with OCCT |
| Binding distribution / module | 7.9.3.1.1 / 7.9.3.1 |
| Reported STEP processor | Open CASCADE STEP processor 7.9 |
| Constructed topology | 1 solid, 6 faces, 12 unique edges, 8 unique vertices |
| Imported topology | 1 solid, 6 faces, 12 unique edges, 8 unique vertices |
| Kernel checks | Constructed and imported shapes reported valid |
| Normalized STEP fixture | 15,416 bytes, SHA-256 `a418c0ce0f670673348a7bfe054ed3480a1e57b6c5851b63338871d8b8b94bea` |
| Recorded installed files | 940,567,380 bytes across the three pinned distributions |
| Internal Part 21 decision | Accept with `part21_parsed` under the v0.49.0 enumeration-token rule |

![Geometry-kernel selection evidence](../results/geometry_kernel_selection.png)

The package footprint is a sum of sizes recorded in the installed Python
distribution manifests. It is not download size, allocated disk space, memory
use, or runtime cost.

## Interpretation

The probe establishes a practical bridge to evaluated geometry: the selected
route can construct one known analytic solid, exchange it through STEP, recover
the expected unique topology, and run without a graphical interface. It also
shows why this release precedes face-level evaluation. The geometry dependency
is large, introduces native-code and license boundaries, and can emit syntax
that the project's strict Part 21 subset does not accept.

The v0.31.0 release originally recorded an internal-parser rejection at the
OCCT enumeration spelling `.PCURVE_S1.`. The v0.49.0 portability study exposed
the narrow token-rule omission against a fixed real writer output, expanded
the enumeration spelling to include underscores, and added a regression test.
The current regenerated observation therefore accepts the same committed
bytes. This update records parser evolution; it does not retroactively claim
that v0.31.0 covered the spelling when first released.

## Decision

CadQuery OCP with OCCT is selected under these conditions:

- It is an optional `geometry` dependency, not a dependency of the Part 21 or
  EXPRESS parser core.
- The repository commits only its own code, synthetic STEP bytes, manifests,
  observations, and figures—not third-party wheels or native libraries.
- v0.32.0 may use it to evaluate controlled face geometry and tolerances.
- A binary application, redistributed environment, installer, service image,
  or commercial product requires a fresh third-party license and notice audit.
- Independent analytical or numerical checks remain necessary; kernel output
  alone is not treated as truth.

## Failure Modes

- Treating the Apache-2.0 wrapper as the license for all loaded native code.
- Assuming that several Python wrappers provide independent kernel evidence
  when they all call OCCT.
- Counting shape occurrences with an explorer and reporting repeated edge or
  vertex visits as unique topology.
- Treating a successful STEP read as complete AP242, geometry, or topology
  conformance.
- Hiding writer-generated nondeterminism instead of narrowly normalizing and
  testing it.
- Treating a missing notice in one inventory method as proof of a license
  violation or as permission to redistribute.
- Selecting a mesh Boolean library as a drop-in replacement for analytic
  trimmed B-Rep evaluation.

## Practical Guidance

- Install the `geometry` extra only for geometry studies.
- Preserve source-linked parser evidence beside kernel-derived values.
- Record distribution, module, processor, platform label, and fixture hash for
  every reference result.
- Use indexed shape maps when a report promises unique topology counts.
- Keep redistribution decisions outside experiment code and document them as
  explicit release gates.
- Revisit an independent kernel family when a qualified Python route can run
  the same fixed corpus.

## Limitations

- This is an engineering decision record, not legal advice.
- Only one Linux x64 reference environment was measured locally.
- The probe uses one axis-aligned analytic box; it does not evaluate curved,
  trimmed, periodic, degenerate, invalid, or tolerance-sensitive geometry.
- Matching topology counts do not prove geometric equality, orientation,
  tolerance preservation, or semantic preservation.
- `BRepCheck_Analyzer` is an OCCT check, not independent validation.
- Candidate gates reduce complex projects to the needs of this repository and
  may change as public packages evolve.
- Proprietary commercial terms were not reviewed because they are not
  publicly reproducible inputs to this experiment.
- The installed-package inventory cannot establish every notice, source-code,
  relinking, patent, export, or downstream distribution obligation.

## Open Questions

1. What exact Part 21 or schema rule governs `.PCURVE_S1.`, and which public
   parsers accept the same OCCT output?
2. Can the geometry runtime be installed without the unused VTK payload while
   retaining an official, reproducible package path?
3. Which notices and source-access materials must accompany each planned form
   of binary distribution?
4. How should v0.32.0 independently verify area, centroid, UV bounds, normals,
   and tolerances for planar and cylindrical trimmed faces?
5. Which independent kernel family can later provide a genuinely independent
   portability comparison?

## Sources

- [OCCT licensing](https://dev.opencascade.org/resources/licensing) describes
  LGPL-2.1 plus the Open CASCADE additional exception for current OCCT
  releases.
- [OCCT overview and license obligations](https://dev.opencascade.org/doc/overview/html/index.html)
  provides the project's official distribution guidance.
- [CadQuery OCP repository](https://github.com/CadQuery/OCP) describes the thin
  OCCT Python wrapper; its [license file](https://github.com/CadQuery/OCP/blob/master/LICENSE)
  contains the Apache License 2.0 text.
- [cadquery-ocp on PyPI](https://pypi.org/project/cadquery-ocp/) provides the
  pinned release metadata and platform wheel inventory.
- [pythonocc-core](https://github.com/tpaviot/pythonocc-core) documents its
  OCCT-based Python route and Conda installation.
- [FreeCAD](https://github.com/FreeCAD/FreeCAD) documents its OCCT-based
  application and Python API; [FreeCAD licensing](https://www.freecad.org/contributing.php?lang=eng)
  states the project's license terms.
- [Gmsh reference manual](https://gmsh.info/doc/texinfo/) documents STEP,
  OpenCASCADE, Python, and headless interfaces; the [Gmsh project page](https://gmsh.info/?lang=en)
  states its dual licensing route.
- [CGAL licensing](https://doc.cgal.org/latest/Manual/license.html) describes
  package-specific open-source terms and commercial licensing.
- [Truck repository](https://github.com/ricosjp/truck) and
  [Truck user book](https://truckkernel.com/) document its Apache-2.0 Rust B-Rep
  and STEP direction.
- [Manifold repository](https://github.com/elalish/manifold) documents its
  Apache-2.0 triangle-mesh kernel and Python binding.
- [Parasolid](https://www.siemens.com/en-us/products/plm-components/parasolid/)
  documents the commercial geometric modeling SDK.
- [Public Part 21 edition-3 text](https://www.steptools.com/stds/step/IS_final_p21e3.html)
  was used to compare the observed enumeration spelling. It is a public mirror,
  not the controlling purchased ISO publication.
