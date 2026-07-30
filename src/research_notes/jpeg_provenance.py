"""Field-level provenance and selective retention for controlled JPEG metadata."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from research_notes.jpeg_recovery import make_jpeg_app_segment


FieldCategory = Literal[
    "interpretation",
    "descriptive",
    "attribution",
    "temporal",
    "location",
    "unclassified",
]
SelectiveRetentionPolicy = Literal[
    "retain_all",
    "drop_location_denylist",
    "allow_visual_context",
    "allow_catalog",
    "allow_attribution",
    "strip_all",
]

JPEG_SELECTIVE_RETENTION_POLICIES: tuple[SelectiveRetentionPolicy, ...] = (
    "retain_all",
    "drop_location_denylist",
    "allow_visual_context",
    "allow_catalog",
    "allow_attribution",
    "strip_all",
)

FIELD_ORDER = (
    "exif.orientation",
    "exif.image_description",
    "exif.artist",
    "exif.datetime",
    "xmp.dc_title",
    "xmp.dc_creator",
    "xmp.exif_gps_latitude",
    "xmp.exif_gps_longitude",
    "xmp.synthetic_pipeline_hint",
    "icc.profile",
    "jpeg.comment",
    "app13.opaque",
)

FIELD_CATEGORIES: dict[str, FieldCategory] = {
    "exif.orientation": "interpretation",
    "exif.image_description": "descriptive",
    "exif.artist": "attribution",
    "exif.datetime": "temporal",
    "xmp.dc_title": "descriptive",
    "xmp.dc_creator": "attribution",
    "xmp.exif_gps_latitude": "location",
    "xmp.exif_gps_longitude": "location",
    "xmp.synthetic_pipeline_hint": "unclassified",
    "icc.profile": "interpretation",
    "jpeg.comment": "descriptive",
    "app13.opaque": "unclassified",
}

CONTROLLED_FIELD_VALUES: dict[str, bytes] = {
    "exif.orientation": b"6",
    "exif.image_description": b"Synthetic calibration frame",
    "exif.artist": b"Synthetic Author",
    "exif.datetime": b"2026:01:02 03:04:05",
    "xmp.dc_title": b"Synthetic field provenance study",
    "xmp.dc_creator": b"Synthetic Author",
    "xmp.exif_gps_latitude": b"35,0.000N",
    "xmp.exif_gps_longitude": b"139,0.000E",
    "xmp.synthetic_pipeline_hint": b"controlled-review-stage",
    "jpeg.comment": b"Synthetic JPEG comment",
    "app13.opaque": b"controlled-opaque-payload",
}

_EXIF_IDENTIFIER = b"Exif\x00\x00"
_XMP_IDENTIFIER = b"http://ns.adobe.com/xap/1.0/\x00"
_ICC_IDENTIFIER = b"ICC_PROFILE\x00"
_APP13_IDENTIFIER = b"ResearchNotesField\x00"
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}
_EXIF_FIELDS = {
    274: ("exif.orientation", 3),
    270: ("exif.image_description", 2),
    315: ("exif.artist", 2),
    306: ("exif.datetime", 2),
}
_EXIF_TAGS = {field_id: tag for tag, (field_id, _) in _EXIF_FIELDS.items()}

_NS = {
    "x": "adobe:ns:meta/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "exif": "http://ns.adobe.com/exif/1.0/",
    "synthetic": "https://example.invalid/research-notes/1.0/",
}

_ALLOWLISTS = {
    "allow_visual_context": {
        "exif.orientation",
        "icc.profile",
    },
    "allow_catalog": {
        "exif.orientation",
        "exif.image_description",
        "exif.datetime",
        "xmp.dc_title",
        "icc.profile",
        "jpeg.comment",
    },
    "allow_attribution": {
        "exif.orientation",
        "exif.artist",
        "xmp.dc_creator",
        "icc.profile",
    },
}


@dataclass(frozen=True)
class JPEGMetadataField:
    """One normalized field extracted from a controlled JPEG source."""

    field_id: str
    category: FieldCategory
    container: str
    source_ordinal: int
    value: bytes

    @property
    def value_sha256(self) -> str:
        """Return a content fingerprint without exposing the field value."""
        return hashlib.sha256(self.value).hexdigest()


@dataclass(frozen=True)
class JPEGFieldDecision:
    """One policy decision linking a source field to an output state."""

    field_id: str
    category: FieldCategory
    container: str
    source_ordinal: int
    source_value_sha256: str
    source_value_bytes: int
    retained: bool
    reason: str
    output_value_sha256: str
    semantic_value_exact: bool


@dataclass(frozen=True)
class JPEGSelectiveRetentionResult:
    """Output and field decisions from one selective metadata policy."""

    policy: SelectiveRetentionPolicy
    output_bytes: bytes
    decisions: tuple[JPEGFieldDecision, ...]

    @property
    def retained_field_count(self) -> int:
        """Return the number of retained source fields."""
        return sum(decision.retained for decision in self.decisions)


def build_controlled_metadata_fixture(
    base_jpeg: bytes,
    *,
    icc_profile: bytes,
    variant: Literal["canonical_order", "reordered_equivalent"],
) -> bytes:
    """Attach one controlled field corpus in two byte-distinct layouts."""
    _validate_jpeg(base_jpeg, "base_jpeg")
    if not isinstance(icc_profile, bytes) or not icc_profile:
        raise TypeError("icc_profile must be non-empty bytes")
    if variant not in ("canonical_order", "reordered_equivalent"):
        raise ValueError(
            "variant must be canonical_order or reordered_equivalent"
        )

    endian = "big" if variant == "canonical_order" else "little"
    exif_order = (
        (
            "exif.orientation",
            "exif.image_description",
            "exif.artist",
            "exif.datetime",
        )
        if variant == "canonical_order"
        else (
            "exif.datetime",
            "exif.artist",
            "exif.image_description",
            "exif.orientation",
        )
    )
    xmp_order = (
        (
            "xmp.dc_title",
            "xmp.dc_creator",
            "xmp.exif_gps_latitude",
            "xmp.exif_gps_longitude",
            "xmp.synthetic_pipeline_hint",
        )
        if variant == "canonical_order"
        else (
            "xmp.synthetic_pipeline_hint",
            "xmp.exif_gps_longitude",
            "xmp.exif_gps_latitude",
            "xmp.dc_creator",
            "xmp.dc_title",
        )
    )
    segments = {
        "exif": make_jpeg_app_segment(
            1,
            _build_exif_payload(
                {
                    field_id: CONTROLLED_FIELD_VALUES[field_id]
                    for field_id in exif_order
                },
                endian=endian,
                field_order=exif_order,
            ),
        ),
        "xmp": make_jpeg_app_segment(
            1,
            _build_xmp_payload(
                {
                    field_id: CONTROLLED_FIELD_VALUES[field_id]
                    for field_id in xmp_order
                },
                field_order=xmp_order,
            ),
        ),
        "icc": _build_icc_segments(icc_profile),
        "comment": _make_segment(
            0xFE, CONTROLLED_FIELD_VALUES["jpeg.comment"]
        ),
        "app13": make_jpeg_app_segment(
            13,
            _APP13_IDENTIFIER + CONTROLLED_FIELD_VALUES["app13.opaque"],
        ),
    }
    order = (
        ("exif", "xmp", "icc", "app13", "comment")
        if variant == "canonical_order"
        else ("comment", "app13", "icc", "xmp", "exif")
    )
    neutral = strip_controlled_metadata(base_jpeg)
    return neutral[:2] + b"".join(segments[name] for name in order) + neutral[2:]


def extract_controlled_metadata_fields(
    jpeg_bytes: bytes,
) -> tuple[JPEGMetadataField, ...]:
    """Extract normalized fields from the controlled v0.16 metadata corpus."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    fields: list[JPEGMetadataField] = []
    icc_chunks: dict[int, bytes] = {}
    icc_count: int | None = None
    icc_first_ordinal: int | None = None
    ordinal = 0
    for marker, payload in _header_segments(jpeg_bytes):
        ordinal += 1
        if marker == 0xE1 and payload.startswith(_EXIF_IDENTIFIER):
            fields.extend(_parse_exif_fields(payload, ordinal))
        elif marker == 0xE1 and payload.startswith(_XMP_IDENTIFIER):
            fields.extend(_parse_xmp_fields(payload, ordinal))
        elif marker == 0xE2 and payload.startswith(_ICC_IDENTIFIER):
            if len(payload) < 14:
                raise ValueError("truncated controlled ICC segment")
            sequence = payload[12]
            declared_count = payload[13]
            if sequence == 0 or declared_count == 0:
                raise ValueError("invalid controlled ICC sequence")
            if icc_count not in (None, declared_count):
                raise ValueError("inconsistent controlled ICC count")
            if sequence in icc_chunks:
                raise ValueError("duplicate controlled ICC sequence")
            icc_count = declared_count
            if icc_first_ordinal is None:
                icc_first_ordinal = ordinal
            icc_chunks[sequence] = payload[14:]
        elif marker == 0xFE:
            fields.append(
                _field("jpeg.comment", "jpeg_com", ordinal, payload)
            )
        elif marker == 0xED and payload.startswith(_APP13_IDENTIFIER):
            fields.append(
                _field(
                    "app13.opaque",
                    "app13",
                    ordinal,
                    payload[len(_APP13_IDENTIFIER) :],
                )
            )
    if icc_count is not None:
        expected = set(range(1, icc_count + 1))
        if set(icc_chunks) != expected:
            raise ValueError("incomplete controlled ICC profile")
        profile = b"".join(icc_chunks[index] for index in sorted(icc_chunks))
        if icc_first_ordinal is None:
            raise RuntimeError("ICC chunks were collected without an ordinal")
        fields.append(
            _field("icc.profile", "app2_icc", icc_first_ordinal, profile)
        )

    identifiers = [field.field_id for field in fields]
    duplicates = {
        field_id for field_id in identifiers if identifiers.count(field_id) > 1
    }
    if duplicates:
        raise ValueError(
            "duplicate controlled metadata fields: "
            + ", ".join(sorted(duplicates))
        )
    return tuple(
        sorted(fields, key=lambda field: FIELD_ORDER.index(field.field_id))
    )


def apply_selective_metadata_policy(
    source_jpeg: bytes,
    reencoded_jpeg: bytes,
    policy: SelectiveRetentionPolicy,
) -> JPEGSelectiveRetentionResult:
    """Apply one explicit field-level policy to a controlled JPEG source."""
    _validate_jpeg(source_jpeg, "source_jpeg")
    _validate_jpeg(reencoded_jpeg, "reencoded_jpeg")
    if policy not in JPEG_SELECTIVE_RETENTION_POLICIES:
        raise ValueError(
            "policy must be one of: "
            + ", ".join(JPEG_SELECTIVE_RETENTION_POLICIES)
        )
    source_fields = extract_controlled_metadata_fields(source_jpeg)
    retained: dict[str, JPEGMetadataField] = {}
    reasons: dict[str, str] = {}
    for field in source_fields:
        keep, reason = _policy_decision(field, policy)
        reasons[field.field_id] = reason
        if keep:
            retained[field.field_id] = field

    neutral = strip_controlled_metadata(reencoded_jpeg)
    output = _attach_selected_fields(neutral, retained)
    output_fields = {
        field.field_id: field
        for field in extract_controlled_metadata_fields(output)
    }
    decisions = tuple(
        JPEGFieldDecision(
            field_id=field.field_id,
            category=field.category,
            container=field.container,
            source_ordinal=field.source_ordinal,
            source_value_sha256=field.value_sha256,
            source_value_bytes=len(field.value),
            retained=field.field_id in retained,
            reason=reasons[field.field_id],
            output_value_sha256=(
                output_fields[field.field_id].value_sha256
                if field.field_id in output_fields
                else ""
            ),
            semantic_value_exact=(
                field.field_id in output_fields
                and output_fields[field.field_id].value == field.value
            ),
        )
        for field in source_fields
    )
    if {
        decision.field_id
        for decision in decisions
        if decision.retained
    } != set(output_fields):
        raise RuntimeError("output fields do not match retention decisions")
    if any(
        decision.retained and not decision.semantic_value_exact
        for decision in decisions
    ):
        raise RuntimeError("a retained field changed its normalized value")
    return JPEGSelectiveRetentionResult(
        policy=policy,
        output_bytes=output,
        decisions=decisions,
    )


def strip_controlled_metadata(jpeg_bytes: bytes) -> bytes:
    """Remove the v0.16 controlled metadata while preserving image data."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    output = bytearray(jpeg_bytes[:2])
    position = 2
    while position < len(jpeg_bytes):
        marker_start = position
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            output.extend(jpeg_bytes[marker_start:])
            break
        if marker in _STANDALONE_MARKERS:
            output.extend(jpeg_bytes[marker_start:position])
            continue
        payload_start, payload_end = _payload_bounds(jpeg_bytes, position)
        payload = jpeg_bytes[payload_start:payload_end]
        controlled = (
            (marker == 0xE1 and payload.startswith(_EXIF_IDENTIFIER))
            or (marker == 0xE1 and payload.startswith(_XMP_IDENTIFIER))
            or (marker == 0xE2 and payload.startswith(_ICC_IDENTIFIER))
            or (
                marker == 0xED and payload.startswith(_APP13_IDENTIFIER)
            )
            or marker == 0xFE
        )
        if not controlled:
            output.extend(jpeg_bytes[marker_start:payload_end])
        position = payload_end
    if not output.endswith(b"\xff\xd9"):
        raise ValueError("JPEG EOI marker was not found")
    return bytes(output)


def metadata_state_sha256(jpeg_bytes: bytes) -> str:
    """Hash normalized field identifiers and values in canonical order."""
    digest = hashlib.sha256()
    for field in extract_controlled_metadata_fields(jpeg_bytes):
        encoded_id = field.field_id.encode("ascii")
        digest.update(len(encoded_id).to_bytes(2, "big"))
        digest.update(encoded_id)
        digest.update(len(field.value).to_bytes(4, "big"))
        digest.update(field.value)
    return digest.hexdigest()


def _policy_decision(
    field: JPEGMetadataField,
    policy: SelectiveRetentionPolicy,
) -> tuple[bool, str]:
    """Return one deterministic retention decision and reason code."""
    if policy == "retain_all":
        return True, "explicit_retain_all"
    if policy == "strip_all":
        return False, "explicit_strip_all"
    if policy == "drop_location_denylist":
        if field.category == "location":
            return False, "category_denylist"
        return True, "not_denied"
    allowlist = _ALLOWLISTS[policy]
    if field.field_id in allowlist:
        return True, "field_allowlist"
    return False, "not_allowlisted"


def _attach_selected_fields(
    jpeg_bytes: bytes,
    retained: dict[str, JPEGMetadataField],
) -> bytes:
    """Serialize retained fields in a deterministic canonical layout."""
    segments: list[bytes] = []
    exif_values = {
        field_id: field.value
        for field_id, field in retained.items()
        if field_id.startswith("exif.")
    }
    if exif_values:
        order = tuple(
            field_id for field_id in FIELD_ORDER if field_id in exif_values
        )
        segments.append(
            make_jpeg_app_segment(
                1,
                _build_exif_payload(
                    exif_values, endian="big", field_order=order
                ),
            )
        )
    xmp_values = {
        field_id: field.value
        for field_id, field in retained.items()
        if field_id.startswith("xmp.")
    }
    if xmp_values:
        order = tuple(
            field_id for field_id in FIELD_ORDER if field_id in xmp_values
        )
        segments.append(
            make_jpeg_app_segment(
                1, _build_xmp_payload(xmp_values, field_order=order)
            )
        )
    if "icc.profile" in retained:
        segments.append(_build_icc_segments(retained["icc.profile"].value))
    if "app13.opaque" in retained:
        segments.append(
            make_jpeg_app_segment(
                13,
                _APP13_IDENTIFIER + retained["app13.opaque"].value,
            )
        )
    if "jpeg.comment" in retained:
        segments.append(
            _make_segment(0xFE, retained["jpeg.comment"].value)
        )
    return jpeg_bytes[:2] + b"".join(segments) + jpeg_bytes[2:]


def _build_exif_payload(
    values: dict[str, bytes],
    *,
    endian: Literal["big", "little"],
    field_order: tuple[str, ...],
) -> bytes:
    """Build a bounded TIFF IFD0 for the controlled EXIF fields."""
    if set(values) != set(field_order):
        raise ValueError("EXIF field order must match the provided values")
    byte_order = b"MM" if endian == "big" else b"II"
    entries_start = 10
    data_offset = entries_start + len(field_order) * 12 + 4
    entries = bytearray()
    data = bytearray()
    for field_id in field_order:
        if field_id not in _EXIF_TAGS:
            raise ValueError(f"unsupported controlled EXIF field: {field_id}")
        tag = _EXIF_TAGS[field_id]
        value = values[field_id]
        if field_id == "exif.orientation":
            orientation = int(value.decode("ascii"))
            entries.extend(tag.to_bytes(2, endian))
            entries.extend((3).to_bytes(2, endian))
            entries.extend((1).to_bytes(4, endian))
            entries.extend(orientation.to_bytes(2, endian) + b"\x00\x00")
            continue
        terminated = value + b"\x00"
        entries.extend(tag.to_bytes(2, endian))
        entries.extend((2).to_bytes(2, endian))
        entries.extend(len(terminated).to_bytes(4, endian))
        entries.extend((data_offset + len(data)).to_bytes(4, endian))
        data.extend(terminated)
    tiff = (
        byte_order
        + (42).to_bytes(2, endian)
        + (8).to_bytes(4, endian)
        + len(field_order).to_bytes(2, endian)
        + bytes(entries)
        + b"\x00\x00\x00\x00"
        + bytes(data)
    )
    return _EXIF_IDENTIFIER + tiff


def _parse_exif_fields(
    payload: bytes, ordinal: int
) -> list[JPEGMetadataField]:
    """Parse the controlled EXIF IFD0 into normalized field values."""
    tiff = payload[len(_EXIF_IDENTIFIER) :]
    if len(tiff) < 10:
        raise ValueError("truncated controlled EXIF header")
    if tiff[:2] == b"MM":
        endian = "big"
    elif tiff[:2] == b"II":
        endian = "little"
    else:
        raise ValueError("invalid controlled EXIF byte order")
    if int.from_bytes(tiff[2:4], endian) != 42:
        raise ValueError("invalid controlled EXIF magic")
    ifd_offset = int.from_bytes(tiff[4:8], endian)
    if ifd_offset < 8 or ifd_offset + 2 > len(tiff):
        raise ValueError("controlled EXIF IFD offset is out of bounds")
    count = int.from_bytes(tiff[ifd_offset : ifd_offset + 2], endian)
    entries_start = ifd_offset + 2
    entries_end = entries_start + count * 12
    if entries_end + 4 > len(tiff):
        raise ValueError("truncated controlled EXIF IFD")
    fields: list[JPEGMetadataField] = []
    for index in range(count):
        start = entries_start + index * 12
        entry = tiff[start : start + 12]
        tag = int.from_bytes(entry[:2], endian)
        if tag not in _EXIF_FIELDS:
            continue
        field_id, expected_type = _EXIF_FIELDS[tag]
        field_type = int.from_bytes(entry[2:4], endian)
        value_count = int.from_bytes(entry[4:8], endian)
        if field_type != expected_type or value_count == 0:
            raise ValueError(f"invalid controlled EXIF field: {field_id}")
        if field_type == 3:
            if value_count != 1:
                raise ValueError("EXIF orientation count must be one")
            value = str(int.from_bytes(entry[8:10], endian)).encode("ascii")
        else:
            if value_count <= 4:
                raw = entry[8 : 8 + value_count]
            else:
                offset = int.from_bytes(entry[8:12], endian)
                if offset + value_count > len(tiff):
                    raise ValueError(
                        f"controlled EXIF value exceeds bounds: {field_id}"
                    )
                raw = tiff[offset : offset + value_count]
            if not raw.endswith(b"\x00"):
                raise ValueError(
                    f"controlled EXIF ASCII is not terminated: {field_id}"
                )
            value = raw[:-1]
        fields.append(_field(field_id, "app1_exif", ordinal, value))
    return fields


def _build_xmp_payload(
    values: dict[str, bytes],
    *,
    field_order: tuple[str, ...],
) -> bytes:
    """Build one compact deterministic XMP packet."""
    if set(values) != set(field_order):
        raise ValueError("XMP field order must match the provided values")
    for prefix, uri in _NS.items():
        ET.register_namespace(prefix, uri)
    root = ET.Element(f"{{{_NS['x']}}}xmpmeta")
    rdf = ET.SubElement(root, f"{{{_NS['rdf']}}}RDF")
    description = ET.SubElement(rdf, f"{{{_NS['rdf']}}}Description")
    for field_id in field_order:
        text = values[field_id].decode("utf-8")
        if field_id == "xmp.dc_title":
            node = ET.SubElement(description, f"{{{_NS['dc']}}}title")
            alt = ET.SubElement(node, f"{{{_NS['rdf']}}}Alt")
            item = ET.SubElement(
                alt,
                f"{{{_NS['rdf']}}}li",
                {"{http://www.w3.org/XML/1998/namespace}lang": "x-default"},
            )
            item.text = text
        elif field_id == "xmp.dc_creator":
            node = ET.SubElement(description, f"{{{_NS['dc']}}}creator")
            sequence = ET.SubElement(node, f"{{{_NS['rdf']}}}Seq")
            ET.SubElement(sequence, f"{{{_NS['rdf']}}}li").text = text
        elif field_id == "xmp.exif_gps_latitude":
            ET.SubElement(
                description, f"{{{_NS['exif']}}}GPSLatitude"
            ).text = text
        elif field_id == "xmp.exif_gps_longitude":
            ET.SubElement(
                description, f"{{{_NS['exif']}}}GPSLongitude"
            ).text = text
        elif field_id == "xmp.synthetic_pipeline_hint":
            ET.SubElement(
                description, f"{{{_NS['synthetic']}}}PipelineHint"
            ).text = text
        else:
            raise ValueError(f"unsupported controlled XMP field: {field_id}")
    return _XMP_IDENTIFIER + ET.tostring(
        root, encoding="utf-8", xml_declaration=False
    )


def _parse_xmp_fields(
    payload: bytes, ordinal: int
) -> list[JPEGMetadataField]:
    """Parse the five controlled XMP properties."""
    xml_bytes = payload[len(_XMP_IDENTIFIER) :]
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ValueError("invalid controlled XMP XML") from error
    paths = {
        "xmp.dc_title": (
            f".//{{{_NS['dc']}}}title/"
            f"{{{_NS['rdf']}}}Alt/{{{_NS['rdf']}}}li"
        ),
        "xmp.dc_creator": (
            f".//{{{_NS['dc']}}}creator/"
            f"{{{_NS['rdf']}}}Seq/{{{_NS['rdf']}}}li"
        ),
        "xmp.exif_gps_latitude": (
            f".//{{{_NS['exif']}}}GPSLatitude"
        ),
        "xmp.exif_gps_longitude": (
            f".//{{{_NS['exif']}}}GPSLongitude"
        ),
        "xmp.synthetic_pipeline_hint": (
            f".//{{{_NS['synthetic']}}}PipelineHint"
        ),
    }
    fields: list[JPEGMetadataField] = []
    for field_id in FIELD_ORDER:
        if field_id not in paths:
            continue
        nodes = root.findall(paths[field_id])
        if len(nodes) > 1:
            raise ValueError(f"duplicate controlled XMP field: {field_id}")
        if not nodes:
            continue
        text = nodes[0].text
        if text is None:
            raise ValueError(f"empty controlled XMP field: {field_id}")
        fields.append(
            _field(field_id, "app1_xmp", ordinal, text.encode("utf-8"))
        )
    return fields


def _build_icc_segments(profile: bytes) -> bytes:
    """Split one ICC profile into deterministic APP2 chunks."""
    maximum_chunk_size = 65533 - 14
    chunks = [
        profile[start : start + maximum_chunk_size]
        for start in range(0, len(profile), maximum_chunk_size)
    ]
    if len(chunks) > 255:
        raise ValueError("ICC profile requires more than 255 APP2 chunks")
    return b"".join(
        make_jpeg_app_segment(
            2,
            _ICC_IDENTIFIER + bytes((index, len(chunks))) + chunk,
        )
        for index, chunk in enumerate(chunks, start=1)
    )


def _header_segments(jpeg_bytes: bytes) -> tuple[tuple[int, bytes], ...]:
    """Return length-delimited JPEG header segments before SOS."""
    segments: list[tuple[int, bytes]] = []
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
        payload_start, payload_end = _payload_bounds(jpeg_bytes, position)
        segments.append((marker, jpeg_bytes[payload_start:payload_end]))
        position = payload_end
    return tuple(segments)


def _payload_bounds(jpeg_bytes: bytes, length_offset: int) -> tuple[int, int]:
    """Return validated payload bounds for one length-delimited segment."""
    if length_offset + 2 > len(jpeg_bytes):
        raise ValueError("truncated JPEG segment length")
    segment_length = int.from_bytes(
        jpeg_bytes[length_offset : length_offset + 2], "big"
    )
    if segment_length < 2:
        raise ValueError("invalid JPEG segment length")
    payload_start = length_offset + 2
    payload_end = length_offset + segment_length
    if payload_end > len(jpeg_bytes):
        raise ValueError("JPEG segment exceeds the input")
    return payload_start, payload_end


def _make_segment(marker: int, payload: bytes) -> bytes:
    """Build one non-APP length-delimited JPEG segment."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    segment_length = len(payload) + 2
    if segment_length > 65535:
        raise ValueError("JPEG segment exceeds the 16-bit length field")
    return (
        b"\xff"
        + bytes((marker,))
        + segment_length.to_bytes(2, "big")
        + payload
    )


def _field(
    field_id: str,
    container: str,
    source_ordinal: int,
    value: bytes,
) -> JPEGMetadataField:
    """Build one validated controlled field record."""
    return JPEGMetadataField(
        field_id=field_id,
        category=FIELD_CATEGORIES[field_id],
        container=container,
        source_ordinal=source_ordinal,
        value=value,
    )


def _validate_jpeg(jpeg_bytes: bytes, name: str) -> None:
    """Validate a complete byte input at the controlled public boundary."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError(f"{name} must be non-empty bytes")
    if not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError(f"{name} must start with a JPEG SOI marker")
