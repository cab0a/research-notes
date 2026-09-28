# STEP Writer Modes and Round-Trip Policies

## 日本語概要

v0.89.0では、元ファイルのバイト列を保存する方式、空白・コメントだけを整理する方式、確定した編集形状からSTEPを作り直す方式を分けました。構文、意味、幾何、位相、属性、公差、バイト一致を別々に報告します。8条件に加えて、書込失敗や出力先の競合も試験しました。詳細は英語本文に示します。

---

## English Summary

The same phrase “write STEP back” can describe incompatible promises. Three
explicit modes make preservation dimensions inspectable before publishing a file.

## Modes

| Mode | Preserved or measured | Excluded claim |
| --- | --- | --- |
| `preserve` | Exact imported source bytes; bounded syntax parse | No edits, semantic validation or signature authentication |
| `canonical` | Significant token kinds, spellings and order; trivia normalized | No entity renumbering, graph canonicalization or schema-aware rewrite |
| `reconstruct` | Current confirmed shape; reimported validity, counts, volume, area and bounds | No preserved design history, product roles, names/colors or persistent topology identity |

Canonical mode joins significant raw tokens with spaces and a final newline.
It retains numeric spellings, string escapes, entity IDs and header values.
Token equivalence is checked by reparsing, and a second canonicalization is
idempotent. Comment markers inside quoted strings remain string content.
Inputs with signatures, anchors or external references are refused in this mode.
Preserve retains supported signed bytes without asserting signature validity.

## Verification and Publication

The named 4 × 3 × 2 mm box provides authored volume 24 mm³ and surface area
52 mm². Reconstruction uses the existing measured round-trip gate; topology
counts are compared without asserting entity identity, and tolerance changes
are recorded. Encoded names/colors can survive preserve/canonical because the
relevant tokens survive; those modes do not evaluate attribute interpretation.

Eight cases cover the three modes, signed preservation/canonical refusal,
read-only original source, explicit overwrite and successful replacement.
Additional tests cover aliases/hardlinks, comment markers in strings, injected
publication failure and an intervening writer creating the target.

Payload verification completes before creating a same-directory temporary file.
After flush/fsync, replacement uses an atomic rename when overwrite is explicit;
otherwise an atomic hard-link publication refuses an intervening destination.
Temporary files are cleaned up after failure. The filesystem must support the
chosen operation; unsupported publication produces an I/O error. This is not a
power-loss durability guarantee or a hostile-directory concurrency guarantee.

Original paths and existing hardlink aliases are protected. For a pending model
draft, reconstructed output is refused. Preserve/canonical can still export the
original immutable source and explicitly warn that model edits are excluded.

## Reproduce

```bash
python experiments/run_step_writer_modes.py
```

At the transactional terminal, select the intended policy explicitly:

```text
export output/source-copy.step preserve
export output/source-canonical.step canonical
export output/edited.step reconstruct
```

- [CSV](../results/step_writer_modes.csv)
- [Per-dimension evidence](../results/step_writer_modes_evidence.json)
- [HTML report](../results/step_writer_modes.html)
- [Implementation](../src/research_notes/step_writer_modes.py)
- [Source-preserving parser](../src/research_notes/step_part21.py)
