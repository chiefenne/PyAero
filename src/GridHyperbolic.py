"""Hyperbolic grid generation for the Structured engine (phase 3).

Simplified Steger–Chan-style front marching with an adaptive hand-off:

1. Layers advance along smoothed front normals by a per-column geometric
   height schedule. An implicit variable-coefficient smoothing solve
   ``(I - d/ds eps d/ds) r = r_predicted`` along the layer plays the role
   of the scheme's dissipation; ``eps`` scales with (marching step /
   local tangential spacing)^2, so crossings are dissolved exactly where
   columns are fine relative to the step (trailing edges) without
   disturbing coarsely spaced regions. Cyclic solve for periodic O-grids;
   C-mesh front ends are pinned to the outlet plane every step.
2. The march continues while every new cell band stays positively
   oriented, up to ``fraction_cap`` of the wall-to-farfield height.
   Hyperbolic marching cannot terminate on a prescribed boundary (the
   design spec's acknowledged tension), so the remaining height is filled
   by a TFI boundary-value solve from the marched front onto the exact
   outer distribution — the same composition the ortho block uses.
3. If the combined grid still contains inverted cells, the hand-off
   point backs off geometrically; the final fallback is a pure TFI fill
   (logged) — the algorithm degrades gracefully instead of returning a
   folded grid.

The full linearized Steger–Chan system (area source + orthogonality
relation) is deliberately not implemented; the predictor/implicit-
smoothing pair is its standard lightweight surrogate at this grid scale.
"""
from __future__ import annotations

import logging

import numpy as np
from scipy import linalg

import GridTFI
from StructuredCore import GridFrame, cell_jacobians, geometric_distances
from StructuredTopologies import side_segment

logger = logging.getLogger(__name__)

_NORMAL_SMOOTHING_PASSES = 3
_EPS_MAX = 100.0


def _rotate(tangents: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(tangents, axis=1)
    lengths[lengths == 0.0] = 1.0
    return np.column_stack(
        (tangents[:, 1], -tangents[:, 0])) / lengths[:, None]


def _front_normals(front: np.ndarray, reference: np.ndarray,
                   periodic: bool) -> np.ndarray:
    if periodic:
        unique = front[:-1]
        tangents = np.roll(unique, -1, axis=0) - np.roll(unique, 1, axis=0)
        tangents = np.vstack((tangents, tangents[:1]))
    else:
        tangents = np.gradient(front, axis=0)
    normals = _rotate(tangents)
    flip = np.sum(normals * reference, axis=1) < 0.0
    normals[flip] = -normals[flip]
    return normals


def _smooth_normals(normals: np.ndarray, periodic: bool,
                    passes: int = _NORMAL_SMOOTHING_PASSES) -> np.ndarray:
    smoothed = normals.copy()
    for _ in range(passes):
        if periodic:
            unique = smoothed[:-1]
            averaged = (0.25 * np.roll(unique, 1, axis=0) +
                        0.5 * unique +
                        0.25 * np.roll(unique, -1, axis=0))
            smoothed = np.vstack((averaged, averaged[:1]))
        else:
            averaged = smoothed.copy()
            averaged[1:-1] = (0.25 * smoothed[:-2] + 0.5 * smoothed[1:-1] +
                              0.25 * smoothed[2:])
            smoothed = averaged
        lengths = np.linalg.norm(smoothed, axis=1)
        lengths[lengths == 0.0] = 1.0
        smoothed /= lengths[:, None]
    return smoothed


def _solve_banded(lower: np.ndarray, diagonal: np.ndarray,
                  upper: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Tridiagonal solve; lower[0] and upper[-1] are ignored."""
    m = len(diagonal)
    ab = np.zeros((3, m))
    ab[0, 1:] = upper[:-1]
    ab[1] = diagonal
    ab[2, :-1] = lower[1:]
    return linalg.solve_banded((1, 1), ab, rhs)


def _cyclic_solve(lower: np.ndarray, diagonal: np.ndarray,
                  upper: np.ndarray, rhs: np.ndarray,
                  corner_upper: float, corner_lower: float) -> np.ndarray:
    """Cyclic tridiagonal solve via Sherman–Morrison.

    corner_upper is A[0, m-1], corner_lower is A[m-1, 0].
    """
    m = len(diagonal)
    gamma = -diagonal[0]
    modified = diagonal.copy()
    modified[0] -= gamma
    modified[-1] -= corner_upper * corner_lower / gamma
    x = _solve_banded(lower, modified, upper, rhs)
    u = np.zeros(m)
    u[0] = gamma
    u[-1] = corner_lower
    z = _solve_banded(lower, modified, upper, u)
    factor = (x[0] + corner_upper * x[-1] / gamma) / \
        (1.0 + z[0] + corner_upper * z[-1] / gamma)
    if x.ndim == 2:
        return x - factor[None, :] * z[:, None]
    return x - factor * z


def _metric_smooth(values: np.ndarray, step: np.ndarray, strength: float,
                   periodic: bool) -> np.ndarray:
    """Implicit metric-aware smoothing along the layer."""
    if strength <= 0.0:
        return values
    if periodic:
        unique = values[:-1]
        step_unique = step[:-1]
        spacing = np.linalg.norm(
            np.roll(unique, -1, axis=0) - unique, axis=1)
        eps_half = np.minimum(
            strength * (0.5 * (step_unique + np.roll(step_unique, -1)) /
                        np.maximum(spacing, 1.0e-12)) ** 2,
            _EPS_MAX)
        eps_minus = np.roll(eps_half, 1)
        lower = -eps_minus
        upper = -eps_half
        diagonal = 1.0 + eps_minus + eps_half
        solution = _cyclic_solve(lower, diagonal, upper, unique,
                                 corner_upper=-eps_half[-1],
                                 corner_lower=-eps_half[-1])
        return np.vstack((solution, solution[:1]))

    spacing = np.linalg.norm(values[1:] - values[:-1], axis=1)
    step_half = 0.5 * (step[1:] + step[:-1])
    eps_half = np.minimum(
        strength * (step_half / np.maximum(spacing, 1.0e-12)) ** 2,
        _EPS_MAX)
    m = len(values)
    lower = np.zeros(m)
    upper = np.zeros(m)
    diagonal = np.ones(m)
    lower[1:-1] = -eps_half[:-1]
    upper[1:-1] = -eps_half[1:]
    diagonal[1:-1] = 1.0 + eps_half[:-1] + eps_half[1:]
    return _solve_banded(lower, diagonal, upper, values)


def march(frame: GridFrame, *, normals: np.ndarray, first_spacing: float,
          fraction_cap: float = 0.5,
          smoothing: float = 1.0) -> np.ndarray:
    wall = np.asarray(frame.wall, dtype=float)
    outer = np.asarray(frame.outer, dtype=float)
    nj = len(frame.side_start)
    periodic = frame.periodic
    x_outlet = frame.metadata.get('x_outlet')

    lengths = np.linalg.norm(outer - wall, axis=1)
    mean_length = float(np.mean(lengths))
    fractions = geometric_distances(mean_length, first_spacing,
                                    nj) / mean_length
    heights = fractions[:, None] * lengths[None, :]
    steps = np.diff(heights, axis=0)

    marched = [wall.copy()]
    front = wall.copy()
    reference = np.asarray(normals, dtype=float)
    target_sign = None

    for layer in range(1, nj - 2):
        if fractions[layer] > fraction_cap:
            break
        smoothed = _smooth_normals(reference, periodic)
        step = steps[layer - 1]
        predicted = front + step[:, None] * smoothed
        predicted = _metric_smooth(predicted, step, smoothing, periodic)
        if not periodic and x_outlet is not None:
            predicted[0, 0] = x_outlet
            predicted[-1, 0] = x_outlet
        if periodic:
            predicted[-1] = predicted[0]
        band = cell_jacobians(np.stack((front, predicted)))
        if target_sign is None:
            target_sign = np.sign(np.median(band))
        if np.any(np.sign(band) != target_sign):
            break
        marched.append(predicted)
        reference = _front_normals(predicted, reference, periodic)
        front = predicted

    def assemble(marched_layers: int) -> np.ndarray:
        hand_off = marched[marched_layers]
        step_index = min(marched_layers, len(steps) - 1)
        next_spacing = float(np.mean(steps[step_index]))
        count = nj - marched_layers
        start = side_segment(hand_off[0], outer[0], next_spacing, count)
        end = start.copy() if periodic else side_segment(
            hand_off[-1], outer[-1], next_spacing, count)
        reduced = GridFrame(
            wall=hand_off, outer=outer, side_start=start, side_end=end,
            kind=frame.kind, te_type=frame.te_type, periodic=periodic,
            metadata=dict(frame.metadata),
        )
        outer_rows = GridTFI.fill(reduced)
        return np.vstack((np.array(marched[:marched_layers + 1]),
                          outer_rows[1:]))

    marched_layers = len(marched) - 1
    while marched_layers >= 2:
        rows = assemble(marched_layers)
        jacobians = cell_jacobians(rows)
        if np.all(jacobians > 0.0) or np.all(jacobians < 0.0):
            logger.info(
                'Hyperbolic march: %d of %d layers marched, remainder '
                'filled algebraically.', marched_layers, nj - 1)
            return rows
        marched_layers = int(0.75 * marched_layers)

    logger.warning(
        'Hyperbolic march could not produce a valid grid for this frame; '
        'falling back to a pure TFI fill.')
    return GridTFI.fill(frame)
