from __future__ import annotations

import numpy as np
from scipy import optimize

from ContourData import CamberData

MIN_RADIUS = 1.0e-8
MIN_NORMAL_DETERMINANT = 1.0e-10
NOSE_REFINE_MARGIN = 0.03

MAX_NEWTON_ITERATIONS = 15
MAX_STEP_SHRINKS = 30
MIN_STEP = 1.0e-9
MIN_PROGRESS_FRACTION = 0.2

INITIAL_STEP = 0.003
MAX_STEP = 0.02
MAX_MARCH_STEPS = 4000
RADIUS_FLOOR = 1.0e-4  # relative to unit chord

BLEND_STATION_COUNT = 10
UPPER_COMPLETE_TOLERANCE = 1.0e-3
LOWER_COMPLETE_TOLERANCE = 1.0e-3


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
    if upper_complete and lower_complete:
        return states, None

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
    """Resample onto `point_count` arc-length-uniform points by linearly
    interpolating center/radius/contact-point coordinates (and parameters)
    directly against cumulative arc length.

    A variant that instead interpolated only the (t_upper, t_lower)
    parameters and re-derived each output circle exactly via
    `_circle_from_parameters` was tried and rejected: near max thickness the
    upper and lower surface normals can become nearly parallel, making that
    2x2 solve ill-conditioned, so a tiny interpolated-parameter difference
    could swing the recomputed center wildly off course -- worse than the
    small, bounded error plain linear interpolation leaves between raw
    (already Newton-validated) march points.
    """
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
