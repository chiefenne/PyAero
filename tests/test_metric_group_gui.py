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


def _toolbox_with_metric_group():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    toolbox = SimpleNamespace()
    toolbox.metric_group = ToolboxPagesMeshing._build_metric_group(toolbox)
    return toolbox


def test_metric_group_has_no_real_choice_and_says_so():
    """Layout family / singularity model are documentation of a fixed
    pipeline, not a live choice -- both combos must be disabled so the
    menu doesn't imply configurability that doesn't exist."""
    toolbox = _toolbox_with_metric_group()
    assert not toolbox.metric_layout_strategy.isEnabled()
    assert not toolbox.metric_singularity_template.isEnabled()
    assert toolbox.metric_layout_strategy.currentData() == 'metric_c_grid'
    assert toolbox.metric_singularity_template.currentData() == \
        'auto_boundary_c'
