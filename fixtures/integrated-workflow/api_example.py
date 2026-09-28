from pathlib import Path
from research_notes.integrated_workflow import IntegratedSession

session = IntegratedSession()
session.open_step(Path("fixtures/step-reconstruction/through_hole.step"))
review = session.review()
proposal = next(p for p in review["alternatives"] if p["explanation"] == "through_hole")
session.select_candidate(proposal["candidate_id"], confirm=True)
session.set_material(7800, "kg/m3")
edit = session.ask("穴の半径を1.3 mmに")
print(edit)  # Inspect the concrete before/after proposal before confirming.
session.apply(edit["proposal_id"], confirm=True)
print(session.mass())
session.export_step(Path("output/integrated-api/edited.step"), overwrite=True)
session.report(Path("output/integrated-api"))
