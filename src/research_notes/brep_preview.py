"""Face-colored diagnostic previews for controlled B-Rep studies."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from research_notes.brep_runtime import indexed_shapes


Vector3 = tuple[float, float, float]


def _mesh_polygons(shape: object) -> tuple[list[list[Vector3]], list[int]]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepTools.Clean_s(shape, True)
    mesher = BRepMesh_IncrementalMesh(shape, 0.12, False, 0.35, False)
    if not mesher.IsDone():
        raise RuntimeError("diagnostic preview meshing failed")
    polygons: list[list[Vector3]] = []
    face_indices: list[int] = []
    face_map = indexed_shapes(shape, TopAbs_FACE)
    for face_index in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(face_index))
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None:
            continue
        transformation = location.Transformation()
        for triangle_index in range(1, triangulation.NbTriangles() + 1):
            triangle = triangulation.Triangle(triangle_index)
            polygon = []
            for slot in (1, 2, 3):
                point = triangulation.Node(triangle.Value(slot)).Transformed(
                    transformation
                )
                polygon.append((float(point.X()), float(point.Y()), float(point.Z())))
            polygons.append(polygon)
            face_indices.append(face_index)
    if not polygons:
        raise RuntimeError("diagnostic preview contains no triangles")
    return polygons, face_indices


def _equal_axes(axis: object, vertices: list[Vector3]) -> None:
    minima = [min(item[index] for item in vertices) for index in range(3)]
    maxima = [max(item[index] for item in vertices) for index in range(3)]
    centers = [(a + b) / 2.0 for a, b in zip(minima, maxima, strict=True)]
    radius = max(b - a for a, b in zip(minima, maxima, strict=True)) / 2.0
    radius = max(radius, 0.5)
    axis.set_xlim(centers[0] - radius, centers[0] + radius)
    axis.set_ylim(centers[1] - radius, centers[1] + radius)
    axis.set_zlim(centers[2] - radius, centers[2] + radius)
    axis.set_box_aspect((1, 1, 1))


def write_shape_previews(
    path: Path,
    entries: tuple[tuple[str, object], ...],
    *,
    title: str,
    columns: int = 3,
) -> None:
    """Render a deterministic grid of face-colored diagnostic meshes."""
    rows = (len(entries) + columns - 1) // columns
    figure = plt.figure(
        figsize=(4.1 * columns, 3.6 * rows), constrained_layout=True
    )
    color_map = plt.get_cmap("tab20")
    for position, (label, shape) in enumerate(entries, start=1):
        axis = figure.add_subplot(rows, columns, position, projection="3d")
        polygons, face_indices = _mesh_polygons(shape)
        collection = Poly3DCollection(
            polygons,
            facecolors=[color_map((index - 1) % 20) for index in face_indices],
            edgecolors="#111827",
            linewidths=0.16,
            alpha=0.94,
        )
        axis.add_collection3d(collection)
        _equal_axes(axis, [vertex for polygon in polygons for vertex in polygon])
        axis.view_init(elev=24, azim=-55)
        axis.set_axis_off()
        axis.set_title(label)
    figure.suptitle(title + "\nFace colors and meshes are diagnostic, not exact geometry")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)

