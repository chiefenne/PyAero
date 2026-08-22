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


NACA0012 = PROJECT_ROOT / 'lib_AE' / 'Construct2D_2.1.4' / \
    'sample_airfoils' / 'naca0012.dat'


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
