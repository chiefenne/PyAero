"""Exact-normal near-wall block for the Structured engine.

Layer k sits at ``P(t_i) + h_k * n(t_i)`` where ``n`` is the exact analytic
spline normal on contour nodes (finite differences elsewhere, e.g. wake
cuts). At tangent-discontinuous corners (sharp TE, blunt base corners,
contour/wake junctions) normals are blended toward the corner bisector in a
small window; outside those windows perpendicularity is exact. Requested
heights are capped against the local concave radius of curvature — the
block thins with a logged warning instead of folding.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


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


def wall_normals(wall: np.ndarray, corner_indices,
                 spline_data=None, contour_slice=None,
                 closed: bool = False, blend_width: int = 4) -> np.ndarray:
    wall = np.asarray(wall, dtype=float)
    normals = _rotate_to_normals(_finite_difference_tangents(wall, closed))

    if spline_data is not None and contour_slice is not None:
        start, stop = contour_slice
        parameters = np.asarray(spline_data.sample_parameters, dtype=float)
        if stop - start == len(parameters):
            exact = np.column_stack(
                spline_data.evaluate(parameters, der=1))
            normals[start:stop] = _rotate_to_normals(exact)

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


def max_offset_heights(wall: np.ndarray, normals: np.ndarray,
                       spline_data=None, contour_slice=None,
                       safety: float = 0.5) -> np.ndarray:
    """Per-node offset cap: safety * radius of curvature on the concave
    side (curvature center along the offset direction), infinite elsewhere.
    """
    wall = np.asarray(wall, dtype=float)
    first = np.gradient(wall, axis=0)
    second = np.gradient(first, axis=0)
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


def _smooth_profile(values: np.ndarray, passes: int = 5,
                    window: int = 5) -> np.ndarray:
    kernel = np.ones(window) / window
    padded = values.copy()
    for _ in range(passes):
        padded = np.convolve(
            np.pad(padded, window // 2, mode='edge'), kernel, mode='valid')
    return padded


def build_layers(wall: np.ndarray, normals: np.ndarray, layer_count: int,
                 first_height: float, growth: float,
                 max_heights=None) -> np.ndarray:
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
            scale = _smooth_profile(cap_scale)
            scale = np.minimum(scale, cap_scale)
            logger.warning(
                'Ortho block thinned at %d of %d wall nodes to respect the '
                'local radius of curvature.',
                int(np.sum(cap_scale < 1.0)), len(wall))

    offsets = heights[:, None, None] * (scale[:, None] * normals)[None, :, :]
    rows = np.concatenate((wall[None, :, :], wall[None, :, :] + offsets))
    rows[0] = wall
    return rows
