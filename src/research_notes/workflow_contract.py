"""Freeze and check a research workflow definition, not a CAD adoption decision.

v1.15 defines one part's hole inventory -> existing table workflow. This module
does not recognise geometry, write a workbook, predict suitability or measure
operator time. A valid reference definition is not customer approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

VERSION = "1.15.0"
SCHEMA_VERSION = "1.0.0"
MAX_CONTRACT_BYTES = 128_000

# Explicit conditional fields keep circle diameter separate from slot dimensions.
FIELD_RULES = {
    "part_reference": ("summary", "always", "text"),
    "source_sha256": ("summary", "always", "sha256"),
    "whole_hole_count": ("summary", "always", "count_or_unknown"),
    "recognized_hole_count": ("summary", "always", "count"),
    "count_state": ("summary", "always", "state"),
    "feature_id": ("feature", "all_features", "input_local_id"),
    "feature_type": ("feature", "all_features", "type"),
    "hole_type": ("feature", "all_features", "type"),
    "diameter_mm": ("feature", "circular_hole", "mm"),
    "width_mm": ("feature", "straight_slot", "mm"),
    "length_mm": ("feature", "straight_slot", "mm"),
    "entry_center_mm": ("feature", "all_features", "mm_vector3"),
    "inward_axis": ("feature", "all_features", "unit_vector3"),
    "long_axis": ("feature", "straight_slot", "unit_vector3"),
    "depth_mm": ("feature", "all_features", "mm"),
    "solid_index": ("feature", "all_features", "input_local_index"),
    "face_references": ("feature", "all_features", "input_local_indices"),
}
COORDINATES = {
    "length_unit": "mm", "origin": "source_model_origin",
    "position": "selected_opening_center", "axis": "opening_to_inside",
    "slot_length": "overall_including_semicircle_ends",
    "slot_axis_sign": "lexicographic_end_centers", "transform": "none",
    "rounding": "presentation_only",
}
COMPLETION = {
    "whole_count_required": True, "partial_is_complete": False,
    "unknown_is_zero": False, "unanalysed_is_zero": False,
    "confirmed_zero_requires_full_coverage": True,
    "unresolved_required_fields_block_completion": True,
}
METRICS = (
    "false_auto_fields", "missed_required_features", "false_complete_parts",
    "unknown_truth_parts", "review_parts", "total_parts", "setup_sample_count",
    "setup_minutes", "manual_task_minutes", "execution_minutes", "review_minutes",
    "correction_minutes", "rerun_minutes", "update_minutes",
)
STAGES = ("input_check", "extract", "review", "transfer", "final_check")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def validate_contract(contract: object) -> list[dict[str, str]]:
    """Return definition issues. No input parts or customer agreement are inferred."""
    issues: list[dict[str, str]] = []

    def issue(path: str, code: str, message: str) -> None:
        issues.append({"path": path, "code": code, "message": message})

    def obj(value: object, path: str, keys: set[str]) -> dict:
        if not isinstance(value, dict):
            issue(path, "object_required", "項目をオブジェクトとして指定してください。")
            return {}
        for key in sorted(keys - value.keys()):
            issue(f"{path}.{key}", "missing_definition", "業務・評価の定義が不足しています。")
        for key in sorted(value.keys() - keys, key=str):
            issue(f"{path}.{key}", "unknown_definition", "未定義の項目です。綴りと仕様版を確認してください。")
        return value

    def text(value: object, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            issue(path, "text_required", "具体的な説明を空でない文字列で指定してください。")

    def exact(value: object, expected: object, path: str) -> None:
        if type(value) is not type(expected) or value != expected:
            issue(path, "policy_mismatch", "基準業務の範囲・座標・完全性の定義と一致しません。")

    def number(value: object, path: str, *, integer: bool = False, positive: bool = False) -> None:
        valid = type(value) is int if integer else type(value) in (int, float)
        try:
            finite = valid and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite or value < 0 or (positive and value <= 0):
            issue(path, "invalid_threshold", "有限の非負値（指定項目は正値）で基準を定めてください。")

    root = obj(contract, "$", {"schema_version", "contract_id", "definition_status", "workflow", "fields",
        "coordinates", "completion", "truth", "comparison", "acceptance", "required_metrics", "customer_inputs"})
    exact(root.get("schema_version"), SCHEMA_VERSION, "$.schema_version")
    exact(root.get("definition_status"), "research_reference", "$.definition_status")
    text(root.get("contract_id"), "$.contract_id")
    workflow = obj(root.get("workflow"), "$.workflow", {"title", "part_unit", "feature_scope", "external_metadata", "stages"})
    text(workflow.get("title"), "$.workflow.title")
    exact(workflow.get("part_unit"), "single_solid_part", "$.workflow.part_unit")
    exact(workflow.get("feature_scope"), ["circular_through", "circular_flat_bottom_blind", "straight_through_slot"], "$.workflow.feature_scope")
    exact(workflow.get("external_metadata"), "manual_with_source_never_infer", "$.workflow.external_metadata")
    exact(workflow.get("stages"), list(STAGES), "$.workflow.stages")
    fields = obj(root.get("fields"), "$.fields", set(FIELD_RULES))
    for name, (level, required, unit) in FIELD_RULES.items():
        path = f"$.fields.{name}"
        field = obj(fields.get(name), path, {"level", "required_when", "unit", "meaning"})
        for key, expected in (("level", level), ("required_when", required), ("unit", unit)):
            exact(field.get(key), expected, path + "." + key)
        text(field.get("meaning"), path + ".meaning")
    for section, policy in (("coordinates", COORDINATES), ("completion", COMPLETION)):
        actual = obj(root.get(section), "$." + section, set(policy))
        for key, expected in policy.items():
            exact(actual.get(key), expected, f"$.{section}.{key}")
    truth = obj(root.get("truth"), "$.truth", {"allowed_sources", "recognizer_output_is_truth", "unknown_truth", "split_unit", "freeze_before_evaluation"})
    for key, expected in {"allowed_sources": ["independent_recipe", "independent_human_review"],
        "recognizer_output_is_truth": False, "unknown_truth": "retain_unknown_and_report_count",
        "split_unit": "part_family", "freeze_before_evaluation": True}.items():
        exact(truth.get(key), expected, "$.truth." + key)
    comparison = obj(root.get("comparison"), "$.comparison", {"baselines", "quality_matched", "time_scope"})
    for key, expected in {"baselines": ["manual_cad_and_transcription", "existing_extraction_with_full_review"],
        "quality_matched": True, "time_scope": "setup_plus_all_operator_work_and_execution"}.items():
        exact(comparison.get(key), expected, "$.comparison." + key)
    acceptance = obj(root.get("acceptance"), "$.acceptance", {"scope", "max_false_auto_fields", "max_false_complete_parts",
        "max_missed_required_features", "dimension_match_tolerance_mm", "net_time_saving_minutes_must_exceed", "planning_runs", "customer_agreed"})
    exact(acceptance.get("scope"), "fixed_labeled_evaluation_set_only", "$.acceptance.scope")
    exact(acceptance.get("customer_agreed"), False, "$.acceptance.customer_agreed")
    for key in ("max_false_auto_fields", "max_false_complete_parts", "max_missed_required_features", "planning_runs"):
        number(acceptance.get(key), "$.acceptance." + key, integer=True, positive=key == "planning_runs")
    number(acceptance.get("dimension_match_tolerance_mm"), "$.acceptance.dimension_match_tolerance_mm", positive=True)
    number(acceptance.get("net_time_saving_minutes_must_exceed"), "$.acceptance.net_time_saving_minutes_must_exceed")
    exact(root.get("required_metrics"), list(METRICS), "$.required_metrics")
    customer = root.get("customer_inputs")
    expected_inputs = {"actual_workbook", "field_mapping", "coordinate_basis", "quality_and_time_targets", "data_use_conditions"}
    customer = obj(customer, "$.customer_inputs", expected_inputs)
    for key in expected_inputs:
        exact(customer.get(key), "pending_customer_agreement", "$.customer_inputs." + key)
    return sorted(issues, key=lambda item: (item["path"], item["code"]))


def review_contract(contract: object) -> dict:
    issues = validate_contract(contract)
    return {
        "version": VERSION, "schema_version": SCHEMA_VERSION, "definition_valid": not issues,
        "contract_id": contract.get("contract_id") if isinstance(contract, dict) and isinstance(contract.get("contract_id"), str) else None,
        "contract_sha256": hashlib.sha256(canonical_bytes(contract)).hexdigest() if not issues else None,
        "definition_state": "research_definition_fixed" if not issues else "definition_incomplete",
        "customer_approved": False, "performance_measured": False, "adoption_decision": "not_evaluated",
        "issues": issues,
        "claim_boundary": "業務・評価の定義を確認した結果です。CADの適用可否、顧客合意、性能・省力化の判定ではありません。",
    }


def read_contract(path: Path) -> object:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("重複したJSONキーは使えません。")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("JSONに有限でない数値は使えません。")

    with path.open("rb") as stream:
        data = stream.read(MAX_CONTRACT_BYTES + 1)
    if len(data) > MAX_CONTRACT_BYTES:
        raise ValueError("業務定義は128000バイト以下にしてください。")
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="研究用の業務・評価定義を確認（CAD解析・帳票転記・採否判定はしません）。")
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        report = review_contract(read_contract(args.contract))
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        report = review_contract(None)
        report["issues"] = [{"path": "$", "code": "definition_read_failed", "message": str(error)}]
    data = canonical_bytes(report)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "contract-review.json").write_bytes(data)
    print(data.decode("utf-8"), end="")
    return 0 if report["definition_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
