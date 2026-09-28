"""Separate source bytes, lexical canonicalization and reconstructed geometry."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import tempfile

from research_notes.step_part21 import parse_part21_document

WRITER_CONTRACT = "1.0.0"
MODES = ("preserve", "canonical", "reconstruct")


def canonical_step(source: bytes) -> bytes:
    """Canonical trivia only: exact significant token spellings and order.

    This preserves entity IDs, numeric spelling, strings and header values. It
    is intentionally not an EXPRESS-aware graph/entity canonicalizer.
    """
    document = parse_part21_document(source)
    if document.signatures or document.external_references or document.anchors:
        raise ValueError("canonical mode excludes signatures, external references and anchors")
    data = (" ".join(token.raw for token in document.significant_tokens) + "\n").encode("utf-8")
    parsed = parse_part21_document(data)
    if [(t.kind, t.raw) for t in parsed.significant_tokens] != [(t.kind, t.raw) for t in document.significant_tokens]:
        raise RuntimeError("canonicalization changed significant tokens")
    return data


def _token_digest(source):
    document = parse_part21_document(source)
    data = repr([(t.kind, t.raw) for t in document.significant_tokens]).encode()
    return hashlib.sha256(data).hexdigest(), document


def prepare_step_write(*, source: bytes | None, mode: str, shape=None) -> tuple[bytes, dict]:
    if mode not in MODES:
        raise ValueError("writer mode must be preserve, canonical or reconstruct")
    if source is not None and (not isinstance(source, bytes) or len(source) > 2_000_000):
        raise ValueError("source requires bounded immutable bytes")
    if mode in {"preserve", "canonical"}:
        if source is None:
            raise ValueError("this writer mode requires imported source bytes")
        before_digest, document = _token_digest(source)
        payload = source if mode == "preserve" else canonical_step(source)
        after_digest, after = _token_digest(payload)
        equal = before_digest == after_digest
        checks = {"syntax": "parsed", "byte_identity": payload == source,
                  "structure": "identical_tokens" if equal else "changed",
                  "schema": "declaration_preserved_not_validated", "semantics": "encoded_tokens_preserved_not_evaluated",
                  "attributes": "encoded_tokens_preserved", "tolerances": "encoded_tokens_preserved",
                  "geometry": "not_evaluated", "topology": "encoded_tokens_preserved_not_evaluated"}
        detail = {"significant_tokens_sha256": after_digest, "entity_count": len(after.entities),
                  "schema_identifiers": after.schema_identifiers, "native_geometry_invoked": False}
    else:
        if shape is None:
            raise ValueError("reconstruction requires a current confirmed shape")
        from research_notes.public_step import measured_round_trip
        fixture, verification = measured_round_trip(shape)
        if verification["status"] != "verified_invariants":
            raise RuntimeError("reconstructed geometry failed measured round-trip invariants")
        payload = fixture.source_bytes
        before_digest = _token_digest(source)[0] if source else None
        after_digest, after = _token_digest(payload)
        checks = {"syntax": "parsed", "byte_identity": source == payload,
                  "structure": "regenerated", "schema": "writer_declaration_not_validated",
                  "semantics": "not_preserved", "attributes": "not_preserved", "tolerances": "remeasured",
                  "geometry": "verified_invariants", "topology": "counts_verified_not_identity"}
        detail = {"native_geometry_invoked": True, "round_trip": verification,
                  "significant_tokens_sha256": after_digest, "entity_count": len(after.entities),
                  "schema_identifiers": after.schema_identifiers}
    return payload, {"contract_version": WRITER_CONTRACT, "mode": mode,
        "source_sha256": hashlib.sha256(source).hexdigest() if source else None,
        "output_sha256": hashlib.sha256(payload).hexdigest(), "output_bytes": len(payload),
        "checks": checks, "detail": detail,
        "scope": "source preservation or declared regenerated invariants; no complete AP conformance or recovered design history"}


def write_step(path: Path, *, source: bytes | None, mode: str, shape=None,
               source_path: Path | None = None, overwrite: bool = False) -> dict:
    """Verify in memory, then publish a complete file in one filesystem operation."""
    path = Path(path).resolve()
    if path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("output must have .step or .stp extension")
    if source_path is not None:
        original = Path(source_path).resolve()
        if path == original or (path.exists() and original.exists() and path.samefile(original)):
            raise ValueError("imported source is read-only")
    if path.exists() and not overwrite:
        raise FileExistsError("output exists; explicit overwrite is required")
    payload, report = prepare_step_write(source=source, mode=mode, shape=shape)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".step-write-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # Hard-link publication is atomic and refuses an intervening file.
            os.link(temporary, path)
        return {**report, "file_name": path.name}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
