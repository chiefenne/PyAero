"""Transfinite interpolation (standard + Hermite) on a GridFrame.

Method
------
- Parameters: ``eta_j`` is the mean of the two sides' normalized cumulative
  arclength (this carries the geometric first-layer clustering into the
  interior); ``xi[j, i] = (1 - eta_j) * xi_wall[i] + eta_j * xi_outer[i]``
  with ``xi_wall`` / ``xi_outer`` the normalized cumulative arclengths of
  wall and outer.
- Standard variant: Boolean-sum Coons patch over the four frame boundaries.
- Hermite variant: transverse cubic Hermite blending with prescribed
  end derivatives for tangent control at wall and outer boundary
  (``TunnelBoundaryControl.angle_mode``: 'orthogonal' forces mesh lines
  perpendicular onto the tunnel boundary, 'free' uses the wall->outer
  secant), plus a linear side-conformity correction.
- All four boundary rows/columns of the result are the frame arrays
  verbatim (copied, never recomputed).
"""
from __future__ import annotations

import numpy as np

from StructuredCore import GridFrame, TunnelBoundaryControl


def _normalized_arclength(points: np.ndarray) -> np.ndarray:
    deltas = np.diff(points, axis=0)
    cumulative = np.concatenate(
        ([0.0], np.cumsum(np.hypot(deltas[:, 0], deltas[:, 1]))))
    total = cumulative[-1]
    if total <= 0.0:
        return np.linspace(0.0, 1.0, len(points))
    return cumulative / total


def _unit_normals(points: np.ndarray) -> np.ndarray:
    tangents = np.gradient(points, axis=0)
    lengths = np.linalg.norm(tangents, axis=1)
    lengths[lengths == 0.0] = 1.0
    return np.column_stack((tangents[:, 1], -tangents[:, 0])) / lengths[:, None]


def fill(frame: GridFrame, variant: str = 'standard',
         boundary_control: TunnelBoundaryControl | None = None) -> np.ndarray:
    if variant not in ('standard', 'hermite'):
        raise ValueError(f'Unknown TFI variant: {variant!r}.')
    control = boundary_control or TunnelBoundaryControl()

    wall = np.asarray(frame.wall, dtype=float)
    outer = np.asarray(frame.outer, dtype=float)
    side_start = np.asarray(frame.side_start, dtype=float)
    side_end = np.asarray(frame.side_end, dtype=float)

    eta = 0.5 * (_normalized_arclength(side_start) +
                 _normalized_arclength(side_end))            # (nj,)
    xi_wall = _normalized_arclength(wall)                    # (ni,)
    xi_outer = _normalized_arclength(outer)
    xi = ((1.0 - eta)[:, None] * xi_wall[None, :] +
          eta[:, None] * xi_outer[None, :])                  # (nj, ni)

    eta_grid = eta[:, None, None]
    xi_grid = xi[..., None]

    if variant == 'standard':
        rows = (
            (1.0 - eta_grid) * wall[None, :, :] +
            eta_grid * outer[None, :, :] +
            (1.0 - xi_grid) * side_start[:, None, :] +
            xi_grid * side_end[:, None, :] -
            (
                (1.0 - xi_grid) * (1.0 - eta_grid) * wall[0] +
                (1.0 - xi_grid) * eta_grid * outer[0] +
                xi_grid * (1.0 - eta_grid) * wall[-1] +
                xi_grid * eta_grid * outer[-1]
            )
        )
    else:
        span = outer - wall                                  # (ni, 2)
        lengths = np.linalg.norm(span, axis=1)
        lengths[lengths == 0.0] = 1.0

        wall_normals = _unit_normals(wall)
        flip = np.sum(wall_normals * span, axis=1) < 0.0
        wall_normals[flip] = -wall_normals[flip]
        derivative_wall = lengths[:, None] * wall_normals

        if control.angle_mode == 'orthogonal':
            outer_normals = _unit_normals(outer)
            flip = np.sum(outer_normals * span, axis=1) < 0.0
            outer_normals[flip] = -outer_normals[flip]
            derivative_outer = lengths[:, None] * outer_normals
        else:
            derivative_outer = span

        h00 = 2.0 * eta ** 3 - 3.0 * eta ** 2 + 1.0
        h01 = -2.0 * eta ** 3 + 3.0 * eta ** 2
        h10 = eta ** 3 - 2.0 * eta ** 2 + eta
        h11 = eta ** 3 - eta ** 2
        rows = (
            h00[:, None, None] * wall[None, :, :] +
            h01[:, None, None] * outer[None, :, :] +
            h10[:, None, None] * derivative_wall[None, :, :] +
            h11[:, None, None] * derivative_outer[None, :, :]
        )
        # linear side-conformity correction
        rows += (1.0 - xi_wall)[None, :, None] * \
            (side_start[:, None, :] - rows[:, :1, :])
        rows += xi_wall[None, :, None] * \
            (side_end[:, None, :] - rows[:, -1:, :])

    rows[0] = wall
    rows[-1] = outer
    rows[:, 0] = side_start
    rows[:, -1] = side_end
    return rows
