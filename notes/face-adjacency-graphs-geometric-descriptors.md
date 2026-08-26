# Face-Adjacency Graphs and Geometric Descriptors

## 日本語概要

箱、貫通穴、段差、丸み付けの4形状について、各面を節、異なる2面が共有する辺を関係とする面隣接グラフを生成した。構築時は合計28面・59関係で、4形状すべてがSTEP読込後も節数、関係数、曲面構成、次数構成、関係構成、粗い構造署名を保持した。貫通穴の円筒面には1本の継ぎ目辺があるため、境界辺ではなく継ぎ目として別に数える。各CSV列の由来を契約へ割り当てるが、局所番号は永続識別子ではなく、形状特徴や設計意図を認識したとは主張しない。詳細は英語本文に示す。

---

## English Summary

This study turns four controlled B-Reps into attributed face-adjacency graphs. It publishes node, relation, graph, provenance, visualization, and STEP round-trip contracts that form an explicit input representation for later feature-recognition studies.

## Research Question

Can face geometry and shared-edge topology be represented as a deterministic, provenance-bound graph that remains structurally comparable after controlled STEP exchange without treating local face indices as persistent identities?

## Background

A B-Rep separates topology from supporting geometry. Faces bound material regions through wires and edges, while surface adaptors expose plane, cylinder, and other geometric behavior over a restricted parameter domain. A face-adjacency graph makes one useful view explicit: faces are nodes, and an edge used by two distinct faces is a relation between them.

This view is not the whole B-Rep. A periodic face may use one seam edge twice without producing adjacency to a different face. Boundary edges have one face use, and non-manifold edges can have more than two. The study counts these cases separately so that a cylinder seam is not mislabeled as an open boundary.

## Method

Four synthetic controls are selected from the earlier feature corpus:

- a six-face planar box;
- a box with one cylindrical through hole;
- an eight-face stepped prism;
- a box with one cylindrical fillet face.

Each shape is measured before and after a normalized STEP round trip. Unique face and edge maps provide graph-local indices. Each face node records surface type, orientation, area, centroid, representative normal, parameter spans, selected axis/radius/curvature values, wire and edge counts, tolerance, maximum edge length, adjacent node IDs, and degree. Each relation records the source edge index, endpoint nodes, curve type, length, tolerance, and representative-normal dot product.

The graph summary records connected components, boundary/seam/non-manifold edge counts, surface and degree histograms, relation-label histograms, curved-area ratio, topology counts, volume, and surface area. A SHA-256 structural signature covers sorted discrete node labels, relation labels, and incidence counts. It is intentionally coarse and is not a complete graph-isomorphism algorithm.

Every CSV column is assigned to contract, topology, geometry, or exchange provenance in `results/face_graph_contract.json`. Constructed rows identify repository construction as their exchange origin; imported rows carry the normalized STEP file name and SHA-256.

## Controlled Experiment

Run:

```bash
python experiments/run_face_adjacency_graphs.py
```

The command byte-verifies four committed STEP fixtures and writes node, relation, descriptor, comparison, graph JSON, contract, summary, adjacency figure, and shape-preview artifacts.

## Results

The constructed graphs contain 28 nodes and 59 distinct-face shared-edge relations:

| Control | Face nodes | Relations | Surface histogram | Degree histogram |
| --- | ---: | ---: | --- | --- |
| Plain block | 6 | 12 | 6 planes | degree 4: 6 |
| Through hole | 7 | 14 | 6 planes, 1 cylinder | degree 2: 1; degree 4: 4; degree 5: 2 |
| Stepped block | 8 | 18 | 8 planes | degree 4: 6; degree 6: 2 |
| Fillet operation | 7 | 15 | 6 planes, 1 cylinder | degree 4: 5; degree 5: 2 |

All four controlled STEP pairs retain node count, relation count, component count, boundary count, seam count, non-manifold count, surface histogram, degree histogram, relation histogram, structural signature, and whole-shape topology counts. Maximum volume difference is approximately `6.83e-13`; maximum surface-area difference is approximately `3.13e-12` in model units.

All controls are one connected face graph with zero open boundary and zero non-manifold edges. The through-hole has one seam edge, which is counted separately and is not emitted as a relation between different nodes.

## Interpretation

The graph distinguishes controls that have similar global topology counts. The box's uniform degree-four pattern differs from the through-hole's low-degree cylindrical node and two degree-five planar nodes. The stepped block remains all-planar but adds two degree-six nodes. The fillet adds a cylindrical node and a mixed line/circle relation inventory. These are useful inputs for later rule-based or learned classification.

Structural agreement after STEP supports comparing this representation across the selected exchange route. It does not mean `f3` before exchange is the same persistent CAD face as `f3` after exchange. The comparison uses graph-level invariants and independently records local file provenance.

## Failure Modes

- Face order can change after import, healing, Boolean operations, or a different kernel.
- A coarse structural signature can collide for non-isomorphic or geometrically different graphs.
- Representative normals and curvatures can miss variation, singularities, or local defects elsewhere on a face.
- Small edges, split faces, periodic seams, degenerate edges, and tolerance changes can alter graph structure.
- Two distinct faces may be geometrically coincident without sharing a topological edge.
- Geometry-derived labels do not recover the operation that created a final boundary.

## Practical Guidance

- Scope node and relation IDs to one analysis stage and preserve input hashes.
- Keep seam, open-boundary, and non-manifold incidence separate from distinct-face adjacency.
- Store continuous descriptors together with their calculation source and tolerance context.
- Compare graphs with explicit invariants or a documented matching method; never rely on face-list position alone.
- Use construction truth only for generated training/evaluation data, not as an inferred property of imported models.
- Add abstention when unsupported surfaces, invalid topology, incomplete provenance, or ambiguous matching is present.

## Limitations

Only four synthetic, analyzer-valid solids and one OCCT exchange route are evaluated. Relations are simple and undirected; the graph omits seam self-loops, wire ordering, p-curves, vertex nodes, face-use orientation on each relation, assembly context, units, names, colors, PMI, and material semantics. The structural signature is not canonical labeling. No arbitrary-file performance, independent kernel, healed geometry, tolerance sweep, feature classification, dataset split, or learned model is evaluated.

## Sources

- [Open CASCADE Technology `TopExp` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_top_exp.html)
- [Open CASCADE Technology `BRepAdaptor_Surface` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_b_rep_adaptor___surface.html)
- [Open CASCADE Technology `BRepAdaptor_Curve` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_b_rep_adaptor___curve.html)
- [Open CASCADE Technology `BRepGProp` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_b_rep_g_prop.html)
- [Open CASCADE Technology `BRep_Tool` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_b_rep___tool.html)
- [Open CASCADE Technology topology training material](https://dev.opencascade.org/sites/default/files/pdf/Topology.pdf)
