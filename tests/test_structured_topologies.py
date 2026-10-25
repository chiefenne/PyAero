import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import StructuredCore as core
import StructuredTopologies as topo


def _load_dat(path):
    xs, ys = [], []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
        except ValueError:
            continue
    return np.column_stack((np.array(xs), np.array(ys)))


NACA0012 = Path(__file__).resolve().parent / 'data' / 'naca0012.dat'


def _sharp_contour():
    contour = _load_dat(NACA0012)
    te = 0.5 * (contour[0] + contour[-1])
    contour[0] = te                   # force exactly sharp, symmetrically
    contour[-1] = te
    return contour


def _blunt_contour(thickness=0.005, blend=0.6):
    contour = _load_dat(NACA0012)
    x, y = contour[:, 0], contour[:, 1].copy()
    ramp = np.clip((x - (1.0 - blend)) / blend, 0.0, 1.0) ** 2
    le_index = int(np.argmin(x))
    y[:le_index] += 0.5 * thickness * ramp[:le_index]     # upper surface
    y[le_index:] -= 0.5 * thickness * ramp[le_index:]     # lower surface
    return np.column_stack((x, y))


def _contour_embedded_in_wall(wall, contour):
    """True if contour appears as a contiguous verbatim slice of wall."""
    n = len(contour)
    for start in range(len(wall) - n + 1):
        if np.allclose(wall[start:start + n], contour, atol=1e-12):
            return True
    return False


def test_c_sharp_single_frame_wall_verbatim():
    settings = core.StructuredMeshSettings(topology='c')
    frames = topo.build_frames(_sharp_contour(), settings)
    assert len(frames) == 1
    frame = frames[0]
    assert frame.te_type == 'sharp'
    assert frame.metadata.get('wake_cut_matched') is True
    assert _contour_embedded_in_wall(frame.wall, _sharp_contour())
    assert len(frame.outer) == len(frame.wall)
    assert len(frame.side_start) == settings.normal_divisions + 1


def test_c_blunt_two_frames_shared_cuts_and_base():
    settings = core.StructuredMeshSettings(topology='c')
    contour = _blunt_contour()
    frames = topo.build_frames(contour, settings)
    assert len(frames) == 2
    main, strip = frames
    assert main.te_type == 'blunt'
    assert strip.kind == 'wake_strip'
    assert _contour_embedded_in_wall(main.wall, contour)
    base = strip.metadata['base']
    assert np.allclose(base[0], contour[-1])
    assert np.allclose(base[-1], contour[0])
    # strip boundaries are the same wake-cut nodes bounding the main wall
    wake_points = settings.wake_points
    lower_cut_in_main = main.wall[-wake_points:]
    upper_cut_in_main = main.wall[:wake_points][::-1]
    assert np.allclose(strip.wall, lower_cut_in_main)
    assert np.allclose(strip.outer, upper_cut_in_main)


def test_o_blunt_closed_loop_with_base():
    settings = core.StructuredMeshSettings(topology='o',
                                           tunnel_shape='circular')
    contour = _blunt_contour()
    frames = topo.build_frames(contour, settings)
    assert len(frames) == 1
    frame = frames[0]
    assert frame.periodic is True
    assert np.allclose(frame.wall[0], frame.wall[-1])
    assert _contour_embedded_in_wall(frame.wall, contour)


def test_o_sharp_both_tunnels():
    contour = _sharp_contour()
    for shape in ('legacy', 'circular'):
        settings = core.StructuredMeshSettings(topology='o',
                                               tunnel_shape=shape)
        frame = topo.build_frames(contour, settings)[0]
        assert np.allclose(frame.wall[0], frame.wall[-1])
        assert len(frame.outer) == len(frame.wall)


def test_circular_c_wake_too_long_raises():
    settings = core.StructuredMeshSettings(
        topology='c', tunnel_shape='circular',
        tunnel_height=2.0, wake_length=7.0)
    try:
        topo.build_frames(_sharp_contour(), settings)
    except ValueError as error:
        assert 'farfield' in str(error).lower() or \
               'wake' in str(error).lower()
    else:
        raise AssertionError('Expected ValueError for wake past farfield.')


def _te_line(frame):
    start = frame.metadata['contour_slice'][0]
    return frame.wall[start], frame.outer[start]


def _angle_from_vertical(te, anchor):
    return np.degrees(np.arctan2(anchor[0] - te[0], abs(anchor[1] - te[1])))


def test_c_te_anchor_fraction_zero_is_vertical():
    for shape, height in (('legacy', 3.5), ('circular', 10.0)):
        settings = core.StructuredMeshSettings(
            topology='c', tunnel_shape=shape, tunnel_height=height)
        frame = topo.build_frames(_sharp_contour(), settings)[0]
        te, anchor = _te_line(frame)
        assert np.isclose(anchor[0], te[0], atol=1e-9)
        assert anchor[1] > 0.0
        assert np.allclose(frame.metadata['te_anchors'][0], anchor)


def test_c_te_anchor_fraction_moves_toward_outlet_with_reserve():
    contour = _sharp_contour()
    xs = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        settings = core.StructuredMeshSettings(
            topology='c', te_anchor_value=fraction)
        frame = topo.build_frames(contour, settings)[0]
        upper, lower = frame.metadata['te_anchors']
        assert np.isclose(upper[0], lower[0])
        xs.append(upper[0])
    assert np.all(np.diff(xs) > 0.0)
    x_te = contour[0][0]
    reserve = topo.ANCHOR_OUTLET_RESERVE * settings.wake_length
    assert np.isclose(xs[-1], x_te + settings.wake_length - reserve)


def test_c_te_anchor_angle_is_exact_and_clamped():
    contour = _sharp_contour()
    for shape, height in (('legacy', 3.5), ('circular', 10.0)):
        settings = core.StructuredMeshSettings(
            topology='c', tunnel_shape=shape, tunnel_height=height,
            te_anchor_mode='angle', te_anchor_value=25.0)
        frame = topo.build_frames(contour, settings)[0]
        te, _anchor = _te_line(frame)
        for anchor in frame.metadata['te_anchors']:
            assert np.isclose(_angle_from_vertical(te, anchor), 25.0)

        steep = core.StructuredMeshSettings(
            topology='c', tunnel_shape=shape, tunnel_height=height,
            te_anchor_mode='angle', te_anchor_value=89.0)
        limit = core.StructuredMeshSettings(
            topology='c', tunnel_shape=shape, tunnel_height=height,
            te_anchor_value=1.0)
        steep_anchor = topo.build_frames(contour, steep)[0] \
            .metadata['te_anchors'][0]
        limit_anchor = topo.build_frames(contour, limit)[0] \
            .metadata['te_anchors'][0]
        assert np.allclose(steep_anchor, limit_anchor)


def test_c_outer_row_monotone_for_all_anchors():
    for contour in (_sharp_contour(), _blunt_contour()):
        for shape, height in (('legacy', 3.5), ('circular', 10.0)):
            for distribution in ('uniform', 'clustered'):
                for fraction in (0.0, 0.5, 1.0):
                    settings = core.StructuredMeshSettings(
                        topology='c', tunnel_shape=shape,
                        tunnel_height=height, te_anchor_value=fraction,
                        boundary_control=core.TunnelBoundaryControl(
                            distribution=distribution,
                            clustering_ratio=3.0))
                    frame = topo.build_frames(contour, settings)[0]
                    steps = np.linalg.norm(np.diff(frame.outer, axis=0),
                                           axis=1)
                    assert len(frame.outer) == len(frame.wall)
                    assert np.all(steps > 1e-9)


def test_c_te_anchor_invalid_values_raise():
    for mode, value in (('fraction', -0.1), ('fraction', 1.5),
                        ('angle', 90.0), ('angle', -1.0)):
        settings = core.StructuredMeshSettings(
            topology='c', te_anchor_mode=mode, te_anchor_value=value)
        try:
            topo.build_frames(_sharp_contour(), settings)
        except ValueError as error:
            assert 'anchor' in str(error).lower()
        else:
            raise AssertionError(f'Expected ValueError for {mode}={value}.')


def test_te_base_divisions_setting_for_c_and_o():
    contour = _blunt_contour()
    for topology in ('c', 'o'):
        auto = core.StructuredMeshSettings(topology=topology)
        fixed = core.StructuredMeshSettings(topology=topology,
                                            te_base_divisions=11)
        auto_frames = topo.build_frames(contour, auto)
        fixed_frames = topo.build_frames(contour, fixed)
        if topology == 'c':
            strip = fixed_frames[1]
            assert len(strip.side_start) == 12
            assert len(strip.side_end) == 12
        else:
            extra = len(fixed_frames[0].wall) - len(auto_frames[0].wall)
            auto_base = len(auto_frames[0].wall) - len(contour)
            assert len(fixed_frames[0].wall) - len(contour) == 11
            assert extra == 11 - auto_base
