# Policy Composition and Explainable Decisions

## 日本語概要

この研究ノートは、resource admission、metadata relationship coverage、opaque metadata、integrity assertion、field retentionを順序付きで合成し、9個の合成入力を4種類のpolicy profileで評価します。36観測は`accept` 4、`sanitize` 5、`quarantine` 23、`reject` 4となり、各traceは最初に判断を確定したstageとreason codeを1つだけ記録しました。同じ入力でもprofileによって判断が変わるため、結果を普遍的な安全基準やproduction推奨値とは扱いません。詳細は以下の英語本文に示します。

---

## English Summary

This study composes resource admission, metadata relationship coverage,
opaque-data handling, digest integrity, and field retention into an ordered
decision trace. Nine synthetic inputs are evaluated under four explicit
profiles, producing 36 observations: 4 `accept`, 5 `sanitize`, 23
`quarantine`, and 4 `reject`. Every trace records exactly one decisive final
stage and a stable reason code.

## Research Question

Can independently tested JPEG metadata controls be composed into deterministic
`accept`, `sanitize`, `quarantine`, and `reject` decisions while preserving the
first decisive rule, profile assumptions, and output effects as auditable
evidence?

## Background

The previous studies intentionally separated concerns:

- v0.16.0 records field-level retention decisions;
- v0.17.0 bounds metadata work before parsing or decoding;
- v0.18.0 resolves selected nested metadata relationships and marks opaque
  components;
- v0.19.0 distinguishes missing, malformed, stale, and matching unsigned
  digest assertions.

None of those stages alone determines what an application should do with an
input. A pipeline needs an explicit combining rule. Access-control standards
such as XACML distinguish individual rule results from the algorithm that
combines them. NIST describes a policy decision point as the component that
evaluates applicable policy. This study adopts the separation between evidence
and decision, but its four image-routing results and profiles are project-
specific and are not an XACML or zero-trust implementation.

## Method

The engine evaluates five ordered stages:

1. `resource` applies the v0.17.0 default admission budget;
2. `coverage` applies the v0.18.0 relationship checks;
3. `opacity` follows the selected profile's allow, quarantine, or strip rule;
4. `integrity` distinguishes optional absence, required absence, valid, stale,
   malformed, and duplicate v0.19.0 assertions;
5. `retention` either emits the source or applies a v0.16.0 selective policy.

The first stopping rule is decisive. Later stages are not evaluated after a
terminal resource, coverage, opacity, or integrity outcome. Emitted outputs
record source and retained field counts, input and output hashes, and integrity
status before and after transformation.

The four controlled profiles are:

| Profile | Integrity | Opaque metadata | Retention |
| --- | --- | --- | --- |
| `open_catalog` | optional | allow | `retain_all` |
| `privacy_review` | optional | quarantine | `allow_visual_context` |
| `verified_archive` | required | quarantine | `retain_all` |
| `minimal_export` | optional | strip | `strip_all` |

These names describe experimental rule combinations. They are not deployment
recommendations or claims of privacy, archival, or security compliance.

## Controlled Experiment

All inputs are synthesized in code from one quality-75, 4:4:4 JPEG carrier.
The nine conditions are:

- clean controlled metadata without an integrity assertion;
- the same input with a valid assertion;
- a stale inherited assertion after metadata changes;
- a valid assertion over an opaque maker note;
- an incomplete Extended XMP relationship;
- a metadata-segment count above the resource budget;
- a JPEG segment-length overrun;
- malformed assertion JSON;
- duplicate assertions.

Every input is evaluated under every profile, yielding 36 observations.

Run:

```bash
python experiments/run_policy_composition.py
```

The command writes the observation CSV, profile summary, runtime manifest, and
figure documented in `results/README.md`.

## Results

All 36 fixture-profile observations match their declared decision and reason.

| Profile | Accept | Sanitize | Quarantine | Reject | Emitted |
| --- | ---: | ---: | ---: | ---: | ---: |
| `open_catalog` | 3 | 0 | 5 | 1 | 3 |
| `privacy_review` | 0 | 2 | 6 | 1 | 2 |
| `verified_archive` | 1 | 0 | 7 | 1 | 1 |
| `minimal_export` | 0 | 3 | 5 | 1 | 3 |

The decisive stage is `resource` for 8 observations, `coverage` for 4,
`opacity` for 2, `integrity` for 13, and `retention` for 9. Every trace contains
one decisive final step.

For the valid six-field input, `open_catalog` and `verified_archive` retain all
six fields. `privacy_review` retains the two declared visual-context fields,
and `minimal_export` retains none. Both sanitizing profiles remove the unsigned
integrity assertion, so the emitted output reports `missing_assertion` rather
than carrying a stale record.

The valid opaque maker-note input is accepted by `open_catalog`, quarantined by
the two profiles that prohibit opaque metadata, and stripped by
`minimal_export`. The malformed container is rejected by every profile before
metadata policy is considered. Resource, coverage, and integrity failures are
therefore not collapsed into one generic outcome.

## Interpretation

The experiment shows why evidence and policy must remain separate. The same
clean unsigned input is accepted, sanitized, or quarantined depending on
whether integrity is optional, which fields may be emitted, and whether an
assertion is required.

Ordered evaluation also improves attribution. An input above the resource
budget never reaches XML or integrity processing. An incomplete Extended XMP
relationship stops at coverage. A stale assertion reaches integrity but not
retention. The trace identifies which assumption prevented later work.

Sanitization is an active transform, not a weaker name for acceptance. The
output hash and retained-field count change, and the inherited unsigned
assertion is removed. Issuing a new authenticated assertion would require a
separate authorized provenance operation that this study does not perform.

## Failure Modes

### All policy failures are mapped to one reject state

Container rejection, quarantine for review, and an intentional sanitizing
transform have different downstream implications. Collapsing them loses
routing and audit evidence.

### A profile name is treated as a compliance guarantee

`privacy_review` and `verified_archive` are controlled labels. They do not
establish privacy-law compliance, archival suitability, or trusted provenance.

### A later permissive rule overrides an earlier failed boundary

The engine stops at the first decisive resource, coverage, opacity, or
integrity failure. Retention rules cannot restore an input that failed an
earlier precondition.

### Sanitization preserves provenance automatically

Changing metadata invalidates or removes its old binding. This implementation
removes the unsigned assertion and does not generate a replacement identity or
signature.

### Trace completeness is treated as operational enforcement

The result records a decision and optional output bytes. It does not move a
file into quarantine, enforce storage access, schedule deletion, notify an
operator, or prevent another caller from ignoring the result.

## Practical Guidance

- Define policy profiles as data with explicit integrity, opacity, and
  retention choices.
- Order inexpensive framing and resource checks before deeper parsing.
- Preserve the first decisive stage and stable reason code.
- Distinguish non-emitting quarantine and reject results from transformed
  sanitize outputs.
- Record both input and output integrity state when a transform occurs.
- Treat unknown metadata according to a declared allow, strip, or quarantine
  rule rather than an implicit default.
- Test each input under multiple profiles to expose policy-dependent behavior.
- Keep decision generation separate from storage, access-control, and operator
  workflow enforcement.

## Limitations

- The nine inputs and four profiles are synthetic study controls, not a threat
  model or production policy catalog.
- Retention covers only the twelve v0.16.0 controlled fields.
- Coverage is limited to the v0.18.0 synthetic metadata structures.
- Integrity uses the unsigned v0.19.0 assertion and does not authenticate an
  actor or parent.
- Sanitizing outputs are rebuilt from one metadata-free JPEG core supplied by
  the experiment; arbitrary transcoding pipelines are not evaluated.
- Early terminal results do not compute field counts for stages that were not
  reached, so profile summary field totals are not exposure estimates.
- `quarantine` and `reject` are returned decisions, not enforced operational
  controls.
- No concurrency, storage, latency, memory, adversarial bypass, or human-review
  experiment is included.
- The implementation is not XACML, zero trust, a policy engine standard, a
  privacy framework, or an archival standard.
- Stable results apply only to the fixed fixtures, profiles, dependencies, and
  recorded execution environments.

## Sources

- [OASIS XACML Version 3.0](https://docs.oasis-open.org/xacml/3.0/errata01/os/xacml-3.0-core-spec-errata01-os.html)
- [NIST policy decision point glossary](https://csrc.nist.gov/glossary/term/policy_decision_point)
- [NIST SP 800-207: Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final)
- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [C2PA Technical Specification](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html)
