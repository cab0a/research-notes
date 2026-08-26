"""Build a provenance-bound synthetic STEP dataset and grouped splits."""

from __future__ import annotations

import hashlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path

from research_notes.brep_runtime import StepRoundTrip, status_name, step_round_trip
from research_notes.feature_benchmark import BenchmarkCase, _transform_shape, benchmark_cases
from research_notes.feature_recognition import _measure_graph
from research_notes.modeling_common import measure_shape


CONTRACT_VERSION = "1.0.0"
SPLIT_BY_FAMILY = {
    "plain_block": "train",
    "through_hole": "train",
    "blind_hole": "train",
    "stepped_block": "train",
    "through_slot": "validation",
    "chamfer_operation": "validation",
    "cylindrical_boss": "validation",
    "fillet_operation": "test",
    "toroidal_surface": "test",
}


@dataclass(frozen=True)
class DatasetSample:
    """One STEP-backed sample with labels, split, and measured descriptors."""

    sample_id: str
    family_id: str
    perturbation: str
    split: str
    feature_label: str
    supported_feature: bool
    source_file: str
    source_sha256: str
    source_bytes: int
    fixture_origin: str
    label_provenance: str
    vertex_count: int
    edge_count: int
    face_count: int
    relation_count: int
    plane_face_count: int
    cylinder_face_count: int
    other_curved_face_count: int
    mean_degree: float
    curved_area_ratio: float
    absolute_volume: float
    surface_area: float
    structural_signature_sha256: str


@dataclass(frozen=True)
class DatasetLeakageCheck:
    """One declared leakage invariant and its observed violation count."""

    check_id: str
    scope: str
    violation_count: int
    passed: bool
    interpretation: str


@dataclass(frozen=True)
class SyntheticDatasetProbe:
    """Complete v0.53.0 dataset, fixture, graph, and leakage evidence."""

    samples: tuple[DatasetSample, ...]
    graphs: tuple[dict[str, object], ...]
    leakage_checks: tuple[DatasetLeakageCheck, ...]
    added_fixtures: tuple[StepRoundTrip, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def _read_step(path: Path) -> object:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed for {path.name}: {status_name(status)}")
    if int(reader.TransferRoots()) <= 0:
        raise RuntimeError(f"STEP file has no transferred roots: {path.name}")
    return reader.OneShape()


def _torus_cases() -> tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase("toroidal_surface_baseline", "toroidal_surface", "baseline", None, None, 1.0, 0.0, 1.0e-7, False),
        BenchmarkCase("toroidal_surface_small_scale", "toroidal_surface", "small_scale", None, None, 0.5, 0.0, 1.0e-7, False),
        BenchmarkCase("toroidal_surface_rotated_x_30", "toroidal_surface", "rotated_x_30", None, None, 1.0, 30.0, 1.0e-7, False),
        BenchmarkCase("toroidal_surface_tolerance_healed", "toroidal_surface", "tolerance_healed", None, None, 1.0, 0.0, 1.0e-3, True),
    )


def _transform_torus(source: object, case: BenchmarkCase) -> object:
    if case.perturbation != "rotated_x_30":
        return _transform_shape(source, case)
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf
    import math

    transform = gp_Trsf()
    transform.SetRotation(
        gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(1.0, 0.0, 0.0)),
        math.radians(case.rotation_degrees),
    )
    return BRepBuilderAPI_Transform(source, transform, True).Shape()


def _generate_torus_fixtures() -> tuple[tuple[BenchmarkCase, StepRoundTrip], ...]:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus

    source = BRepPrimAPI_MakeTorus(3.0, 1.0).Shape()
    rows = []
    for case in _torus_cases():
        shape = _transform_torus(source, case)
        rows.append((case, step_round_trip(shape, f"dataset_{case.case_id}")))
    return tuple(rows)


def _feature_label(case: BenchmarkCase) -> str:
    if case.expected_type is None:
        return "none"
    return f"{case.expected_type}:{case.expected_subtype}"


def _signature(nodes: tuple[object, ...], relations: tuple[object, ...]) -> str:
    payload = "|".join(
        sorted(f"n:{item.surface_type}:{len(item.adjacent_face_indices)}" for item in nodes)
        + sorted(
            f"e:{nodes[item.first_face_index - 1].surface_type}:{nodes[item.second_face_index - 1].surface_type}:{item.curve_type}"
            for item in relations
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sample(case: BenchmarkCase, path: Path, origin: str) -> tuple[DatasetSample, dict[str, object], object]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    shape = _read_step(path)
    nodes, relations = _measure_graph(case.case_id, "step_imported", shape)
    metrics = measure_shape(shape)
    surfaces = [item.surface_type for item in nodes]
    curved_area = sum(item.area for item in nodes if item.surface_type != "plane")
    label = _feature_label(case)
    sample = DatasetSample(
        case.case_id,
        case.source_control_id,
        case.perturbation,
        SPLIT_BY_FAMILY[case.source_control_id],
        label,
        label != "none",
        path.name,
        digest,
        len(payload),
        origin,
        "repository synthetic construction specification",
        metrics.vertex_count,
        metrics.edge_count,
        metrics.face_count,
        len(relations),
        surfaces.count("plane"),
        surfaces.count("cylinder"),
        sum(item not in {"plane", "cylinder"} for item in surfaces),
        sum(len(item.adjacent_face_indices) for item in nodes) / len(nodes),
        curved_area / metrics.surface_area,
        metrics.absolute_volume,
        metrics.surface_area,
        _signature(nodes, relations),
    )
    graph = {
        "sample_id": sample.sample_id,
        "source_sha256": digest,
        "directed": False,
        "nodes": [
            {
                "id": f"f{item.face_index}",
                "surface_type": item.surface_type,
                "area": item.area,
                "degree": len(item.adjacent_face_indices),
            }
            for item in nodes
        ],
        "relations": [
            {
                "id": f"e{item.edge_index}",
                "source": f"f{item.first_face_index}",
                "target": f"f{item.second_face_index}",
                "curve_type": item.curve_type,
            }
            for item in relations
        ],
        "structural_signature_sha256": sample.structural_signature_sha256,
    }
    return sample, graph, shape


def _leakage_checks(samples: tuple[DatasetSample, ...]) -> tuple[DatasetLeakageCheck, ...]:
    def across_splits(attribute: str) -> int:
        split_sets: dict[str, set[str]] = {}
        for item in samples:
            split_sets.setdefault(str(getattr(item, attribute)), set()).add(item.split)
        return sum(len(splits) > 1 for splits in split_sets.values())

    duplicate_ids = len(samples) - len({item.sample_id for item in samples})
    missing = sum(not item.label_provenance or not item.source_sha256 for item in samples)
    values = (
        ("unique_sample_id", "dataset", duplicate_ids, "sample identifiers are unique"),
        ("family_group_isolation", "split", across_splits("family_id"), "one construction family appears in only one split"),
        ("source_digest_isolation", "split", across_splits("source_sha256"), "identical STEP bytes do not cross splits"),
        ("source_file_isolation", "split", across_splits("source_file"), "one source path does not cross splits"),
        ("required_provenance", "dataset", missing, "every sample has label and STEP digest provenance"),
    )
    return tuple(DatasetLeakageCheck(check, scope, count, count == 0, text) for check, scope, count, text in values)


def probe_synthetic_dataset(source_fixture_dir: Path, added_fixture_dir: Path, *, refresh_added: bool) -> SyntheticDatasetProbe:
    """Build the dataset from v0.52 fixtures plus four torus negatives."""
    existing_cases = benchmark_cases()
    torus_pairs = _generate_torus_fixtures()
    expected = {fixture.file_name: fixture.source_bytes for _, fixture in torus_pairs}
    added_fixture_dir.mkdir(parents=True, exist_ok=True)
    if refresh_added:
        for name, payload in expected.items():
            (added_fixture_dir / name).write_bytes(payload)
    else:
        for name, payload in expected.items():
            target = added_fixture_dir / name
            if not target.exists() or target.read_bytes() != payload:
                raise RuntimeError(f"dataset fixture differs; rerun with --refresh-fixtures: {target}")

    samples: list[DatasetSample] = []
    graphs: list[dict[str, object]] = []
    previews: list[tuple[str, object]] = []
    for case in existing_cases:
        path = source_fixture_dir / f"benchmark_{case.case_id}.step"
        sample, graph, shape = _sample(case, path, "v0.52.0 feature benchmark fixture")
        samples.append(sample)
        graphs.append(graph)
        if case.perturbation == "baseline":
            previews.append((case.source_control_id, shape))
    for case, fixture in torus_pairs:
        path = added_fixture_dir / fixture.file_name
        sample, graph, shape = _sample(case, path, "v0.53.0 dataset fixture")
        samples.append(sample)
        graphs.append(graph)
        if case.perturbation == "baseline":
            previews.append((case.source_control_id, shape))
    sample_tuple = tuple(samples)
    return SyntheticDatasetProbe(
        sample_tuple,
        tuple(graphs),
        _leakage_checks(sample_tuple),
        tuple(fixture for _, fixture in torus_pairs),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
