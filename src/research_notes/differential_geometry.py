"""Local differential geometry and sampled, explicitly parameterized continuity."""
from __future__ import annotations
import math
import numpy as np


def surface_differential(surface, u: float, v: float, *, orientation=1) -> dict:
    from OCP.gp import gp_Pnt, gp_Vec
    if orientation not in {-1, 1} or not all(math.isfinite(t) for t in (u,v)):
        raise ValueError("invalid orientation or parameters")
    p, du, dv, duu, dvv, duv = gp_Pnt(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec(), gp_Vec()
    surface.D2(u, v, p, du, dv, duu, dvv, duv)
    a,b,aa,bb,ab = (np.array(x.Coord()) for x in (du,dv,duu,dvv,duv))
    normal = np.cross(a,b)
    if np.linalg.norm(normal) < 1e-12:
        return {"status": "singular", "uv": [u,v], "point": list(p.Coord())}
    normal *= orientation/np.linalg.norm(normal)
    first = np.array([[a@a, a@b], [a@b, b@b]])
    second = np.array([[normal@aa, normal@ab], [normal@ab, normal@bb]])
    if np.linalg.cond(first) > 1e12:
        return {"status": "singular", "uv": [u,v], "point": list(p.Coord())}
    # Whitening makes the generalized eigenproblem symmetric.
    eigen, vectors = np.linalg.eigh(first)
    invroot = vectors @ np.diag(1/np.sqrt(eigen)) @ vectors.T
    curvatures, directions = np.linalg.eigh(invroot @ second @ invroot)
    tangent_vectors = np.column_stack((a,b)) @ invroot @ directions
    return {"status": "regular", "uv": [u,v], "point": list(p.Coord()), "normal": normal.tolist(),
            "first_form": first.tolist(), "second_form": second.tolist(), "principal_curvatures": curvatures.tolist(),
            "principal_directions": tangent_vectors.T.tolist(), "principal_directions_unique": bool(abs(curvatures[0]-curvatures[1]) > 1e-9),
            "gaussian_curvature": float(np.prod(curvatures)), "mean_curvature": float(np.mean(curvatures))}


def sampled_continuity(first, second, pairs, *, position_tolerance=1e-7, angle_tolerance=1e-6, curvature_tolerance=1e-6):
    pairs = tuple(pairs)
    if not 1 <= len(pairs) <= 1024 or any(not math.isfinite(t) or t <= 0 for t in (position_tolerance,angle_tolerance,curvature_tolerance)):
        raise ValueError("invalid sample or tolerance budget")
    observations = []
    for uv_a, uv_b in pairs:
        a,b = surface_differential(first,*uv_a), surface_differential(second,*uv_b)
        if a["status"] != "regular" or b["status"] != "regular":
            observations.append({"status": "singular", "first": a, "second": b}); continue
        position = float(np.linalg.norm(np.array(a["point"])-b["point"]))
        dot = float(np.dot(a["normal"],b["normal"]))
        angle = math.acos(max(-1., min(1., dot)))
        # Compare normal-curvature tensors in the shared world tangent frame.
        def tensor(r):
            d = np.array(r["principal_directions"]).T
            return d @ np.diag(r["principal_curvatures"]) @ d.T
        curvature = float(np.linalg.norm(tensor(a)-tensor(b), ord=2))
        g0 = position <= position_tolerance
        g1 = g0 and angle <= angle_tolerance
        g2 = g1 and curvature <= curvature_tolerance
        observations.append({"uv_first": uv_a, "uv_second": uv_b, "position_gap": position,
            "normal_angle": angle, "curvature_tensor_gap": curvature, "status": "G2" if g2 else "G1" if g1 else "G0" if g0 else "disconnected"})
    return {"scope": "sampled matched parameters; no whole-boundary certification", "samples": observations,
            "status": min((r["status"] for r in observations), key=lambda s: {"singular":0,"disconnected":1,"G0":2,"G1":3,"G2":4}[s])}
