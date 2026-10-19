# Workflow baseline accounting controls — v1.16.0

[control-plan.json](control-plan.json) is an **invented arithmetic/quality
control**, not operator work or measured CAD accuracy. It contains 180 seconds
of preparation, 60 and 100 seconds for two part tasks, three explicit
not-needed phases, one invented wrong field, one missed feature and one false
completion. The independently written expected total is 340 seconds.

The two cases reuse `no_holes` and `single` from the
[v1.15 manifest](../cad-workflow-contract/reference-cases.json). Their geometry
truth comes from existing independent recipes. The invented task outcomes are
not new observations about the recognizer. No STEP assets are copied or altered.
The plate variants remain one part family, not unseen independent evaluation.

The study also creates an empty seven-case operator-observation template.
It has **no measured operator time, no operator error rate, and no real workbook
or execution-tool context**. All missing durations and quality totals stay null.

All new definitions/control values are authored in this repository. Existing
source asset licenses remain in the original manifests and
[public corpus README](../public-step-corpus/README.md).

See the [guide](../../docs/cad-workflow-baseline.md) and
[study](../../notes/cad-workflow-baseline.md).
