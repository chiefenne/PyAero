"""Shared dataclasses and distribution utilities for the Structured engine.

See docs/superpowers/specs/2026-08-22-structured-grid-framework-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class TunnelBoundaryControl:
    distribution: str = 'uniform'      # 'uniform' | 'clustered'
    clustering_ratio: float = 1.0      # last/first spacing when clustered
    angle_mode: str = 'free'           # 'free' | 'orthogonal'


@dataclass(slots=True)
class StructuredMeshSettings:
    topology: str = 'c'                # 'c' | 'o'
    tunnel_shape: str = 'legacy'       # 'legacy' | 'circular'
    tunnel_height: float = 3.5         # legacy half-height / circular radius
    wake_length: float = 7.0           # TE to outlet (C-mesh only)
    algorithm: str = 'tfi'             # 'tfi' | 'elliptic'
    tfi_variant: str = 'standard'      # 'standard' | 'hermite'
    elliptic_iterations: int = 150
    elliptic_relaxation: float = 0.8
    normal_divisions: int = 60         # total wall->outer cells (incl. ortho)
    first_layer_thickness: float = 0.002
    wake_points: int = 60              # nodes along each wake cut (C-mesh)
    ortho_layers: int = 0              # 0 = ortho block off
    ortho_growth: float = 1.15
    boundary_control: TunnelBoundaryControl = field(
        default_factory=TunnelBoundaryControl
    )


@dataclass(slots=True)
class GridFrame:
    """Boundary frame a volume algorithm fills. All arrays are (n, 2) float.

    wall is row j=0, outer is row j=nj-1; side_start / side_end are the
    i=0 / i=ni-1 columns running wall -> outer. len(side_start) ==
    len(side_end) and side endpoints coincide with wall/outer endpoints.
    """
    wall: np.ndarray
    outer: np.ndarray
    side_start: np.ndarray
    side_end: np.ndarray
    kind: str                  # 'o' | 'c' | 'wake_strip'
    te_type: str               # 'sharp' | 'blunt'
    periodic: bool = False
    metadata: dict = field(default_factory=dict)


def contour_array(spline_data) -> np.ndarray:
    x, y = spline_data.coordinates
    return np.column_stack((np.asarray(x, float), np.asarray(y, float)))


def detect_te_type(contour: np.ndarray, tolerance: float = 1.0e-6) -> str:
    contour = np.asarray(contour, dtype=float)
    chord = float(np.ptp(contour[:, 0])) or 1.0
    gap = float(np.linalg.norm(contour[0] - contour[-1]))
    return 'sharp' if gap <= tolerance * chord else 'blunt'


def _growth_for_length(length: float, first_spacing: float,
                       divisions: int) -> float:
    """Solve sum_{k=0}^{divisions-1} first*g**k == length for g by bisection."""
    if divisions * first_spacing >= length:
        return 1.0
    low, high = 1.0 + 1.0e-12, 10.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        total = first_spacing * (mid ** divisions - 1.0) / (mid - 1.0)
        if total < length:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def geometric_distances(length: float, first_spacing: float,
                        count: int) -> np.ndarray:
    if count < 2:
        raise ValueError('geometric_distances needs count >= 2.')
    if first_spacing <= 0.0 or length <= 0.0:
        raise ValueError('length and first_spacing must be positive.')
    divisions = count - 1
    if divisions * first_spacing >= length:
        # First spacing too large to grow: fall back to uniform.
        return np.linspace(0.0, length, count)
    growth = _growth_for_length(length, first_spacing, divisions)
    steps = first_spacing * growth ** np.arange(divisions)
    distances = np.concatenate(([0.0], np.cumsum(steps)))
    distances *= length / distances[-1]
    return distances


def sample_te_base(p_from: np.ndarray, p_to: np.ndarray,
                   spacing: float) -> np.ndarray:
    p_from = np.asarray(p_from, dtype=float)
    p_to = np.asarray(p_to, dtype=float)
    gap = float(np.linalg.norm(p_to - p_from))
    if gap <= 0.0:
        raise ValueError('sample_te_base needs distinct endpoints.')
    divisions = max(2, int(round(gap / max(spacing, 1.0e-12))))
    fractions = np.linspace(0.0, 1.0, divisions + 1)[:, None]
    return p_from[None, :] * (1.0 - fractions) + p_to[None, :] * fractions


def polyline_cumulative(points: np.ndarray) -> np.ndarray:
    deltas = np.diff(points, axis=0)
    return np.concatenate(([0.0], np.cumsum(np.hypot(deltas[:, 0],
                                                     deltas[:, 1]))))


def sample_polyline_at(points: np.ndarray,
                       distances: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    cumulative = polyline_cumulative(points)
    distances = np.clip(distances, 0.0, cumulative[-1])
    x = np.interp(distances, cumulative, points[:, 0])
    y = np.interp(distances, cumulative, points[:, 1])
    return np.column_stack((x, y))


def cell_jacobians(rows: np.ndarray) -> np.ndarray:
    """Signed area of each quad cell of a (nj, ni, 2) structured array."""
    a = rows[:-1, :-1]
    b = rows[:-1, 1:]
    c = rows[1:, 1:]
    d = rows[1:, :-1]
    return 0.5 * (
        (a[..., 0] * b[..., 1] - b[..., 0] * a[..., 1]) +
        (b[..., 0] * c[..., 1] - c[..., 0] * b[..., 1]) +
        (c[..., 0] * d[..., 1] - d[..., 0] * c[..., 1]) +
        (d[..., 0] * a[..., 1] - a[..., 0] * d[..., 1])
    )


def distribute_on_polyline(points: np.ndarray, count: int,
                           distribution: str = 'uniform',
                           ratio: float = 1.0) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    length = polyline_cumulative(points)[-1]
    if distribution == 'uniform' or ratio == 1.0:
        distances = np.linspace(0.0, length, count)
    elif distribution == 'clustered':
        growth = ratio ** (1.0 / (count - 2))
        steps = growth ** np.arange(count - 1)
        distances = np.concatenate(([0.0], np.cumsum(steps)))
        distances *= length / distances[-1]
    else:
        raise ValueError(
            f'Unknown boundary distribution: {distribution!r}.')
    return sample_polyline_at(points, distances)
