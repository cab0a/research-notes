"""Atomic publication of a bounded feature DAG with retained attempt diagnostics."""
from __future__ import annotations

from dataclasses import replace
import hashlib

from research_notes.deterministic_recompute import (
    FeatureModel, RecomputeResult, edit_parameter, model_fingerprint, recompute,
    recompute_record, validate_model,
)


class RevisionConflict(ValueError):
    pass


def isolated_result(result: RecomputeResult) -> RecomputeResult:
    """Native operations receive geometry copies, never the published cache."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    return replace(result, states=tuple(replace(state,
        shape=BRepBuilderAPI_Copy(state.shape, True, False).Shape() if state.shape is not None else None)
        for state in result.states))


class TransactionalModel:
    """One atomic boundary: all nodes in one FeatureModel (including side branches).

    Candidate branches evaluate independently, but no node is published if any
    branch fails. Checkpoints are in-memory snapshots, not process-crash recovery.
    """
    def __init__(self, model: FeatureModel, *, checkpoint_limit: int = 16):
        validate_model(model)
        if model.provenance == "unconfirmed_candidate":
            raise ValueError("candidate selection must be confirmed")
        if type(checkpoint_limit) is not int or not 1 <= checkpoint_limit <= 64:
            raise ValueError("checkpoint limit must be 1..64")
        initial = recompute(model)
        if any(s.status != "valid" for s in initial.states):
            raise ValueError("initial model must have only valid nodes")
        self.committed_model = self.draft = model
        self.committed = initial
        self.attempt: RecomputeResult | None = None
        self.epoch = 0
        self.checkpoint_limit = checkpoint_limit
        self.checkpoints = {model_fingerprint(model): (model, initial)}
        self.last_outcome = "initialized"
        self.attempt_error = None

    @property
    def token(self):
        return hashlib.sha256(f"{self.epoch}:{model_fingerprint(self.draft)}".encode()).hexdigest()

    @property
    def dirty(self):
        return model_fingerprint(self.draft) != model_fingerprint(self.committed_model)

    def _guard(self, expected_revision):
        if expected_revision != self.token:
            raise RevisionConflict("revision token is stale; query status before retrying")

    def edit(self, node_id, parameter, value, *, expected_revision):
        self._guard(expected_revision)
        candidate = edit_parameter(self.draft, node_id, parameter, value)
        self.draft, self.attempt = candidate, None
        self.attempt_error = None
        self.epoch += 1
        self.last_outcome = "staged"
        return self.record()

    def commit(self, *, expected_revision):
        self._guard(expected_revision)
        # Compute everything off to the side. Exceptions cannot publish a prefix.
        try:
            candidate = recompute(self.draft, isolated_result(self.committed))
        except Exception as error:
            self.attempt = None
            self.attempt_error = {"diagnostic_class": type(error).__name__, "detail": str(error)}
            self.last_outcome = "aborted"
            self.epoch += 1
            raise
        self.attempt_error = None
        self.attempt = candidate
        self.epoch += 1
        if any(s.status != "valid" for s in candidate.states):
            self.last_outcome = "aborted"
            return self.record()
        self.committed_model, self.committed = self.draft, candidate
        key = model_fingerprint(self.committed_model)
        self.checkpoints[key] = (self.committed_model, self.committed)
        while len(self.checkpoints) > self.checkpoint_limit:
            del self.checkpoints[next(iter(self.checkpoints))]
        self.last_outcome = "committed"
        return self.record()

    def rollback(self, checkpoint=None, *, expected_revision):
        self._guard(expected_revision)
        key = checkpoint or model_fingerprint(self.committed_model)
        if key not in self.checkpoints:
            raise ValueError("checkpoint is unknown or evicted")
        self.committed_model, self.committed = self.checkpoints[key]
        self.draft, self.attempt = self.committed_model, None
        self.attempt_error = None
        self.epoch += 1  # An old token cannot become valid again after rollback.
        self.last_outcome = "rolled_back"
        return self.record()

    def current(self):
        if self.dirty:
            raise ValueError("draft differs from committed state; recompute or rollback before export")
        return self.committed.current_output()

    def record(self):
        return {"contract_version": "1.0.0", "atomic_boundary": "all_feature_model_nodes",
            "outcome": self.last_outcome, "revision_token": self.token, "draft_pending": self.dirty,
            "draft_fingerprint": model_fingerprint(self.draft),
            "committed_fingerprint": model_fingerprint(self.committed_model),
            "checkpoints": list(self.checkpoints), "committed": recompute_record(self.committed),
            "attempt": recompute_record(self.attempt) if self.attempt else None,
            "attempt_error": self.attempt_error,
            "retained_geometry_is_current_draft": not self.dirty}


class TransactionalAssembly:
    """All authored components, placements and interference checks commit together."""
    def __init__(self, document):
        from research_notes.assembly_recompute import recompute_assembly, assembly_fingerprint
        result = recompute_assembly(document)
        if not self._acceptable(result):
            raise ValueError("initial assembly must be fully constrained without interference")
        self.committed_document = self.draft = document
        self.committed, self.attempt = result, None
        self.epoch = 0
        self.last_outcome = "initialized"
        self.attempt_error = None
        self.checkpoints = {assembly_fingerprint(document): (document, result)}

    @staticmethod
    def _acceptable(result):
        return (result.status == "fully_constrained"
                and all(state.status == "valid" for _, component in result.component_results for state in component.states)
                and not any(p["status"] == "interference" for p in result.pair_checks))

    @property
    def token(self):
        from research_notes.assembly_recompute import assembly_fingerprint
        return hashlib.sha256(f"{self.epoch}:{assembly_fingerprint(self.draft)}".encode()).hexdigest()

    def _guard(self, token):
        if token != self.token:
            raise RevisionConflict("assembly revision token is stale")

    def edit(self, name, expression, *, expected_revision):
        from research_notes.assembly_recompute import edit_assembly_parameter
        self._guard(expected_revision)
        self.draft = edit_assembly_parameter(self.draft, name, expression)
        self.attempt = None
        self.attempt_error = None
        self.epoch += 1
        self.last_outcome = "staged"
        return self.record()

    def commit(self, *, expected_revision):
        from research_notes.assembly_recompute import recompute_assembly, assembly_fingerprint
        self._guard(expected_revision)
        try:
            previous = replace(self.committed, component_results=tuple((name, isolated_result(result)) for name, result in self.committed.component_results))
            candidate = recompute_assembly(self.draft, previous)
        except Exception as error:
            self.attempt = None
            self.attempt_error = {"diagnostic_class": type(error).__name__, "detail": str(error)}
            self.last_outcome = "aborted"
            self.epoch += 1
            raise
        self.attempt_error = None
        self.attempt = candidate
        self.epoch += 1
        if self._acceptable(candidate):
            self.committed_document, self.committed = self.draft, candidate
            self.checkpoints[assembly_fingerprint(self.draft)] = (self.draft, candidate)
            while len(self.checkpoints) > 16:
                del self.checkpoints[next(iter(self.checkpoints))]
            self.last_outcome = "committed"
        else:
            self.last_outcome = "aborted"
        return self.record()

    def rollback(self, checkpoint=None, *, expected_revision):
        from research_notes.assembly_recompute import assembly_fingerprint
        self._guard(expected_revision)
        key = checkpoint or assembly_fingerprint(self.committed_document)
        if key not in self.checkpoints:
            raise ValueError("assembly checkpoint is unknown or evicted")
        self.committed_document, self.committed = self.checkpoints[key]
        self.draft, self.attempt = self.committed_document, None
        self.attempt_error = None
        self.epoch += 1
        self.last_outcome = "rolled_back"
        return self.record()

    def current(self):
        from research_notes.assembly_recompute import assembly_fingerprint
        if assembly_fingerprint(self.draft) != assembly_fingerprint(self.committed_document):
            raise ValueError("assembly draft is pending; recompute or rollback")
        return self.committed

    def record(self):
        from research_notes.assembly_recompute import assembly_record, assembly_fingerprint
        return {"contract_version": "1.0.0", "atomic_boundary": "all_components_placements_interference",
            "outcome": self.last_outcome, "revision_token": self.token,
            "draft_pending": assembly_fingerprint(self.draft) != assembly_fingerprint(self.committed_document),
            "checkpoints": list(self.checkpoints), "committed": assembly_record(self.committed),
            "attempt": assembly_record(self.attempt) if self.attempt else None, "attempt_error": self.attempt_error}
