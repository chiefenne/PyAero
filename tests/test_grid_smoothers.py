import sys
from pathlib import Path
from unittest import mock

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import GridElliptic
import GridSmoothers
import GridTFI
import StructuredCore as core
import StructuredTopologies as topo
from test_structured_topologies import _blunt_contour, _load_dat, _sharp_contour

MW166 = Path(__file__).resolve().parent / 'data' / 'MW-166-39-44-43.dat'
METHODS = ('laplacian', 'elliptic', 'angle_based')


def _tfi_rows(contour, topology):
    settings = core.StructuredMeshSettings(
        topology=topology, normal_divisions=40, wake_points=40)
    frame = topo.build_frames(np.asarray(contour, float), settings)[0]
    return frame, GridTFI.fill(frame)


def test_wall_and_outer_bitidentical_all_methods():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    for method in METHODS:
        out, _info = GridSmoothers.smooth(rows, method=method, iterations=5,
                                          periodic=frame.periodic,
                                          frozen_rows=1)
        assert np.array_equal(out[0], rows[0]), method
        assert np.array_equal(out[-1], rows[-1]), method


def test_frozen_rows_beyond_wall_bitidentical():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    for method in METHODS:
        out, _info = GridSmoothers.smooth(rows, method=method, iterations=5,
                                          periodic=frame.periodic,
                                          frozen_rows=4)
        assert np.array_equal(out[:4], rows[:4]), method
        assert np.array_equal(out[-1], rows[-1]), method


def test_side_columns_fixed_when_not_periodic():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    for method in METHODS:
        out, _info = GridSmoothers.smooth(rows, method=method, iterations=5,
                                          periodic=False, frozen_rows=1)
        assert np.array_equal(out[:, 0], rows[:, 0]), method
        assert np.array_equal(out[:, -1], rows[:, -1]), method


def test_periodic_seam_stays_welded():
    frame, rows = _tfi_rows(_sharp_contour(), 'o')
    for method in METHODS:
        out, _info = GridSmoothers.smooth(rows, method=method, iterations=5,
                                          periodic=True, frozen_rows=1)
        assert np.array_equal(out[:, 0], out[:, -1]), method


def test_laplacian_moves_interior():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    out, info = GridSmoothers.smooth(rows, method='laplacian',
                                     iterations=10, periodic=False,
                                     frozen_rows=1)
    assert not np.array_equal(out, rows)
    assert info['quality_after'] >= info['quality_before']


def test_elliptic_delegates_to_grid_elliptic_on_sliced_rows():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    solved = rows.copy()
    with mock.patch.object(GridElliptic, 'solve',
                          wraps=GridElliptic.solve) as spy:
        GridSmoothers.smooth(rows, method='elliptic', iterations=5,
                             periodic=False, frozen_rows=3)
    spy.assert_called_once()
    passed_rows = spy.call_args[0][0]
    assert passed_rows.shape[0] == rows.shape[0] - 2   # frozen_rows-1 onward
    assert np.array_equal(passed_rows[0], rows[2])


def test_quality_never_degrades_shipped_airfoils():
    cases = (_sharp_contour(), _blunt_contour(), _load_dat(MW166))
    for contour in cases:
        for topology in ('c', 'o'):
            frame, rows = _tfi_rows(contour, topology)
            for method in METHODS:
                out, info = GridSmoothers.smooth(
                    rows, method=method, iterations=10,
                    periodic=frame.periodic, frozen_rows=1)
                assert info['quality_after'] >= info['quality_before']
                if info['quality_after'] == info['quality_before']:
                    # guard may have reverted; either way it's a no-op
                    # in the degrading direction
                    pass


def test_guard_reverts_when_smoothing_would_degrade():
    # Empirically: a C-mesh TFI grid's near-wall quality is already so
    # tight that a generic elliptic relaxation pass makes it worse there.
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    out, info = GridSmoothers.smooth(rows, method='elliptic', iterations=10,
                                     periodic=False, frozen_rows=1)
    assert np.array_equal(out, rows)
    assert info['quality_after'] == info['quality_before']


def test_unknown_method_raises():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    try:
        GridSmoothers.smooth(rows, method='spectral', periodic=False)
    except ValueError:
        pass
    else:
        raise AssertionError('Expected ValueError for unknown method.')


def test_frozen_rows_must_include_wall():
    frame, rows = _tfi_rows(_sharp_contour(), 'c')
    try:
        GridSmoothers.smooth(rows, method='laplacian', frozen_rows=0,
                             periodic=False)
    except ValueError:
        pass
    else:
        raise AssertionError('Expected ValueError for frozen_rows < 1.')
