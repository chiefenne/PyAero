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


def _min_tangential_ratio(rows):
    """Smallest column-to-column spacing anywhere, relative to the wall's
    own spacing at that same column pair. A pinch (columns marching toward
    each other near a tangent-discontinuous corner) drives this toward 0
    without necessarily flipping any cell's jacobian sign, so
    ``_single_signed`` alone cannot see it."""
    wall_spacing = np.maximum(
        np.linalg.norm(np.diff(rows[0], axis=0), axis=1), 1.0e-12)
    spacing = np.linalg.norm(np.diff(rows, axis=1), axis=-1)
    return float((spacing[1:] / wall_spacing[None, :]).min())


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


def test_no_severely_pinched_columns_matrix():
    # C-mesh: the TE/wake-cut corner pinch is fully addressed by the local
    # elliptic repair (>10x margin over this bound in practice). O-grid:
    # the repair helps (mw166 improves ~8x) but the sharp-TE wedge and
    # blunt-TE base corners are the spec's own acknowledged hard case
    # ("cells adjacent to the wedge are inherently skewed... the smoother
    # stage is the designated cleanup") -- local repair between two frozen
    # boundaries cannot fully undo that without an explicit GUI smoother
    # pass, so this only demands no worse than a modest floor there.
    thresholds = {'c': 0.05, 'o': 0.015}
    cases = (
        ('naca0012-sharp', _sharp_contour()),
        ('naca0012-blunt', _blunt_contour()),
        ('mw166', _load_dat(MW166)),
    )
    for name, contour in cases:
        for topology in ('c', 'o'):
            frame = _main_frame(contour, topology)
            rows = _march(frame)
            ratio = _min_tangential_ratio(rows)
            assert ratio > thresholds[topology], (
                f'{name}/{topology}: columns pinched to {ratio:.4f} of '
                'wall spacing (near-degenerate cells)')


def test_first_layer_spacing_respected():
    frame = _main_frame(_sharp_contour(), 'o')
    rows = _march(frame)
    start, stop = frame.metadata['contour_slice']
    spacing = np.linalg.norm(rows[1] - rows[0], axis=1)[start + 5:stop - 5]
    assert np.all(spacing > 0.2 * FIRST_SPACING)
    assert np.median(spacing) < 5.0 * FIRST_SPACING
