from PySide6 import QtWidgets

from MetricTriangulation import MetricExampleFactory
from ToolboxWidgets import (
    configure_form_layout,
    make_page_label,
    right_aligned_row,
)


def build_metric_tests_panel(toolbox):
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    intro = QtWidgets.QLabel(
        'Play with the cleanroom triangulation core on simple PSLG examples before we connect it to the full metric / Ricci-flow backend. These examples stay in the viewer and let you inspect boundary recovery and hole handling directly.'
    )
    intro.setWordWrap(True)
    intro.setProperty('pageSectionHint', 'true')
    layout.addWidget(intro)

    geometry_group = QtWidgets.QGroupBox('Example Geometry')
    geometry_form = QtWidgets.QFormLayout()
    configure_form_layout(geometry_form)

    toolbox.metric_test_example = QtWidgets.QComboBox()
    toolbox.metric_test_example.addItem('Rectangle', userData='rectangle')
    toolbox.metric_test_example.addItem(
        'Rectangle + one circle',
        userData='rectangle_circle',
    )
    toolbox.metric_test_example.addItem(
        'Rectangle + two circles',
        userData='rectangle_two_circles',
    )
    toolbox.metric_test_example.addItem(
        'Tunnel + default airfoil',
        userData='default_airfoil_tunnel',
    )
    geometry_form.addRow(make_page_label('Example'), toolbox.metric_test_example)

    toolbox.metric_test_width = QtWidgets.QDoubleSpinBox()
    toolbox.metric_test_width.setRange(0.2, 100.0)
    toolbox.metric_test_width.setDecimals(3)
    toolbox.metric_test_width.setSingleStep(0.1)
    toolbox.metric_test_width.setValue(4.0)
    geometry_form.addRow(make_page_label('Width'), toolbox.metric_test_width)

    toolbox.metric_test_height = QtWidgets.QDoubleSpinBox()
    toolbox.metric_test_height.setRange(0.2, 100.0)
    toolbox.metric_test_height.setDecimals(3)
    toolbox.metric_test_height.setSingleStep(0.1)
    toolbox.metric_test_height.setValue(2.0)
    geometry_form.addRow(make_page_label('Height'), toolbox.metric_test_height)

    toolbox.metric_test_hole_radius = QtWidgets.QDoubleSpinBox()
    toolbox.metric_test_hole_radius.setRange(0.01, 20.0)
    toolbox.metric_test_hole_radius.setDecimals(3)
    toolbox.metric_test_hole_radius.setSingleStep(0.02)
    toolbox.metric_test_hole_radius.setValue(0.35)
    geometry_form.addRow(
        make_page_label('Hole radius'),
        toolbox.metric_test_hole_radius,
    )

    toolbox.metric_test_hole_spacing = QtWidgets.QDoubleSpinBox()
    toolbox.metric_test_hole_spacing.setRange(0.05, 100.0)
    toolbox.metric_test_hole_spacing.setDecimals(3)
    toolbox.metric_test_hole_spacing.setSingleStep(0.05)
    toolbox.metric_test_hole_spacing.setValue(1.40)
    geometry_form.addRow(
        make_page_label('Hole spacing'),
        toolbox.metric_test_hole_spacing,
    )

    geometry_group.setLayout(geometry_form)
    layout.addWidget(geometry_group)

    discretization_group = QtWidgets.QGroupBox('Triangulation Controls')
    discretization_form = QtWidgets.QFormLayout()
    configure_form_layout(discretization_form)

    toolbox.metric_test_outer_resolution = QtWidgets.QSpinBox()
    toolbox.metric_test_outer_resolution.setRange(8, 1000)
    toolbox.metric_test_outer_resolution.setValue(72)
    discretization_form.addRow(
        make_page_label('Outer boundary points'),
        toolbox.metric_test_outer_resolution,
    )

    toolbox.metric_test_hole_resolution = QtWidgets.QSpinBox()
    toolbox.metric_test_hole_resolution.setRange(12, 1000)
    toolbox.metric_test_hole_resolution.setValue(44)
    discretization_form.addRow(
        make_page_label('Hole boundary points'),
        toolbox.metric_test_hole_resolution,
    )

    toolbox.metric_test_interior_x = QtWidgets.QSpinBox()
    toolbox.metric_test_interior_x.setRange(0, 400)
    toolbox.metric_test_interior_x.setValue(32)
    discretization_form.addRow(
        make_page_label('Interior grid X'),
        toolbox.metric_test_interior_x,
    )

    toolbox.metric_test_interior_y = QtWidgets.QSpinBox()
    toolbox.metric_test_interior_y.setRange(0, 400)
    toolbox.metric_test_interior_y.setValue(16)
    discretization_form.addRow(
        make_page_label('Interior grid Y'),
        toolbox.metric_test_interior_y,
    )

    discretization_group.setLayout(discretization_form)
    layout.addWidget(discretization_group)

    toolbox.metric_test_status = QtWidgets.QLabel(
        'Choose an example and click Generate Example to draw the triangulation in the viewer.'
    )
    toolbox.metric_test_status.setWordWrap(True)
    toolbox.metric_test_status.setProperty('pageSectionHint', 'true')
    layout.addWidget(toolbox.metric_test_status)

    toolbox.metric_test_generate_button = QtWidgets.QPushButton('Generate Example')
    toolbox.metric_test_generate_button.setObjectName('pagePrimaryActionButton')
    toolbox.metric_test_clear_button = QtWidgets.QPushButton('Clear')
    toolbox.metric_test_clear_button.setObjectName('pageSecondaryActionButton')
    toolbox.metric_test_actions = QtWidgets.QWidget()
    toolbox.metric_test_actions.setLayout(
        right_aligned_row(
            toolbox.metric_test_clear_button,
            toolbox.metric_test_generate_button,
        )
    )
    layout.addWidget(toolbox.metric_test_actions)
    layout.addStretch(1)

    toolbox.item_metric_tests = QtWidgets.QWidget()
    toolbox.item_metric_tests.setLayout(layout)

    toolbox.metric_test_generate_button.clicked.connect(toolbox.generateMetricTest)
    toolbox.metric_test_clear_button.clicked.connect(toolbox.clearMetricTest)
    toolbox.metric_test_example.currentIndexChanged.connect(
        toolbox.metricTestControlsChanged
    )

    toolbox.metricTestControlsChanged()


def metric_test_example_labels() -> dict[str, str]:
    return {
        'rectangle': 'Rectangle',
        'rectangle_circle': 'Rectangle + one circle',
        'rectangle_two_circles': 'Rectangle + two circles',
        'default_airfoil_tunnel': 'Tunnel + default airfoil',
        **{
            key: key.replace('_', ' ').title()
            for key in MetricExampleFactory.available_examples()
        },
    }
