import os
import sys

import numpy as np
import pytest
from scipy import interpolate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import CamberMedialAxis as cma
from ContourData import CamberData, SplineData


def _build_spline_data(x, y, points=200, degree=3):
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


def _load_dat(path):
    xs, ys = [], []
    with open(path) as handle:
        lines = handle.readlines()
    for line in lines:
        if line.strip().startswith('#'):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
        except ValueError:
            continue
    return np.array(xs), np.array(ys)


_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
NACA2315 = os.path.join(_DATA_DIR, 'naca2315.dat')
NACA0012 = os.path.join(_DATA_DIR, 'naca0012.dat')
MW166 = os.path.join(_DATA_DIR, 'MW-166-39-44-43.dat')


def _le_radius_inputs(spline_data):
    t_le = spline_data.leading_edge_parameter_value()
    sample_t = spline_data.sample_parameters
    dx, dy = spline_data.evaluate(sample_t, der=1)
    x2, y2 = spline_data.evaluate(sample_t, der=2)
    curvature_radius = ((dx ** 2 + dy ** 2) ** 1.5) / np.abs(dx * y2 - dy * x2)
    le_id = int(np.argmin(curvature_radius))
    rc = float(curvature_radius[le_id])
    point = np.array((spline_data.coordinates[0][le_id], spline_data.coordinates[1][le_id]))
    # Reference point well inside the airfoil body (near mid-chord), not the
    # coordinate origin -- the origin sits right at/near the LE point itself
    # for chord-normalized data, which is too close to reliably disambiguate
    # "inward" from "outward" for a point that's also right at the LE.
    normal = cma.inward_normal(np.array((dx[le_id], dy[le_id])), point, np.array((0.3, 0.0)))
    xc, yc = point + rc * normal
    xle, yle = point
    return t_le, rc, float(xc), float(yc), float(xle), float(yle), le_id


def _build_legacy_camber_data(spline_data, point_count=240):
    stations = np.linspace(0.0, 1.0, point_count)
    t_le = spline_data.leading_edge_parameter_value()
    upper_params = t_le * (1.0 - stations)
    lower_params = t_le + stations * (1.0 - t_le)
    upper = np.array(spline_data.evaluate(upper_params, der=0), dtype=float).T
    lower = np.array(spline_data.evaluate(lower_params, der=0), dtype=float).T
    centers = 0.5 * (upper + lower)
    radius = 0.5 * np.linalg.norm(upper - lower, axis=1)
    return CamberData(
        method='legacy_midpoint',
        coordinates=(centers[:, 0], centers[:, 1]), radius=radius,
        upper_contact=(upper[:, 0], upper[:, 1]), lower_contact=(lower[:, 0], lower[:, 1]),
        upper_parameters=upper_params, lower_parameters=lower_params,
        display_indices=np.arange(point_count), valid=np.ones(point_count, dtype=bool),
        fallback_used=np.zeros(point_count, dtype=bool),
    )


# --- Task 1: geometry primitives and nose refinement ---------------------

def test_inward_normal_points_toward_reference():
    point = np.array((0.0, 0.0))
    derivative = np.array((1.0, 0.0))
    reference = np.array((0.0, 1.0))
    normal = cma.inward_normal(derivative, point, reference)
    assert np.dot(normal, reference - point) > 0
    np.testing.assert_allclose(np.linalg.norm(normal), 1.0)


def test_intersect_normals_finds_equidistant_center():
    upper_point = np.array((1.0, 0.0))
    lower_point = np.array((0.0, 1.0))
    upper_normal = np.array((-1.0, 0.0))
    lower_normal = np.array((0.0, -1.0))
    center, radius_upper, radius_lower = cma.intersect_normals(
        upper_point, upper_normal, lower_point, lower_normal,
    )
    np.testing.assert_allclose(center, (0.0, 0.0), atol=1e-12)
    assert radius_upper == pytest.approx(1.0)
    assert radius_lower == pytest.approx(1.0)


def test_intersect_normals_rejects_parallel_normals():
    upper_point = np.array((0.0, 0.0))
    lower_point = np.array((1.0, 0.0))
    normal = np.array((0.0, 1.0))
    assert cma.intersect_normals(upper_point, normal, lower_point, normal) is None


def test_refine_nose_start_matches_true_curvature_extremum():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)

    t_star, center, radius = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)

    assert np.linalg.norm(center - np.array((xc, yc))) < 5e-4
    assert abs(radius - rc) < 5e-4
    assert 0.0 < t_star < 1.0


def test_refine_nose_start_falls_back_when_window_collapses():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    # margin=0.0 collapses the search window to a single point (upper <=
    # lower), which must trigger the fallback rather than raise.
    t_star, center, radius = cma.refine_nose_start(
        spline_data, t_le=0.5, xc=0.01, yc=0.0, rc=0.01, margin=0.0,
    )
    assert t_star == 0.5
    np.testing.assert_allclose(center, (0.01, 0.0))
    assert radius == 0.01


# --- Task 2: continuation step ---------------------------------------------

def test_continuation_step_advances_from_the_nose_with_correct_radius():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    t_star, center0, radius0 = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)

    step = 0.003
    guess_upper = t_star - step / np.sqrt(2.0)
    guess_lower = t_star + step / np.sqrt(2.0)
    result = cma._continuation_step(
        spline_data, t_star, t_star, center0, guess_upper, guess_lower, step,
    )
    assert result is not None
    t_upper, t_lower, solution, used_step = result

    assert t_upper < t_star
    assert t_lower > t_star
    assert abs(solution['radius_upper'] - solution['radius_lower']) < 1e-8 * radius0
    assert abs(solution['radius_upper'] - radius0) < 0.05 * radius0


def test_continuation_step_returns_none_when_guess_carries_no_direction():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    result = cma._continuation_step(
        spline_data, 0.5, 0.5, np.array((0.0, 0.0)), 0.5, 0.5, step=1e-9, min_step=1e-9,
    )
    assert result is None


# --- Task 3: full march ------------------------------------------------

def test_march_on_symmetric_naca0012_stays_on_the_chord_line():
    x, y = _load_dat(NACA0012)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    t_star, center0, radius0 = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)
    states = cma._march(spline_data, t_star, center0, radius0)

    assert len(states) > 20
    centers = np.array([s['center'] for _, _, s in states])
    assert np.max(np.abs(centers[:, 1])) < 1e-4
    assert np.all(np.diff(centers[:, 0]) > 0) or np.all(np.diff(centers[:, 0]) < 0)


def test_march_on_naca2315_reaches_both_surface_ends_smoothly():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    t_star, center0, radius0 = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)
    states = cma._march(spline_data, t_star, center0, radius0)

    assert len(states) > 20
    assert states[-1][0] < 1e-3
    assert states[-1][1] > 1.0 - 1e-3

    centers = np.array([s['center'] for _, _, s in states])
    jumps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    # The raw march's adaptive step can grow large in low-curvature regions
    # (by design -- it's resampled to a uniform grid afterward, checked
    # separately in test_trace_camberline_has_no_large_jumps); this just
    # guards against a genuine discontinuity, not the largest normal step.
    assert np.max(jumps) < 0.035


# --- Task 4: legacy blend, resampling, public trace() -----------------

@pytest.mark.parametrize('dat_path', [NACA2315, MW166, NACA0012])
def test_trace_tangency_matches_true_nearest_surface_point(dat_path):
    x, y = _load_dat(dat_path)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    legacy = _build_legacy_camber_data(spline_data)

    result = cma.trace(
        spline_data, t_le, legacy, rc, xc, yc, xle, yle,
        point_count=240, display_count=17,
    )

    assert result.point_count == 240
    assert np.all(result.valid)

    t_full = np.linspace(0.0, 1.0, 40000)
    full_points = np.column_stack(spline_data.evaluate(t_full, der=0))
    centers = np.column_stack(result.coordinates)
    radii = np.asarray(result.radius)

    worst_gap = 0.0
    for center, radius in zip(centers, radii):
        distance = np.min(np.linalg.norm(full_points - center, axis=1))
        worst_gap = max(worst_gap, abs(distance - radius))
    assert worst_gap < 5.0e-4


def test_trace_camberline_has_no_large_jumps():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    legacy = _build_legacy_camber_data(spline_data)
    result = cma.trace(spline_data, t_le, legacy, rc, xc, yc, xle, yle, 240, 17)

    centers = np.column_stack(result.coordinates)
    steps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    assert np.max(steps) < 0.02
    radii = np.asarray(result.radius)
    radius_steps = np.abs(np.diff(radii))
    assert np.max(radius_steps) < 0.01


def test_trace_leaves_get_le_radius_marker_point_untouched():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    legacy = _build_legacy_camber_data(spline_data)

    before = (rc, xc, yc, xle, yle)
    result = cma.trace(spline_data, t_le, legacy, rc, xc, yc, xle, yle, 240, 17)
    after = (rc, xc, yc, xle, yle)
    assert before == after

    first_center = np.array((result.coordinates[0][0], result.coordinates[1][0]))
    assert np.linalg.norm(first_center - np.array((xc, yc))) < 5e-4


def test_trace_degrades_gracefully_on_pathological_input():
    theta = np.linspace(0.0, 2 * np.pi, 60)
    x = 0.5 + 0.5 * np.cos(theta)
    y = 0.01 * np.sin(theta)
    spline_data = _build_spline_data(x, y, points=60)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    legacy = _build_legacy_camber_data(spline_data, point_count=60)

    result = cma.trace(spline_data, t_le, legacy, rc, xc, yc, xle, yle, 60, 12)
    assert result.point_count == 60
    assert np.all(result.valid)
    assert np.all(np.isfinite(result.radius))


# --- Task 5: integration through CamberBuilder --------------------------

def test_camber_builder_inscribed_method_uses_medial_axis_tracer():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    import Camber

    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)

    builder = Camber.CamberBuilder()
    result = builder.build(spline_data, rc, xc, yc, xle, yle)
    assert result.method == Camber.CAMBER_METHOD_INSCRIBED_CIRCLES
    assert result.point_count == builder.DEFAULT_CALCULATION_POINTS
    assert np.all(result.valid)

    t_full = np.linspace(0.0, 1.0, 40000)
    full_points = np.column_stack(spline_data.evaluate(t_full, der=0))
    centers = np.column_stack(result.coordinates)
    radii = np.asarray(result.radius)
    worst_gap = max(
        abs(np.min(np.linalg.norm(full_points - center, axis=1)) - radius)
        for center, radius in zip(centers, radii)
    )
    assert worst_gap < 5.0e-4
