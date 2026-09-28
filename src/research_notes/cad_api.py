"""Version 1 of the deliberately bounded Python CAD workspace interface."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path

from research_notes.integrated_workflow import IntegratedSession
from research_notes.transactional_recompute import TransactionalModel, RevisionConflict

API_VERSION = "1.0.0"
ERROR_CODES = ("invalid_request", "revision_conflict", "confirmation_required", "resource_limit",
               "no_model", "no_source", "pending_changes", "io_error", "native_failure")


class CadAPIError(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code, self.detail = code, detail

    def record(self):
        return {"api_version": API_VERSION, "status": "error", "code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class APIResult:
    api_version: str
    operation: str
    status: str
    revision_token: str | None
    data: dict
    warnings: tuple[str, ...] = ()

    def record(self):
        return asdict(self)


def api_operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except CadAPIError:
            raise
        except RevisionConflict as error:
            raise CadAPIError("revision_conflict", str(error)) from error
        except OSError as error:
            raise CadAPIError("io_error", str(error)) from error
        except (ValueError, TypeError, KeyError) as error:
            raise CadAPIError("invalid_request", str(error)) from error
        except RuntimeError as error:
            raise CadAPIError("native_failure", str(error)) from error
    return call


class CadWorkspace:
    """Source inspection, confirmed reconstruction and transactional model edits.

    Version 1 freezes method inputs, envelope and error codes. Diagnostic data
    is operation-specific evidence, not a serialization of native objects.
    No inferred candidate is automatically adopted. All edits require a token.
    """
    def __init__(self):
        self._session = IntegratedSession()
        self._transaction = None
        self._generation = 0

    @property
    def revision_token(self):
        import hashlib
        value = f"{self._generation}:{self._transaction.token if self._transaction else 'no_model'}"
        return hashlib.sha256(value.encode()).hexdigest()

    def _guard(self, token):
        if token != self.revision_token:
            raise RevisionConflict("workspace revision changed; query status before retrying")

    def _result(self, operation, data, *, status="ok", warnings=()):
        return APIResult(API_VERSION, operation, status, self.revision_token, data, tuple(warnings))

    def _model(self):
        if self._transaction is None:
            raise CadAPIError("no_model", "select and confirm an editable candidate first")
        return self._transaction

    def _sync(self):
        if self._transaction:
            self._session.model = self._transaction.committed_model
            self._session.result = self._transaction.committed

    @api_operation
    def open_step(self, path: Path, *, mode="inspect"):
        if mode not in {"inspect", "reconstruct"}:
            raise CadAPIError("invalid_request", "mode must be inspect or reconstruct")
        with Path(path).open("rb") as stream:
            source = stream.read(2_000_001)
        if len(source) > 2_000_000:
            raise CadAPIError("resource_limit", "STEP exceeds the 2 MB API input budget")
        candidate = IntegratedSession()
        report = candidate.open_step_for_inspection(path) if mode == "inspect" else candidate.open_step(path)
        if candidate.inspection.imported.source_bytes != source:
            raise CadAPIError("revision_conflict", "input file changed during acquisition")
        self._session, self._transaction = candidate, None
        self._generation += 1
        return self._result("open_step", report, warnings=("source_history_not_recovered",))

    @api_operation
    def status(self):
        return self._result("status", {"source": self._session.inspection.imported.file_name if self._session.inspection else None,
            "source_sha256": self._session.inspection.imported.source_sha256 if self._session.inspection else None,
            "transaction": self._transaction.record() if self._transaction else None})

    @api_operation
    def candidates(self):
        if self._session.inspection is None:
            raise CadAPIError("no_source", "open a source first")
        values = self._session.inspect()["candidates"]
        return self._result("candidates", {"candidates": values}, status="ok" if values else "abstained",
                            warnings=() if values else ("no_qualified_editable_candidate",))

    @api_operation
    def select(self, candidate_id, *, confirm=False, expected_revision):
        self._guard(expected_revision)
        if confirm is not True:
            raise CadAPIError("confirmation_required", "explicit candidate confirmation is required")
        import copy
        candidate_session = copy.copy(self._session)
        candidate_session.select_candidate(candidate_id, confirm=True)
        transaction = TransactionalModel(candidate_session.model)
        self._session, self._transaction = candidate_session, transaction
        self._generation += 1
        self._sync()
        return self._result("select", transaction.record(), warnings=("inferred_history_explicitly_selected",))

    @api_operation
    def edit(self, node_id, parameter, value, *, expected_revision):
        self._guard(expected_revision)
        tx = self._model()
        return self._result("edit", tx.edit(node_id, parameter, value, expected_revision=tx.token), status="staged")

    @api_operation
    def recompute(self, *, expected_revision):
        self._guard(expected_revision)
        tx = self._model()
        report = tx.commit(expected_revision=tx.token)
        self._sync()
        return self._result("recompute", report, status=report["outcome"],
                            warnings=("last_valid_geometry_retained",) if report["outcome"] == "aborted" else ())

    @api_operation
    def rollback(self, checkpoint=None, *, expected_revision):
        self._guard(expected_revision)
        tx = self._model()
        report = tx.rollback(checkpoint, expected_revision=tx.token)
        self._sync()
        return self._result("rollback", report)

    @api_operation
    def compare(self):
        tx = self._model()
        if tx.dirty:
            raise CadAPIError("pending_changes", "comparison requires committed or rolled-back geometry")
        self._sync()
        return self._result("compare", self._session.compare())

    @api_operation
    def semantics(self):
        from research_notes.portable_step import inspect_step_semantics
        if self._session.inspection is None:
            raise CadAPIError("no_source", "open a source first")
        report = inspect_step_semantics(self._session.inspection.imported.source_bytes)
        return self._result("semantics", report, status="ok" if report["status"] == "resolved_subset" else "partial")

    @api_operation
    def export_step(self, path: Path, *, mode="reconstruct", overwrite=False):
        from research_notes.step_writer_modes import write_step
        source = self._session.inspection.imported.source_bytes if self._session.inspection else None
        shape = None
        if mode == "reconstruct":
            tx = self._model()
            if tx.dirty:
                raise CadAPIError("pending_changes", "cannot export retained geometry as the pending draft")
            shape = tx.current().shape
        report = write_step(path, source=source, mode=mode, shape=shape,
                            source_path=self._session.source_path, overwrite=overwrite)
        warnings = ("source_bytes_do_not_include_model_edits",) if mode != "reconstruct" and self._transaction else ()
        return self._result("export_step", report, warnings=warnings)

    @api_operation
    def workspace(self, directory: Path):
        from research_notes.diagnostic_workspace import write_workspace
        return self._result("workspace", write_workspace(self, directory))


def api_contract():
    """Reviewable contract fixture; additive diagnostic data is not frozen."""
    import inspect
    return {"api_version": API_VERSION, "result_fields": list(APIResult.__dataclass_fields__),
        "error_fields": ["api_version", "status", "code", "detail"], "error_codes": list(ERROR_CODES),
        "methods": {name: str(inspect.signature(getattr(CadWorkspace, name))) for name in
            ("open_step", "status", "candidates", "select", "edit", "recompute", "rollback", "compare", "semantics", "export_step", "workspace")},
        "revision_policy": "opaque token required for select/edit/recompute/rollback; stale tokens fail without mutation",
        "result_statuses": ["ok", "partial", "abstained", "staged", "committed", "aborted"],
        "limits": {"source_bytes": 2_000_000, "model_nodes": 64, "checkpoints": 16,
                   "workspace_faces": 256, "workspace_edges": 512, "workspace_triangles": 60000},
        "scope": "method inputs, result envelope, statuses, error codes and declared limits; additive diagnostic data may evolve; no hard native CPU/RAM isolation"}
