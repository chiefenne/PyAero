import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import GridElliptic
import GridTFI
import StructuredCore as core
import StructuredTopologies as topo
from test_ortho_layers import _build_spline_data
from test_structured_topologies import (
    NACA0012, _blunt_contour, _load_dat, _sharp_contour,
)

MW166 = Path(__file__).resolve().parent / 'data' / 'MW-166-39-44-43.dat'


def _clustered_rect_rows(nx=15, ny=10):
    x = np.linspace(0.0, 2.0, nx)
    d = core.geometric_distances(1.0, 0.02, ny)
    xs, ys = np.meshgrid(x, d)
    return np.stack((xs, ys), axis=-1)


def _tfi_rows(contour, topology, tunnel_shape='legacy', tunnel_height=3.5):
    settings = core.StructuredMeshSettings(
        topology=topology, tunnel_shape=tunnel_shape,
        tunnel_height=tunnel_height,
        normal_divisions=30, wake_points=30)
    frame = topo.build_frames(np.asarray(contour, float), settings)[0]
    return frame, GridTFI.fill(frame)


def _single_signed(rows):
    jacobians = core.cell_jacobians(rows)
    return bool(np.all(jacobians > 0) or np.all(jacobians < 0))


def test_clustered_rectangle_is_fixed_point():
    rows = _clustered_rect_rows()
    out, _info = GridElliptic.solve(rows, iterations=50)
    assert np.max(np.abs(out - rows)) < 1e-6


def test_pure_winslow_would_move_it():
    rows = _clustered_rect_rows()
    out, _info = GridElliptic.solve(rows, iterations=50, control='none')
    assert np.max(np.abs(out - rows)) > 1e-3


def test_boundaries_dirichlet_and_wall_bitidentical():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    out, _info = GridElliptic.solve(rows, iterations=30)
    assert np.array_equal(out[0], rows[0])
    assert np.array_equal(out[-1], rows[-1])
    assert np.array_equal(out[:, 0], rows[:, 0])
    assert np.array_equal(out[:, -1], rows[:, -1])
    assert np.max(np.abs(out[1:-1, 1:-1] - rows[1:-1, 1:-1])) > 0.0


def test_o_grid_periodic_seam_relaxes():
    frame, rows = _tfi_rows(_sharp_contour(), 'o')
    out, _info = GridElliptic.solve(rows, periodic=True, iterations=50)
    assert np.array_equal(out[:, 0], out[:, -1])       # seam stays welded
    assert np.array_equal(out[0], rows[0])             # wall fixed
    assert np.array_equal(out[-1], rows[-1])           # outer fixed
    seam_delta = np.max(np.abs(out[1:-1, 0] - rows[1:-1, 0]))
    assert seam_delta > 1e-6                           # seam actually moved


def test_no_inverted_cells_after_elliptic_all_airfoils():
    mw166 = _load_dat(MW166)
    cases = (
        ('naca0012-sharp', _sharp_contour()),
        ('naca0012-blunt', _blunt_contour()),
        ('mw166', mw166),
    )
    for name, contour in cases:
        for topology in ('c', 'o'):
            frame, rows = _tfi_rows(contour, topology)
            out, _info = GridElliptic.solve(
                rows, periodic=frame.periodic, iterations=60)
            assert _single_signed(out), f'inverted cells: {name}/{topology}'


def test_outer_orthogonality_improves_angle():
    frame, rows = _tfi_rows(_sharp_contour(), 'o', tunnel_shape='circular',
                            tunnel_height=10.0)

    def median_angle_deviation(grid):
        edge = grid[-1] - grid[-2]
        tangent = np.gradient(frame.outer, axis=0)
        cos = np.abs(np.sum(edge * tangent, axis=1)) / (
            np.linalg.norm(edge, axis=1) *
            np.linalg.norm(tangent, axis=1))
        angles = np.degrees(np.arccos(np.clip(cos, 0.0, 1.0)))
        return float(np.median(np.abs(angles - 90.0)))

    baseline = median_angle_deviation(rows)
    out, _info = GridElliptic.solve(rows, periodic=True, iterations=100,
                                    outer_orthogonal=True)
    improved = median_angle_deviation(out)
    assert improved < baseline
    assert improved < 10.0
    assert _single_signed(out)


def test_info_reports_convergence():
    rows = _clustered_rect_rows()
    _out, info = GridElliptic.solve(rows, iterations=40)
    assert set(info) >= {'iterations', 'residual', 'converged'}
    assert info['iterations'] <= 40
    assert info['residual'] >= 0.0
