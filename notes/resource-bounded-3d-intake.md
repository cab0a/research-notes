# Resource-Bounded 3D Intake

## 日本語概要

STEPと制御した圧縮容器の受入を、事前検査、構文解析、外部参照方針、形状計算核、三角形化の5段階へ分け、ファイル量、字句数、実体数、参照数、展開量、入れ子、経路、面数、三角形数、実行時間の上限を検証した。13条件すべてが予定した判定理由で停止または受理され、2件を受理、5件を隔離、6件を拒否した。構文解析とネイティブ形状処理は別々の子プロセスで実行する。ただし、これらの上限と時間切れはメモリ安全性、脆弱性耐性、任意の悪意あるファイルの安全性を証明しない。詳細は英語本文に示す。

---

## English Summary

This study implements a staged intake policy for raw STEP files and a small controlled ZIP-container subset. It records where each control stops, isolates syntax and native-kernel work in child processes, disables external retrieval, and keeps security claims narrower than the observed counters and timeouts.

## Research Question

Can an untrusted 3D-input workflow make file, syntax, archive, external-reference, topology, tessellation, and execution-time boundaries explicit before treating transferred geometry as admitted?

## Background

Reading STEP is not one operation. Physical-file bytes must be acquired, optional container members must be selected, Part 21 syntax must be parsed, external references may require policy decisions, a native importer may construct topology, and a mesher may create substantially more output. A limit observed after one stage does not retroactively bound work already performed by an earlier library.

Python's subprocess API provides a wall-clock timeout that raises `TimeoutExpired` when a child does not finish. Python's ZIP API exposes declared member sizes and names, but those declarations are not proof that all decompression behavior is safe. OCCT's STEP reader transfers file contents into Open CASCADE models, and `BRepMesh_IncrementalMesh` constructs meshes using declared linear and angular parameters. The study therefore isolates and records these stages rather than describing the whole pipeline as a safe parser.

## Method

The admission order is fixed:

1. preflight raw bytes or ZIP central-directory declarations;
2. source-preserving Part 21 parsing in a child process;
3. external-reference policy without network retrieval;
4. OCCT shape transfer and topology counting in a separate child process;
5. deterministic tessellation and triangle counting in that native worker.

The preflight accepts raw `.step` files and a controlled `.stpz` subset with exactly one `.step` or `.stp` member. It rejects absolute or parent-traversing member paths, nested archives when depth is zero, excessive member counts, excessive declared expansion, and oversized selected STEP payloads. It never extracts archive members to the filesystem.

The parser receives explicit byte, token, entity, reference, nesting-depth, and token-length limits. Accepted syntax with an external reference is quarantined before native transfer because retrieval is disabled. The kernel worker counts unique edges and faces before meshing, then counts generated triangles. Parent-side process timeouts bound elapsed waiting for the parser and native worker.

## Controlled Experiment

Seven committed files support thirteen policy controls:

- a box STEP file used for accepted, byte, syntax, topology, and timeout conditions;
- a through-hole STEP file used for the triangle-output boundary;
- a valid syntax-only external-reference file;
- one admitted ZIP container;
- one over-expansion container;
- one nested container;
- one parent-traversing member container.

Run:

```bash
python experiments/run_resource_bounded_3d.py
```

Use `--refresh-fixtures` only when intentionally regenerating the deterministic corpus.

## Results

All thirteen controls match their declared terminal decision and reason code:

| Decision | Controls |
| --- | ---: |
| Accept | 2 |
| Quarantine | 5 |
| Reject | 6 |

Four controls stop during preflight, three at syntax parsing, one at the external-reference policy, two at native transfer, and three at tessellation, where the count includes the two accepted paths. The raw box and admitted archive select the same payload SHA-256 and both produce 12 unique edges, 6 faces, and 12 triangles. The through-hole produces 120 triangles and is rejected against a limit of 10. The six-face box is rejected against a face limit of 5. The delayed native worker is quarantined at its 0.1-second parent timeout.

The external-reference fixture parses with one external occurrence and stops before the kernel worker. No resolver or network client is called.

## Interpretation

The result establishes policy ordering and evidence locality. A rejected archive path never reaches syntax parsing. A syntax resource overrun never reaches native code. A valid external-reference spelling does not imply permission to retrieve it. A shape can pass topology limits and still exceed mesh-output limits.

Running syntax and native geometry in different processes creates a practical cancellation boundary and prevents one stage's Python object state from becoming another stage's implicit input. It does not provide an operating-system sandbox, memory quota, syscall filter, or proof that a native dependency cannot fail before the parent observes a result.

## Failure Modes

- Declared ZIP sizes can be misleading, and decompression may allocate before an application counter is updated.
- A child may consume excessive memory or trigger a native defect before its wall-clock timeout.
- Killing one worker is not equivalent to constraining every descendant process or operating-system resource.
- Topology counts do not bound geometric conditioning, surface evaluation cost, or all importer healing work.
- Triangle counts are observed after meshing; they do not prevent allocations required to produce that count.
- One STEP member per controlled container is not a general Part 21 edition-3 container implementation.

## Practical Guidance

- Apply byte and archive-path policy before parsing or extraction.
- Keep external retrieval disabled by default and require a separate resolver policy.
- Run native CAD import and meshing outside the request-handling process.
- Record the terminal stage and reason code, not only an overall failure message.
- Add operating-system memory, CPU, filesystem, and network restrictions before processing genuinely hostile inputs.
- Calibrate topology and mesh budgets from representative workloads; the study values are controls, not production defaults.

## Limitations

The corpus is synthetic and small. The archive reader relies on Python's ZIP implementation and declared metadata. Process isolation is not a security sandbox. No memory or CPU quota, seccomp policy, container boundary, antivirus scan, recursive process supervision, decompression-ratio limit, encrypted member, data-descriptor variant, multi-model container, arbitrary malformed geometry, or native crash recovery is tested. Time values are policy inputs; measured durations are intentionally excluded from deterministic reference artifacts.

## Sources

- [Python `subprocess` documentation](https://docs.python.org/3/library/subprocess.html)
- [Python `zipfile` documentation](https://docs.python.org/3/library/zipfile.html)
- [Open CASCADE Technology `STEPControl_Reader` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_s_t_e_p_control___reader.html)
- [Open CASCADE Technology `BRepMesh_IncrementalMesh` reference](https://dev.opencascade.org/doc/occt-7.9.0/refman/html/class_b_rep_mesh___incremental_mesh.html)
- [Public final edition-3 draft of ISO 10303-21](https://www.steptools.com/stds/step/IS_final_p21e3.html)
