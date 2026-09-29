"""Geometry-only revision matching for axis-aligned plates with through holes.

The imported B-Rep must pass a reconstructed-material gate before it can enter
the matching grammar. Local face numbers are output references, never identity.
"""
from __future__ import annotations

import math

from research_notes.modeling_common import measure_shape
from research_notes.parametric_features import boolean_shape, shape_difference_volume
from research_notes.step_reconstruction import face_evidence

LENGTH_TOL = 1e-5
FIT_REL_TOL = 1e-8
MATCH_FRACTION = .25
STATUS_LABELS = {"unchanged": "許容差内", "changed": "変更候補", "added": "追加候補",
                 "deleted": "削除候補", "unresolved": "判定保留"}
COLORS = {"unchanged": "#99b0b8", "changed": "#e4a13b", "added": "#43a77d",
          "deleted": "#d87570", "unresolved": "#9981bd"}


def plate_shape(low, high, holes):
    """Build the qualifying grammar from measured boundaries and cylinders."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    shape = BRepPrimAPI_MakeBox(gp_Pnt(*low), *(high[i] - low[i] for i in range(3))).Shape()
    for hole in holes:
        axis = gp_Ax2(gp_Pnt(hole["x"], hole["y"], low[2] - 1.), gp_Dir(0, 0, 1))
        tool = BRepPrimAPI_MakeCylinder(axis, hole["radius"], high[2] - low[2] + 2.).Shape()
        shape = boolean_shape(shape, tool, operation="cut")
    return shape


def describe_plate(imported):
    """Return a measured descriptor or explicit abstention; do not infer history."""
    try:
        faces = face_evidence(imported.shape)
        if max(imported.metrics.maximum_face_tolerance, imported.metrics.maximum_edge_tolerance,
               imported.metrics.maximum_vertex_tolerance) > LENGTH_TOL:
            raise ValueError("入力形状の許容差が比較許容差を超えています。")
        low = [min(f.bounds_min[i] for f in faces) for i in range(3)]
        high = [max(f.bounds_max[i] for f in faces) for i in range(3)]
        if any(b - a <= LENGTH_TOL * 10 for a, b in zip(low, high)):
            raise ValueError("板の寸法が比較許容差に近すぎます。")
        planes, holes = {}, []
        for face in faces:
            if face.surface_type == "plane":
                axis = face.axis
                value = face.bounds_min[axis]
                if abs(value - face.bounds_max[axis]) > LENGTH_TOL:
                    raise ValueError("板の平面境界を確定できません。")
                end = "min" if abs(value - low[axis]) <= LENGTH_TOL else "max" if abs(value - high[axis]) <= LENGTH_TOL else None
                role = f"{'xyz'[axis]}_{end}"
                if end is None or role in planes:
                    raise ValueError("平面の分割・段差・ポケットは今回の判定範囲外です。")
                planes[role] = face.face_index
            else:
                if abs(face.bounds_min[2] - low[2]) > LENGTH_TOL or abs(face.bounds_max[2] - high[2]) > LENGTH_TOL:
                    raise ValueError("全厚を貫通しない円筒面は今回の判定範囲外です。")
                x, y, r = face.center_x, face.center_y, face.radius
                if r <= LENGTH_TOL or not (low[0] + r + LENGTH_TOL < x < high[0] - r - LENGTH_TOL
                                           and low[1] + r + LENGTH_TOL < y < high[1] - r - LENGTH_TOL):
                    raise ValueError("板の外周に接する穴や突起は今回の判定範囲外です。")
                holes.append({"x": x, "y": y, "radius": r, "faces": [face.face_index]})
        if len(planes) != 6:
            raise ValueError("長方形の板の6平面を確認できません。")
        for i, a in enumerate(holes):
            if any(math.hypot(a["x"] - b["x"], a["y"] - b["y"]) <= a["radius"] + b["radius"] + LENGTH_TOL for b in holes[i+1:]):
                raise ValueError("穴の交差、または円筒面の分割・重複があり対応を確定できません。")
        rebuilt = plate_shape(low, high, holes)
        metrics = measure_shape(rebuilt)
        residual = shape_difference_volume(imported.shape, rebuilt)
        volume_gate = max(1e-7, imported.metrics.absolute_volume * FIT_REL_TOL)
        area_gate = max(1e-7, imported.metrics.surface_area * FIT_REL_TOL)
        if not metrics.analyzer_valid or residual > volume_gate or abs(metrics.surface_area - imported.metrics.surface_area) > area_gate:
            raise ValueError("板と貫通穴で再構成した形状が、読込形状に十分一致しません。")
        holes.sort(key=lambda h: (h["x"], h["y"], h["radius"]))
        for i, hole in enumerate(holes, 1):
            hole["id"] = f"H{i}"
        return {"status": "qualified", "reason": "6平面と全厚の円筒面を、再構成した材料領域と照合しました。",
                "low": low, "high": high, "thickness": high[2] - low[2], "planes": planes, "holes": holes,
                "material_residual_mm3": residual, "material_gate_mm3": volume_gate}
    except (ValueError, RuntimeError) as error:
        return {"status": "unsupported", "reason": "形状の判定範囲外: " + str(error), "holes": []}


def dimension(name, old, new):
    delta = new - old
    return {"name": name, "old": old, "new": new, "delta": delta, "unit": "mm",
            "status": "changed" if abs(delta) > LENGTH_TOL else "unchanged"}


def compare_revisions(old, new):
    """Compare qualified descriptors in a declared common coordinate frame."""
    result = {"status": "waiting", "regions": [], "face_relations": [], "dimensions": [], "unresolved": [],
              "face_status": {"old": {}, "new": {}}, "markers": {"old": [], "new": []},
              "conditions": {"length_tolerance_mm": LENGTH_TOL, "fit_relative_tolerance": FIT_REL_TOL,
                             "hole_search_fraction": MATCH_FRACTION, "hole_search_distance_mm": None,
                             "coordinate_policy": "source_coordinates_no_alignment",
                             "position_reference": "共通座標系のX/Y座標（mm）。板のXY外周とZ下端が一致する場合に比較。",
                             "matching_policy": "同位置の穴を優先し、残りは検索距離内で双方の候補が1つの場合のみ対応付け。",
                             "measurement_scope": "幾何からの測定値。元CADの公称寸法・公差・設計履歴ではありません。"}}
    if not old or not new:
        return result
    for side, data in (("old", old), ("new", new)):
        result["face_status"][side] = {str(f["index"]): "unresolved" for f in data["faces"]}
    a, b = old["features"], new["features"]
    reasons = [f"{'旧版' if side == 'old' else '新版'}: {d['reason']}"
               for side, d in (("old", a), ("new", b)) if d["status"] != "qualified"]
    if not reasons:
        frame_a = a["low"] + a["high"][:2]
        frame_b = b["low"] + b["high"][:2]
        if any(abs(x - y) > LENGTH_TOL for x, y in zip(frame_a, frame_b)):
            reasons.append("板のXY外周またはZ下端が一致しません。外形変更と位置・向きの違いを区別できないため保留します。")
    if reasons:
        result.update(status="unresolved", unresolved=reasons)
        result["regions"].append({"id": "unresolved", "label": "形状全体", "status": "unresolved",
            "reason": " / ".join(reasons), "old_faces": [f["index"] for f in old["faces"]],
            "new_faces": [f["index"] for f in new["faces"]]})
        return result
    gate = max(a["high"][0] - a["low"][0], a["high"][1] - a["low"][1]) * MATCH_FRACTION
    result["conditions"]["hole_search_distance_mm"] = gate
    thickness = dimension("板厚", a["thickness"], b["thickness"])
    result["regions"].append({"id": "plate", "label": "板厚", "status": thickness["status"],
        "reason": "同じXY外周とZ下端を持つ板の、上下平面間距離を比較。",
        "old_faces": [a["planes"]["z_min"], a["planes"]["z_max"]],
        "new_faces": [b["planes"]["z_min"], b["planes"]["z_max"]]})
    result["dimensions"].append({"region_id": "plate", "label": "板", **thickness})
    left, right = set(range(len(a["holes"]))), set(range(len(b["holes"])))
    pairs = []
    distance = lambda i, j: math.hypot(a["holes"][i]["x"] - b["holes"][j]["x"], a["holes"][i]["y"] - b["holes"][j]["y"])
    # Exact-position anchors precede a conservative mutual-singleton search.
    # No minimum-cost assignment is forced when several holes are plausible.
    for threshold, reason in ((LENGTH_TOL, "同位置の円筒軸が一意に対応。"), (gate, "検索距離内の対応候補が双方で1つ。移動・変更の候補です。")):
        candidates = {i: [j for j in sorted(right) if distance(i, j) <= threshold] for i in sorted(left)}
        inverse = {j: [i for i in sorted(left) if j in candidates[i]] for j in sorted(right)}
        matches = [(i, js[0]) for i, js in candidates.items() if len(js) == 1 and len(inverse[js[0]]) == 1]
        for i, j in matches:
            pairs.append((i, j, reason))
            left.remove(i)
            right.remove(j)

    def add_hole(i, j, status, reason):
        ah = a["holes"][i] if i is not None else None
        bh = b["holes"][j] if j is not None else None
        region_id = f"hole-{len(result['regions'])}"
        label = (f"旧{ah['id']}" if ah else "—") + " → " + (f"新{bh['id']}" if bh else "—")
        values = []
        if ah and bh:
            values = [dimension("穴径", 2 * ah["radius"], 2 * bh["radius"]),
                      dimension("穴中心X", ah["x"], bh["x"]), dimension("穴中心Y", ah["y"], bh["y"])]
            status = "changed" if thickness["status"] == "changed" or any(v["status"] == "changed" for v in values) else "unchanged"
            if thickness["status"] == "changed":
                reason += " 板厚変更により穴の貫通長さも変化しています。"
        region = {"id": region_id, "label": label, "status": status, "reason": reason,
                  "outline_changed": any(v["status"] == "changed" for v in values) if ah and bh else True,
                  "old_faces": ah["faces"] if ah else [], "new_faces": bh["faces"] if bh else []}
        result["regions"].append(region)
        result["dimensions"].extend({"region_id": region_id, "label": label, **v} for v in values)
        result["face_relations"].append({"role": label, **region})
        for side, hole, data in (("old", ah, a), ("new", bh, b)):
            if hole:
                result["face_status"][side].update({str(f): status for f in hole["faces"]})
                result["markers"][side].append({"region_id": region_id, "label": hole["id"], "status": status,
                    "position": [hole["x"], hole["y"], data["high"][2]]})
        if status == "unresolved":
            result["unresolved"].append(label + ": " + reason)

    for i, j, reason in sorted(pairs):
        add_hole(i, j, "unchanged", reason)
    ambiguous = bool(left and right)
    for i in sorted(left):
        add_hole(i, None, "unresolved" if ambiguous else "deleted",
                 "複数候補または検索範囲外の穴が残り、移動と増減を区別できません。" if ambiguous else "他の穴の対応後、新版に対応候補が残りません。")
    for j in sorted(right):
        add_hole(None, j, "unresolved" if ambiguous else "added",
                 "複数候補または検索範囲外の穴が残り、移動と増減を区別できません。" if ambiguous else "他の穴の対応後、旧版に対応候補が残りません。")
    trim_changed = any(r.get("outline_changed") for r in result["regions"])
    trim_status = "unresolved" if ambiguous else "changed" if trim_changed else "unchanged"
    for role in a["planes"]:
        status = thickness["status"] if role != "z_min" else "unchanged"
        if role.startswith("z_") and trim_status != "unchanged":
            status = trim_status
        relation = {"role": role, "old_faces": [a["planes"][role]], "new_faces": [b["planes"][role]],
                    "status": status, "reason": "板の境界面の役割で対応。上下面は穴による輪郭の変更も含みます。"}
        result["face_relations"].append(relation)
        for side in ("old", "new"):
            result["face_status"][side][str(relation[side + "_faces"][0])] = status
    result["status"] = "partial" if result["unresolved"] else "compared"
    return result
