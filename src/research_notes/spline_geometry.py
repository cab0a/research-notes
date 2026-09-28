"""Bounded rational B-splines with an independent Cox-de Boor evaluator."""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SplineCurve:
    degree: int
    poles: tuple[tuple[float, float, float], ...]
    knots: tuple[float, ...]
    multiplicities: tuple[int, ...]
    weights: tuple[float, ...]
    periodic: bool = False

    def validate(self):
        if self.periodic:
            raise ValueError("periodic input is recorded but outside the clamped evaluator")
        if type(self.degree) is not int or not 1 <= self.degree <= 5 or not self.degree+1 <= len(self.poles) <= 64:
            raise ValueError("degree/pole budget exceeded")
        if len(self.weights) != len(self.poles) or len(self.knots) != len(self.multiplicities) or len(self.knots) < 2:
            raise ValueError("inconsistent spline arrays")
        numbers = [*self.knots, *self.weights, *(v for p in self.poles for v in p)]
        if any(not math.isfinite(v) or abs(v) > 10000 for v in numbers) or any(w <= 0 for w in self.weights):
            raise ValueError("nonfinite, out-of-domain, or nonpositive weight")
        if any(len(p) != 3 for p in self.poles) or any(a >= b for a, b in zip(self.knots, self.knots[1:])):
            raise ValueError("invalid poles or knot order")
        if any(type(m) is not int or not 1 <= m <= self.degree+1 for m in self.multiplicities):
            raise ValueError("invalid multiplicity")
        if self.multiplicities[0] != self.degree+1 or self.multiplicities[-1] != self.degree+1 or sum(self.multiplicities) != len(self.poles)+self.degree+1:
            raise ValueError("expected clamped knot vector")


def _array(cls, values):
    result = cls(1, len(values))
    for index, value in enumerate(values, 1):
        result.SetValue(index, value)
    return result


def kernel_curve(spec: SplineCurve):
    from OCP.Geom import Geom_BSplineCurve
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from OCP.gp import gp_Pnt
    spec.validate()
    return Geom_BSplineCurve(_array(TColgp_Array1OfPnt, [gp_Pnt(*p) for p in spec.poles]),
        _array(TColStd_Array1OfReal, spec.weights), _array(TColStd_Array1OfReal, spec.knots),
        _array(TColStd_Array1OfInteger, spec.multiplicities), spec.degree, False)


def evaluate_curve(spec: SplineCurve, parameter: float) -> dict:
    """Position and first derivative from homogeneous basis functions, no OCCT."""
    spec.validate()
    if not math.isfinite(parameter) or not spec.knots[0] <= parameter <= spec.knots[-1]:
        raise ValueError("parameter outside spline domain")
    knots = tuple(t for t, count in zip(spec.knots, spec.multiplicities) for _ in range(count))
    u = np.nextafter(parameter, -math.inf) if parameter == knots[-1] else parameter
    basis = np.array([float(a <= u < b) for a, b in zip(knots, knots[1:])])
    lower = basis
    for degree in range(1, spec.degree+1):
        lower = basis
        basis = np.array([(0. if knots[i+degree] == knots[i] else (u-knots[i])/(knots[i+degree]-knots[i])*lower[i]) +
                          (0. if knots[i+degree+1] == knots[i+1] else (knots[i+degree+1]-u)/(knots[i+degree+1]-knots[i+1])*lower[i+1])
                          for i in range(len(lower)-1)])
    degree = spec.degree
    deriv = np.array([(0. if knots[i+degree] == knots[i] else degree*lower[i]/(knots[i+degree]-knots[i])) -
                      (0. if knots[i+degree+1] == knots[i+1] else degree*lower[i+1]/(knots[i+degree+1]-knots[i+1]))
                      for i in range(len(spec.poles))])
    weights, poles = np.array(spec.weights), np.array(spec.poles)
    denominator = basis @ weights
    point = (basis*weights) @ poles / denominator
    tangent = ((deriv*weights) @ poles - point*(deriv @ weights))/denominator
    return {"point": point.tolist(), "derivative": tangent.tolist(), "parameter": parameter}


def quarter_circle(radius=2.):
    return SplineCurve(2, ((radius, 0., 0.), (radius, radius, 0.), (0., radius, 0.)),
                       (0., 1.), (3, 3), (1., math.sqrt(.5), 1.))


def rational_cylinder_patch(radius=2., height=3.):
    """A rational quadratic-by-linear quarter cylinder, u is not the angle."""
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger, TColStd_Array2OfReal
    from OCP.gp import gp_Pnt
    if not all(math.isfinite(v) and 0 < v <= 1000 for v in (radius, height)):
        raise ValueError("radius and height outside domain")
    curve = quarter_circle(radius)
    poles, weights = TColgp_Array2OfPnt(1, 3, 1, 2), TColStd_Array2OfReal(1, 3, 1, 2)
    for i, (x, y, _) in enumerate(curve.poles, 1):
        for j, z in enumerate((0., height), 1):
            poles.SetValue(i, j, gp_Pnt(x, y, z)); weights.SetValue(i, j, curve.weights[i-1])
    return Geom_BSplineSurface(poles, weights, _array(TColStd_Array1OfReal, (0., 1.)),
        _array(TColStd_Array1OfReal, (0., 1.)), _array(TColStd_Array1OfInteger, (3, 3)),
        _array(TColStd_Array1OfInteger, (2, 2)), 2, 1)


def curve_record(curve):
    return {"degree": curve.Degree(), "poles": [list(curve.Pole(i).Coord()) for i in range(1, curve.NbPoles()+1)],
            "knots": [curve.Knot(i) for i in range(1, curve.NbKnots()+1)],
            "multiplicities": [curve.Multiplicity(i) for i in range(1, curve.NbKnots()+1)],
            "weights": [curve.Weight(i) for i in range(1, curve.NbPoles()+1)], "periodic": curve.IsPeriodic()}


def surface_record(surface):
    return {"u_degree": surface.UDegree(), "v_degree": surface.VDegree(),
            "u_knots": [surface.UKnot(i) for i in range(1, surface.NbUKnots()+1)],
            "v_knots": [surface.VKnot(i) for i in range(1, surface.NbVKnots()+1)],
            "u_multiplicities": [surface.UMultiplicity(i) for i in range(1, surface.NbUKnots()+1)],
            "v_multiplicities": [surface.VMultiplicity(i) for i in range(1, surface.NbVKnots()+1)],
            "poles": [[list(surface.Pole(i,j).Coord()) for j in range(1,surface.NbVPoles()+1)] for i in range(1,surface.NbUPoles()+1)],
            "weights": [[surface.Weight(i,j) for j in range(1,surface.NbVPoles()+1)] for i in range(1,surface.NbUPoles()+1)],
            "u_periodic": surface.IsUPeriodic(), "v_periodic": surface.IsVPeriodic()}
