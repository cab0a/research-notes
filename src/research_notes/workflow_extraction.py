"""Connect the existing STEP inventory to workflow fields with local provenance.

The adapter observes and maps; it does not certify workflow completion,
customer suitability, manufacturing dimensions or time savings.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import time

from .workflow_contract import canonical_bytes, read_contract, review_contract, FIELD_RULES

VERSION = "1.17.0"
SCHEMA_VERSION = "1.0.0"
ROUTE = "existing_occt_step_hole_inventory"
MAX_SOURCE_BYTES = 2_000_000
IMPLEMENTATION_FILES = ("workflow_extraction.py", "hole_inventory.py", "public_hole_inventory.py",
                        "slot_inventory.py", "hole_review.py", "local_material.py")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _count(value, *, positive=False):
    return type(value) is int and value >= (1 if positive else 0)


def _number(value, *, positive=False):
    return type(value) in (int, float) and abs(value) <= 1e100 and math.isfinite(value) and (not positive or value > 0)


def _vector(value, *, unit=False):
    return isinstance(value, list) and len(value) == 3 and all(_number(v) for v in value) and (
        not unit or abs(sum(v*v for v in value) - 1) <= 1e-8)


def _copy(value):
    return json.loads(canonical_bytes(value))


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _binding(session, case_id, source_sha256, contract_sha256):
    if session is None:
        _require(case_id is None, "--caseには--baseline-sessionが必要です。")
        return None
    from .workflow_baseline import validate_session
    validate_session(session)
    _require(session["method"] == "existing_extraction_with_full_review", "抽出の接続には抽出＋全件確認のセッションを使ってください。")
    _require(session["contract_sha256"] == contract_sha256, "基準記録と業務定義のハッシュが一致しません。")
    _require(isinstance(case_id, str), "基準記録へ接続する部品IDが必要です。")
    case = next((c for c in session["case_manifest"]["cases"] if c["id"] == case_id), None)
    _require(case is not None and case["source_sha256"] == source_sha256, "部品IDまたは入力SHA-256が基準記録と一致しません。")
    return {"session_id": session["session_id"], "session_sha256": _digest(session),
        "case_manifest_sha256": session["case_manifest_sha256"], "case_id": case_id,
        "family_id": case["family_id"], "record_kind": session["record_kind"],
        "session_modified": False, "timing_or_quality_record_added": False}


def _validate_inventory(result, source_sha256, size):
    _require(isinstance(result, dict), "既存認識器の結果がオブジェクトではありません。")
    _require(result.get("inventory_version") == "1.14.0" and result.get("analysis_mode") == "public_inspection"
        and result.get("feature_scope") == "circular_and_slots", "接続対象の認識版・読込モードと一致しません。")
    _require(result.get("source_sha256") == source_sha256 and result.get("source_bytes") == size, "入力と抽出結果のハッシュ・バイト数が一致しません。")
    status = result.get("status")
    _require(status in ("complete", "partial", "unresolved", "rejected"), "抽出結果の状態が不明です。")
    holes, metrics = result.get("holes"), result.get("metrics")
    _require(isinstance(holes, list), "抽出行が配列ではありません。")
    _require(all(isinstance(h, dict) for h in holes), "抽出行の形式が不正です。")
    circles = sum(h.get("feature_type") == "circular_hole" for h in holes)
    slots = sum(h.get("feature_type") == "straight_slot" for h in holes)
    for key, value in (("recognized_hole_count", len(holes)), ("recognized_circular_hole_count", circles), ("recognized_slot_count", slots)):
        _require(_count(result.get(key)) and result[key] == value, "認識行数・内訳と行の内容が一致しません。")
    _require(circles + slots == len(holes), "未定義の特徴種別があります。")
    count = result.get("hole_count")
    if status == "complete":
        _require(_count(count) and count == len(holes), "全体数と全体確定の行が一致しません。")
    else:
        _require(count is None, "部分確認・未解析の全体数を数値へ置き換えられません。")
    state = "unknown" if count is None else "certified_zero" if count == 0 else "certified_count"
    _require(isinstance(result.get("review_summary"), dict) and result["review_summary"].get("count_state") == state,
             "全体数の状態が既存の保留説明と一致しません。")
    _require(isinstance(result.get("review_items"), list) and isinstance(result.get("conditions"), dict), "既存の保留説明・実行条件がありません。")
    if status == "rejected":
        _require(not holes and metrics is None and result.get("length_unit") is None, "読込拒否に測定済みの形状を割り当てられません。")
        return
    _require(result.get("length_unit") == "mm" and isinstance(metrics, dict), "mmの形状測定結果が必要です。")
    _require(_count(metrics.get("solid_count"), positive=True) and _count(metrics.get("face_count"), positive=True), "部品数・面数が不正です。")
    if status == "complete":
        _require(metrics["solid_count"] == 1, "全体確定は単一ソリッドの既存条件に限定します。")
    ids = set()
    for hole in holes:
        _require(set(("id", "feature_type", "kind", "diameter_mm", "width_mm", "length_mm", "longitudinal_direction",
                      "x_mm", "y_mm", "entry_z_mm", "axis", "depth_mm", "faces")) <= hole.keys(), "抽出行に必要な項目が不足しています。")
        identifier = hole.get("id")
        _require(isinstance(identifier, str) and identifier and identifier not in ids, "特徴IDが空または重複しています。")
        ids.add(identifier)
        _require(_vector(hole.get("axis"), unit=True) and _number(hole.get("depth_mm"), positive=True)
            and all(_number(hole.get(k)) for k in ("x_mm", "y_mm", "entry_z_mm")), "位置・方向・深さの値が不正です。")
        faces = hole.get("faces")
        _require(isinstance(faces, list) and bool(faces) and all(_count(f, positive=True) and f <= metrics["face_count"] for f in faces), "参照面が入力の面数に整合しません。")
        if "solid_index" in hole:
            _require(_count(hole["solid_index"], positive=True) and hole["solid_index"] <= metrics["solid_count"], "ソリッド参照が不正です。")
        if hole["feature_type"] == "circular_hole":
            _require(hole.get("kind") in ("through", "blind") and _number(hole.get("diameter_mm"), positive=True)
                and all(hole.get(k) is None for k in ("width_mm", "length_mm", "longitudinal_direction")), "丸穴の寸法欄が不整合です。")
        else:
            _require(hole.get("kind") == "straight_through_slot" and hole.get("diameter_mm") is None
                and _number(hole.get("width_mm"), positive=True) and _number(hole.get("length_mm"), positive=True)
                and hole["length_mm"] >= hole["width_mm"] and _vector(hole.get("longitudinal_direction"), unit=True), "長孔の寸法・長手方向が不整合です。")
    canonical_bytes(result)  # Refuse nonfinite observations anywhere in the retained snapshot.


def _runtime():
    directory = Path(__file__).parent
    return {"python": platform.python_version(), "platform": platform.platform(),
        "package_version": importlib.metadata.version("research-notes"),
        "cadquery_ocp": importlib.metadata.version("cadquery-ocp"),
        "selected_implementation_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in IMPLEMENTATION_FILES}}


def _assemble(result, contract, part_reference, binding, seconds):
    def cell(name, value, paths, *, operation="copy", availability=None):
        return {"value": value, "availability": availability or ("unknown" if value is None else "present"),
                "unit": FIELD_RULES[name][2], "provenance": {"paths": paths, "operation": operation}}

    summary = {"part_reference": cell("part_reference", part_reference, ["/caller_input/part_reference"],
                    availability="not_provided" if part_reference is None else "present")}
    for name, source in (("source_sha256", "source_sha256"), ("whole_hole_count", "hole_count"), ("recognized_hole_count", "recognized_hole_count")):
        summary[name] = cell(name, result[source], ["/inventory/" + source])
    summary["count_state"] = cell("count_state", result["review_summary"]["count_state"], ["/inventory/review_summary/count_state"])
    features = []
    for index, hole in enumerate(result["holes"]):
        prefix = f"/inventory/holes/{index}/"
        fields = {}
        for name, source in (("feature_id", "id"), ("feature_type", "feature_type"), ("hole_type", "kind"),
                             ("diameter_mm", "diameter_mm"), ("width_mm", "width_mm"), ("length_mm", "length_mm"),
                             ("inward_axis", "axis"), ("long_axis", "longitudinal_direction"), ("depth_mm", "depth_mm"), ("face_references", "faces")):
            nonapplicable = FIELD_RULES[name][1] in ("circular_hole", "straight_slot") and FIELD_RULES[name][1] != hole["feature_type"]
            fields[name] = cell(name, hole[source], [prefix + source], availability="not_applicable" if nonapplicable else None)
        fields["entry_center_mm"] = cell("entry_center_mm", [hole[k] for k in ("x_mm", "y_mm", "entry_z_mm")],
            [prefix + k for k in ("x_mm", "y_mm", "entry_z_mm")], operation="xyz_vector")
        if "solid_index" in hole:
            fields["solid_index"] = cell("solid_index", hole["solid_index"], [prefix + "solid_index"])
        elif result["metrics"]["solid_count"] == 1:
            fields["solid_index"] = cell("solid_index", 1, ["/inventory/metrics/solid_count"], operation="sole_solid_index")
        else:
            fields["solid_index"] = cell("solid_index", None, ["/inventory/metrics/solid_count"], operation="owner_not_recorded")
        features.append({"fields": fields})
    return _copy({"connector_version": VERSION, "schema_version": SCHEMA_VERSION,
        "route": {"id": ROUTE, "entry_point": "research_notes.hole_inventory.analyze_step", "inventory_version": result["inventory_version"],
            "options": {"inspection": True, "include_slots": True, "preview": False}, "runtime": _runtime()},
        "source": {"format": "STEP_Part21", "sha256": result["source_sha256"], "bytes": result["source_bytes"], "file_name": result["file_name"]},
        "contract": contract, "contract_sha256": _digest(contract), "caller_input": {"part_reference": part_reference},
        "inventory": result, "inventory_sha256": _digest(result), "baseline_binding": binding,
        "input_observations": {"inventory_status": result["status"], "length_unit": result["length_unit"],
            "unit_contexts": result.get("unit_contexts"), "roots": result.get("roots"), "metrics": result["metrics"],
            "single_solid_observed": result["metrics"]["solid_count"] == 1 if result["metrics"] else None,
            "provenance_paths": ["/inventory/metrics", "/inventory/length_unit"]},
        "summary": summary, "features": features,
        "timing": {"extraction_seconds": seconds, "scope": "inventory_call_only", "operator_time_measured": False},
        "contract_conformance": "not_evaluated", "business_completion": "not_evaluated", "adoption_decision": "not_evaluated",
        "customer_approved": False,
        "claim_boundary": "既存抽出の観測値と出所の接続です。値の存在は業務への自動採用・全体完了・加工精度・顧客合意・省力化を意味しません。"})


def extract_step(source: bytes, contract, *, file_name="uploaded.step", part_reference=None, baseline_session=None, case_id=None):
    """Run exactly one existing inventory call and retain its unmodified snapshot."""
    _require(type(source) is bytes and 0 < len(source) <= MAX_SOURCE_BYTES, "入力は空でない2 MB以下のSTEPバイト列です。")
    _require(isinstance(file_name, str), "ファイル名は文字列にしてください。")
    _require(part_reference is None or isinstance(part_reference, str) and bool(part_reference.strip()), "部品参照は明示した文字列または未指定のNoneです。")
    _require(review_contract(contract)["definition_valid"], "業務定義がv1.15の基準仕様と一致しません。")
    contract = _copy(contract)
    digest = hashlib.sha256(source).hexdigest()
    binding = _binding(baseline_session, case_id, digest, _digest(contract))
    from .hole_inventory import analyze_step
    start = time.perf_counter()
    result = analyze_step(source, file_name, inspection=True, include_slots=True, preview=False)
    seconds = time.perf_counter() - start
    _validate_inventory(result, digest, len(source))
    return _assemble(result, contract, part_reference, binding, seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description="既存のSTEP穴一覧を業務項目へ接続し、値・条件・出所を保存します。")
    parser.add_argument("step", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--part-reference")
    parser.add_argument("--baseline-session", type=Path)
    parser.add_argument("--case", dest="case_id")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        destination = args.output_dir / "workflow-extraction.json" if args.output_dir else None
        inputs = [args.step, args.contract] + ([args.baseline_session] if args.baseline_session else [])
        _require(destination is None or all(destination.resolve() != p.resolve() for p in inputs), "出力先が入力ファイルと同じです。")
        contract = read_contract(args.contract)
        session = read_contract(args.baseline_session) if args.baseline_session else None
        with args.step.open("rb") as stream:
            source = stream.read(MAX_SOURCE_BYTES + 1)
        report = extract_step(source, contract, file_name=args.step.name, part_reference=args.part_reference,
            baseline_session=session, case_id=args.case_id)
        data = canonical_bytes(report)
        if destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        print(data.decode(), end="")
        return 0
    except (ValueError, OSError, RuntimeError, ImportError, RecursionError) as error:
        print(canonical_bytes({"connector_version": VERSION, "connection_succeeded": False, "error": str(error), "adoption_decision": "not_evaluated"}).decode(), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
