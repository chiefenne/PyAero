import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import StructuredCore as core


def _sharp_contour():
    x = np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0])
    y = np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0])
    return np.column_stack((x, y))


def _blunt_contour():
    x = np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0])
    y = np.array([0.01, 0.05, 0.08, 0.0, -0.08, -0.05, -0.01])
    return np.column_stack((x, y))


def test_detect_te_type():
    assert core.detect_te_type(_sharp_contour()) == 'sharp'
    assert core.detect_te_type(_blunt_contour()) == 'blunt'


def test_geometric_distances_first_spacing_and_length():
    d = core.geometric_distances(length=2.0, first_spacing=0.01, count=30)
    assert d.shape == (30,)
    assert d[0] == 0.0
    assert np.isclose(d[-1], 2.0)
    assert np.isclose(d[1] - d[0], 0.01, rtol=1e-6)
    assert np.all(np.diff(d) > 0.0)
    # growth is monotone: each step at least as large as the previous
    steps = np.diff(d)
    assert np.all(steps[1:] >= steps[:-1] - 1e-12)


def test_sample_te_base_endpoints_verbatim():
    lower = np.array([1.0, -0.01])
    upper = np.array([1.0, 0.01])
    base = core.sample_te_base(lower, upper, spacing=0.004)
    assert np.allclose(base[0], lower)
    assert np.allclose(base[-1], upper)
    assert len(base) >= 3
    assert np.all(np.diff(base[:, 1]) > 0.0)


def test_distribute_on_polyline_uniform_and_clustered():
    line = np.column_stack((np.linspace(0.0, 10.0, 5), np.zeros(5)))
    uniform = core.distribute_on_polyline(line, 21, distribution='uniform')
    assert uniform.shape == (21, 2)
    assert np.allclose(uniform[0], line[0])
    assert np.allclose(uniform[-1], line[-1])
    assert np.allclose(np.diff(uniform[:, 0]), 0.5)

    clustered = core.distribute_on_polyline(
        line, 21, distribution='clustered', ratio=4.0)
    steps = np.diff(clustered[:, 0])
    assert np.isclose(steps[-1] / steps[0], 4.0, rtol=0.05)


def test_settings_defaults_valid():
    settings = core.StructuredMeshSettings()
    assert settings.topology in ('c', 'o')
    assert settings.tunnel_shape in ('legacy', 'circular')
    assert settings.boundary_control.distribution == 'uniform'
