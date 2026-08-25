"""Elliptic grid solver for the Structured engine (phase 2).

Winslow/TTM equations with Thomas–Middlecoff control functions, solved by
an under-relaxed Jacobi sweep on a (nj, ni, 2) rows array (eta = axis 0,
xi = axis 1). The control functions are computed from the boundary point
distributions, which makes a grid whose spacing already matches its
boundaries (e.g. the geometrically clustered TFI initial grid on a
rectangle) a fixed point — pure Winslow would uniformize it and destroy
the first-layer clustering.

Periodic xi (O-grids) treats the seam column as interior: the seam
relaxes, and both duplicate columns stay welded. Near-wall rows are
anchored to the initial grid (releasing quadratically over
``wall_anchor_rows``) because harmonic maps otherwise invert the first
cell at convex wall corners (TE wedge, blunt base corners).

Outer-boundary orthogonality is a simplified Sorenson-style forcing: the
row next to the outer boundary is nudged toward the foot of the local
boundary normal each sweep. The full P,Q source-term iteration is
deliberately not implemented at this grid scale.

``solve`` takes an initial grid and never builds one — the same entry
point doubles as the elliptic smoother in phase 5.
"""
from __future__ import annotations

import numpy as np

_EPS = 1.0e-12
_CONTROL_CLIP = 1.5


def _phi_along_row(row: np.ndarray, periodic: bool) -> np.ndarray:
    """Thomas–Middlecoff xi-control on one boundary row."""
    if periodic:
        forward = np.roll(row, -1, axis=0)
        backward = np.roll(row, 1, axis=0)
        tangent = 0.5 * (forward - backward)
        second = forward - 2.0 * row + backward
    else:
        tangent = 0.5 * (row[2:] - row[:-2])
        second = row[2:] - 2.0 * row[1:-1] + row[:-2]
    numerator = np.sum(tangent * second, axis=-1)
    denominator = np.sum(tangent * tangent, axis=-1) + _EPS
    return np.clip(-numerator / denominator, -_CONTROL_CLIP, _CONTROL_CLIP)


def _psi_along_column(column: np.ndarray) -> np.ndarray:
    """Thomas–Middlecoff eta-control on one side column (interior rows)."""
    tangent = 0.5 * (column[2:] - column[:-2])
    second = column[2:] - 2.0 * column[1:-1] + column[:-2]
    numerator = np.sum(tangent * second, axis=-1)
    denominator = np.sum(tangent * tangent, axis=-1) + _EPS
    return np.clip(-numerator / denominator, -_CONTROL_CLIP, _CONTROL_CLIP)


def _outer_orthogonality_step(rows: np.ndarray, periodic: bool,
                              ortho_relaxation: float) -> None:
    outer = rows[-1]
    if periodic:
        forward = np.roll(outer[:-1], -1, axis=0)
        backward = np.roll(outer[:-1], 1, axis=0)
        tangent = np.empty_like(outer)
        tangent[:-1] = 0.5 * (forward - backward)
        tangent[-1] = tangent[0]
    else:
        tangent = np.gradient(outer, axis=0)
    lengths = np.linalg.norm(tangent, axis=1)
    lengths[lengths == 0.0] = 1.0
    normal = np.column_stack((tangent[:, 1], -tangent[:, 0])) / lengths[:, None]
    inward = rows[-2] - outer
    flip = np.sum(normal * inward, axis=1) < 0.0
    normal[flip] = -normal[flip]
    distance = np.linalg.norm(inward, axis=1)
    target = outer + distance[:, None] * normal
    rows[-2] = ((1.0 - ortho_relaxation) * rows[-2] +
                ortho_relaxation * target)
    if periodic:
        rows[-2, -1] = rows[-2, 0]


def solve(rows: np.ndarray, *, periodic: bool = False,
          iterations: int = 100, relaxation: float = 0.8,
          tolerance: float = 1.0e-8, control: str = 'thomas_middlecoff',
          outer_orthogonal: bool = False,
          ortho_relaxation: float = 0.3,
          wall_anchor_rows: int = 4) -> tuple[np.ndarray, dict]:
    if control not in ('thomas_middlecoff', 'none'):
        raise ValueError(f'Unknown elliptic control: {control!r}.')
    rows = np.array(rows, dtype=float, copy=True)
    nj, ni = rows.shape[:2]
    if nj < 3 or ni < 3 or iterations <= 0:
        return rows, {'iterations': 0, 'residual': 0.0, 'converged': True}

    eta_fraction = (np.arange(1, nj - 1) / (nj - 1))[:, None]

    # Control functions are frozen from the initial grid (standard TTM
    # practice): the boundary rows are Dirichlet anyway, and the periodic
    # seam column must not feed back into its own control as it relaxes.
    if control == 'thomas_middlecoff':
        phi_wall = _phi_along_row(rows[0, :-1] if periodic
                                  else rows[0], periodic)
        phi_outer = _phi_along_row(rows[-1, :-1] if periodic
                                   else rows[-1], periodic)
        phi = ((1.0 - eta_fraction) * phi_wall[None, :] +
               eta_fraction * phi_outer[None, :])
        interior_columns = (ni - 1) if periodic else (ni - 2)
        if periodic:
            psi_profile = _psi_along_column(rows[:, 0])
            psi = np.repeat(psi_profile[:, None], interior_columns, axis=1)
        else:
            xi_fraction = (np.arange(1, ni - 1) / (ni - 1))[None, :]
            psi_start = _psi_along_column(rows[:, 0])
            psi_end = _psi_along_column(rows[:, -1])
            psi = ((1.0 - xi_fraction) * psi_start[:, None] +
                   xi_fraction * psi_end[:, None])
    else:
        phi = 0.0
        psi = 0.0
    phi3 = np.asarray(phi)[..., None] if np.ndim(phi) else 0.0
    psi3 = np.asarray(psi)[..., None] if np.ndim(psi) else 0.0

    # Harmonic maps squeeze the first cell at convex wall corners (sharp
    # or reflexed TE wedge, blunt base corners) until it inverts. Anchor
    # the near-wall rows to the initial grid — whose near-wall structure
    # comes from the clustering/ortho construction and is already good —
    # with a weight that releases smoothly away from the wall.
    initial_interior = rows[1:-1].copy()
    if wall_anchor_rows > 0:
        release = np.minimum(
            np.arange(1, nj - 1) / float(wall_anchor_rows),
            1.0)[:, None, None] ** 2
    else:
        release = None

    residual = np.inf
    iteration = 0
    for iteration in range(1, iterations + 1):
        if periodic:
            u = rows[:, :-1]
            east = np.roll(u, -1, axis=1)
            west = np.roll(u, 1, axis=1)
            e = east[1:-1]
            w = west[1:-1]
            n = u[2:]
            s = u[:-2]
            ne = east[2:]
            se = east[:-2]
            nw = west[2:]
            sw = west[:-2]
            center = u[1:-1]
        else:
            e = rows[1:-1, 2:]
            w = rows[1:-1, :-2]
            n = rows[2:, 1:-1]
            s = rows[:-2, 1:-1]
            ne = rows[2:, 2:]
            se = rows[:-2, 2:]
            nw = rows[2:, :-2]
            sw = rows[:-2, :-2]
            center = rows[1:-1, 1:-1]

        x_xi = 0.5 * (e - w)
        x_eta = 0.5 * (n - s)
        alpha = np.sum(x_eta * x_eta, axis=-1)
        gamma = np.sum(x_xi * x_xi, axis=-1)
        beta = np.sum(x_xi * x_eta, axis=-1)
        cross = ne - nw - se + sw

        alpha3 = alpha[..., None]
        gamma3 = gamma[..., None]
        beta3 = beta[..., None]

        candidate = (
            alpha3 * ((1.0 + 0.5 * phi3) * e + (1.0 - 0.5 * phi3) * w) +
            gamma3 * ((1.0 + 0.5 * psi3) * n + (1.0 - 0.5 * psi3) * s) -
            0.5 * beta3 * cross
        ) / (2.0 * (alpha3 + gamma3) + _EPS)

        updated = (1.0 - relaxation) * center + relaxation * candidate
        if release is not None:
            anchor = initial_interior[:, :-1] if periodic \
                else initial_interior[:, 1:-1]
            updated = (1.0 - release) * anchor + release * updated
        residual = float(np.max(np.abs(updated - center)))
        if periodic:
            rows[1:-1, :-1] = updated
            rows[:, -1] = rows[:, 0]
        else:
            rows[1:-1, 1:-1] = updated

        if outer_orthogonal:
            _outer_orthogonality_step(rows, periodic, ortho_relaxation)

        if residual < tolerance:
            break

    info = {
        'iterations': iteration,
        'residual': residual,
        'converged': residual < tolerance,
    }
    return rows, info
