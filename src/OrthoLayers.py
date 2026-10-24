"""Exact-normal near-wall block for the Structured engine.

Layer k sits at ``P(t_i) + h_k * n(t_i)`` where ``n`` is the exact analytic
spline normal on contour nodes (finite differences elsewhere, e.g. wake
cuts). At tangent-discontinuous corners (sharp TE, blunt base corners,
contour/wake junctions) normals are blended toward the corner bisector in a
small window; outside those windows perpendicularity is exact. On an open
(C-mesh) wall the window is an arclength proportional to the block height
(``CORNER_BLEND_FACTOR``): at the concave contour/wake junction offsets of
height H from both sides converge, and a fixed node count shrinks with the
contour spacing until the rows cross. Requested heights are capped against
the local concave radius of curvature — the block thins with a logged
warning instead of folding; the thinning profile is slope-limited
(``MAX_THINNING_SLOPE``) so a locally capped node cannot notch the rim.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Corner blend half-width on open walls, in multiples of the block height.
CORNER_BLEND_FACTOR = 2.0
# Max change of the (thinned) block height per unit wall arclength.
MAX_THINNING_SLOPE = 0.5


def _rotate_to_normals(tangents: np.ndarray) -> np.ndarray:
    lengths = np.linalg.norm(tangents, axis=1)
    lengths[lengths == 0.0] = 1.0
    return np.column_stack(
        (tangents[:, 1], -tangents[:, 0])) / lengths[:, None]


def _finite_difference_tangents(wall: np.ndarray,
                                closed: bool) -> np.ndarray:
    if closed:
        unique = wall[:-1]
        tangents = np.roll(unique, -1, axis=0) - np.roll(unique, 1, axis=0)
        return np.vstack((tangents, tangents[:1]))
    return np.gradient(wall, axis=0)


def _arclength(wall: np.ndarray) -> np.ndarray:
    return np.concatenate(
        ([0.0], np.cumsum(np.linalg.norm(np.diff(wall, axis=0), axis=1))))


def _blend_by_arclength(wall: np.ndarray, normals: np.ndarray,
                        corner: int, blend_length: float) -> None:
    """Rotate the normals within ``blend_length`` of ``corner`` (each side)
    from the window-start to the window-end direction, cosine-weighted in
    arclength, in place."""
    arclength = _arclength(wall)
    start = int(np.searchsorted(arclength, arclength[corner] - blend_length))
    start = max(start - 1, 0)
    stop = int(np.searchsorted(arclength, arclength[corner] + blend_length))
    stop = min(stop, len(wall) - 1)
    if stop - start < 2:
        return
    angle_start = np.arctan2(normals[start, 1], normals[start, 0])
    angle_stop = np.arctan2(normals[stop, 1], normals[stop, 0])
    turn = (angle_stop - angle_start + np.pi) % (2.0 * np.pi) - np.pi
    weight = ((arclength[start:stop + 1] - arclength[start]) /
              (arclength[stop] - arclength[start]))
    weight = 0.5 - 0.5 * np.cos(np.pi * weight)
    angle = angle_start + weight * turn
    normals[start:stop + 1] = np.column_stack((np.cos(angle), np.sin(angle)))


def wall_normals(wall: np.ndarray, corner_indices,
                 spline_data=None, contour_slice=None,
                 closed: bool = False, blend_width: int = 4,
                 blend_length: float | None = None) -> np.ndarray:
    """Unit wall normals; ``blend_length`` (open walls only) switches the
    corner blend from ``blend_width`` nodes to that arclength per side."""
    wall = np.asarray(wall, dtype=float)
    normals = _rotate_to_normals(_finite_difference_tangents(wall, closed))

    if spline_data is not None and contour_slice is not None:
        start, stop = contour_slice
        parameters = np.asarray(spline_data.sample_parameters, dtype=float)
        if stop - start == len(parameters):
            exact = np.column_stack(
                spline_data.evaluate(parameters, der=1))
            normals[start:stop] = _rotate_to_normals(exact)

    if blend_length is not None and not closed:
        for corner in corner_indices:
            _blend_by_arclength(wall, normals, corner, blend_length)
        return normals

    count = len(wall)
    unique_count = count - 1 if closed else count
    for corner in corner_indices:
        window = np.arange(corner - blend_width, corner + blend_width + 1)
        if closed:
            window = np.mod(window, unique_count)
        else:
            window = window[(window >= 0) & (window < count)]
        for _ in range(4):
            blended = normals.copy()
            for index in window:
                prev_index = (index - 1) % unique_count if closed \
                    else max(index - 1, 0)
                next_index = (index + 1) % unique_count if closed \
                    else min(index + 1, count - 1)
                vector = (normals[prev_index] + 2.0 * normals[index] +
                          normals[next_index])
                norm = np.linalg.norm(vector)
                if norm > 0.0:
                    blended[index] = vector / norm
            normals = blended
    if closed:
        normals[-1] = normals[0]
    return normals


def layer_heights(layer_count: int, first_height: float,
                  growth: float) -> np.ndarray:
    if layer_count < 1:
        raise ValueError('layer_heights needs at least one layer.')
    if first_height <= 0.0 or growth < 1.0:
        raise ValueError('first_height must be positive and growth >= 1.')
    steps = first_height * growth ** np.arange(layer_count)
    return np.cumsum(steps)


def _piecewise_gradients(wall: np.ndarray, corner_indices):
    """First/second finite differences computed separately on each piece
    between corners, so no stencil straddles a tangent discontinuity."""
    first = np.zeros_like(wall)
    second = np.zeros_like(wall)
    bounds = sorted({0, len(wall) - 1, *[int(c) for c in corner_indices]})
    for start, stop in zip(bounds[:-1], bounds[1:]):
        piece = wall[start:stop + 1]
        if len(piece) < 3:
            first[start:stop + 1] = piece[-1] - piece[0]
            continue
        piece_first = np.gradient(piece, axis=0)
        first[start:stop + 1] = piece_first
        second[start:stop + 1] = np.gradient(piece_first, axis=0)
    return first, second


def max_offset_heights(wall: np.ndarray, normals: np.ndarray,
                       spline_data=None, contour_slice=None,
                       safety: float = 0.5,
                       corner_indices=()) -> np.ndarray:
    """Per-node offset cap: safety * radius of curvature on the concave
    side (curvature center along the offset direction), infinite elsewhere.
    Finite differences never span ``corner_indices``.
    """
    wall = np.asarray(wall, dtype=float)
    first, second = _piecewise_gradients(wall, corner_indices)
    if spline_data is not None and contour_slice is not None:
        start, stop = contour_slice
        parameters = np.asarray(spline_data.sample_parameters, dtype=float)
        if stop - start == len(parameters):
            first[start:stop] = np.column_stack(
                spline_data.evaluate(parameters, der=1))
            second[start:stop] = np.column_stack(
                spline_data.evaluate(parameters, der=2))

    cross = first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]
    speed_sq = np.sum(first ** 2, axis=1)
    denominator = np.maximum(speed_sq, 1.0e-300) ** 1.5
    curvature = np.abs(cross) / denominator

    # left normal = rotate tangent by +90 deg: (-t_y, t_x); the curvature
    # center lies along +left when cross > 0, along -left otherwise
    lengths = np.sqrt(np.maximum(speed_sq, 1.0e-300))
    left = np.column_stack((-first[:, 1], first[:, 0])) / lengths[:, None]
    center_direction = np.sign(cross)[:, None] * left

    concave = np.sum(np.asarray(normals) * center_direction, axis=1) > 0.0
    caps = np.full(len(wall), np.inf)
    curved = curvature > 1.0e-12
    mask = concave & curved
    caps[mask] = safety / curvature[mask]
    return caps


def _slope_limited(caps: np.ndarray, arclength: np.ndarray,
                   closed: bool) -> np.ndarray:
    """Largest profile <= caps whose slope in arclength stays within
    MAX_THINNING_SLOPE (forward + backward sweep; twice round if closed)."""
    allowed = caps.copy()
    count = len(allowed)
    steps = np.diff(arclength) * MAX_THINNING_SLOPE
    for _ in range(2 if closed else 1):
        for index in range(1, count):
            allowed[index] = min(allowed[index],
                                 allowed[index - 1] + steps[index - 1])
        for index in range(count - 2, -1, -1):
            allowed[index] = min(allowed[index],
                                 allowed[index + 1] + steps[index])
        if closed:
            shared = min(allowed[0], allowed[-1])
            allowed[0] = allowed[-1] = shared
    return allowed


def build_layers(wall: np.ndarray, normals: np.ndarray, layer_count: int,
                 first_height: float, growth: float,
                 max_heights=None, closed: bool = False) -> np.ndarray:
    wall = np.asarray(wall, dtype=float)
    normals = np.asarray(normals, dtype=float)
    heights = layer_heights(layer_count, first_height, growth)
    total = heights[-1]

    scale = np.ones(len(wall))
    if max_heights is not None:
        caps = np.asarray(max_heights, dtype=float)
        with np.errstate(invalid='ignore'):
            cap_scale = np.where(np.isfinite(caps),
                                 np.minimum(caps / total, 1.0), 1.0)
        if np.any(cap_scale < 1.0):
            scale = _slope_limited(cap_scale * total, _arclength(wall),
                                   closed) / total
            logger.warning(
                'Ortho block thinned at %d of %d wall nodes to respect the '
                'local radius of curvature.',
                int(np.sum(cap_scale < 1.0)), len(wall))

    offsets = heights[:, None, None] * (scale[:, None] * normals)[None, :, :]
    rows = np.concatenate((wall[None, :, :], wall[None, :, :] + offsets))
    rows[0] = wall
    return rows
