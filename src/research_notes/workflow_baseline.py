"""Record a workflow baseline without inventing operator measurements.

One local session contains one method, one operator and a frozen case order.
Reported timings/quality remain observations supplied by the operator, not
independently certified facts or an adoption decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from .workflow_contract import canonical_bytes, read_contract, review_contract, MAX_CONTRACT_BYTES

VERSION = "1.16.0"
SCHEMA_VERSION = "1.0.0"
METHODS = {
    "manual_cad_and_transcription": ("input_check", "cad_open", "cad_check", "transfer", "final_check", "correction", "rerun"),
    "existing_extraction_with_full_review": ("input_check", "extract", "review", "transfer", "final_check", "correction", "rerun"),
}
BATCH_PHASES = ("input_preparation", "truth_labeling", "setup", "training", "update")
KINDS = ("operator_observation", "synthetic_control")
MAX_SECONDS = 7 * 24 * 60 * 60
PHASE_LABELS = {"input_preparation": "入力整備", "truth_labeling": "正解付け", "setup": "設定・準備", "training": "説明・習熟",
    "update": "更新", "input_check": "入力確認", "cad_open": "CAD・ファイルを開く", "cad_check": "形状・寸法確認",
    "extract": "抽出処理", "review": "抽出結果の全件確認", "transfer": "転記", "final_check": "最終チェック",
    "correction": "訂正", "rerun": "再実行"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _count(value):
    return type(value) is int and 0 <= value <= 1_000_000_000


def _seconds(value):
    return type(value) in (int, float) and 0 <= value <= MAX_SECONDS and math.isfinite(value)


def _digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _keys(value, expected, label):
    _require(isinstance(value, dict) and value.keys() == set(expected), label + "の項目が仕様と一致しません。")


def _cases(cases):
    _require(isinstance(cases, list) and 0 < len(cases) <= 100, "部品は1〜100件指定してください。")
    ids = set()
    for case in cases:
        _require(isinstance(case, dict), "部品定義がオブジェクトではありません。")
        for key in ("id", "family_id", "truth_origin", "truth_reference"):
            _require(_text(case.get(key)), "部品の" + key + "が必要です。")
        _require(case["id"] not in ids, "部品IDが重複しています。")
        ids.add(case["id"])
        digest = case.get("source_sha256")
        _require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "入力SHA-256が不正です。")
        _require("whole_count_truth" in case and (case["whole_count_truth"] is None or _count(case["whole_count_truth"])), "全体数の正解は非負整数またはnullです。")
        _require(case["whole_count_truth"] is None or case["truth_origin"] in ("independent_recipe", "independent_human_review"), "全体数の正解には独立した出所が必要です。")


def new_session(contract, manifest, *, method, operator, kind="operator_observation", tool=None, workbook=None):
    _require(review_contract(contract)["definition_valid"], "v1.15の業務定義が不整合です。")
    _require(isinstance(manifest, dict), "部品manifestが必要です。")
    _cases(manifest.get("cases"))
    session = {
        "version": VERSION, "schema_version": SCHEMA_VERSION, "session_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(), "record_kind": kind,
        "method": method, "operator_reference": operator, "tool_reference": tool, "workbook_reference": workbook,
        "contract": json.loads(canonical_bytes(contract)), "contract_sha256": _digest(contract),
        "case_manifest": json.loads(canonical_bytes(manifest)), "case_manifest_sha256": _digest(manifest),
        "phase_records": [], "quality_records": [],
    }
    validate_session(session)
    return session


def _phase_key(session, case_id, phase):
    _require(case_id is None or _text(case_id), "部品IDは文字列にしてください。")
    ids = {c["id"] for c in session["case_manifest"]["cases"]}
    if case_id is None:
        _require(phase in BATCH_PHASES, "部品IDなしでは準備・正解付け・設定・説明・更新だけ記録できます。")
    else:
        _require(case_id in ids and phase in METHODS[session["method"]], "部品IDまたは工程が対象外です。")
    return case_id, phase


def validate_session(session):
    _keys(session, ("version", "schema_version", "session_id", "created_at", "record_kind", "method", "operator_reference",
                    "tool_reference", "workbook_reference", "contract", "contract_sha256", "case_manifest",
                    "case_manifest_sha256", "phase_records", "quality_records"), "セッション")
    _require(session["version"] == VERSION and session["schema_version"] == SCHEMA_VERSION, "記録の版が異なります。")
    _require(_text(session["session_id"]) and _text(session["created_at"]), "記録IDと作成日時が必要です。")
    _require(session["record_kind"] in KINDS and isinstance(session["method"], str) and session["method"] in METHODS, "記録種別または方法が不正です。")
    _require(_text(session["operator_reference"]), "匿名の作業者参照が必要です。")
    for key in ("tool_reference", "workbook_reference"):
        _require(session[key] is None or _text(session[key]), key + "は文字列またはnullです。")
    _require(review_contract(session["contract"])["definition_valid"], "業務定義が不整合です。")
    _require(session["contract_sha256"] == _digest(session["contract"]), "業務定義のハッシュが不一致です。")
    _require(isinstance(session["case_manifest"], dict), "部品manifestが必要です。")
    _cases(session["case_manifest"].get("cases"))
    _require(session["case_manifest_sha256"] == _digest(session["case_manifest"]), "部品manifestのハッシュが不一致です。")
    _require(isinstance(session["phase_records"], list) and isinstance(session["quality_records"], list), "記録は配列にしてください。")
    closed = set()
    seen = set()
    for row in session["phase_records"]:
        _keys(row, ("id", "case_id", "phase", "seconds", "completed", "basis", "evidence_reference"), "時間記録")
        key = _phase_key(session, row["case_id"], row["phase"])
        _require(_text(row["id"]) and row["id"] not in seen, "時間記録IDが重複または空です。")
        seen.add(row["id"])
        _require(key not in closed, "完了した工程に重複記録できません。訂正・再実行は別工程へ記録してください。")
        _require(type(row["completed"]) is bool and _text(row["evidence_reference"]), "完了状態と記録根拠が必要です。")
        if row["basis"] == "not_needed":
            _require(row["seconds"] is None and row["completed"] and not any(
                (r["case_id"], r["phase"]) == key for r in session["phase_records"][:len(seen)-1]), "不要な工程は未計測と区別し、既存の時間を消さずに記録してください。")
        else:
            allowed = ("synthetic",) if session["record_kind"] == "synthetic_control" else ("interactive_monotonic", "reported_stopwatch")
            _require(row["basis"] in allowed and _seconds(row["seconds"]), "時間は有限の0〜604800秒、計測根拠は記録種別に合わせてください。")
        if row["completed"]:
            closed.add(key)
    ids = set()
    for row in session["quality_records"]:
        _validate_quality(session, row)
        _require(row["case_id"] not in ids, "同じ部品の品質記録が重複しています。")
        ids.add(row["case_id"])


def _validate_quality(session, row):
    _keys(row, ("case_id", "truth_scope", "truth_origin", "truth_reference", "truth_hole_count", "checked_fields",
                "incorrect_fields", "missed_features", "false_complete"), "品質記録")
    case = next((c for c in session["case_manifest"]["cases"] if c["id"] == row["case_id"]), None)
    _require(case is not None, "品質記録の部品IDが対象外です。")
    _require(row["truth_scope"] in ("unknown", "selected_fields", "whole_part"), "正解の確認範囲が不正です。")
    _require(row["truth_origin"] in ("unknown", "independent_recipe", "independent_human_review"), "正解は独立したレシピ・人の確認から作ってください。")
    _require(_text(row["truth_reference"]), "正解の参照先または未確認の理由が必要です。")
    for name in ("truth_hole_count", "checked_fields", "incorrect_fields", "missed_features"):
        _require(row[name] is None or _count(row[name]), name + "は非負整数または未確認のnullです。")
    _require(row["false_complete"] is None or type(row["false_complete"]) is bool, "誤った完了判定は真偽値またはnullです。")
    if row["incorrect_fields"] is not None:
        _require(row["checked_fields"] is not None and row["checked_fields"] > 0 and row["incorrect_fields"] <= row["checked_fields"], "誤り数には1件以上の確認が必要で、確認した項目数以下にしてください。")
    if row["truth_scope"] == "unknown":
        _require(row["truth_origin"] == "unknown" and all(row[k] is None for k in (
            "truth_hole_count", "checked_fields", "incorrect_fields", "missed_features", "false_complete")), "正解不明を誤り0として登録できません。")
    else:
        _require(row["truth_origin"] != "unknown", "独立した正解の出所が必要です。")
    if row["truth_scope"] != "whole_part":
        _require(all(row[k] is None for k in ("truth_hole_count", "missed_features", "false_complete")), "部分確認から全体の見逃し・完了誤りを0と断定できません。")
    else:
        _require(_count(row["truth_hole_count"]), "全体確認には独立した正解の穴数が必要です。")
        _require(row["missed_features"] is None or row["missed_features"] <= row["truth_hole_count"], "見逃し数が正解の全体数を超えています。")
        if row["truth_origin"] == "independent_recipe":
            _require(case["whole_count_truth"] is not None and row["truth_hole_count"] == case["whole_count_truth"], "レシピの全体数と一致しません。新しい人の確認は別の出所を指定してください。")


def add_phase(session, *, case_id=None, phase, seconds=None, completed=True, basis="reported_stopwatch", evidence):
    result = json.loads(canonical_bytes(session))
    result["phase_records"].append({"id": uuid.uuid4().hex, "case_id": case_id, "phase": phase,
        "seconds": seconds, "completed": completed, "basis": basis, "evidence_reference": evidence})
    validate_session(result)
    return result


def add_quality(session, *, case_id, truth_scope, truth_origin, truth_reference, truth_hole_count=None,
                checked_fields=None, incorrect_fields=None, missed_features=None, false_complete=None):
    result = json.loads(canonical_bytes(session))
    result["quality_records"].append({"case_id": case_id, "truth_scope": truth_scope, "truth_origin": truth_origin,
        "truth_reference": truth_reference, "truth_hole_count": truth_hole_count, "checked_fields": checked_fields,
        "incorrect_fields": incorrect_fields, "missed_features": missed_features, "false_complete": false_complete})
    validate_session(result)
    return result


def summarize(session):
    validate_session(session)
    expected = [(None, p) for p in BATCH_PHASES] + [(c["id"], p) for c in session["case_manifest"]["cases"] for p in METHODS[session["method"]]]
    phases = []
    for case_id, phase in expected:
        rows = [r for r in session["phase_records"] if (r["case_id"], r["phase"]) == (case_id, phase)]
        accounted = bool(rows) and rows[-1]["completed"]
        known = sum(r["seconds"] for r in rows if r["seconds"] is not None)
        phases.append({"case_id": case_id, "phase": phase, "accounted": accounted,
                       "not_needed": bool(rows) and rows[-1]["basis"] == "not_needed",
                       "known_seconds": known, "seconds": known if accounted else None})
    quality = []
    for case in session["case_manifest"]["cases"]:
        row = next((r for r in session["quality_records"] if r["case_id"] == case["id"]), None)
        quality.append(row or {"case_id": case["id"], "truth_scope": "unknown", "truth_origin": "unknown",
            "truth_reference": "not_recorded", "truth_hole_count": None, "checked_fields": None,
            "incorrect_fields": None, "missed_features": None, "false_complete": None})
    errors = {}
    for field in ("incorrect_fields", "missed_features", "false_complete"):
        values = [r[field] for r in quality]
        unknown = sum(v is None for v in values)
        known = sum(int(v) for v in values if v is not None)
        errors[field] = {"known_total": known, "unknown_cases": unknown, "total": None if unknown else known}
    timing_complete = all(p["accounted"] for p in phases)
    quality_accounted = [r["truth_scope"] == "whole_part" and r["checked_fields"] is not None and r["checked_fields"] > 0
                        and all(r[k] is not None for k in errors) for r in quality]
    quality_complete = all(quality_accounted)
    measured = session["record_kind"] == "operator_observation" and any(r["basis"] != "not_needed" for r in session["phase_records"])
    context_complete = session["tool_reference"] is not None and session["workbook_reference"] is not None
    complete = measured and timing_complete and quality_complete and context_complete
    return {"version": VERSION, "session_id": session["session_id"], "created_at": session["created_at"],
        "session_sha256": _digest(session), "record_kind": session["record_kind"],
        "operator_reference": session["operator_reference"], "tool_reference": session["tool_reference"],
        "workbook_reference": session["workbook_reference"],
        "method": session["method"], "planned_case_ids": [c["id"] for c in session["case_manifest"]["cases"]],
        "planned_cases": len(quality), "case_order_frozen": True,
        "contract_sha256": session["contract_sha256"], "case_manifest_sha256": session["case_manifest_sha256"],
        "operator_time_measured": measured, "timing_complete": timing_complete, "quality_complete": quality_complete,
        "context_complete": context_complete, "baseline_record_complete": complete,
        "measurement_state": "synthetic_control" if session["record_kind"] == "synthetic_control" else
            "complete_observation" if complete else "incomplete_observation" if measured else "not_measured",
        "known_active_seconds": sum(p["known_seconds"] for p in phases),
        "total_active_seconds": sum(p["seconds"] for p in phases) if timing_complete else None,
        "missing_or_unfinished_phases": sum(not p["accounted"] for p in phases),
        "not_needed_phases": sum(p["not_needed"] for p in phases),
        "quality_unknown_cases": sum(not v for v in quality_accounted),
        "whole_truth_unknown_cases": sum(r["truth_scope"] != "whole_part" for r in quality),
        "error_counts": errors, "phases": phases, "quality": quality,
        "customer_approved": False, "adoption_decision": "not_evaluated", "time_saving_seconds": None,
        "claim_boundary": "利用者が記録した基準作業の集計です。記録の完全性と業務の成功は別です。実測の独立監査・顧客合意・省力化や採否の判定ではありません。"}


def measure_interactive(*, reader=input, clock=time.perf_counter):
    """Return active seconds and completion; interrupted work remains recorded."""
    last = clock()
    active, paused = 0.0, False
    print("計測開始。Enter=工程完了 / p=中断 / r=再開 / q=未完了で保存", flush=True)
    while True:
        try:
            command = reader().strip().lower()
        except (EOFError, KeyboardInterrupt):
            command = "q"
        now = clock()
        _require(_seconds(now - last), "計測時計が逆転または範囲外です。")
        if not paused:
            active += now - last
        last = now
        if command == "q":
            return active, False
        if command == "" and not paused:
            return active, True
        if command == "p":
            paused = True
        elif command == "r":
            paused = False
        else:
            print("中断中はrで再開してください。Enter=完了 / p=中断 / r=再開 / q=未完了", flush=True)


def _save(path, session, *, original=None):
    validate_session(session)
    data = canonical_bytes(session)
    _require(len(data) <= MAX_CONTRACT_BYTES, "記録は128000バイト以下です。別セッションに分けてください。")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with lock.open("x"):
        pass
    try:
        if original is None:
            _require(not path.exists(), "既存の記録は上書きしません。別の保存先を指定してください。")
        else:
            _require(path.read_bytes() == original, "別操作で記録が更新されました。再読込してください。")
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(data)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        lock.unlink(missing_ok=True)


def report_markdown(report):
    total = "未測定・未完了" if report["total_active_seconds"] is None else f'{report["total_active_seconds"]:.3f} 秒'
    def cell(phase):
        return "対象なし（理由を記録）" if phase["not_needed"] else "未記録・未完了" if phase["seconds"] is None else f'{phase["seconds"]:.3f}'
    text = (f'# 基準作業の記録 — v{VERSION}\n\n'
        f'- 記録種別: {report["record_kind"]}\n- 状態: {report["measurement_state"]}\n'
        f'- 計画部品数: {report["planned_cases"]}\n- 全工程の作業時間: {total}\n'
        f'- 未記録・未完了の工程数: {report["missing_or_unfinished_phases"]}\n'
        f'- 品質の確認が未完了の部品数: {report["quality_unknown_cases"]}\n\n'
        '合成記録は現場実測ではありません。未確認の誤りは0件とせずJSONでnullを保持します。\n\n'
        '| 共通作業 | 作業秒数 |\n| --- | --- |\n')
    for phase in report["phases"]:
        if phase["case_id"] is None:
            text += f'| {PHASE_LABELS[phase["phase"]]} | {cell(phase)} |\n'
    text += '\n| 部品 | 作業秒数 | 未記録・未完了の工程 |\n| --- | --- | --- |\n'
    for index, case_id in enumerate(report["planned_case_ids"], 1):
        phases = [r for r in report["phases"] if r["case_id"] == case_id]
        missing = [PHASE_LABELS[r["phase"]] for r in phases if not r["accounted"]]
        seconds = "未完了" if missing else f'{sum(r["seconds"] for r in phases):.3f}'
        # User identifiers remain in JSON; table labels cannot inject Markdown.
        text += f'| 入力{index} | {seconds} | {"、".join(missing) or "なし"} |\n'
    text += '\n| 品質項目 | 全件の件数 | 正解・確認が不足する部品数 |\n| --- | --- | --- |\n'
    for field, label in (("incorrect_fields", "転記等の誤り項目"), ("missed_features", "必要特徴の見逃し"), ("false_complete", "誤った完了判定")):
        row = report["error_counts"][field]
        value = "不明" if row["total"] is None else str(row["total"])
        text += f'| {label} | {value} | {row["unknown_cases"]} |\n'
    return text + '\n' + report["claim_boundary"] + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description="CAD確認・転記の基準作業をローカル記録。実測を推定で埋めません。")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="工程未測定の記録を作る")
    init.add_argument("session", type=Path)
    init.add_argument("--contract", type=Path, required=True)
    init.add_argument("--cases", type=Path, required=True)
    init.add_argument("--method", choices=METHODS, default="manual_cad_and_transcription")
    init.add_argument("--operator", required=True)
    init.add_argument("--kind", choices=KINDS, default="operator_observation")
    init.add_argument("--tool")
    init.add_argument("--workbook")
    for name in ("record", "time"):
        cmd = sub.add_parser(name, help="ストップウォッチ値を記録" if name == "record" else "その場で工程を計測")
        cmd.add_argument("session", type=Path)
        cmd.add_argument("--case", dest="case_id")
        cmd.add_argument("--phase", required=True)
        cmd.add_argument("--evidence", required=True)
        if name == "record":
            value = cmd.add_mutually_exclusive_group(required=True)
            value.add_argument("--seconds", type=float)
            value.add_argument("--not-needed", action="store_true")
            cmd.add_argument("--unfinished", action="store_true")
    quality = sub.add_parser("quality", help="独立した確認結果を記録（未確認はnull）")
    quality.add_argument("session", type=Path)
    quality.add_argument("--case", dest="case_id", required=True)
    quality.add_argument("--truth-scope", choices=("unknown", "selected_fields", "whole_part"), required=True)
    quality.add_argument("--truth-origin", choices=("unknown", "independent_recipe", "independent_human_review"), required=True)
    quality.add_argument("--truth-reference", required=True)
    for name in ("truth-hole-count", "checked-fields", "incorrect-fields", "missed-features"):
        quality.add_argument("--" + name, type=int)
    quality.add_argument("--false-complete", choices=("yes", "no"))
    report_cmd = sub.add_parser("report", help="未測定を保持して集計")
    report_cmd.add_argument("session", type=Path)
    report_cmd.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            session = new_session(read_contract(args.contract), read_contract(args.cases), method=args.method,
                operator=args.operator, kind=args.kind, tool=args.tool, workbook=args.workbook)
            _save(args.session, session)
        else:
            original = args.session.read_bytes()
            _require(len(original) <= MAX_CONTRACT_BYTES, "記録が128000バイトを超えています。")
            session = read_contract(args.session)
            validate_session(session)
            if args.command in ("record", "time"):
                _phase_key(session, args.case_id, args.phase)
                _require(not any(r["case_id"] == args.case_id and r["phase"] == args.phase and r["completed"] for r in session["phase_records"]), "工程は既に記録完了です。")
                if args.command == "time":
                    seconds, completed = measure_interactive()
                    basis = "synthetic" if session["record_kind"] == "synthetic_control" else "interactive_monotonic"
                else:
                    seconds, completed = args.seconds, not args.unfinished
                    basis = "not_needed" if args.not_needed else "synthetic" if session["record_kind"] == "synthetic_control" else "reported_stopwatch"
                session = add_phase(session, case_id=args.case_id, phase=args.phase, seconds=seconds,
                    completed=completed, basis=basis, evidence=args.evidence)
                _save(args.session, session, original=original)
                if not completed:
                    print("未完了の時間を保存しました。同じ工程を再計測すると合算します。", flush=True)
                    return 130
            elif args.command == "quality":
                session = add_quality(session, case_id=args.case_id, truth_scope=args.truth_scope, truth_origin=args.truth_origin,
                    truth_reference=args.truth_reference, truth_hole_count=args.truth_hole_count, checked_fields=args.checked_fields,
                    incorrect_fields=args.incorrect_fields, missed_features=args.missed_features,
                    false_complete=None if args.false_complete is None else args.false_complete == "yes")
                _save(args.session, session, original=original)
        report = summarize(session)
        if args.command == "report" and args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            _require(args.session.resolve() not in {(args.output_dir / name).resolve() for name in ("baseline-report.json", "baseline-report.md")}, "出力先が入力記録と同じです。")
            (args.output_dir / "baseline-report.json").write_bytes(canonical_bytes(report))
            (args.output_dir / "baseline-report.md").write_text(report_markdown(report), encoding="utf-8")
        output = report if args.command == "report" else {"version": VERSION, "record_saved": True,
            "measurement_state": report["measurement_state"], "missing_or_unfinished_phases": report["missing_or_unfinished_phases"],
            "quality_unknown_cases": report["quality_unknown_cases"], "adoption_decision": "not_evaluated"}
        print(canonical_bytes(output).decode(), end="")
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print(canonical_bytes({"version": VERSION, "record_valid": False, "error": str(error), "adoption_decision": "not_evaluated"}).decode(), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
