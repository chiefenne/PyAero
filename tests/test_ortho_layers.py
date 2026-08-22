import sys
from pathlib import Path

import numpy as np
from scipy import interpolate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import OrthoLayers
import StructuredCore as core
from ContourData import SplineData
from test_structured_topologies import _load_dat, NACA0012


def _build_spline_data(contour, points=200, degree=3):
    x, y = contour[:, 0], contour[:, 1]
    tck, u = interpolate.splprep([x, y], s=0.0, k=degree)
    t = np.linspace(0.0, 1.0, points)
    coo = interpolate.splev(t, tck, der=0)
    der1 = interpolate.splev(t, tck, der=1)
    der2 = interpolate.splev(t, tck, der=2)
    return SplineData(
        coordinates=coo, fit_parameters=u, sample_parameters=t,
        first_derivative=der1, second_derivative=der2, spline=tck,
        method='bspline', metadata={'degree': degree},
        leading_edge_parameter=float(t[int(np.argmin(coo[0]))]),
    )


def _spline_wall():
    contour_raw = _load_dat(NACA0012)
    te = 0.5 * (contour_raw[0] + contour_raw[-1])
    contour_raw[0] = te
    contour_raw[-1] = te
    spline_data = _build_spline_data(contour_raw)
    return spline_data, core.contour_array(spline_data)


def test_exact_perpendicularity_outside_corner_blend():
    spline_data, wall = _spline_wall()
    n = len(wall)
    corner = [0, n - 1]
    normals = OrthoLayers.wall_normals(
        wall, corner, spline_data=spline_data,
        contour_slice=(0, n), closed=True, blend_width=4)
    tangents = np.column_stack(spline_data.evaluate(
        spline_data.sample_parameters, der=1))
    dots = np.abs(np.sum(normals * tangents, axis=1)) / \
        np.linalg.norm(tangents, axis=1)
    interior = np.ones(n, dtype=bool)
    interior[:5] = False
    interior[-5:] = False
    assert np.max(dots[interior]) < 1e-9        # mathematically perpendicular
    lengths = np.linalg.norm(normals, axis=1)
    assert np.allclose(lengths, 1.0, atol=1e-12)


def test_normals_point_away_from_body():
    spline_data, wall = _spline_wall()
    normals = OrthoLayers.wall_normals(
        wall, [0, len(wall) - 1], spline_data=spline_data,
        contour_slice=(0, len(wall)), closed=True)
    centroid = wall.mean(axis=0)
    outward = np.sum((wall - centroid) * normals, axis=1)
    assert np.mean(outward > 0.0) > 0.95


def test_build_layers_wall_verbatim_and_no_fold():
    spline_data, wall = _spline_wall()
    normals = OrthoLayers.wall_normals(
        wall, [0, len(wall) - 1], spline_data=spline_data,
        contour_slice=(0, len(wall)), closed=True)
    rows = OrthoLayers.build_layers(wall, normals, layer_count=8,
                                    first_height=0.001, growth=1.2)
    assert rows.shape == (9, len(wall), 2)
    assert np.array_equal(rows[0], wall)
    jacobians = core.cell_jacobians(rows)
    assert np.all(jacobians != 0.0)
    assert np.all(jacobians > 0) or np.all(jacobians < 0)


def test_thinning_on_concave_wall_instead_of_folding():
    # synthetic concave arc: offsetting toward the center must trigger caps
    theta = np.linspace(0.25 * np.pi, 0.75 * np.pi, 80)
    radius = 0.05
    wall = np.column_stack((radius * np.cos(theta),
                            -radius * np.sin(theta)))
    normals = OrthoLayers.wall_normals(wall, [])
    # ensure normals point toward the center (concave side) for this test
    to_center = -wall / np.linalg.norm(wall, axis=1)[:, None]
    if np.sum(normals * to_center) < 0:
        normals = -normals
    caps = np.full(len(wall), 0.5 * radius)
    rows = OrthoLayers.build_layers(wall, normals, layer_count=10,
                                    first_height=0.01, growth=1.2,
                                    max_heights=caps)
    total = np.linalg.norm(rows[-1] - rows[0], axis=1)
    assert np.all(total <= 0.5 * radius + 1e-9)      # thinned
    jacobians = core.cell_jacobians(rows)
    assert np.all(jacobians > 0) or np.all(jacobians < 0)   # not folded
