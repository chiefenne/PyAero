"""Post-smoothing stage for the Structured engine (phase 5).

A smoother is an optional pass over an already-filled ``(nj, ni, 2)`` rows
array, independent of which topology, tunnel shape, or volume algorithm
produced it. It never touches the frozen rows (the wall plus any ortho
layers, which carry the framework's exact-spacing and exact-normal
invariants) or the outer row (the prescribed farfield boundary); side
columns stay fixed too, unless the frame is periodic (an O-grid seam,
which is interior and allowed to relax exactly like it does in
``GridElliptic``).

Three methods:

- ``laplacian``: under-relaxed 4-neighbor averaging. Cheap relief for
  local kinks (e.g. a TFI wedge at a sharp TE) without the cost of a full
  elliptic solve.
- ``elliptic``: delegates to ``GridElliptic.solve`` on the sub-grid from
  the last frozen row (acting as its Dirichlet wall) to the outer row —
  the same solver phase 2 uses to build a grid, reused here to relax an
  existing one, exactly as the design spec anticipated.
- ``angle_based``: Zhou-Shimada-style relaxation. For each unfrozen node
  P with neighbors E, N, W, S, the locus of points from which a segment
  between two given points subtends a right angle is the circle with
  that segment as diameter (Thales' theorem). For each of the four
  neighbor pairs around P — (E,N), (N,W), (W,S), (S,E) — the point on
  that pair's Thales circle nearest to P is exactly the position that
  would make P's edges meet those two neighbors at 90 degrees. P is
  relaxed toward the average of the four projections.

Quality is ``min(abs(cell_jacobian))`` over the whole grid. If a method
would leave the grid worse than it started, ``smooth`` returns the
original rows unchanged (logged) — smoothers are guaranteed to never
degrade the mesh, not merely expected to.
"""
from __future__ import annotations

import logging

import numpy as np

import GridElliptic
from StructuredCore import cell_jacobians

logger = logging.getLogger(__name__)

_METHODS = ('laplacian', 'elliptic', 'angle_based')
_THALES_EPS = 1.0e-12


def _quality(rows: np.ndarray) -> float:
    return float(np.min(np.abs(cell_jacobians(rows))))


def _neighbors(rows: np.ndarray, periodic: bool, frozen_rows: int):
    """North/south/east/west neighbor arrays and the point array itself,
    aligned over the unfrozen interior (rows frozen_rows .. nj-2,
    columns 1..ni-2, or all periodic columns for an O-grid seam)."""
    interior = rows[frozen_rows:-1]
    north = rows[frozen_rows + 1:]
    south = rows[frozen_rows - 1:-2]
    if periodic:
        unique = interior[:, :-1]
        point = unique
        east = np.roll(unique, -1, axis=1)
        west = np.roll(unique, 1, axis=1)
        north = north[:, :-1]
        south = south[:, :-1]
    else:
        point = interior[:, 1:-1]
        east = interior[:, 2:]
        west = interior[:, :-2]
        north = north[:, 1:-1]
        south = south[:, 1:-1]
    return point, north, south, east, west


def _write_back(rows: np.ndarray, updated: np.ndarray, periodic: bool,
                frozen_rows: int) -> None:
    if periodic:
        rows[frozen_rows:-1, :-1] = updated
        rows[:, -1] = rows[:, 0]
    else:
        rows[frozen_rows:-1, 1:-1] = updated


def _laplacian_pass(rows: np.ndarray, periodic: bool, frozen_rows: int,
                    relaxation: float) -> None:
    point, north, south, east, west = _neighbors(rows, periodic,
                                                  frozen_rows)
    candidate = 0.25 * (north + south + east + west)
    updated = (1.0 - relaxation) * point + relaxation * candidate
    _write_back(rows, updated, periodic, frozen_rows)


def _thales_projection(point: np.ndarray, a: np.ndarray,
                       b: np.ndarray) -> np.ndarray:
    mid = 0.5 * (a + b)
    radius = 0.5 * np.linalg.norm(a - b, axis=-1)
    offset = point - mid
    length = np.linalg.norm(offset, axis=-1)
    safe = length > _THALES_EPS
    unit = np.divide(offset, length[..., None], out=np.zeros_like(offset),
                     where=safe[..., None])
    projected = mid + radius[..., None] * unit
    return np.where(safe[..., None], projected, point)


def _angle_based_pass(rows: np.ndarray, periodic: bool, frozen_rows: int,
                      relaxation: float) -> None:
    point, north, south, east, west = _neighbors(rows, periodic,
                                                  frozen_rows)
    targets = (
        _thales_projection(point, east, north) +
        _thales_projection(point, north, west) +
        _thales_projection(point, west, south) +
        _thales_projection(point, south, east)
    ) / 4.0
    updated = (1.0 - relaxation) * point + relaxation * targets
    _write_back(rows, updated, periodic, frozen_rows)


def smooth(rows: np.ndarray, *, method: str, iterations: int = 10,
          periodic: bool = False, frozen_rows: int = 1,
          relaxation: float = 0.5) -> tuple[np.ndarray, dict]:
    if method not in _METHODS:
        raise ValueError(f'Unknown smoother method: {method!r}.')
    if frozen_rows < 1:
        raise ValueError('frozen_rows must be at least 1 (the wall row).')

    original = np.array(rows, dtype=float, copy=True)
    quality_before = _quality(original)
    nj = original.shape[0]

    if frozen_rows >= nj - 1 or iterations <= 0:
        return original, {'quality_before': quality_before,
                          'quality_after': quality_before}

    if method == 'elliptic':
        sub_grid = original[frozen_rows - 1:]
        solved, _info = GridElliptic.solve(sub_grid, periodic=periodic,
                                           iterations=iterations,
                                           relaxation=relaxation)
        candidate = original.copy()
        candidate[frozen_rows - 1:] = solved
    else:
        candidate = original.copy()
        pass_fn = (_laplacian_pass if method == 'laplacian'
                  else _angle_based_pass)
        for _ in range(iterations):
            pass_fn(candidate, periodic, frozen_rows, relaxation)

    quality_after = _quality(candidate)
    if quality_after < quality_before:
        logger.warning(
            'Smoother %r would degrade grid quality (%.3e -> %.3e); '
            'returning the unsmoothed grid.',
            method, quality_before, quality_after)
        return original, {'quality_before': quality_before,
                          'quality_after': quality_before}

    return candidate, {'quality_before': quality_before,
                       'quality_after': quality_after}
