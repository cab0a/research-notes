# Native B-Rep capability study — 2026-10-19

[Japanese findings and proposed v1.15–v1.34 plan](../../notes/brep-native-recognition-strategy.md).

The goal is to reuse B-Rep queries, stored native features, existing recognition
and shape comparison without requiring an intermediate STEP conversion.
This study does not replace the production kernel or add a production recognizer.

- [solidcraft-observations.json](solidcraft-observations.json): eight CLI invocations,
  including two metadata calls and six scripts, on three small authored examples.
- [sources.json](sources.json): 271 fixed SolidCraft source records, additional
  dated official ClassCAD pages, release/binary hashes and hashes of prior studies.
- [verification.json](verification.json): authored dimensions, semantic boundaries,
  finite JSON, source/code hashes and local documentation-link checks.

## Reproduce the native SolidCraft observations

Obtain `solidcraft-0.15.0-linux-x86_64.tar.gz` from the
[official v0.15.0 release](https://github.com/tangency-labs/solidcraft/releases/tag/v0.15.0).
The archive SHA-256 recorded and checked against GitHub's asset metadata is
`4d62f8e41a92d150da5bd1152ea5d22230a4893e33e81cb573cebab81475bf4f`.
Only `solidcraft-0.15.0-linux-x86_64/bin/solidcraft-cli` was extracted by its exact
member name, without extracting arbitrary archive paths. Its SHA-256 is
`acf0ec79058998b2b34e3b64cd0cff5e40e8353f314800e95b180edfb5245d02`.
The binary reported `solidcraft-cli 0.15.0`. No desktop app was launched.

Run in Linux/WSL with a standard-library Python:

```bash
python3 experiments/run_native_brep_probe.py \
  --cli output/brep-native-capabilities-2026-10-19/bin/solidcraft-cli \
  --output-dir output/native-brep-reproduction
```

Each subprocess has a 45-second wall timeout. This is not a security or resource
admission benchmark. The script creates named files inside the specified output
directory; use a dedicated research output directory. The CLI and vendor sources
are not installed into production or redistributed in the repository.

The script writes native documents, command scripts, a registry and observations.
The complete registry stays in the output directory. The committed observation
keeps its count/hash and eleven relevant entries. Timing values, session paths
and platform rounding are observations, not benchmark thresholds.

### Authored controls and limits

1. A 40×30×5 mm plate receives a diameter-6 hole at (10,10,5), then its native
   `.solidcraft` document is saved and reopened. The recorded HoleFeature
   definition is retrieved directly, and the B-Rep contains two radius-3
   cylindrical wall faces. Two faces are not two holes.
2. A width-6 straight slot has end-center distance 14 and overall length 20 mm.
   The existing profile measurement reports those dimensions. It is cut through
   the plate, saved and reopened. One cylindrical end face is explicitly selected
   using `model.faces`; the existing measurement reports the same dimensions.
   This is **not** a whole-part slot inventory, hole/boss classification or a
   through-depth certificate. The source implementation uses faces and sampled
   points, not the SlotCut feature's parameters, for that selected-face result.
3. Two overlapping native boxes, 10×8×4 and 12×8×4 mm, are compared at their given
   placements with tolerance 0.01 mm and spacing 0.5 mm. Maximum deviation is
   2 mm and whole-body volume difference is 64 mm³. One New-only region has
   approximately 63.970260 mm³ from sampled integration. Region volume is not an
   exact Boolean volume. No automatic alignment or semantic feature matching is
   demonstrated. Coloring was not exercised.

Both saved documents contain `document.json` and `container.json`, **no B-Rep
cache**. Reopening rebuilds the document before inspection. These observations
do not validate the SCBREP03 provisional cache's accuracy or authority.

Eight completed CLI invocations are not eight feature families or an accuracy
score. ClassCAD, Quiddity and SMLib C++ analytic recovery were not executed in
this study. The earlier smlibpy 30-task study is reused, not rerun: five inputs /
22 tasks use directly authored Part objects; two inputs / eight tasks use STEP.
See [the prior observations](../recognition-catalog/builtin-probe.json).

## Source review

SolidCraft is pinned at `fa691707c224cae580c42201ed3a22d5e4b8c716`. Source acquisition
includes kernel, document and IO Rust files plus the relevant command, CLI,
geometry and format documentation. The 271 records are an acquisition inventory;
they do not imply every source line was reviewed or prove the absence of every
unlisted capability. Targeted review is explained in the Japanese note.

ClassCAD's fixed API 21.2.0 package and prior SCG/type inspection are referenced
through the [previous source manifest](../recognition-availability/sources.json).
The live Part/Solid guide and runtime documentation are separately dated and
hashed. Future/live-only functions are not counted as fixed-package runtime
observations. No account, license activation, service session or engine execution
was performed for ClassCAD.

Current recognition code, package dependencies, version, old fixtures and prior
results are unchanged. The production test suite was not rerun for this source
study; the new observation script and its measured controls were checked.
