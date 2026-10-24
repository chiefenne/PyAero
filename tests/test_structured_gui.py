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
    index = toolbox.structured_algorithm.findData('tfi')
    toolbox.structured_algorithm.setCurrentIndex(index)
    toolbox.structured_tfi_variant.setCurrentIndex(1)   # Hermite
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
    index = toolbox.structured_algorithm.findData('elliptic')
    assert index >= 0
    toolbox.structured_algorithm.setCurrentIndex(index)
    toolbox.structured_elliptic_iterations.setValue(80)
    toolbox.structured_elliptic_relaxation.setValue(0.6)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.algorithm == 'elliptic'
    assert settings.tfi_variant == 'standard'
    assert settings.elliptic_iterations == 80
    assert abs(settings.elliptic_relaxation - 0.6) < 1e-9


def test_structured_elliptic_relaxation_default():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert abs(settings.elliptic_relaxation - 0.8) < 1e-9


def test_structured_hyperbolic_selection():
    toolbox = _toolbox_with_group()
    index = toolbox.structured_algorithm.findData('hyperbolic')
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


def test_structured_smoother_defaults_to_none():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.smoother == 'none'
    assert settings.smoother_iterations == 10


def test_structured_smoother_selection_roundtrip():
    toolbox = _toolbox_with_group()
    index = toolbox.structured_smoother.findData('angle_based')
    assert index >= 0
    toolbox.structured_smoother.setCurrentIndex(index)
    toolbox.structured_smoother_iterations.setValue(25)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.smoother == 'angle_based'
    assert settings.smoother_iterations == 25


def _row_visible(toolbox, widget):
    return toolbox.structured_form.isRowVisible(widget)


def test_algorithm_specific_rows_follow_algorithm_choice():
    toolbox = _toolbox_with_group()
    form = toolbox.structured_form

    # Default algorithm is TFI: only the TFI variant row shows.
    assert _row_visible(toolbox, toolbox.structured_tfi_variant)
    assert not _row_visible(toolbox, toolbox.structured_elliptic_iterations)
    assert not _row_visible(toolbox, toolbox.structured_elliptic_relaxation)
    assert not _row_visible(toolbox, toolbox.structured_hyperbolic_fraction_cap)

    toolbox.structured_algorithm.setCurrentIndex(
        toolbox.structured_algorithm.findData('elliptic'))
    assert not _row_visible(toolbox, toolbox.structured_tfi_variant)
    assert _row_visible(toolbox, toolbox.structured_elliptic_iterations)
    assert _row_visible(toolbox, toolbox.structured_elliptic_relaxation)
    assert not _row_visible(toolbox, toolbox.structured_hyperbolic_fraction_cap)

    toolbox.structured_algorithm.setCurrentIndex(
        toolbox.structured_algorithm.findData('hyperbolic'))
    assert not _row_visible(toolbox, toolbox.structured_tfi_variant)
    assert not _row_visible(toolbox, toolbox.structured_elliptic_iterations)
    assert not _row_visible(toolbox, toolbox.structured_elliptic_relaxation)
    assert _row_visible(toolbox, toolbox.structured_hyperbolic_fraction_cap)
    assert form is toolbox.structured_form


def test_outer_ratio_row_only_visible_when_clustered():
    toolbox = _toolbox_with_group()
    assert not _row_visible(toolbox, toolbox.structured_outer_ratio)
    toolbox.structured_outer_distribution.setCurrentIndex(
        toolbox.structured_outer_distribution.findData('clustered'))
    assert _row_visible(toolbox, toolbox.structured_outer_ratio)


def test_smoother_iterations_row_only_visible_when_smoother_active():
    toolbox = _toolbox_with_group()
    assert not _row_visible(toolbox, toolbox.structured_smoother_iterations)
    toolbox.structured_smoother.setCurrentIndex(
        toolbox.structured_smoother.findData('laplacian'))
    assert _row_visible(toolbox, toolbox.structured_smoother_iterations)


def test_outer_angle_enabled_only_where_it_takes_effect():
    toolbox = _toolbox_with_group()

    # Default: TFI + Standard variant -> angle_mode is ignored by the solver.
    assert not toolbox.structured_outer_angle.isEnabled()

    toolbox.structured_tfi_variant.setCurrentIndex(
        toolbox.structured_tfi_variant.findData('hermite'))
    assert toolbox.structured_outer_angle.isEnabled()

    toolbox.structured_algorithm.setCurrentIndex(
        toolbox.structured_algorithm.findData('elliptic'))
    assert toolbox.structured_outer_angle.isEnabled()

    toolbox.structured_algorithm.setCurrentIndex(
        toolbox.structured_algorithm.findData('hyperbolic'))
    assert not toolbox.structured_outer_angle.isEnabled()


def test_structured_te_anchor_controls():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.te_anchor_mode == 'fraction'
    assert settings.te_anchor_value == 0.0
    assert toolbox.structured_te_anchor_value.maximum() == 1.0

    toolbox.structured_te_anchor_mode.setCurrentIndex(
        toolbox.structured_te_anchor_mode.findData('angle'))
    toolbox.structured_te_anchor_value.setValue(30.0)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.te_anchor_mode == 'angle'
    assert settings.te_anchor_value == 30.0

    form = toolbox.structured_form
    assert form.isRowVisible(toolbox.structured_te_anchor_value)
    toolbox.structured_topology.setCurrentIndex(
        toolbox.structured_topology.findData('o'))
    assert not form.isRowVisible(toolbox.structured_te_anchor_value)
    assert not form.isRowVisible(toolbox.structured_te_anchor_mode)
