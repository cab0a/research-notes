"""Material sampling in a translated per-solid frame, without relaxing gates.

Only the classifier's private solid copy and sample points are translated.
Recognition evidence, tolerances, face IDs and output coordinates stay on the
input B-Rep. No scaling, healing or tolerance replacement is performed.
"""
from __future__ import annotations

import math


class LocalMaterialClassifier:
    """Classify world-coordinate samples near a solid's bounding-box centre.

    Keep one classifier per solid, including separated assembly components.
    Refuse samples whose world-coordinate floating-point spacing exceeds 1/16
    of the requested length tolerance. This conservative numerical guard is
    not a measurement-accuracy certificate and cannot recover lost input bits.
    The translated geometry is created lazily, only for qualified candidates.
    """

    def __init__(self, solid, tolerance):
        from OCP.BRepBndLib import BRepBndLib
        from OCP.Bnd import Bnd_Box

        if not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError('Material classification requires a positive finite tolerance.')
        bounds = Bnd_Box()
        BRepBndLib.Add_s(solid, bounds, False)
        limits = bounds.Get()
        if not all(math.isfinite(x) for x in limits):
            raise ValueError('Material classification requires finite solid bounds.')
        self.origin = tuple(limits[i] + (limits[i + 3] - limits[i]) / 2 for i in range(3))
        self.tolerance = tolerance
        self.resolution_limit = tolerance / 16
        self._solid = solid
        self._classifier = None

    def state(self, point):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec

        if len(point) != 3 or not all(math.isfinite(x) for x in (*point, *self.origin)):
            raise ValueError('Material sample coordinates must be finite XYZ values.')
        if max(math.ulp(x) for x in (*point, *self.origin)) > self.resolution_limit:
            raise ValueError('World-coordinate resolution is too coarse for the material qualification tolerance.')
        if self._classifier is None:
            transform = gp_Trsf()
            transform.SetTranslation(gp_Vec(*(-x for x in self.origin)))
            operation = BRepBuilderAPI_Transform(self._solid, transform, True)
            if not operation.IsDone() or operation.Shape().IsNull():
                raise ValueError('Could not translate the private material classification solid.')
            self._classifier = BRepClass3d_SolidClassifier(operation.Shape())
        local = [x - origin for x, origin in zip(point, self.origin)]
        self._classifier.Perform(gp_Pnt(*local), self.tolerance)
        return self._classifier.State()
