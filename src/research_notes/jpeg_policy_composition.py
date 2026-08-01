"""Explainable composition of controlled JPEG metadata policy stages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from research_notes.jpeg_metadata_coverage import (
    build_metadata_coverage_fixtures,
    inspect_jpeg_metadata_coverage,
)
from research_notes.jpeg_provenance import (
    SelectiveRetentionPolicy,
    apply_selective_metadata_policy,
    build_controlled_metadata_fixture,
    extract_controlled_metadata_fields,
)
from research_notes.jpeg_recovery import make_jpeg_app_segment
from research_notes.jpeg_resource_bounds import (
    audit_jpeg_metadata_resources,
    build_resource_boundary_fixtures,
)
from research_notes.jpeg_transform_integrity import (
    attach_transform_integrity_assertion,
    strip_transform_integrity_assertions,
    verify_transform_integrity_assertion,
)


JPEGPolicyDecision = Literal["accept", "sanitize", "quarantine", "reject"]
OpaqueMetadataPolicy = Literal["allow", "quarantine", "strip"]

_ASSERTION_IDENTIFIER = b"ResearchNotesIntegrity\x00"
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}


@dataclass(frozen=True)
class JPEGIntakePolicy:
    """One explicit composition of admission, integrity, and retention rules."""

    name: str
    require_integrity: bool
    opaque_metadata: OpaqueMetadataPolicy
    retention_policy: SelectiveRetentionPolicy


JPEG_INTAKE_POLICIES = (
    JPEGIntakePolicy(
        "open_catalog",
        require_integrity=False,
        opaque_metadata="allow",
        retention_policy="retain_all",
    ),
    JPEGIntakePolicy(
        "privacy_review",
        require_integrity=False,
        opaque_metadata="quarantine",
        retention_policy="allow_visual_context",
    ),
    JPEGIntakePolicy(
        "verified_archive",
        require_integrity=True,
        opaque_metadata="quarantine",
        retention_policy="retain_all",
    ),
    JPEGIntakePolicy(
        "minimal_export",
        require_integrity=False,
        opaque_metadata="strip",
        retention_policy="strip_all",
    ),
)


@dataclass(frozen=True)
class JPEGPolicyTraceStep:
    """One ordered policy-stage outcome."""

    stage: str
    outcome: str
    reason_code: str
    decisive: bool


@dataclass(frozen=True)
class JPEGPolicyCompositionResult:
    """One final routing decision, output, and machine-readable trace."""

    profile: str
    decision: JPEGPolicyDecision
    reason_code: str
    trace: tuple[JPEGPolicyTraceStep, ...]
    output_bytes: bytes | None
    source_field_count: int
    retained_field_count: int
    opaque_component_count: int
    integrity_status_before: str
    integrity_status_after: str

    @property
    def emitted(self) -> bool:
        """Return whether this decision emits a JPEG byte stream."""
        return self.output_bytes is not None


@dataclass(frozen=True)
class JPEGPolicyCompositionFixture:
    """One input condition and expected decision for each policy profile."""

    fixture: str
    condition: str
    jpeg_bytes: bytes
    expected_decisions: tuple[tuple[str, JPEGPolicyDecision], ...]
    expected_reason_codes: tuple[tuple[str, str], ...]

    def expected_decision(self, profile: str) -> JPEGPolicyDecision:
        """Return the declared decision for one profile."""
        return dict(self.expected_decisions)[profile]

    def expected_reason_code(self, profile: str) -> str:
        """Return the declared final reason for one profile."""
        return dict(self.expected_reason_codes)[profile]


def apply_explainable_jpeg_policy(
    source_jpeg: bytes,
    reencoded_jpeg: bytes,
    policy: JPEGIntakePolicy,
) -> JPEGPolicyCompositionResult:
    """Apply ordered resource, coverage, opacity, integrity, and retention rules."""
    if not isinstance(source_jpeg, bytes):
        raise TypeError("source_jpeg must be bytes")
    if not isinstance(reencoded_jpeg, bytes) or not reencoded_jpeg:
        raise TypeError("reencoded_jpeg must be non-empty bytes")
    if not isinstance(policy, JPEGIntakePolicy):
        raise TypeError("policy must be JPEGIntakePolicy")
    trace: list[JPEGPolicyTraceStep] = []

    resource = audit_jpeg_metadata_resources(source_jpeg)
    if resource.decision != "accept":
        decision: JPEGPolicyDecision = (
            "reject" if resource.decision == "reject" else "quarantine"
        )
        reason = f"resource_{resource.reason_code}"
        trace.append(JPEGPolicyTraceStep("resource", "stop", reason, True))
        return _finish(policy, decision, reason, trace)
    trace.append(
        JPEGPolicyTraceStep(
            "resource", "pass", resource.reason_code, False
        )
    )

    coverage = inspect_jpeg_metadata_coverage(source_jpeg)
    if coverage.decision != "accept":
        decision = "reject" if coverage.decision == "reject" else "quarantine"
        reason = f"coverage_{coverage.reason_code}"
        trace.append(JPEGPolicyTraceStep("coverage", "stop", reason, True))
        return _finish(
            policy,
            decision,
            reason,
            trace,
            opaque_component_count=coverage.opaque_components,
        )
    trace.append(
        JPEGPolicyTraceStep("coverage", "pass", coverage.reason_code, False)
    )

    if coverage.opaque_components and policy.opaque_metadata == "quarantine":
        reason = "opaque_metadata_quarantined"
        trace.append(JPEGPolicyTraceStep("opacity", "stop", reason, True))
        return _finish(
            policy,
            "quarantine",
            reason,
            trace,
            opaque_component_count=coverage.opaque_components,
        )
    opacity_reason = (
        "opaque_metadata_allowed"
        if coverage.opaque_components and policy.opaque_metadata == "allow"
        else (
            "opaque_metadata_will_be_stripped"
            if coverage.opaque_components
            else "no_opaque_metadata"
        )
    )
    trace.append(JPEGPolicyTraceStep("opacity", "pass", opacity_reason, False))

    integrity = verify_transform_integrity_assertion(source_jpeg)
    if integrity.status == "missing_assertion":
        if policy.require_integrity:
            reason = "integrity_required_missing"
            trace.append(JPEGPolicyTraceStep("integrity", "stop", reason, True))
            return _finish(
                policy,
                "quarantine",
                reason,
                trace,
                opaque_component_count=coverage.opaque_components,
                integrity_status_before=integrity.status,
            )
        trace.append(
            JPEGPolicyTraceStep(
                "integrity", "pass", "integrity_optional_missing", False
            )
        )
    elif not integrity.valid:
        reason = f"integrity_{integrity.reason_code}"
        trace.append(JPEGPolicyTraceStep("integrity", "stop", reason, True))
        return _finish(
            policy,
            "quarantine",
            reason,
            trace,
            opaque_component_count=coverage.opaque_components,
            integrity_status_before=integrity.status,
        )
    else:
        trace.append(
            JPEGPolicyTraceStep(
                "integrity", "pass", integrity.status, False
            )
        )

    neutral_source = strip_transform_integrity_assertions(source_jpeg)
    source_fields = extract_controlled_metadata_fields(neutral_source)
    if policy.retention_policy == "retain_all":
        output = source_jpeg
        retained_field_count = len(source_fields)
        decision = "accept"
        reason = "policy_accept"
        trace.append(JPEGPolicyTraceStep("retention", "emit", reason, True))
    else:
        retention = apply_selective_metadata_policy(
            neutral_source,
            reencoded_jpeg,
            policy.retention_policy,
        )
        output = retention.output_bytes
        retained_field_count = retention.retained_field_count
        decision = "sanitize"
        reason = "policy_sanitize"
        trace.append(
            JPEGPolicyTraceStep("retention", "transform", reason, True)
        )
    integrity_after = verify_transform_integrity_assertion(output).status
    return JPEGPolicyCompositionResult(
        profile=policy.name,
        decision=decision,
        reason_code=reason,
        trace=tuple(trace),
        output_bytes=output,
        source_field_count=len(source_fields),
        retained_field_count=retained_field_count,
        opaque_component_count=coverage.opaque_components,
        integrity_status_before=integrity.status,
        integrity_status_after=integrity_after,
    )


def build_policy_composition_fixtures(
    base_jpeg: bytes,
    *,
    icc_profile: bytes,
) -> tuple[JPEGPolicyCompositionFixture, ...]:
    """Build the deterministic v0.20 composition fixture corpus."""
    if not isinstance(base_jpeg, bytes) or not base_jpeg:
        raise TypeError("base_jpeg must be non-empty bytes")
    if not isinstance(icc_profile, bytes) or not icc_profile:
        raise TypeError("icc_profile must be non-empty bytes")
    full_metadata = build_controlled_metadata_fixture(
        base_jpeg,
        icc_profile=icc_profile,
        variant="canonical_order",
    )
    catalog_metadata = apply_selective_metadata_policy(
        full_metadata,
        base_jpeg,
        "allow_catalog",
    ).output_bytes
    valid = attach_transform_integrity_assertion(
        catalog_metadata, action="created"
    )
    stale_source = apply_selective_metadata_policy(
        catalog_metadata,
        base_jpeg,
        "allow_visual_context",
    ).output_bytes
    stale = _copy_integrity_assertion(valid, stale_source)

    coverage_fixtures = {
        fixture.fixture: fixture.jpeg_bytes
        for fixture in build_metadata_coverage_fixtures(base_jpeg)
    }
    opaque = attach_transform_integrity_assertion(
        coverage_fixtures["maker_note_opaque"], action="created"
    )
    incomplete = coverage_fixtures["extended_xmp_missing_chunk"]

    resource_fixtures = {
        fixture.fixture: fixture.jpeg_bytes
        for fixture in build_resource_boundary_fixtures(base_jpeg)
    }
    over_budget = resource_fixtures["metadata_segments_over_limit"]
    malformed_container = resource_fixtures["segment_length_overrun"]

    malformed_assertion = _attach_raw_integrity_json(
        catalog_metadata, b"{not-json"
    )
    valid_json = _extract_integrity_json(valid)
    duplicate_assertion = (
        catalog_metadata[:2]
        + make_jpeg_app_segment(
            15, _ASSERTION_IDENTIFIER + valid_json
        )
        + make_jpeg_app_segment(
            15, _ASSERTION_IDENTIFIER + valid_json
        )
        + catalog_metadata[2:]
    )

    expected = {
        "clean_unsigned": (
            ("open_catalog", "accept", "policy_accept"),
            ("privacy_review", "sanitize", "policy_sanitize"),
            ("verified_archive", "quarantine", "integrity_required_missing"),
            ("minimal_export", "sanitize", "policy_sanitize"),
        ),
        "clean_valid_assertion": (
            ("open_catalog", "accept", "policy_accept"),
            ("privacy_review", "sanitize", "policy_sanitize"),
            ("verified_archive", "accept", "policy_accept"),
            ("minimal_export", "sanitize", "policy_sanitize"),
        ),
        "stale_assertion": tuple(
            (policy.name, "quarantine", "integrity_binding_mismatch")
            for policy in JPEG_INTAKE_POLICIES
        ),
        "opaque_valid_assertion": (
            ("open_catalog", "accept", "policy_accept"),
            ("privacy_review", "quarantine", "opaque_metadata_quarantined"),
            ("verified_archive", "quarantine", "opaque_metadata_quarantined"),
            ("minimal_export", "sanitize", "policy_sanitize"),
        ),
        "incomplete_relationship": tuple(
            (
                policy.name,
                "quarantine",
                "coverage_extended_xmp_incomplete",
            )
            for policy in JPEG_INTAKE_POLICIES
        ),
        "resource_over_budget": tuple(
            (
                policy.name,
                "quarantine",
                "resource_metadata_segment_limit_exceeded",
            )
            for policy in JPEG_INTAKE_POLICIES
        ),
        "malformed_container": tuple(
            (policy.name, "reject", "resource_segment_overrun")
            for policy in JPEG_INTAKE_POLICIES
        ),
        "malformed_assertion": tuple(
            (
                policy.name,
                "quarantine",
                "integrity_assertion_json_invalid",
            )
            for policy in JPEG_INTAKE_POLICIES
        ),
        "duplicate_assertion": tuple(
            (
                policy.name,
                "quarantine",
                "integrity_assertion_multiple",
            )
            for policy in JPEG_INTAKE_POLICIES
        ),
    }
    sources = {
        "clean_unsigned": catalog_metadata,
        "clean_valid_assertion": valid,
        "stale_assertion": stale,
        "opaque_valid_assertion": opaque,
        "incomplete_relationship": incomplete,
        "resource_over_budget": over_budget,
        "malformed_container": malformed_container,
        "malformed_assertion": malformed_assertion,
        "duplicate_assertion": duplicate_assertion,
    }
    return tuple(
        JPEGPolicyCompositionFixture(
            fixture=name,
            condition=name,
            jpeg_bytes=sources[name],
            expected_decisions=tuple(
                (profile, decision)
                for profile, decision, _ in rows
            ),
            expected_reason_codes=tuple(
                (profile, reason) for profile, _, reason in rows
            ),
        )
        for name, rows in expected.items()
    )


def _finish(
    policy: JPEGIntakePolicy,
    decision: JPEGPolicyDecision,
    reason_code: str,
    trace: list[JPEGPolicyTraceStep],
    *,
    opaque_component_count: int = 0,
    integrity_status_before: str = "not_evaluated",
) -> JPEGPolicyCompositionResult:
    """Build a non-emitting terminal result."""
    return JPEGPolicyCompositionResult(
        profile=policy.name,
        decision=decision,
        reason_code=reason_code,
        trace=tuple(trace),
        output_bytes=None,
        source_field_count=0,
        retained_field_count=0,
        opaque_component_count=opaque_component_count,
        integrity_status_before=integrity_status_before,
        integrity_status_after="not_emitted",
    )


def _copy_integrity_assertion(source: bytes, destination: bytes) -> bytes:
    """Copy exactly one controlled assertion JSON to another JPEG."""
    return _attach_raw_integrity_json(destination, _extract_integrity_json(source))


def _attach_raw_integrity_json(jpeg_bytes: bytes, payload: bytes) -> bytes:
    """Attach caller-supplied assertion JSON for negative controls."""
    neutral = strip_transform_integrity_assertions(jpeg_bytes)
    segment = make_jpeg_app_segment(
        15, _ASSERTION_IDENTIFIER + payload
    )
    return neutral[:2] + segment + neutral[2:]


def _extract_integrity_json(jpeg_bytes: bytes) -> bytes:
    """Extract exactly one controlled integrity JSON payload."""
    found = []
    for marker, payload in _header_segments(jpeg_bytes):
        if marker == 0xEF and payload.startswith(_ASSERTION_IDENTIFIER):
            found.append(payload[len(_ASSERTION_IDENTIFIER) :])
    if len(found) != 1:
        raise ValueError("expected exactly one controlled integrity assertion")
    return found[0]


def _header_segments(jpeg_bytes: bytes) -> tuple[tuple[int, bytes], ...]:
    """Return length-delimited JPEG header segments before SOS."""
    segments = []
    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker in _STANDALONE_MARKERS:
            continue
        if position + 2 > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment length")
        length = int.from_bytes(jpeg_bytes[position : position + 2], "big")
        if length < 2:
            raise ValueError("invalid JPEG segment length")
        start = position + 2
        end = position + length
        if end > len(jpeg_bytes):
            raise ValueError("JPEG segment exceeds the input")
        segments.append((marker, jpeg_bytes[start:end]))
        position = end
    return tuple(segments)


def output_sha256(result: JPEGPolicyCompositionResult) -> str:
    """Return the emitted output digest or an empty string."""
    if result.output_bytes is None:
        return ""
    return hashlib.sha256(result.output_bytes).hexdigest()
