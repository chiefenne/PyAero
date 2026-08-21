# Robust inscribed-circle camberline (medial-axis tracing)

Status: approved for planning
Date: 2026-08-21

## Problem

`CamberBuilder._build_inscribed()` in [src/Camber.py](../../../src/Camber.py) computes the
camberline for `CAMBER_METHOD_INSCRIBED_CIRCLES` by solving each displayed circle
independently: `_solve_station` runs a bounded fixed-point iteration seeded from a naive
"legacy" midpoint guess and a narrow ±0.08-parameter search window inherited from the
previous station; if it fails to converge to a tolerance-checked equal-radius solution,
`_solve_station_optimized` (an unconstrained L-BFGS-B soft-penalty fallback with no
equal-radius validation) is used instead, and its result is accepted unconditionally.

Diagnosis (see prior conversation) confirmed this produces circles whose reported radius
does not match the true nearest-surface distance on one side — the circle crosses through
the surface — concentrated in the region immediately following the leading-edge circle,
where the true closest point on one surface is genuinely pinned at the upper/lower
parameter split point `t_le`, causing the primary solver's fixed-point iteration to lock
onto an inconsistent state. Measured on real airfoils: up to 0.029 chord of penetration
(NACA 2315: 0.0039c; MW-166-39-44-43: 0.029c). The `fallback_used` diagnostic also
under-reports this because it is only set when *both* solvers fail, not when the
unvalidated optimizer path is used.

Additionally, the leading-edge circle (`(xc, yc, rc)` from `ContourAnalysis.getLeRadius`,
a discrete argmin over sampled curvature) is spliced in as the camberline's literal first
vertex (`centers[0] = (xc, yc)`), which can create a visible kink between it and the rest
of the traced curve since the two are independent approximations that don't necessarily
agree exactly.

## Goals

- Every displayed circle is genuinely tangent to both surfaces (reported radius matches
  the true nearest-surface distance on both sides, within a tight tolerance).
- The camberline is a smooth, continuous curve with no kink at the nose or anywhere else.
- The existing leading-edge circle computation (`getLeRadius`, fit to the discrete
  maximum-curvature point) is left unchanged and remains visibly marked — it is not
  forced to be an exact vertex of the camberline.
- `CamberData`'s public shape/contract is unchanged, so `Airfoil.py`, `export_camber`,
  and `ContourData.polyline_coordinates()` need no changes.

## Non-goals

- Changing `CAMBER_METHOD_LEGACY` or `CAMBER_METHOD_CST` (`_surface_midline_data`).
- Changing `ContourAnalysis.getLeRadius`, `ContourAnalysis.getCurvature`, or
  `SplineRefine.makeLeCircle` (the existing LE tangent-point marker already displays the
  discrete max-curvature point; no new marker UI is needed).
- Wiring `CAMBER_METHOD_INSCRIBED_CIRCLES` into the GUI's method selector — out of scope
  for this change (it's already reachable via `CamberBuilder.build(..., method=...)` for
  direct/programmatic use and tests, same as today).

## Architecture

New module `src/CamberMedialAxis.py` holds the whole inscribed-circle subsystem, replacing
`_build_inscribed`, `_station_bounds`, `_closest_parameter` (station-search variant),
`_solve_station`, `_solve_station_optimized`, `_optimization_objective`, `_contact_solution`
in `Camber.py`. `CamberBuilder._build_inscribed` becomes a thin call:

```python
def _build_inscribed(self, legacy, rc, xc, yc, xle, yle, display_count):
    return CamberMedialAxis.trace(
        spline_data=self.spline_data,
        t_le=self.t_le,
        legacy=legacy,
        point_count=legacy.point_count,
        display_count=display_count,
    )
```

`_validate_solution`, `_intersect_normals`, `_inward_normal`, `_point_and_derivative`,
`_evaluate_point`, `_evaluate_derivative` are either moved into the new module (if only
used there) or kept on `CamberBuilder` and passed/reused (`_intersect_normals` and
`_inward_normal` are pure geometry helpers with no builder state — move them as module-
level functions in `CamberMedialAxis.py` and have `Camber.py` import them if still needed).

## Algorithm

### 1. Nose start (continuous refinement)

`ContourAnalysis.getLeRadius` gives a discrete `(rc, xc, yc, xle, yle, le_id)` from
`argmin` over sampled curvature radius. `CamberMedialAxis` independently refines this to a
continuous extremum:

- Bracket a small window around `spline_data.sample_parameters[le_id]` (e.g. ± 2 sample
  spacings, clipped to a sane range).
- `t_star = optimize.minimize_scalar(radius_of_curvature, bounds=window, method='bounded')`,
  where `radius_of_curvature(t)` uses the same formula as `ContourAnalysis.getCurvature`
  (via `spline_data.evaluate(t, der=1)` and `der=2)`) evaluated at a single continuous `t`
  instead of the discrete sample grid.
- `center0, radius0 = point(t_star) - radius(t_star) * normal(t_star)`, `t_u0 = t_l0 = t_star`.

If this refinement fails (non-finite result, or the window collapses because `le_id` is at
a contour endpoint), fall back to the discrete `(xc, yc, rc)` as the start — the algorithm
degrades to "old start point, new tracing," never crashes.

This start is independent of `(xc, yc)` from `getLeRadius`; the two will typically differ
by a small, usually sub-visual amount. `getLeRadius`, `makeLeCircle`, and the LE-radius
readout are untouched, so the existing marker continues to show the same discrete point as
today, per the "keep that point still and mark it" requirement.

### 2. Continuation march (pseudo-arclength)

State is a pair of surface parameters `(t_u, t_l)` with `t_u ∈ [0, t_le]`,
`t_l ∈ [t_le, 1]`. Given `(t_u, t_l)`:

- `P_u, dP_u = evaluate(t_u, der=0/1)`; `P_l, dP_l = evaluate(t_l, der=0/1)`.
- Inward normals `n_u, n_l` via the existing `_inward_normal` logic, using the *previous
  accepted center* as the reference (for the first step, `center0`).
- `center, r_u, r_l = intersect_normals(P_u, n_u, P_l, n_l)` (existing `_intersect_normals`
  logic).
- Constraint `F(t_u, t_l) = r_u - r_l`.

Marching alternates predictor and corrector:

- **Predictor.** Tangent direction `d ∝ (∂F/∂t_l, -∂F/∂t_u)` (central finite differences),
  sign chosen to match the previous accepted step's direction (continue outward, never
  reverse). Step `(t_u*, t_l*) = (t_u, t_l) + h·d̂`. `h` starts small (e.g. equivalent to a
  target center-displacement of ~0.2% chord) and adapts: grow `h` after an easy corrector
  convergence, shrink after a hard one.
- **Corrector.** Solve the 2×2 system `F(t_u, t_l) = 0` and
  `d̂ · [(t_u, t_l) − (t_u*, t_l*)] = 0` (pseudo-arclength constraint — keeps the system
  well-posed even through turning points where `dt_u/dt_l` reverses sign, e.g. near max
  thickness) via Newton with a finite-difference Jacobian, ≤ 6 iterations, tight tolerance
  (`|F| < 1e-9 · max(radius, 1e-6)`).
- **Accept/retry.** If the corrector converges and `t_u, t_l` stay within their valid
  ranges and `radius > 0`: accept, record `(center, radius, t_u, t_l, P_u, P_l)`, recompute
  `d̂` from the last two accepted points. If it fails to converge: halve `h` and retry, down
  to a minimum step; if still failing at the minimum step, stop the march (see stopping
  conditions below).

### 3. Stopping conditions → blend to legacy tail

The march stops when any of:
- `t_u ≤ 0` or `t_l ≥ 1` (reached a contour end),
- the corrector fails even at the minimum step size,
- `radius` drops below a small threshold (e.g. `1e-4 · chord`).

From the last accepted `(t_u, t_l)`, find the legacy station whose naive
`(upper_parameter, lower_parameter)` is closest (by parameter distance) to
`(t_u, t_l)`, and continue the existing naive upper/lower-midpoint construction
(`_surface_midline_data`'s per-station centers/radius) from there to the trailing edge.
To avoid a visible seam, blend over a short transition (a fixed number of stations, e.g.
10, or fewer if less than 10 legacy stations remain): linearly fade the offset between the
continuation's last point and the legacy midpoint's value at the matching station from
100% to 0% across the transition, so the handoff is continuous in both position and radius.

### 4. Resampling to the output contract

The combined curve (nose start → continuation points, naturally arc-length-spaced by the
adaptive stepping → blended legacy tail) is resampled by cumulative arc length to exactly
`point_count` points (`np.interp` of x, y, radius, upper/lower contact points and
parameters against arc length), preserving `CamberData`'s existing array shapes.
`display_indices` reuses the existing arc-length-based `_display_indices` unchanged.
`valid` is `True` everywhere (the algorithm always produces *some* result, degrading
gracefully rather than failing); `fallback_used` is `True` only for stations resampled
from the blended legacy tail, giving it an honest meaning again.

## Error handling

The design has no "both solvers failed" case like today's code — the nose-refinement and
blend-to-legacy steps are explicit, unconditional fallbacks, so the output is always a
complete, continuous curve. Newton corrector non-convergence is an expected, handled
control-flow path (triggers step-shrink then march termination), not an error.

## Testing

New `tests/test_camber_medial_axis.py`, following the existing `tests/test_*.py` style
(no Qt/GUI dependencies needed — `ContourAnalysis.getCurvature`/`getLeRadius` are static
methods, and `SplineData` can be built directly via `scipy.interpolate.splprep`/`splev`,
same as the diagnostic repro used during investigation):

- **Tangency accuracy**: for `naca0012.dat` (symmetric), `naca2315.dat` (cambered), and
  `MW-166-39-44-43.dat` (heavily cambered), assert every reported circle's radius matches
  the true nearest-surface distance — found by dense independent sampling of the upper and
  lower branches, not reusing any of the traced algorithm's own bookkeeping — within a
  tight tolerance (e.g. 1e-4 chord) on both sides.
- **Smoothness**: assert no large jump between consecutive accepted circles (center step
  and radius step both bounded relative to local step size) across the continuation
  region.
- **Nose continuity**: assert the first traced circle's center is close to (not
  necessarily identical to) `getLeRadius`'s `(xc, yc)`, within a small tolerance, and that
  `getLeRadius`'s return value is completely unaffected by calling the tracer (regression
  guard for "keep that point still").
- **Graceful degradation**: a pathological/degenerate input (e.g. a nearly-straight strip)
  still returns a complete `CamberData` with `valid` all `True`, never raises.
