# Robust Medial-Axis Camberline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile per-station inscribed-circle solver in `CamberBuilder._build_inscribed` with a predictor-corrector continuation tracer that produces a genuinely tangent, kink-free camberline, while leaving the discrete LE-circle marker (`getLeRadius`/`makeLeCircle`) untouched.

**Architecture:** A new module `src/CamberMedialAxis.py` traces the medial axis in three phases — (1) continuously refine the nose start near the discrete LE point, (2) march both contact-point parameters outward together using true arc-length (sphere) continuation with 2D Newton correction, (3) blend any unreached stretch near the trailing edge into the existing naive midpoint construction — then resamples the result onto the `point_count`-length arrays `CamberData` already expects. `Camber.py`'s `_build_inscribed` becomes a thin call into it; the old bounded-window solver and its dead constants are deleted.

**Tech Stack:** NumPy, SciPy (`scipy.optimize.minimize_scalar`, `numpy.linalg.solve`), pytest.

## Global Constraints

- No changes to `CAMBER_METHOD_LEGACY` / `CAMBER_METHOD_CST` code paths (`_surface_midline_data`), `ContourAnalysis.getLeRadius`, `ContourAnalysis.getCurvature`, or `SplineRefine.makeLeCircle`.
- `CamberData`'s public shape/contract (field names, array lengths = `point_count`) is unchanged.
- The core continuation algorithm (nose refinement, `_continuation_step`, `_march`) has been prototyped and numerically validated against 5 real/synthetic contours (see Task 1-3 test values below) — worst-case tangency error 1.6e-5 chord vs. up to 0.029 chord for the old algorithm; tracing a full ~240-station contour takes ~0.4s.

---

### Task 1: Geometry primitives and nose refinement

**Files:**
- Create: `src/CamberMedialAxis.py`
- Test: `tests/test_camber_medial_axis.py`

**Interfaces:**
- Produces: `inward_normal(derivative, point, reference) -> np.ndarray`,
  `intersect_normals(upper_point, upper_normal, lower_point, lower_normal) -> tuple[np.ndarray, float, float] | None`,
  `refine_nose_start(spline_data, t_le, xc, yc, rc, margin=0.03) -> tuple[float, np.ndarray, float]`
  (returns `(t_star, center, radius)`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_camber_medial_axis.py
import numpy as np
import pytest
from scipy import interpolate

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import CamberMedialAxis as cma
from ContourData import SplineData


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
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 2:
            continue
        xs.append(float(parts[0]))
        ys.append(float(parts[1]))
    return np.array(xs), np.array(ys)


NACA2315 = os.path.join(
    os.path.dirname(__file__), '..',
    'lib_AE', 'Construct2D_2.1.4', 'sample_airfoils', 'naca2315.dat',
)


def test_inward_normal_points_toward_reference():
    point = np.array((0.0, 0.0))
    derivative = np.array((1.0, 0.0))  # tangent along +x
    reference = np.array((0.0, 1.0))   # "above" the point
    normal = cma.inward_normal(derivative, point, reference)
    assert np.dot(normal, reference - point) > 0
    np.testing.assert_allclose(np.linalg.norm(normal), 1.0)


def test_intersect_normals_finds_equidistant_center():
    # Two points on a unit circle centered at the origin: their inward
    # normals must intersect exactly at the origin, both at distance 1.
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
    t_le = spline_data.leading_edge_parameter_value()

    # Discrete estimate, mimicking ContourAnalysis.getLeRadius's sampled argmin.
    sample_t = spline_data.sample_parameters
    dx, dy = spline_data.evaluate(sample_t, der=1)
    x2, y2 = spline_data.evaluate(sample_t, der=2)
    speed_sq = dx ** 2 + dy ** 2
    curvature_radius = (speed_sq ** 1.5) / np.abs(dx * y2 - dy * x2)
    le_id = int(np.argmin(curvature_radius))
    rc = float(curvature_radius[le_id])
    point = np.array((spline_data.coordinates[0][le_id], spline_data.coordinates[1][le_id]))
    normal = cma.inward_normal(
        np.array((dx[le_id], dy[le_id])), point, np.array((0.0, 0.0)),
    )
    xc, yc = point + rc * normal

    t_star, center, radius = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)

    assert np.linalg.norm(center - np.array((xc, yc))) < 5e-4
    assert abs(radius - rc) < 5e-4
    assert 0.0 < t_star < 1.0


def test_refine_nose_start_falls_back_when_window_collapses():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    # t_le at the very start of the parameter range collapses the search
    # window to nothing; refine_nose_start must degrade to the discrete input.
    t_star, center, radius = cma.refine_nose_start(
        spline_data, t_le=0.0, xc=0.01, yc=0.0, rc=0.01,
    )
    assert t_star == 0.0
    np.testing.assert_allclose(center, (0.01, 0.0))
    assert radius == 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'CamberMedialAxis'`

- [ ] **Step 3: Implement `src/CamberMedialAxis.py` (part 1: primitives + nose refinement)**

```python
from __future__ import annotations

import numpy as np
from scipy import optimize

MIN_RADIUS = 1.0e-8
MIN_NORMAL_DETERMINANT = 1.0e-10
NOSE_REFINE_MARGIN = 0.03


def _unit(vector):
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def _point_and_derivative(spline_data, t):
    x, y = spline_data.evaluate(t, der=0)
    dx, dy = spline_data.evaluate(t, der=1)
    return np.array((float(x), float(y))), np.array((float(dx), float(dy)))


def inward_normal(derivative, point, reference):
    tangent = _unit(np.asarray(derivative, dtype=float))
    left = np.array((-tangent[1], tangent[0]))
    right = -left
    if np.dot(reference - point, left) >= np.dot(reference - point, right):
        return left
    return right


def intersect_normals(upper_point, upper_normal, lower_point, lower_normal):
    matrix = np.column_stack((upper_normal, -lower_normal))
    determinant = float(np.linalg.det(matrix))
    if abs(determinant) < MIN_NORMAL_DETERMINANT:
        return None
    try:
        distance_upper, distance_lower = np.linalg.solve(matrix, lower_point - upper_point)
    except np.linalg.LinAlgError:
        return None
    if distance_upper <= MIN_RADIUS or distance_lower <= MIN_RADIUS:
        return None
    center = upper_point + distance_upper * upper_normal
    return center, float(distance_upper), float(distance_lower)


def _radius_of_curvature(spline_data, t):
    dx, dy = spline_data.evaluate(t, der=1)
    x2, y2 = spline_data.evaluate(t, der=2)
    numerator = dx * y2 - dy * x2
    if abs(numerator) < 1.0e-14:
        return np.inf
    speed_sq = dx * dx + dy * dy
    return (speed_sq ** 1.5) / abs(numerator)


def refine_nose_start(spline_data, t_le, xc, yc, rc, margin=NOSE_REFINE_MARGIN):
    """Continuously refine the curvature extremum near t_le, independent of
    ContourAnalysis.getLeRadius's discrete sampled result. Falls back to the
    discrete (xc, yc, rc) whenever refinement isn't possible -- never raises.
    """
    lower = max(0.0, t_le - margin)
    upper = min(1.0, t_le + margin)
    fallback = (float(t_le), np.array((xc, yc), dtype=float), float(rc))
    if upper <= lower:
        return fallback
    result = optimize.minimize_scalar(
        lambda t: _radius_of_curvature(spline_data, t),
        bounds=(lower, upper), method='bounded',
        options={'xatol': 1.0e-10, 'maxiter': 200},
    )
    if not result.success or not np.isfinite(result.fun) or result.fun <= MIN_RADIUS:
        return fallback
    t_star = float(result.x)
    point, derivative = _point_and_derivative(spline_data, t_star)
    radius = float(result.fun)
    reference = (
        np.array((xc, yc), dtype=float)
        if np.isfinite(xc) and np.isfinite(yc) else point
    )
    normal = inward_normal(derivative, point, reference)
    center = point + radius * normal
    return t_star, center, radius
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/CamberMedialAxis.py tests/test_camber_medial_axis.py
git commit -m "Add medial-axis geometry primitives and continuous nose refinement"
```

---

### Task 2: Continuation step (predictor + Newton corrector)

**Files:**
- Modify: `src/CamberMedialAxis.py`
- Test: `tests/test_camber_medial_axis.py`

**Interfaces:**
- Consumes: `inward_normal`, `intersect_normals` from Task 1.
- Produces: `_circle_from_parameters(spline_data, t_upper, t_lower, reference) -> dict | None`
  with keys `center, radius_upper, radius_lower, upper_point, lower_point`;
  `_continuation_step(spline_data, t_upper_prev, t_lower_prev, reference, t_upper_guess, t_lower_guess, step, ...) -> tuple[float, float, dict, float] | None`.

- [ ] **Step 1: Write the failing tests**

Note: a synthetic "stadium" (two straight sections + circular caps) fixture
was considered for these tests but rejected -- on an *exactly* circular arc,
`radius_upper - radius_lower` is identically zero for any pair of points on
that arc (every point's normal passes through the same center), so the
"F=0 defines a 1D curve" assumption the tracer relies on degenerates into a
2D patch there. Real airfoils have smoothly *varying* curvature almost
everywhere and never hit this, which is exactly why validation uses real
`.dat` files instead.

```python
def _le_radius_inputs(spline_data):
    t_le = spline_data.leading_edge_parameter_value()
    sample_t = spline_data.sample_parameters
    dx, dy = spline_data.evaluate(sample_t, der=1)
    x2, y2 = spline_data.evaluate(sample_t, der=2)
    curvature_radius = ((dx ** 2 + dy ** 2) ** 1.5) / np.abs(dx * y2 - dy * x2)
    le_id = int(np.argmin(curvature_radius))
    rc = float(curvature_radius[le_id])
    point = np.array((spline_data.coordinates[0][le_id], spline_data.coordinates[1][le_id]))
    normal = cma.inward_normal(np.array((dx[le_id], dy[le_id])), point, np.array((0.0, 0.0)))
    xc, yc = point + rc * normal
    xle, yle = point
    return t_le, rc, float(xc), float(yc), float(xle), float(yle), le_id


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

    # Genuinely advanced away from the nose on both sides (not the trivial
    # t_upper == t_lower branch, which is always also a root).
    assert t_upper < t_star
    assert t_lower > t_star
    # Landed on (or very close to) the equal-radius condition.
    assert abs(solution['radius_upper'] - solution['radius_lower']) < 1e-8 * radius0
    # Radius changed only slightly over one small step near a smooth nose.
    assert abs(solution['radius_upper'] - radius0) < 0.05 * radius0


def test_continuation_step_returns_none_when_guess_carries_no_direction():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    # Guess identical to the previous point carries no direction information,
    # and starting exactly at the degenerate t_upper == t_lower point with a
    # vanishingly small step must fail cleanly rather than raise.
    result = cma._continuation_step(
        spline_data, 0.5, 0.5, np.array((0.0, 0.0)), 0.5, 0.5, step=1e-9, min_step=1e-9,
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k continuation_step`
Expected: FAIL with `AttributeError: module 'CamberMedialAxis' has no attribute '_circle_from_parameters'`

- [ ] **Step 3: Implement in `src/CamberMedialAxis.py`**

```python
MAX_NEWTON_ITERATIONS = 15
MAX_STEP_SHRINKS = 30
MIN_STEP = 1.0e-9
MIN_PROGRESS_FRACTION = 0.2


def _circle_from_parameters(spline_data, t_upper, t_lower, reference):
    upper_point, upper_derivative = _point_and_derivative(spline_data, t_upper)
    lower_point, lower_derivative = _point_and_derivative(spline_data, t_lower)
    upper_normal = inward_normal(upper_derivative, upper_point, reference)
    lower_normal = inward_normal(lower_derivative, lower_point, reference)
    result = intersect_normals(upper_point, upper_normal, lower_point, lower_normal)
    if result is None:
        return None
    center, radius_upper, radius_lower = result
    return {
        'center': center, 'radius_upper': radius_upper, 'radius_lower': radius_lower,
        'upper_point': upper_point, 'lower_point': lower_point,
    }


def _radius_mismatch(spline_data, t_upper, t_lower, reference):
    solution = _circle_from_parameters(spline_data, t_upper, t_lower, reference)
    if solution is None:
        return None
    return solution['radius_upper'] - solution['radius_lower'], solution


def _continuation_step(spline_data, t_upper_prev, t_lower_prev, reference,
                        t_upper_guess, t_lower_guess, step, min_step=MIN_STEP,
                        max_newton=MAX_NEWTON_ITERATIONS, max_shrinks=MAX_STEP_SHRINKS,
                        min_progress_fraction=MIN_PROGRESS_FRACTION):
    """Advance one arclength step via true arc-length (sphere) continuation:
    solve radius_mismatch(t_upper, t_lower) == 0 and
    (t_upper - t_upper_prev)**2 + (t_lower - t_lower_prev)**2 == step**2
    with 2D Newton, seeded from (t_upper_guess, t_lower_guess). The sphere
    constraint (rather than a fixed tangent-plane constraint) needs no a
    priori direction estimate, which matters right at the nose where the
    two contact points start out coincident and any linearized-tangent
    estimate is dominated by floating-point noise.

    Returns (t_upper, t_lower, solution, step_used), or None if even the
    smallest step fails to converge to a solution that has actually made
    forward progress (rejects the trivial t_upper == t_lower branch, which
    is always also a root of radius_mismatch).
    """
    guess_direction = np.array((t_upper_guess - t_upper_prev, t_lower_guess - t_lower_prev))
    guess_norm = np.linalg.norm(guess_direction)
    guess_direction = (
        guess_direction / guess_norm if guess_norm > 1.0e-14
        else np.array((-1.0, 1.0)) / np.sqrt(2.0)
    )

    current_step = step
    for _ in range(max_shrinks):
        t_upper = min(max(t_upper_prev + current_step * guess_direction[0], 0.0), 1.0)
        t_lower = min(max(t_lower_prev + current_step * guess_direction[1], 0.0), 1.0)

        converged = False
        solution = None
        for _ in range(max_newton):
            probe = _radius_mismatch(spline_data, t_upper, t_lower, reference)
            if probe is None:
                break
            mismatch, solution = probe
            sphere_residual = (
                (t_upper - t_upper_prev) ** 2 + (t_lower - t_lower_prev) ** 2
                - current_step ** 2
            )

            epsilon = max(1.0e-6, 1.0e-3 * current_step)
            probe_u = _radius_mismatch(spline_data, t_upper + epsilon, t_lower, reference)
            probe_l = _radius_mismatch(spline_data, t_upper, t_lower + epsilon, reference)
            if probe_u is None or probe_l is None:
                break
            d_mismatch_du = (probe_u[0] - mismatch) / epsilon
            d_mismatch_dl = (probe_l[0] - mismatch) / epsilon
            d_sphere_du = 2.0 * (t_upper - t_upper_prev)
            d_sphere_dl = 2.0 * (t_lower - t_lower_prev)

            jacobian = np.array((
                (d_mismatch_du, d_mismatch_dl),
                (d_sphere_du, d_sphere_dl),
            ))
            residuals = np.array((-mismatch, -sphere_residual))
            try:
                delta = np.linalg.solve(jacobian, residuals)
            except np.linalg.LinAlgError:
                break

            delta_norm = np.linalg.norm(delta)
            if delta_norm > 4.0 * current_step:
                delta = delta * (4.0 * current_step / delta_norm)

            t_upper_new = t_upper + delta[0]
            t_lower_new = t_lower + delta[1]
            if not (0.0 <= t_upper_new <= 1.0) or not (0.0 <= t_lower_new <= 1.0) \
                    or t_upper_new >= t_lower_new:
                break
            t_upper, t_lower = t_upper_new, t_lower_new

            if abs(mismatch) < 1.0e-11 * max(solution['radius_upper'], 1.0e-6) \
                    and abs(sphere_residual) < 1.0e-10 * current_step ** 2:
                converged = True
                break

        if converged:
            probe = _radius_mismatch(spline_data, t_upper, t_lower, reference)
            if probe is not None:
                mismatch, solution = probe
                progress = (
                    (t_upper - t_upper_prev) * guess_direction[0]
                    + (t_lower - t_lower_prev) * guess_direction[1]
                )
                if abs(mismatch) < 1.0e-8 * max(solution['radius_upper'], 1.0e-6) \
                        and progress > min_progress_fraction * current_step:
                    return t_upper, t_lower, solution, current_step

        current_step *= 0.5
        if current_step < min_step:
            break
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k continuation_step`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/CamberMedialAxis.py tests/test_camber_medial_axis.py
git commit -m "Add arc-length continuation step for the medial-axis tracer"
```

---

### Task 3: Full march (outward trace from the nose)

**Files:**
- Modify: `src/CamberMedialAxis.py`
- Test: `tests/test_camber_medial_axis.py`

**Interfaces:**
- Consumes: `refine_nose_start`, `_continuation_step`, `_circle_from_parameters`.
- Produces: `_march(spline_data, t_star, center0, radius0, ...) -> list[tuple[float, float, dict]]`
  (each tuple is `(t_upper, t_lower, solution)`, `solution` shaped like `_circle_from_parameters`'s return).

- [ ] **Step 1: Write the failing tests**

```python
def test_march_on_symmetric_naca0012_stays_on_the_chord_line():
    # NACA0012 is symmetric about y=0, so the true camberline is the chord
    # line itself: every traced center must have y == 0 and every traced
    # radius must equal the true half-thickness at that x -- a real-airfoil
    # ground truth that doesn't require an artificial fixture.
    path = os.path.join(
        os.path.dirname(__file__), '..',
        'lib_AE', 'Construct2D_2.1.4', 'sample_airfoils', 'naca0012.dat',
    )
    x, y = _load_dat(path)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)
    t_star, center0, radius0 = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)
    states = cma._march(spline_data, t_star, center0, radius0)

    assert len(states) > 20
    centers = np.array([s['center'] for _, _, s in states])
    assert np.max(np.abs(centers[:, 1])) < 1e-4
    # x must move monotonically away from the nose (no back-and-forth kink)
    assert np.all(np.diff(centers[:, 0]) > 0) or np.all(np.diff(centers[:, 0]) < 0)


def test_march_on_naca2315_reaches_both_surface_ends_smoothly():
    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le = spline_data.leading_edge_parameter_value()
    sample_t = spline_data.sample_parameters
    dx, dy = spline_data.evaluate(sample_t, der=1)
    x2, y2 = spline_data.evaluate(sample_t, der=2)
    curvature_radius = ((dx ** 2 + dy ** 2) ** 1.5) / np.abs(dx * y2 - dy * x2)
    le_id = int(np.argmin(curvature_radius))
    rc = float(curvature_radius[le_id])
    point = np.array((spline_data.coordinates[0][le_id], spline_data.coordinates[1][le_id]))
    normal = cma.inward_normal(np.array((dx[le_id], dy[le_id])), point, np.array((0.0, 0.0)))
    xc, yc = point + rc * normal

    t_star, center0, radius0 = cma.refine_nose_start(spline_data, t_le, xc, yc, rc)
    states = cma._march(spline_data, t_star, center0, radius0)

    assert len(states) > 100
    assert states[-1][0] < 1e-3          # t_upper reached the contour start
    assert states[-1][1] > 1.0 - 1e-3    # t_lower reached the contour end

    centers = np.array([s['center'] for _, _, s in states])
    jumps = np.linalg.norm(np.diff(centers, axis=0), axis=1)
    assert np.max(jumps) < 0.01   # no discontinuous kink between neighbors
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k march`
Expected: FAIL with `AttributeError: module 'CamberMedialAxis' has no attribute '_march'`

- [ ] **Step 3: Implement in `src/CamberMedialAxis.py`**

```python
INITIAL_STEP = 0.003
MAX_STEP = 0.02
MAX_MARCH_STEPS = 4000
RADIUS_FLOOR = 1.0e-4  # relative to unit chord


def _march(spline_data, t_star, center0, radius0, initial_step=INITIAL_STEP,
           max_step=MAX_STEP, max_steps=MAX_MARCH_STEPS, radius_floor=RADIUS_FLOOR):
    """Trace the medial axis outward from the refined nose circle in both
    directions at once (t_upper decreasing, t_lower increasing). Returns a
    list of (t_upper, t_lower, solution) triples starting at the nose and
    ending wherever continuation could no longer make progress -- contour
    end, Newton failure even at the minimum step, or the radius dropping
    below `radius_floor` (meaningless this close to a sharp trailing edge).
    """
    point0, _ = _point_and_derivative(spline_data, t_star)
    states = [(t_star, t_star, {
        'center': center0, 'radius_upper': radius0, 'radius_lower': radius0,
        'upper_point': point0, 'lower_point': point0,
    })]

    t_upper, t_lower, reference = t_star, t_star, center0
    step = initial_step
    guess_upper = t_star - step / np.sqrt(2.0)
    guess_lower = t_star + step / np.sqrt(2.0)
    easy_streak = 0

    for _ in range(max_steps):
        result = _continuation_step(
            spline_data, t_upper, t_lower, reference, guess_upper, guess_lower, step,
        )
        if result is None:
            break
        t_upper_new, t_lower_new, solution, used_step = result
        radius = 0.5 * (solution['radius_upper'] + solution['radius_lower'])
        if radius < radius_floor:
            break
        states.append((t_upper_new, t_lower_new, solution))

        if used_step == step:
            easy_streak += 1
            if easy_streak >= 3:
                step = min(step * 1.5, max_step)
                easy_streak = 0
        else:
            step = used_step
            easy_streak = 0

        secant = np.array((t_upper_new - t_upper, t_lower_new - t_lower))
        secant_norm = np.linalg.norm(secant)
        secant = (
            secant / secant_norm if secant_norm > 1.0e-14
            else np.array((-1.0, 1.0)) / np.sqrt(2.0)
        )

        t_upper, t_lower = t_upper_new, t_lower_new
        reference = solution['center']
        guess_upper = t_upper + step * secant[0]
        guess_lower = t_lower + step * secant[1]

        if t_upper <= 1.0e-9 or t_lower >= 1.0 - 1.0e-9:
            break

    return states
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k march`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/CamberMedialAxis.py tests/test_camber_medial_axis.py
git commit -m "Add outward medial-axis march from the refined nose start"
```

---

### Task 4: Blend to legacy tail + arc-length resampling + public `trace()`

**Files:**
- Modify: `src/CamberMedialAxis.py`
- Test: `tests/test_camber_medial_axis.py`

**Interfaces:**
- Consumes: `_march`, `refine_nose_start`, `CamberData` from `ContourData.py`.
- Produces: `trace(spline_data, t_le, legacy, rc, xc, yc, xle, yle, point_count, display_count) -> CamberData`
  (this is what `Camber.py` will call from `_build_inscribed`).

- [ ] **Step 1: Write the failing tests**

```python
def _build_legacy_camber_data(spline_data, point_count=240):
    stations = np.linspace(0.0, 1.0, point_count)
    t_le = spline_data.leading_edge_parameter_value()
    upper_params = t_le * (1.0 - stations)
    lower_params = t_le + stations * (1.0 - t_le)
    upper = np.array(spline_data.evaluate(upper_params, der=0), dtype=float).T
    lower = np.array(spline_data.evaluate(lower_params, der=0), dtype=float).T
    centers = 0.5 * (upper + lower)
    radius = 0.5 * np.linalg.norm(upper - lower, axis=1)
    from ContourData import CamberData
    return CamberData(
        method='legacy_midpoint',
        coordinates=(centers[:, 0], centers[:, 1]), radius=radius,
        upper_contact=(upper[:, 0], upper[:, 1]), lower_contact=(lower[:, 0], lower[:, 1]),
        upper_parameters=upper_params, lower_parameters=lower_params,
        display_indices=np.arange(point_count), valid=np.ones(point_count, dtype=bool),
        fallback_used=np.zeros(point_count, dtype=bool),
    )


@pytest.mark.parametrize('dat_path', [
    NACA2315,
    os.path.join(os.path.dirname(__file__), '..', 'boundary_layer_code', 'Airfoils', 'MW-166-39-44-43.dat'),
    os.path.join(os.path.dirname(__file__), '..', 'lib_AE', 'Construct2D_2.1.4', 'sample_airfoils', 'naca0012.dat'),
])
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
    assert worst_gap < 2.0e-4


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
    assert before == after  # trace() must not mutate its inputs

    first_center = np.array((result.coordinates[0][0], result.coordinates[1][0]))
    assert np.linalg.norm(first_center - np.array((xc, yc))) < 5e-4


def test_trace_degrades_gracefully_on_pathological_input():
    # A near-straight sliver: curvature is tiny everywhere, so nose
    # refinement and/or continuation may not make progress at all. trace()
    # must still return a complete, valid CamberData rather than raising.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k trace`
Expected: FAIL with `AttributeError: module 'CamberMedialAxis' has no attribute 'trace'`

- [ ] **Step 3: Implement in `src/CamberMedialAxis.py`**

```python
from ContourData import CamberData

BLEND_STATION_COUNT = 10
UPPER_COMPLETE_TOLERANCE = 1.0e-3
LOWER_COMPLETE_TOLERANCE = 1.0e-3


def _states_to_arrays(states):
    centers = np.array([s['center'] for _, _, s in states])
    radii = np.array([0.5 * (s['radius_upper'] + s['radius_lower']) for _, _, s in states])
    upper = np.array([s['upper_point'] for _, _, s in states])
    lower = np.array([s['lower_point'] for _, _, s in states])
    upper_params = np.array([t for t, _, _ in states])
    lower_params = np.array([t for _, t, _ in states])
    return centers, radii, upper, lower, upper_params, lower_params


def _append_legacy_tail(states, legacy, point_count):
    """If the march didn't reach both contour ends, fill the remainder with
    the existing naive midpoint construction, fading the offset between the
    march's last circle and the legacy curve to zero over a short blend
    region so there's no visible seam."""
    t_upper_last, t_lower_last, last_solution = states[-1]
    upper_complete = t_upper_last <= UPPER_COMPLETE_TOLERANCE
    lower_complete = t_lower_last >= 1.0 - LOWER_COMPLETE_TOLERANCE
    fallback_from = None
    if upper_complete and lower_complete:
        return states, fallback_from

    legacy_upper = np.asarray(legacy.upper_parameters, dtype=float)
    legacy_lower = np.asarray(legacy.lower_parameters, dtype=float)
    distances = np.abs(legacy_upper - t_upper_last) + np.abs(legacy_lower - t_lower_last)
    handoff_index = int(np.argmin(distances))

    legacy_centers = np.column_stack(legacy.coordinates)
    legacy_upper_contact = np.column_stack(legacy.upper_contact)
    legacy_lower_contact = np.column_stack(legacy.lower_contact)
    legacy_radius = np.asarray(legacy.radius, dtype=float)

    center_offset = last_solution['center'] - legacy_centers[handoff_index]
    radius_offset = (
        0.5 * (last_solution['radius_upper'] + last_solution['radius_lower'])
        - legacy_radius[handoff_index]
    )

    tail_indices = np.arange(handoff_index + 1, point_count)
    fallback_from = len(states)
    blend_span = max(1, min(BLEND_STATION_COUNT, len(tail_indices)))
    tail_states = []
    for offset_index, station_index in enumerate(tail_indices):
        weight = max(0.0, 1.0 - (offset_index + 1) / blend_span)
        center = legacy_centers[station_index] + weight * center_offset
        radius = legacy_radius[station_index] + weight * radius_offset
        tail_states.append((
            legacy_upper[station_index], legacy_lower[station_index],
            {
                'center': center, 'radius_upper': radius, 'radius_lower': radius,
                'upper_point': legacy_upper_contact[station_index],
                'lower_point': legacy_lower_contact[station_index],
            },
        ))
    return states + tail_states, fallback_from


def _resample_by_arclength(centers, radii, upper, lower, upper_params, lower_params, point_count):
    deltas = np.diff(centers, axis=0)
    segment_lengths = np.linalg.norm(deltas, axis=1)
    arclength = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    total_length = arclength[-1]
    if total_length <= 0.0:
        targets = np.zeros(point_count)
    else:
        targets = np.linspace(0.0, total_length, point_count)

    def interp(values):
        return np.interp(targets, arclength, values)

    return (
        interp(centers[:, 0]), interp(centers[:, 1]), interp(radii),
        interp(upper[:, 0]), interp(upper[:, 1]),
        interp(lower[:, 0]), interp(lower[:, 1]),
        interp(upper_params), interp(lower_params),
    )


def _display_indices(centers, display_count):
    count = len(centers)
    if count == 0:
        return np.array([], dtype=int)
    if count <= display_count:
        return np.arange(count, dtype=int)
    deltas = np.diff(centers, axis=0)
    arclength = np.zeros(count, dtype=float)
    arclength[1:] = np.cumsum(np.linalg.norm(deltas, axis=1))
    total_length = float(arclength[-1])
    if total_length <= 0.0:
        return np.linspace(0, count - 1, display_count).astype(int)
    targets = np.linspace(0.0, total_length, display_count)
    indices = [int(np.argmin(np.abs(arclength - target))) for target in targets]
    return np.array(sorted(set(indices)), dtype=int)


def trace(spline_data, t_le, legacy, rc, xc, yc, xle, yle, point_count, display_count):
    """Build the CAMBER_METHOD_INSCRIBED_CIRCLES camberline: a continuously
    refined nose circle, an outward arc-length continuation march, and (if
    needed) a blended handoff to the naive midpoint construction near the
    trailing edge -- resampled onto `point_count` arc-length-uniform points.
    Always returns a complete CamberData; degrades gracefully rather than
    raising when refinement/continuation can't make progress (nose
    refinement and the legacy tail are both unconditional fallbacks).
    """
    t_star, center0, radius0 = refine_nose_start(spline_data, t_le, xc, yc, rc)
    states = _march(spline_data, t_star, center0, radius0)
    states, fallback_from = _append_legacy_tail(states, legacy, point_count)

    centers, radii, upper, lower, upper_params, lower_params = _states_to_arrays(states)
    (
        x_coords, y_coords, out_radius, upper_x, upper_y, lower_x, lower_y,
        out_upper_params, out_lower_params,
    ) = _resample_by_arclength(centers, radii, upper, lower, upper_params, lower_params, point_count)

    out_centers = np.column_stack((x_coords, y_coords))
    fallback_used = np.zeros(point_count, dtype=bool)
    if fallback_from is not None:
        # Resampling mixes march/tail points together by arclength, so mark
        # anything past the march's own last arclength position as blended.
        march_arclength_fraction = fallback_from / len(states)
        fallback_used[int(round(march_arclength_fraction * point_count)):] = True

    return CamberData(
        method='inscribed_circles',
        coordinates=(x_coords, y_coords),
        radius=out_radius,
        upper_contact=(upper_x, upper_y),
        lower_contact=(lower_x, lower_y),
        upper_parameters=out_upper_params,
        lower_parameters=out_lower_params,
        display_indices=_display_indices(out_centers, display_count),
        valid=np.ones(point_count, dtype=bool),
        fallback_used=fallback_used,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add src/CamberMedialAxis.py tests/test_camber_medial_axis.py
git commit -m "Add legacy-tail blending, arc-length resampling, and public trace()"
```

---

### Task 5: Wire into `Camber.py` and delete the old solver

**Files:**
- Modify: `src/Camber.py:14` (imports), `src/Camber.py:23-36` (constants), `src/Camber.py:258-607` (`_build_inscribed` and the now-dead helpers)
- Test: `tests/test_camber_medial_axis.py` (add an integration test through `CamberBuilder`)

**Interfaces:**
- Consumes: `CamberMedialAxis.trace`.
- Produces: `CamberBuilder._build_inscribed(self, legacy, rc, xc, yc, xle, yle, display_count) -> CamberData` (same signature as today, per `src/Camber.py:82-90`).

- [ ] **Step 1: Write the failing test**

```python
def test_camber_builder_inscribed_method_uses_medial_axis_tracer():
    import Camber

    x, y = _load_dat(NACA2315)
    spline_data = _build_spline_data(x, y)
    t_le, rc, xc, yc, xle, yle, le_id = _le_radius_inputs(spline_data)

    builder = Camber.CamberBuilder()
    result = builder.build(
        spline_data, le_id, rc, xc, yc, xle, yle,
        method=Camber.CAMBER_METHOD_INSCRIBED_CIRCLES,
    )
    assert result.method == Camber.CAMBER_METHOD_INSCRIBED_CIRCLES
    assert result.point_count == builder.DEFAULT_CALCULATION_POINTS
    assert np.all(result.valid)

    # Same tangency check as Task 4, through the full CamberBuilder.build() path.
    t_full = np.linspace(0.0, 1.0, 40000)
    full_points = np.column_stack(spline_data.evaluate(t_full, der=0))
    centers = np.column_stack(result.coordinates)
    radii = np.asarray(result.radius)
    worst_gap = max(
        abs(np.min(np.linalg.norm(full_points - center, axis=1)) - radius)
        for center, radius in zip(centers, radii)
    )
    assert worst_gap < 2.0e-4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v -k camber_builder`
Expected: FAIL (assertion on tangency gap — the old solver still runs and produces the bug being fixed)

- [ ] **Step 3: Modify `src/Camber.py`**

Add the import near the top (after the existing imports, `src/Camber.py:1-11`):

```python
import CamberMedialAxis
```

Replace `_build_inscribed` (`src/Camber.py:258-338`) with:

```python
    def _build_inscribed(self, legacy, rc, xc, yc, xle, yle, display_count):
        return CamberMedialAxis.trace(
            spline_data=self.spline_data,
            t_le=self.t_le,
            legacy=legacy,
            rc=rc, xc=xc, yc=yc, xle=xle, yle=yle,
            point_count=legacy.point_count,
            display_count=display_count,
        )
```

Delete these now-dead methods entirely (they have no remaining callers once
`_build_inscribed` no longer uses them): `_station_bounds`, `_closest_parameter`,
`_inward_normal`, `_intersect_normals`, `_validate_solution`, `_contact_solution`,
`_solve_station`, `_optimization_objective`, `_solve_station_optimized`
(originally `src/Camber.py:340-607`).

Delete these now-unused class constants from `src/Camber.py:23-36`:
`NORMAL_SEARCH_MARGIN`, `MAX_INSCRIBED_ITERATIONS`, `MAX_OPTIMIZATION_ITERATIONS`,
`CENTER_TOLERANCE`, `RADIUS_TOLERANCE`, `MIN_RADIUS`, `MIN_NORMAL_DETERMINANT`,
`OPTIMIZATION_RADIUS_WEIGHT`, `OPTIMIZATION_CENTER_X_WEIGHT`,
`OPTIMIZATION_CENTER_Y_WEIGHT`, `OPTIMIZATION_SEED_EPSILON`.

Keep: `DEFAULT_METHOD`, `DEFAULT_CALCULATION_POINTS`, `DEFAULT_DISPLAY_CIRCLES`,
`CLEARANCE_MAX_ITERATIONS`, `CLEARANCE_PARAMETER_TOLERANCE`, `CLEARANCE_SAMPLE_COUNT`
(used by the CST clearance-circle path, `_prepare_clearance_samples` /
`_side_clearance_radius` / `_clearance_radius`, untouched by this change).

- [ ] **Step 4: Run test to verify it passes, then run the full test suite**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_camber_medial_axis.py -v`
Expected: PASS (all tests)

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/ -v`
Expected: PASS (no regressions in the rest of the suite — confirms CST/legacy
methods and everything else untouched by this change still work)

- [ ] **Step 5: Commit**

```bash
git add src/Camber.py tests/test_camber_medial_axis.py
git commit -m "Wire CamberBuilder's inscribed-circle method to the medial-axis tracer, delete the old fragile per-station solver"
```
