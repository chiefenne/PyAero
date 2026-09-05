import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6 import QtWidgets

import ToolboxPagesMeshing


def _toolbox_with_group():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    toolbox = SimpleNamespace()
    toolbox.structured_group = \
        ToolboxPagesMeshing._build_structured_group(toolbox)
    return toolbox


def test_structured_group_defaults_map_to_settings():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.topology == 'c'
    assert settings.tunnel_shape == 'legacy'
    assert settings.tunnel_height == 3.5
    assert settings.tfi_variant == 'standard'
    assert settings.ortho_layers == 0
    assert settings.boundary_control.distribution == 'uniform'
    assert settings.boundary_control.angle_mode == 'free'


def test_structured_group_selection_roundtrip():
    toolbox = _toolbox_with_group()
    toolbox.structured_topology.setCurrentIndex(1)      # O-grid
    toolbox.structured_tunnel_shape.setCurrentIndex(1)  # circular
    toolbox.structured_algorithm.setCurrentIndex(1)     # TFI Hermite
    toolbox.structured_ortho_layers.setValue(8)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.topology == 'o'
    assert settings.tunnel_shape == 'circular'
    assert settings.algorithm == 'tfi'
    assert settings.tfi_variant == 'hermite'
    assert settings.ortho_layers == 8


def test_structured_algorithm_defaults_to_tfi():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.algorithm == 'tfi'
    assert settings.elliptic_iterations == 150


def test_structured_elliptic_selection():
    toolbox = _toolbox_with_group()
    index = toolbox.structured_algorithm.findData('elliptic:standard')
    assert index >= 0
    toolbox.structured_algorithm.setCurrentIndex(index)
    toolbox.structured_elliptic_iterations.setValue(80)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.algorithm == 'elliptic'
    assert settings.tfi_variant == 'standard'
    assert settings.elliptic_iterations == 80


def test_structured_hyperbolic_selection():
    toolbox = _toolbox_with_group()
    index = toolbox.structured_algorithm.findData('hyperbolic:standard')
    assert index >= 0
    toolbox.structured_algorithm.setCurrentIndex(index)
    toolbox.structured_hyperbolic_fraction_cap.setValue(0.35)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.algorithm == 'hyperbolic'
    assert settings.tfi_variant == 'standard'
    assert abs(settings.hyperbolic_fraction_cap - 0.35) < 1e-9


def test_structured_hyperbolic_defaults():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert abs(settings.hyperbolic_fraction_cap - 0.5) < 1e-9
    assert abs(settings.hyperbolic_smoothing - 1.0) < 1e-9
