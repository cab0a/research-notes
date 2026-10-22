# Compound drawing reconstruction fixtures

Own FreeCAD 1.1.4 TechDraw exports. Repository PolyForm Noncommercial 1.0.0 applies.
No external data set, runtime or trained model is redistributed.

- `development/`: four compound configurations, each SVG/DXF, independent authoring STEP and edited STEP.
- `holdout/`: nine new configurations exported only after `engine-freeze.json`; known families and authoring route, not held-out-family accuracy.
- `controls/`: two previous failed drawings promoted to development/review, four missing/conflicting input controls.
- `*-specs.json`: authoring/evaluation only; never reconstruction inputs.
- `protocol.json`, `engine-freeze.json`: scope, seed and source-order evidence.
- `controls/*/review.json`: actual IDs exported through the browser. Bound to source SHA-256; contains no numeric parameter overrides.
- `controls/*/interaction.json`: actual **agent** UI checks, not human work-time or ROI evidence.
- `inventory.json`: SHA-256 of the fixture payloads, excluding this inventory itself.

Each cohort manifest records source/context hashes. Authoring files and truth remain outside
the drawing worker's supplied inputs. This is input separation, not an OS security sandbox.
Original/edited truth is generated with FreeCAD; reconstruction and comparison use OCP.
Both are OCCT-based, not independent geometry kernels.

See [Japanese study](../../notes/drawing-composites.md) and [reproduction](../../docs/drawing-composites.md).
