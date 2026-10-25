from PySide6 import QtWidgets

from ToolboxWidgets import (
    configure_form_layout,
    make_page_label,
    right_aligned_row,
)


def build_meshing_panel(toolbox):
    engine_group = _build_engine_group(toolbox)
    _build_airfoil_mesh_form(toolbox)
    _build_tunnel_mesh_form(toolbox)
    metric_group = _build_metric_group(toolbox)
    structured_group = _build_structured_group(toolbox)
    export_group = _build_export_group(toolbox)

    box_airfoil = QtWidgets.QGroupBox('Airfoil')
    airfoil_layout = QtWidgets.QVBoxLayout()
    airfoil_layout.addLayout(toolbox.form_mesh_airfoil)
    box_airfoil.setLayout(airfoil_layout)

    box_tunnel = QtWidgets.QGroupBox('Tunnel')
    tunnel_layout = QtWidgets.QVBoxLayout()
    tunnel_layout.addLayout(toolbox.form_mesh_tunnel)
    box_tunnel.setLayout(tunnel_layout)

    toolbox.mesh_airfoil_group = box_airfoil
    toolbox.mesh_tunnel_group = box_tunnel
    toolbox.mesh_engine_specific_groups = {
        'metric_based': metric_group,
        'structured': structured_group,
    }

    toolbox.createMeshButton = QtWidgets.QPushButton('Create Mesh')
    toolbox.createMeshButton.setObjectName('pagePrimaryActionButton')
    toolbox.createMeshActionPanel = QtWidgets.QWidget()
    toolbox.createMeshActionPanel.setLayout(
        right_aligned_row(toolbox.createMeshButton)
    )

    layout = QtWidgets.QVBoxLayout()
    layout.addStretch(1)
    layout.addWidget(engine_group)
    layout.addWidget(box_airfoil)
    layout.addWidget(box_tunnel)
    layout.addWidget(metric_group)
    layout.addWidget(structured_group)
    layout.addWidget(toolbox.createMeshActionPanel)
    layout.addStretch(1)
    layout.addWidget(export_group)
    layout.addStretch(10)

    toolbox.item_msh = QtWidgets.QWidget()
    toolbox.item_msh.setLayout(layout)

    toolbox.meshEngineSelector.currentIndexChanged.connect(
        toolbox.mesh_engine_changed
    )
    toolbox.createMeshButton.clicked.connect(toolbox.generateMesh)
    toolbox.exportMeshButton.clicked.connect(toolbox.exportMesh)
    toolbox.mesh_engine_changed()


def _build_engine_group(toolbox):
    toolbox.mesh_engine = 'metric_based'
    toolbox.meshEngineSelector = QtWidgets.QComboBox()
    toolbox.meshEngineSelector.addItem(
        'Metric based',
        userData='metric_based',
    )
    toolbox.meshEngineSelector.addItem(
        'Structured',
        userData='structured',
    )

    form = QtWidgets.QFormLayout()
    configure_form_layout(form)
    label = make_page_label('Mesh engine')
    label.setToolTip(
        'Metric-based structured wind-tunnel mesher inspired by the reference paper.'
    )
    form.addRow(label, toolbox.meshEngineSelector)

    group = QtWidgets.QGroupBox('Engine')
    group.setLayout(form)
    return group


def _build_structured_group(toolbox):
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    intro = QtWidgets.QLabel(
        'Composable structured mesher: topology × tunnel shape × '
        'algorithm. Sharp vs blunt trailing edge is detected automatically '
        'from the prepared contour and changes the block topology (a blunt '
        'C-mesh adds a wake strip).'
    )
    intro.setWordWrap(True)
    intro.setProperty('pageSectionHint', 'true')
    layout.addWidget(intro)

    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    toolbox.structured_topology = QtWidgets.QComboBox()
    toolbox.structured_topology.addItem('C-mesh', userData='c')
    toolbox.structured_topology.addItem('O-grid', userData='o')
    form.addRow(make_page_label('Topology'), toolbox.structured_topology)

    toolbox.structured_tunnel_shape = QtWidgets.QComboBox()
    toolbox.structured_tunnel_shape.addItem(
        'Legacy (half-circle + rectangle)', userData='legacy')
    toolbox.structured_tunnel_shape.addItem('Circular', userData='circular')
    form.addRow(make_page_label('Tunnel shape'),
                toolbox.structured_tunnel_shape)

    toolbox.structured_tunnel_height = QtWidgets.QDoubleSpinBox()
    toolbox.structured_tunnel_height.setRange(0.5, 50.0)
    toolbox.structured_tunnel_height.setSingleStep(0.5)
    toolbox.structured_tunnel_height.setValue(3.5)
    form.addRow(make_page_label('Farfield radius / half-height'),
                toolbox.structured_tunnel_height)

    toolbox.structured_wake_length = QtWidgets.QDoubleSpinBox()
    toolbox.structured_wake_length.setRange(0.5, 50.0)
    toolbox.structured_wake_length.setSingleStep(0.5)
    toolbox.structured_wake_length.setValue(7.0)
    form.addRow(make_page_label('Wake length'),
                toolbox.structured_wake_length)

    toolbox.structured_te_anchor_mode = QtWidgets.QComboBox()
    toolbox.structured_te_anchor_mode.addItem('Fraction',
                                              userData='fraction')
    toolbox.structured_te_anchor_mode.addItem('Angle', userData='angle')
    toolbox.structured_te_anchor_mode.setToolTip(
        'Where the grid line leaving the trailing edge meets the tunnel '
        'wall (same above and below).')
    form.addRow(make_page_label('TE line target'),
                toolbox.structured_te_anchor_mode)

    toolbox.structured_te_anchor_value = QtWidgets.QDoubleSpinBox()
    form.addRow(make_page_label('TE line position'),
                toolbox.structured_te_anchor_value)
    _update_te_anchor_range(toolbox)

    toolbox.structured_algorithm = QtWidgets.QComboBox()
    toolbox.structured_algorithm.addItem('TFI', userData='tfi')
    toolbox.structured_algorithm.addItem('Elliptic (Winslow + TM)',
                                         userData='elliptic')
    toolbox.structured_algorithm.addItem('Hyperbolic (marching)',
                                         userData='hyperbolic')
    form.addRow(make_page_label('Algorithm'), toolbox.structured_algorithm)

    toolbox.structured_tfi_variant = QtWidgets.QComboBox()
    toolbox.structured_tfi_variant.addItem('Standard', userData='standard')
    toolbox.structured_tfi_variant.addItem('Hermite', userData='hermite')
    form.addRow(make_page_label('TFI variant'), toolbox.structured_tfi_variant)

    toolbox.structured_elliptic_iterations = QtWidgets.QSpinBox()
    toolbox.structured_elliptic_iterations.setRange(10, 2000)
    toolbox.structured_elliptic_iterations.setValue(150)
    form.addRow(make_page_label('Elliptic iterations'),
                toolbox.structured_elliptic_iterations)

    toolbox.structured_elliptic_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.structured_elliptic_relaxation.setRange(0.01, 1.0)
    toolbox.structured_elliptic_relaxation.setSingleStep(0.05)
    toolbox.structured_elliptic_relaxation.setDecimals(2)
    toolbox.structured_elliptic_relaxation.setValue(0.8)
    form.addRow(make_page_label('Elliptic relaxation'),
                toolbox.structured_elliptic_relaxation)

    toolbox.structured_hyperbolic_fraction_cap = QtWidgets.QDoubleSpinBox()
    toolbox.structured_hyperbolic_fraction_cap.setRange(0.05, 0.9)
    toolbox.structured_hyperbolic_fraction_cap.setSingleStep(0.05)
    toolbox.structured_hyperbolic_fraction_cap.setValue(0.5)
    toolbox.structured_hyperbolic_fraction_cap.setToolTip(
        'Maximum wall-to-farfield height fraction the march may reach '
        'before the remainder is filled algebraically onto the '
        'prescribed outer boundary.')
    form.addRow(make_page_label('Hyperbolic march height fraction'),
                toolbox.structured_hyperbolic_fraction_cap)

    toolbox.structured_normal_divisions = QtWidgets.QSpinBox()
    toolbox.structured_normal_divisions.setRange(5, 500)
    toolbox.structured_normal_divisions.setValue(60)
    form.addRow(make_page_label('Normal divisions'),
                toolbox.structured_normal_divisions)

    toolbox.structured_first_layer = QtWidgets.QDoubleSpinBox()
    toolbox.structured_first_layer.setDecimals(5)
    toolbox.structured_first_layer.setRange(1.0e-5, 1.0)
    toolbox.structured_first_layer.setSingleStep(0.001)
    toolbox.structured_first_layer.setValue(0.002)
    form.addRow(make_page_label('First layer thickness'),
                toolbox.structured_first_layer)

    toolbox.structured_wake_points = QtWidgets.QSpinBox()
    toolbox.structured_wake_points.setRange(5, 500)
    toolbox.structured_wake_points.setValue(60)
    form.addRow(make_page_label('Wake points'),
                toolbox.structured_wake_points)

    toolbox.structured_te_base_divisions = QtWidgets.QSpinBox()
    toolbox.structured_te_base_divisions.setRange(0, 200)
    toolbox.structured_te_base_divisions.setSpecialValueText('Auto')
    toolbox.structured_te_base_divisions.setValue(0)
    toolbox.structured_te_base_divisions.setToolTip(
        'Cells across a blunt trailing edge (wake strip for C-mesh, base '
        'for O-grid). Auto matches the contour spacing at the trailing '
        'edge. Ignored for a sharp trailing edge.')
    form.addRow(make_page_label('TE base divisions'),
                toolbox.structured_te_base_divisions)

    toolbox.structured_ortho_layers = QtWidgets.QSpinBox()
    toolbox.structured_ortho_layers.setRange(0, 100)
    toolbox.structured_ortho_layers.setValue(0)
    toolbox.structured_ortho_layers.setToolTip(
        'Exact-normal near-wall layers (0 = off).')
    form.addRow(make_page_label('Ortho layers'),
                toolbox.structured_ortho_layers)

    toolbox.structured_ortho_growth = QtWidgets.QDoubleSpinBox()
    toolbox.structured_ortho_growth.setRange(1.0, 2.0)
    toolbox.structured_ortho_growth.setSingleStep(0.05)
    toolbox.structured_ortho_growth.setValue(1.15)
    form.addRow(make_page_label('Ortho growth'),
                toolbox.structured_ortho_growth)

    toolbox.structured_outer_distribution = QtWidgets.QComboBox()
    toolbox.structured_outer_distribution.addItem('Uniform',
                                                  userData='uniform')
    toolbox.structured_outer_distribution.addItem('Clustered to outlet',
                                                  userData='clustered')
    form.addRow(make_page_label('Outer distribution'),
                toolbox.structured_outer_distribution)

    toolbox.structured_outer_ratio = QtWidgets.QDoubleSpinBox()
    toolbox.structured_outer_ratio.setRange(1.0, 20.0)
    toolbox.structured_outer_ratio.setSingleStep(0.5)
    toolbox.structured_outer_ratio.setValue(2.0)
    form.addRow(make_page_label('Outer clustering ratio'),
                toolbox.structured_outer_ratio)

    toolbox.structured_outer_angle = QtWidgets.QComboBox()
    toolbox.structured_outer_angle.addItem('Free', userData='free')
    toolbox.structured_outer_angle.addItem('Orthogonal',
                                           userData='orthogonal')
    form.addRow(make_page_label('Outer boundary angle'),
                toolbox.structured_outer_angle)

    toolbox.structured_smoother = QtWidgets.QComboBox()
    toolbox.structured_smoother.addItem('None', userData='none')
    toolbox.structured_smoother.addItem('Laplacian', userData='laplacian')
    toolbox.structured_smoother.addItem('Elliptic', userData='elliptic')
    toolbox.structured_smoother.addItem('Angle-based',
                                        userData='angle_based')
    toolbox.structured_smoother.setToolTip(
        'Optional post-smoothing pass; never runs implicitly and never '
        'lowers mesh quality (a degrading pass is reverted).')
    form.addRow(make_page_label('Smoother'), toolbox.structured_smoother)

    toolbox.structured_smoother_iterations = QtWidgets.QSpinBox()
    toolbox.structured_smoother_iterations.setRange(1, 500)
    toolbox.structured_smoother_iterations.setValue(10)
    form.addRow(make_page_label('Smoother iterations'),
                toolbox.structured_smoother_iterations)

    layout.addLayout(form)

    group = QtWidgets.QGroupBox('Structured Grid')
    group.setLayout(layout)

    toolbox.structured_form = form
    toolbox.structured_topology.currentIndexChanged.connect(
        lambda _index=None: _update_structured_algorithm_visibility(toolbox))
    toolbox.structured_te_anchor_mode.currentIndexChanged.connect(
        lambda _index=None: _update_te_anchor_range(toolbox))
    toolbox.structured_algorithm.currentIndexChanged.connect(
        lambda _index=None: _update_structured_algorithm_visibility(toolbox))
    toolbox.structured_tfi_variant.currentIndexChanged.connect(
        lambda _index=None: _update_structured_algorithm_visibility(toolbox))
    toolbox.structured_outer_distribution.currentIndexChanged.connect(
        lambda _index=None: _update_structured_algorithm_visibility(toolbox))
    toolbox.structured_smoother.currentIndexChanged.connect(
        lambda _index=None: _update_structured_algorithm_visibility(toolbox))
    _update_structured_algorithm_visibility(toolbox)

    return group


def _update_te_anchor_range(toolbox):
    spin = toolbox.structured_te_anchor_value
    spin.setValue(0.0)
    if toolbox.structured_te_anchor_mode.currentData() == 'angle':
        spin.setDecimals(1)
        spin.setRange(0.0, 89.0)
        spin.setSingleStep(5.0)
        spin.setSuffix(' °')
        spin.setToolTip(
            'Angle from the vertical through the trailing edge. Clamped so '
            'the downstream lines keep the last 10 % of the wake length '
            'to exit through the tunnel walls.')
    else:
        spin.setSuffix('')
        spin.setRange(0.0, 1.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setToolTip(
            '0 = straight up/down from the trailing edge, 1 = close to the '
            'outlet (the last 10 % of the wake length stays free for the '
            'downstream lines).')


def _update_structured_algorithm_visibility(toolbox):
    """Show only the rows relevant to the selected algorithm, and grey out
    settings that the current algorithm/variant combination ignores."""
    form = toolbox.structured_form
    algorithm = toolbox.structured_algorithm.currentData()
    variant = toolbox.structured_tfi_variant.currentData()
    outer_distribution = toolbox.structured_outer_distribution.currentData()
    smoother = toolbox.structured_smoother.currentData()

    is_c_mesh = toolbox.structured_topology.currentData() == 'c'
    form.setRowVisible(toolbox.structured_te_anchor_mode, is_c_mesh)
    form.setRowVisible(toolbox.structured_te_anchor_value, is_c_mesh)
    form.setRowVisible(toolbox.structured_tfi_variant, algorithm == 'tfi')
    form.setRowVisible(toolbox.structured_elliptic_iterations,
                       algorithm == 'elliptic')
    form.setRowVisible(toolbox.structured_elliptic_relaxation,
                       algorithm == 'elliptic')
    form.setRowVisible(toolbox.structured_hyperbolic_fraction_cap,
                       algorithm == 'hyperbolic')
    form.setRowVisible(toolbox.structured_outer_ratio,
                       outer_distribution == 'clustered')
    form.setRowVisible(toolbox.structured_smoother_iterations,
                       smoother != 'none')

    # Orthogonal outer forcing is only implemented for the Elliptic solver
    # and the Hermite TFI variant; Standard TFI and Hyperbolic marching's
    # algebraic hand-off both ignore boundary_control.angle_mode.
    angle_applies = algorithm == 'elliptic' or (
        algorithm == 'tfi' and variant == 'hermite')
    toolbox.structured_outer_angle.setEnabled(angle_applies)
    toolbox.structured_outer_angle.setToolTip(
        'Forces mesh lines perpendicular onto the farfield boundary.'
        if angle_applies else
        'Only takes effect for the Elliptic algorithm or the Hermite TFI '
        'variant; Standard TFI and Hyperbolic marching ignore this setting.'
    )


def structured_settings_from_toolbox(toolbox):
    import Meshing
    return Meshing.StructuredMeshSettings(
        topology=toolbox.structured_topology.currentData(),
        tunnel_shape=toolbox.structured_tunnel_shape.currentData(),
        tunnel_height=toolbox.structured_tunnel_height.value(),
        wake_length=toolbox.structured_wake_length.value(),
        te_anchor_mode=toolbox.structured_te_anchor_mode.currentData(),
        te_anchor_value=toolbox.structured_te_anchor_value.value(),
        algorithm=toolbox.structured_algorithm.currentData(),
        tfi_variant=toolbox.structured_tfi_variant.currentData(),
        elliptic_iterations=toolbox.structured_elliptic_iterations.value(),
        elliptic_relaxation=toolbox.structured_elliptic_relaxation.value(),
        hyperbolic_fraction_cap=(
            toolbox.structured_hyperbolic_fraction_cap.value()),
        smoother=toolbox.structured_smoother.currentData(),
        smoother_iterations=(
            toolbox.structured_smoother_iterations.value()),
        normal_divisions=toolbox.structured_normal_divisions.value(),
        first_layer_thickness=toolbox.structured_first_layer.value(),
        wake_points=toolbox.structured_wake_points.value(),
        te_base_divisions=toolbox.structured_te_base_divisions.value(),
        ortho_layers=toolbox.structured_ortho_layers.value(),
        ortho_growth=toolbox.structured_ortho_growth.value(),
        boundary_control=Meshing.TunnelBoundaryControl(
            distribution=toolbox.structured_outer_distribution.currentData(),
            clustering_ratio=toolbox.structured_outer_ratio.value(),
            angle_mode=toolbox.structured_outer_angle.currentData(),
        ),
    )


def _build_metric_group(toolbox):
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    intro = QtWidgets.QLabel(
        'Fixed pipeline, not a choice of algorithms: always builds a '
        'sharp-trailing-edge C-mesh in the legacy half-circle / '
        'rectangular wind-tunnel (a blunt contour is rejected — use the '
        'Structured engine for those). Boundary singularities are created '
        'automatically at TE upper, TE lower, wake upper, and wake lower, '
        'with the wake cut collapsing back onto the outlet centerline for '
        'CFD-ready topology. The two fields below document that fixed '
        'setup; the future singularity editor will expose full manual '
        'placement and valence editing on top of this data model.'
    )
    intro.setWordWrap(True)
    intro.setProperty('pageSectionHint', 'true')
    layout.addWidget(intro)

    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    label = make_page_label('Layout family')
    toolbox.metric_layout_strategy = QtWidgets.QComboBox()
    toolbox.metric_layout_strategy.addItem(
        'C-mesh (sharp TE)',
        userData='metric_c_grid',
    )
    toolbox.metric_layout_strategy.setEnabled(False)
    toolbox.metric_layout_strategy.setToolTip(
        'No alternative layout is implemented yet.')
    form.addRow(label, toolbox.metric_layout_strategy)

    label = make_page_label('Singularity model')
    toolbox.metric_singularity_template = QtWidgets.QComboBox()
    toolbox.metric_singularity_template.addItem(
        'Auto boundary singularities',
        userData='auto_boundary_c',
    )
    toolbox.metric_singularity_template.setEnabled(False)
    toolbox.metric_singularity_template.setToolTip(
        'No alternative singularity model is implemented yet.')
    form.addRow(label, toolbox.metric_singularity_template)

    layout.addLayout(form)

    group = QtWidgets.QGroupBox('Metric Based Layout')
    group.setLayout(layout)
    return group


def _build_airfoil_mesh_form(toolbox):
    toolbox.form_mesh_airfoil = QtWidgets.QFormLayout()
    configure_form_layout(toolbox.form_mesh_airfoil)

    label = make_page_label('Points on contour')
    label.setToolTip('Number of points as derived from the prepared contour')
    toolbox.points_on_airfoil = QtWidgets.QLineEdit('0')
    toolbox.points_on_airfoil.setEnabled(False)
    toolbox.form_mesh_airfoil.addRow(label, toolbox.points_on_airfoil)

    label = make_page_label('Normal divisions')
    label.setToolTip(
        'Number of points in the mesh which is constructed  normal to the airfoil contour'
    )
    toolbox.points_n = QtWidgets.QSpinBox()
    toolbox.points_n.setSingleStep(1)
    toolbox.points_n.setRange(1, 500)
    toolbox.points_n.setValue(15)
    toolbox.form_mesh_airfoil.addRow(label, toolbox.points_n)

    label = make_page_label('First layer (m)')
    label.setToolTip('Thickness of 1st cell layer perpendicular to the airfoil')
    toolbox.normal_thickness = QtWidgets.QDoubleSpinBox()
    toolbox.normal_thickness.setSingleStep(0.001)
    toolbox.normal_thickness.setRange(1.e-10, 1.e10)
    toolbox.normal_thickness.setDecimals(8)
    toolbox.normal_thickness.setValue(0.00400)
    toolbox.form_mesh_airfoil.addRow(label, toolbox.normal_thickness)

    label = make_page_label('Growth rate')
    label.setToolTip('Rate at which 1st cell layer grows')
    toolbox.ratio = QtWidgets.QDoubleSpinBox()
    toolbox.ratio.setSingleStep(0.01)
    toolbox.ratio.setRange(1., 100.)
    toolbox.ratio.setValue(1.05)
    toolbox.ratio.setDecimals(3)
    toolbox.form_mesh_airfoil.addRow(label, toolbox.ratio)


def _build_tunnel_mesh_form(toolbox):
    toolbox.form_mesh_tunnel = QtWidgets.QFormLayout()
    configure_form_layout(toolbox.form_mesh_tunnel)

    label = make_page_label('Tunnel height (c)')
    label.setToolTip('The height of the windtunnel in units of chord length')
    toolbox.tunnel_height = QtWidgets.QDoubleSpinBox()
    toolbox.tunnel_height.setSingleStep(0.1)
    toolbox.tunnel_height.setRange(0.1, 100.)
    toolbox.tunnel_height.setValue(3.5)
    toolbox.tunnel_height.setDecimals(1)
    toolbox.form_mesh_tunnel.addRow(label, toolbox.tunnel_height)

    label = make_page_label('Wake divisions')
    label.setToolTip(
        'Number of points traced along each sharp-TE wake branch from the trailing edge to the outlet.'
    )
    toolbox.divisions_height = QtWidgets.QSpinBox()
    toolbox.divisions_height.setSingleStep(5)
    toolbox.divisions_height.setRange(4, 1000)
    toolbox.divisions_height.setValue(80)
    toolbox.form_mesh_tunnel.addRow(label, toolbox.divisions_height)

    label = make_page_label('Wake length (c)')
    label.setToolTip(
        'The length of the wake of the windtunnel in units of chord length'
    )
    toolbox.tunnel_wake = QtWidgets.QDoubleSpinBox()
    toolbox.tunnel_wake.setSingleStep(0.1)
    toolbox.tunnel_wake.setRange(0.1, 100.)
    toolbox.tunnel_wake.setValue(7.0)
    toolbox.tunnel_wake.setDecimals(1)
    toolbox.form_mesh_tunnel.addRow(label, toolbox.tunnel_wake)


def _build_export_group(toolbox):
    label = make_page_label('Boundary names')
    label.setToolTip(
        'Here you can define the names of the boundaries for the mesh export'
    )
    boundary_header = QtWidgets.QGridLayout()
    boundary_header.addWidget(label, 0, 0)

    toolbox.form_bnd = QtWidgets.QFormLayout()
    configure_form_layout(toolbox.form_bnd)
    header_1 = make_page_label('Boundary')
    header_1.setStyleSheet('font-weight: bold;')
    header_2 = make_page_label('Name')
    header_2.setStyleSheet('font-weight: bold;')
    toolbox.form_bnd.addRow(header_1, header_2)

    _add_boundary_name_row(
        toolbox,
        label='Airfoil',
        tooltip='Name of the boundary definition for the airfoil',
        attribute_name='lineedit_airfoil',
        default='Airfoil',
    )
    _add_boundary_name_row(
        toolbox,
        label='Inlet (C-arc)',
        tooltip='Name of the boundary definition for the inlet',
        attribute_name='lineedit_inlet',
        default='Inlet',
    )
    _add_boundary_name_row(
        toolbox,
        label='Outlet',
        tooltip='Name of the boundary definition for the outlet',
        attribute_name='lineedit_outlet',
        default='Outlet',
    )
    _add_boundary_name_row(
        toolbox,
        label='Top',
        tooltip='Name of the boundary definition for the top of the windtunnel',
        attribute_name='lineedit_top',
        default='Top',
    )
    _add_boundary_name_row(
        toolbox,
        label='Bottom',
        tooltip='Name of the boundary definition for the bottom of the windtunnel',
        attribute_name='lineedit_bottom',
        default='Bottom',
    )

    toolbox.check_FIRE = QtWidgets.QCheckBox('AVL FIRE')
    toolbox.check_SU2 = QtWidgets.QCheckBox('SU2')
    toolbox.check_GMSH = QtWidgets.QCheckBox('GMSH')
    toolbox.check_VTU = QtWidgets.QCheckBox('VTU')
    toolbox.check_FIRE.setChecked(True)
    toolbox.check_SU2.setChecked(True)
    toolbox.check_GMSH.setChecked(False)
    toolbox.check_VTU.setChecked(False)

    format_label = make_page_label('Formats')
    format_label.setToolTip('Check format to be exported')
    format_grid = QtWidgets.QGridLayout()
    format_grid.addWidget(format_label, 0, 0)
    format_grid.addWidget(toolbox.check_FIRE, 1, 1)
    format_grid.addWidget(toolbox.check_SU2, 1, 2)
    format_grid.addWidget(toolbox.check_GMSH, 1, 3)
    format_grid.addWidget(toolbox.check_VTU, 2, 1)

    toolbox.exportMeshButton = QtWidgets.QPushButton('Export Mesh')
    toolbox.exportMeshButton.setObjectName('pageSecondaryActionButton')
    export_button_layout = right_aligned_row(toolbox.exportMeshButton)

    group_layout = QtWidgets.QVBoxLayout()
    group_layout.addLayout(boundary_header)
    group_layout.addLayout(toolbox.form_bnd)
    group_layout.addLayout(format_grid)
    group_layout.addLayout(export_button_layout)

    toolbox.box_meshexport = QtWidgets.QGroupBox('Mesh Export')
    toolbox.box_meshexport.setLayout(group_layout)
    toolbox.box_meshexport.setEnabled(False)
    return toolbox.box_meshexport


def _add_boundary_name_row(toolbox, label, tooltip, attribute_name, default):
    widget_label = make_page_label(label, tooltip)
    line_edit = QtWidgets.QLineEdit(default)
    setattr(toolbox, attribute_name, line_edit)
    toolbox.form_bnd.addRow(widget_label, line_edit)
