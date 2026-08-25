import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import GridHyperbolic
import OrthoLayers
import StructuredCore as core
import StructuredTopologies as topo
from test_structured_topologies import (
    _blunt_contour, _load_dat, _sharp_contour,
)

MW166 = Path(__file__).resolve().parent / 'data' / 'MW-166-39-44-43.dat'
FIRST_SPACING = 0.002


def _main_frame(contour, topology):
    settings = core.StructuredMeshSettings(
        topology=topology, normal_divisions=40, wake_points=40,
        first_layer_thickness=FIRST_SPACING)
    return topo.build_frames(np.asarray(contour, float), settings)[0]


def _frame_normals(frame):
    if frame.kind == 'o':
        corners = [0, len(frame.wall) - 1]
    else:
        start, stop = frame.metadata['contour_slice']
        corners = [start, stop - 1]
    return OrthoLayers.wall_normals(frame.wall, corners,
                                    closed=frame.periodic)


def _march(frame):
    return GridHyperbolic.march(frame, normals=_frame_normals(frame),
                                first_spacing=FIRST_SPACING)


def _single_signed(rows):
    jacobians = core.cell_jacobians(rows)
    return bool(np.all(jacobians > 0) or np.all(jacobians < 0))


def test_wall_and_outer_verbatim():
    frame = _main_frame(_sharp_contour(), 'c')
    rows = _march(frame)
    assert rows.shape == (len(frame.side_start), len(frame.wall), 2)
    assert np.array_equal(rows[0], frame.wall)
    assert np.array_equal(rows[-1], frame.outer)


def test_no_inverted_cells_matrix():
    cases = (
        ('naca0012-sharp', _sharp_contour()),
        ('naca0012-blunt', _blunt_contour()),
        ('mw166', _load_dat(MW166)),
    )
    for name, contour in cases:
        for topology in ('c', 'o'):
            frame = _main_frame(contour, topology)
            rows = _march(frame)
            assert _single_signed(rows), f'inverted: {name}/{topology}'


def test_o_seam_welded():
    frame = _main_frame(_sharp_contour(), 'o')
    rows = _march(frame)
    assert np.array_equal(rows[:, 0], rows[:, -1])


def test_c_front_ends_stay_on_outlet_plane():
    frame = _main_frame(_sharp_contour(), 'c')
    x_outlet = frame.metadata['x_outlet']
    rows = _march(frame)
    assert np.allclose(rows[:, 0, 0], x_outlet, atol=1e-9)
    assert np.allclose(rows[:, -1, 0], x_outlet, atol=1e-9)


def test_first_layer_spacing_respected():
    frame = _main_frame(_sharp_contour(), 'o')
    rows = _march(frame)
    start, stop = frame.metadata['contour_slice']
    spacing = np.linalg.norm(rows[1] - rows[0], axis=1)[start + 5:stop - 5]
    assert np.all(spacing > 0.2 * FIRST_SPACING)
    assert np.median(spacing) < 5.0 * FIRST_SPACING
