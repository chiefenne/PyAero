import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import GridTFI
import StructuredCore as core
import StructuredTopologies as topo
from test_structured_topologies import _blunt_contour, _sharp_contour


def _rect_frame(nx=11, ny=6, width=2.0, height=1.0):
    x = np.linspace(0.0, width, nx)
    y = np.linspace(0.0, height, ny)
    return core.GridFrame(
        wall=np.column_stack((x, np.zeros(nx))),
        outer=np.column_stack((x, np.full(nx, height))),
        side_start=np.column_stack((np.zeros(ny), y)),
        side_end=np.column_stack((np.full(ny, width), y)),
        kind='c', te_type='sharp',
    )


def test_standard_tfi_reproduces_rectangle():
    frame = _rect_frame()
    rows = GridTFI.fill(frame)
    assert rows.shape == (6, 11, 2)
    xs, ys = np.meshgrid(np.linspace(0, 2, 11), np.linspace(0, 1, 6))
    assert np.allclose(rows[..., 0], xs, atol=1e-12)
    assert np.allclose(rows[..., 1], ys, atol=1e-12)


def test_boundaries_verbatim_on_real_frame():
    settings = core.StructuredMeshSettings(topology='c')
    frame = topo.build_frames(_sharp_contour(), settings)[0]
    rows = GridTFI.fill(frame)
    assert np.array_equal(rows[0], frame.wall)
    assert np.array_equal(rows[-1], frame.outer)
    assert np.array_equal(rows[:, 0], frame.side_start)
    assert np.array_equal(rows[:, -1], frame.side_end)


def test_no_inverted_cells_o_and_c_both_te_types():
    for topology in ('c', 'o'):
        for shape in ('legacy', 'circular'):
            for contour in (_sharp_contour(), _blunt_contour()):
                settings = core.StructuredMeshSettings(
                    topology=topology, tunnel_shape=shape,
                    tunnel_height=3.5 if shape == 'legacy' else 10.0)
                for frame in topo.build_frames(contour, settings):
                    rows = GridTFI.fill(frame)
                    jacobians = core.cell_jacobians(rows)
                    assert np.all(np.abs(jacobians) > 1e-14), \
                        f'degenerate cell: {topology}/{shape}'
                    assert np.all(jacobians > 0) or np.all(jacobians < 0), \
                        f'inverted cells: {topology}/{shape}'


def test_hermite_orthogonal_angle_at_outer_boundary():
    control = core.TunnelBoundaryControl(angle_mode='orthogonal')
    settings = core.StructuredMeshSettings(
        topology='o', tunnel_shape='circular',
        boundary_control=control, tfi_variant='hermite')
    frame = topo.build_frames(_sharp_contour(), settings)[0]
    rows = GridTFI.fill(frame, variant='hermite', boundary_control=control)
    # angle between last mesh edge and outer-boundary tangent, all nodes
    edge = rows[-1] - rows[-2]
    tangent = np.gradient(frame.outer, axis=0)
    cos = np.abs(np.sum(edge * tangent, axis=1)) / (
        np.linalg.norm(edge, axis=1) * np.linalg.norm(tangent, axis=1))
    angles = np.degrees(np.arccos(np.clip(cos, 0.0, 1.0)))
    assert np.median(np.abs(angles - 90.0)) < 10.0
