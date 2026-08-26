# Independent Parser and Kernel Portability

## 日本語概要

3つの合成STEP標本を3つの独立した構文解析実装と2つの読込経路で比較した。全9件の構文解析は受理され、同じOpen CASCADE Technology内の2経路は位相・体積・表面積・支持曲面構成で一致した。一方、形状のみの経路は名前と色を提供せず、文書対応経路は3件の名前と2件の色一覧を取得した。独立した形状計算核は未選定のため、計算核間の可搬性は結論としていない。英語本文では、固定標本、実装の固定方法、比較可能な主張、今回発見して修正した列挙値の字句範囲を説明する。

---

## English Summary

This study compares three fixed synthetic STEP files across the repository parser, two pinned public parsers, and two OCCT import routes. It separates parser acceptance, shape transfer, document attributes, and cross-kernel portability instead of collapsing them into one compatibility claim.

## Research Question

Which observations remain stable when the same STEP bytes pass through independently implemented Part 21 parsers and distinct import APIs, and which portability claims remain unsupported without a second geometry kernel?

## Background

A Part 21 parser can accept physical-file syntax without validating the declared EXPRESS schema or constructing geometry. A geometry importer can transfer B-Rep shapes while exposing a different information surface from a document-aware importer. The OCCT STEP guide describes separate file reading, root transfer, and resulting-shape operations; its XDE guide describes document-level support for names, colors, and assemblies. These layers require separate observations.

The study uses the source STEP files frozen by v0.48.0: an analytic box, a Boolean through-hole solid, and a free-form B-spline shell. Their SHA-256 values are recorded in `results/step_portability_manifest.csv`.

## Method

Three parser implementations receive identical bytes:

- the repository's source-preserving, resource-bounded Part 21 parser;
- STEPutils at commit `547860b349a36cf24c564d6c87ffd8f60484f6fb`;
- IfcOpenShell's standalone STEP file parser at commit `9400d243d880dace57490949d74ab1932ce99a09`.

The public parsers run in child processes. The internal parser additionally reports entity and reference counts and exact source reconstruction; blank fields for the public parsers mean that the adapter did not normalize those implementation-specific models.

Two OCCT import routes then receive the same files:

- `STEPControl_Reader`, observed as a shape-only transfer route;
- `STEPCAFControl_Reader`, observed as an XCAF document-aware route with name and color modes enabled.

Both routes use cadquery-ocp 7.9.3.1.1 and therefore share one OCCT kernel build. Topology counts, absolute volume, surface area, and support-surface inventory are compared at tight deterministic tolerances. Names and color-table inventories are recorded as route-specific availability, not geometry equality.

## Controlled Experiment

Run the study after checking out the two pinned parser repositories described in `docs/reproducibility.md`:

```bash
python experiments/run_step_portability.py
```

The command writes parser observations, importer observations, a compact summary, a fixed-corpus manifest, an interpretation contract, and a figure under `results/`.

During development, the repository parser initially rejected the OCCT spelling `.PCURVE_S1.` because its enumeration-token rule omitted underscores. A focused regression test now covers that spelling. This is useful evidence for the study's premise: parser portability is not established by passing only hand-written minimal examples.

## Results

All three parser implementations accepted all three fixed files, producing 9 accepted parser observations. The internal parser reconstructed the exact source bytes and reported 361, 457, and 121 entity instances for the box, through-hole, and B-spline controls respectively.

The two OCCT import routes agreed for all three files on unique topology counts, absolute volume, surface area, and support-surface inventories. The document-aware route exposed names for all three controls and color-table inventories for two. The shape-only adapter intentionally reports no document names or colors. The missing through-hole color already occurs in the frozen v0.48.0 source file and is not attributed to the v0.49.0 import comparison.

The study records zero independent geometry kernels and sets `cross_kernel_conclusion` to false.

## Interpretation

Agreement among three parsers is evidence that these exact physical files are accepted by independently implemented syntax readers. It is not evidence that every entity is schema-valid or semantically equivalent in each parser's model.

Agreement between the two OCCT routes shows that choosing the document-aware route did not change measured B-Rep geometry for this corpus. Their shared kernel means the result is an API-route comparison, not an independent geometric implementation comparison.

Document attributes depend on the selected information model. A shape-only API's empty attribute fields do not prove that attributes are absent from the file; they show that the selected route does not expose them through this adapter.

## Failure Modes

- A parser may accept syntax while ignoring schema constraints, unresolved references, or unsupported entity semantics.
- An importer may return a shape after warnings, healing, or tolerance changes that coarse counts do not detect.
- Two APIs backed by one kernel may repeat the same implementation defect.
- Names or colors may exist on subshape labels even when a top-level inventory is empty.
- Passing three files does not cover assemblies, mapped items, units, presentation styles, or the wider AP242 entity set.

## Practical Guidance

- Pin parser source revisions and record the exact input digest.
- Keep syntax acceptance, schema validation, geometry transfer, document attributes, and kernel agreement as separate fields.
- Treat unobserved fields as unavailable through a route, not as proof of absence.
- Add independently calculated invariants and a genuinely independent kernel before making cross-kernel claims.
- Retain disagreement fixtures as regression cases rather than normalizing away the differences.

## Limitations

The corpus contains only three synthetic files generated through one OCCT writer family. Both geometric import routes use the same OCCT build. Public parser adapters record coarse outcomes and do not compare abstract syntax trees. No malformed input, assembly structure, unit conversion, warning stream, healing history, or performance behavior is evaluated here. The successful result is local to the committed fixtures and pinned implementations.

## Sources

- [Open CASCADE Technology STEP translator guide](https://dev.opencascade.org/doc/occt-7.9.0/overview/html/occt_user_guides__step.html)
- [Open CASCADE Technology Extended Data Exchange guide](https://dev.opencascade.org/doc/occt-7.9.0/overview/html/occt_user_guides__xde.html)
- [Open CASCADE Technology `STEPControl_Reader` reference](https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_control___reader.html)
- [Open CASCADE Technology `STEPCAFControl_Reader` reference](https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_c_a_f_control___reader.html)
- [STEPutils source repository](https://github.com/mozman/steputils)
- [IfcOpenShell standalone STEP file parser source repository](https://github.com/IfcOpenShell/step-file-parser)
