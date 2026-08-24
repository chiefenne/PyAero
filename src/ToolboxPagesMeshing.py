from PySide6 import QtGui, QtWidgets

from ToolboxWidgets import (
    configure_form_layout,
    make_page_label,
    make_page_radio,
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
    toolbox.mesh_te_group = None
    toolbox.mesh_wake_group = None
    toolbox.mesh_smoothing_group = None
    toolbox.mesh_standard_only_groups = []
    toolbox.mesh_shared_groups = [box_airfoil, box_tunnel]
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

    toolbox.structured_algorithm = QtWidgets.QComboBox()
    toolbox.structured_algorithm.addItem('TFI (standard)',
                                         userData='standard')
    toolbox.structured_algorithm.addItem('TFI (Hermite)',
                                         userData='hermite')
    form.addRow(make_page_label('Algorithm'), toolbox.structured_algorithm)

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

    layout.addLayout(form)

    group = QtWidgets.QGroupBox('Structured Grid')
    group.setLayout(layout)
    return group


def structured_settings_from_toolbox(toolbox):
    import Meshing
    return Meshing.StructuredMeshSettings(
        topology=toolbox.structured_topology.currentData(),
        tunnel_shape=toolbox.structured_tunnel_shape.currentData(),
        tunnel_height=toolbox.structured_tunnel_height.value(),
        wake_length=toolbox.structured_wake_length.value(),
        tfi_variant=toolbox.structured_algorithm.currentData(),
        normal_divisions=toolbox.structured_normal_divisions.value(),
        first_layer_thickness=toolbox.structured_first_layer.value(),
        wake_points=toolbox.structured_wake_points.value(),
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
        'This engine currently builds a sharp-trailing-edge C-mesh in the legacy half-circle / rectangular wind-tunnel. Boundary singularities are created automatically at TE upper, TE lower, wake upper, and wake lower, with the wake cut collapsing back onto the outlet centerline for CFD-ready topology. The future singularity editor will expose full manual placement and valence editing on top of this data model.'
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
    form.addRow(label, toolbox.metric_layout_strategy)

    label = make_page_label('Singularity model')
    toolbox.metric_singularity_template = QtWidgets.QComboBox()
    toolbox.metric_singularity_template.addItem(
        'Auto boundary singularities',
        userData='auto_boundary_c',
    )
    form.addRow(label, toolbox.metric_singularity_template)

    layout.addLayout(form)

    group = QtWidgets.QGroupBox('Metric Based Layout')
    group.setLayout(layout)
    return group


def _build_hybrid_group(toolbox):
    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    label = make_page_label('Layout source')
    label.setToolTip(
        'Stage 4 global layout source. The hybrid engine builds per-element boundary loops, near-wall orthogonal rings, and outer O/C-style connector blocks.'
    )
    toolbox.hybrid_layout_strategy = QtWidgets.QComboBox()
    toolbox.hybrid_layout_strategy.addItem(
        'Multi-element O/C layout',
        userData='multi_element_oc',
    )
    form.addRow(label, toolbox.hybrid_layout_strategy)

    label = make_page_label('Protect wall layers')
    label.setToolTip(
        'Keep the per-element near-wall orthogonal ring blocks out of Stage 2 redistribution and Stage 1 cleanup to preserve wall orthogonality.'
    )
    toolbox.hybrid_protect_near_wall = QtWidgets.QCheckBox(
        'Preserve near-wall rings'
    )
    toolbox.hybrid_protect_near_wall.setChecked(True)
    form.addRow(label, toolbox.hybrid_protect_near_wall)

    label = make_page_label('Stage 2 enabled')
    label.setToolTip(
        'Apply local monitor/metric-based redistribution in the connector blocks while keeping block boundaries fixed.'
    )
    toolbox.hybrid_stage2_enabled = QtWidgets.QCheckBox('Enable redistribution')
    toolbox.hybrid_stage2_enabled.setChecked(True)
    form.addRow(label, toolbox.hybrid_stage2_enabled)

    label = make_page_label('Stage 2 sweeps')
    label.setToolTip(
        'Number of alternating U/V redistribution sweeps.'
    )
    toolbox.hybrid_stage2_sweeps = QtWidgets.QSpinBox()
    toolbox.hybrid_stage2_sweeps.setRange(0, 20)
    toolbox.hybrid_stage2_sweeps.setValue(2)
    form.addRow(label, toolbox.hybrid_stage2_sweeps)

    label = make_page_label('Redistribute U')
    label.setToolTip(
        'Redistribute interior U-lines using boundary-derived size fields.'
    )
    toolbox.hybrid_redistribute_u = QtWidgets.QCheckBox('Use U-lines')
    toolbox.hybrid_redistribute_u.setChecked(True)
    form.addRow(label, toolbox.hybrid_redistribute_u)

    label = make_page_label('Redistribute V')
    label.setToolTip(
        'Redistribute interior V-lines using boundary-derived size fields.'
    )
    toolbox.hybrid_redistribute_v = QtWidgets.QCheckBox('Use V-lines')
    toolbox.hybrid_redistribute_v.setChecked(True)
    form.addRow(label, toolbox.hybrid_redistribute_v)

    label = make_page_label('Stage 1 enabled')
    label.setToolTip(
        'Run a final cleanup pass on the layout-driven mesh after redistribution.'
    )
    toolbox.hybrid_stage1_enabled = QtWidgets.QCheckBox('Enable cleanup')
    toolbox.hybrid_stage1_enabled.setChecked(True)
    form.addRow(label, toolbox.hybrid_stage1_enabled)

    label = make_page_label('Cleanup method')
    label.setToolTip(
        'Final practical optimizer proxy used after redistribution.'
    )
    toolbox.hybrid_stage1_algorithm = QtWidgets.QComboBox()
    toolbox.hybrid_stage1_algorithm.addItem('Angle based', userData='angle_based')
    toolbox.hybrid_stage1_algorithm.addItem('Elliptic', userData='elliptic')
    toolbox.hybrid_stage1_algorithm.addItem('Simple', userData='simple')
    toolbox.hybrid_stage1_algorithm.addItem('None', userData='none')
    form.addRow(label, toolbox.hybrid_stage1_algorithm)

    label = make_page_label('Cleanup iterations')
    toolbox.hybrid_stage1_iterations = QtWidgets.QSpinBox()
    toolbox.hybrid_stage1_iterations.setRange(0, 2000)
    toolbox.hybrid_stage1_iterations.setValue(15)
    form.addRow(label, toolbox.hybrid_stage1_iterations)

    label = make_page_label('Cleanup tolerance')
    toolbox.hybrid_stage1_tolerance = QtWidgets.QLineEdit()
    hybrid_validator = QtGui.QDoubleValidator()
    hybrid_validator.setRange(1.0e-10, 1.0)
    hybrid_validator.setDecimals(10)
    toolbox.hybrid_stage1_tolerance.setValidator(hybrid_validator)
    toolbox.hybrid_stage1_tolerance.setText('1.e-4')
    form.addRow(label, toolbox.hybrid_stage1_tolerance)

    label = make_page_label('Cleanup relaxation')
    label.setToolTip(
        'Under-relaxation used when the cleanup method is elliptic.'
    )
    toolbox.hybrid_stage1_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.hybrid_stage1_relaxation.setSingleStep(0.05)
    toolbox.hybrid_stage1_relaxation.setRange(0.01, 1.0)
    toolbox.hybrid_stage1_relaxation.setDecimals(2)
    toolbox.hybrid_stage1_relaxation.setValue(0.60)
    form.addRow(label, toolbox.hybrid_stage1_relaxation)

    group = QtWidgets.QGroupBox('Hybrid Pipeline (One Shot)')
    group.setLayout(form)
    group.setVisible(False)
    return group


def _build_hybrid_staged_group(toolbox):
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    intro = QtWidgets.QLabel(
        'This staged engine always starts with Stage 4. Run Stage 4 first to inspect the layout-driven mesh, then apply Stage 2 redistribution and Stage 1 cleanup explicitly. The legacy trailing-edge block and legacy smoother controls are not used by this staged path.'
    )
    intro.setWordWrap(True)
    intro.setProperty('pageSectionHint', 'true')
    layout.addWidget(intro)

    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    label = make_page_label('Layout source')
    label.setToolTip(
        'Stage 4 global layout source. This staged path builds per-element boundary loops, near-wall orthogonal rings, and outer O/C-style connector blocks.'
    )
    toolbox.hybrid_staged_layout_strategy = QtWidgets.QComboBox()
    toolbox.hybrid_staged_layout_strategy.addItem(
        'Multi-element O/C layout',
        userData='multi_element_oc',
    )
    form.addRow(label, toolbox.hybrid_staged_layout_strategy)

    label = make_page_label('Protect wall layers')
    label.setToolTip(
        'Keep the per-element near-wall orthogonal ring blocks out of Stage 2 redistribution and Stage 1 cleanup to preserve wall orthogonality.'
    )
    toolbox.hybrid_staged_protect_near_wall = QtWidgets.QCheckBox(
        'Preserve near-wall rings'
    )
    toolbox.hybrid_staged_protect_near_wall.setChecked(True)
    form.addRow(label, toolbox.hybrid_staged_protect_near_wall)

    label = make_page_label('TE closure divisions')
    label.setToolTip(
        'Number of points used to close a blunt trailing edge or an open boundary loop during Stage 4 layout preparation.'
    )
    toolbox.hybrid_staged_te_divisions = QtWidgets.QSpinBox()
    toolbox.hybrid_staged_te_divisions.setRange(1, 40)
    toolbox.hybrid_staged_te_divisions.setValue(3)
    form.addRow(label, toolbox.hybrid_staged_te_divisions)

    layout.addLayout(form)

    toolbox.hybrid_staged_status_label = QtWidgets.QLabel(
        'Stage 4 has not been run yet.'
    )
    toolbox.hybrid_staged_status_label.setWordWrap(True)
    toolbox.hybrid_staged_status_label.setProperty('pageSectionHint', 'true')
    layout.addWidget(toolbox.hybrid_staged_status_label)

    stage4_row = QtWidgets.QHBoxLayout()
    stage4_row.setContentsMargins(0, 0, 0, 0)
    stage4_row.setSpacing(8)
    toolbox.hybridStagedStage4Button = QtWidgets.QPushButton('Run Stage 4')
    toolbox.hybridStagedStage4Button.setObjectName('pagePrimaryActionButton')
    stage4_row.addWidget(toolbox.hybridStagedStage4Button)
    stage4_row.addStretch(1)
    layout.addLayout(stage4_row)

    separator_1 = QtWidgets.QFrame()
    separator_1.setFrameShape(QtWidgets.QFrame.HLine)
    separator_1.setFrameShadow(QtWidgets.QFrame.Sunken)
    layout.addWidget(separator_1)

    stage2_hint = QtWidgets.QLabel(
        'Stage 2 redistributes points on the Stage 4 connectivity without changing the block topology.'
    )
    stage2_hint.setWordWrap(True)
    stage2_hint.setProperty('pageSectionHint', 'true')
    layout.addWidget(stage2_hint)

    stage2_form = QtWidgets.QFormLayout()
    configure_form_layout(stage2_form)

    label = make_page_label('Stage 2 sweeps')
    toolbox.hybrid_staged_stage2_sweeps = QtWidgets.QSpinBox()
    toolbox.hybrid_staged_stage2_sweeps.setRange(1, 20)
    toolbox.hybrid_staged_stage2_sweeps.setValue(2)
    stage2_form.addRow(label, toolbox.hybrid_staged_stage2_sweeps)

    label = make_page_label('Redistribute U')
    toolbox.hybrid_staged_redistribute_u = QtWidgets.QCheckBox('Use U-lines')
    toolbox.hybrid_staged_redistribute_u.setChecked(True)
    stage2_form.addRow(label, toolbox.hybrid_staged_redistribute_u)

    label = make_page_label('Redistribute V')
    toolbox.hybrid_staged_redistribute_v = QtWidgets.QCheckBox('Use V-lines')
    toolbox.hybrid_staged_redistribute_v.setChecked(True)
    stage2_form.addRow(label, toolbox.hybrid_staged_redistribute_v)

    layout.addLayout(stage2_form)

    stage2_row = QtWidgets.QHBoxLayout()
    stage2_row.setContentsMargins(0, 0, 0, 0)
    stage2_row.setSpacing(8)
    toolbox.hybridStagedStage2Button = QtWidgets.QPushButton('Apply Stage 2')
    toolbox.hybridStagedStage2Button.setObjectName('pageSecondaryActionButton')
    stage2_row.addWidget(toolbox.hybridStagedStage2Button)
    stage2_row.addStretch(1)
    layout.addLayout(stage2_row)

    separator_2 = QtWidgets.QFrame()
    separator_2.setFrameShape(QtWidgets.QFrame.HLine)
    separator_2.setFrameShadow(QtWidgets.QFrame.Sunken)
    layout.addWidget(separator_2)

    stage1_hint = QtWidgets.QLabel(
        'Stage 1 runs the final cleanup pass on the current staged mesh.'
    )
    stage1_hint.setWordWrap(True)
    stage1_hint.setProperty('pageSectionHint', 'true')
    layout.addWidget(stage1_hint)

    stage1_form = QtWidgets.QFormLayout()
    configure_form_layout(stage1_form)

    label = make_page_label('Cleanup method')
    toolbox.hybrid_staged_stage1_algorithm = QtWidgets.QComboBox()
    toolbox.hybrid_staged_stage1_algorithm.addItem(
        'Angle based',
        userData='angle_based',
    )
    toolbox.hybrid_staged_stage1_algorithm.addItem(
        'Elliptic',
        userData='elliptic',
    )
    toolbox.hybrid_staged_stage1_algorithm.addItem(
        'Simple',
        userData='simple',
    )
    toolbox.hybrid_staged_stage1_algorithm.addItem(
        'None',
        userData='none',
    )
    stage1_form.addRow(label, toolbox.hybrid_staged_stage1_algorithm)

    label = make_page_label('Cleanup iterations')
    toolbox.hybrid_staged_stage1_iterations = QtWidgets.QSpinBox()
    toolbox.hybrid_staged_stage1_iterations.setRange(0, 2000)
    toolbox.hybrid_staged_stage1_iterations.setValue(15)
    stage1_form.addRow(label, toolbox.hybrid_staged_stage1_iterations)

    label = make_page_label('Cleanup tolerance')
    toolbox.hybrid_staged_stage1_tolerance = QtWidgets.QLineEdit()
    hybrid_validator = QtGui.QDoubleValidator()
    hybrid_validator.setRange(1.0e-10, 1.0)
    hybrid_validator.setDecimals(10)
    toolbox.hybrid_staged_stage1_tolerance.setValidator(hybrid_validator)
    toolbox.hybrid_staged_stage1_tolerance.setText('1.e-4')
    stage1_form.addRow(label, toolbox.hybrid_staged_stage1_tolerance)

    label = make_page_label('Cleanup relaxation')
    toolbox.hybrid_staged_stage1_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.hybrid_staged_stage1_relaxation.setSingleStep(0.05)
    toolbox.hybrid_staged_stage1_relaxation.setRange(0.01, 1.0)
    toolbox.hybrid_staged_stage1_relaxation.setDecimals(2)
    toolbox.hybrid_staged_stage1_relaxation.setValue(0.60)
    stage1_form.addRow(label, toolbox.hybrid_staged_stage1_relaxation)

    layout.addLayout(stage1_form)

    stage1_row = QtWidgets.QHBoxLayout()
    stage1_row.setContentsMargins(0, 0, 0, 0)
    stage1_row.setSpacing(8)
    toolbox.hybridStagedStage1Button = QtWidgets.QPushButton('Apply Stage 1')
    toolbox.hybridStagedStage1Button.setObjectName('pageSecondaryActionButton')
    stage1_row.addWidget(toolbox.hybridStagedStage1Button)
    stage1_row.addStretch(1)
    layout.addLayout(stage1_row)

    group = QtWidgets.QGroupBox('Hybrid Pipeline (Staged 4 -> 2 -> 1)')
    group.setLayout(layout)
    group.setVisible(False)
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


def _build_trailing_edge_mesh_form(toolbox):
    toolbox.form_mesh_TE = QtWidgets.QFormLayout()
    configure_form_layout(toolbox.form_mesh_TE)

    label = make_page_label(u'TE divisions')
    label.setToolTip('Number of subdivisions along the vertical part of the TE')
    toolbox.te_div = QtWidgets.QSpinBox()
    toolbox.te_div.setSingleStep(1)
    toolbox.te_div.setRange(1, 20)
    toolbox.te_div.setValue(3)
    toolbox.form_mesh_TE.addRow(label, toolbox.te_div)

    label = make_page_label(u'Downstream divisions')
    label.setToolTip('Number of subdivisions downstream within the TE block')
    toolbox.points_te = QtWidgets.QSpinBox()
    toolbox.points_te.setSingleStep(1)
    toolbox.points_te.setRange(1, 100)
    toolbox.points_te.setValue(15)
    toolbox.form_mesh_TE.addRow(label, toolbox.points_te)

    label = make_page_label('First layer (m)')
    label.setToolTip('Thickness of first cell layer in downstream direction')
    toolbox.length_te = QtWidgets.QDoubleSpinBox()
    toolbox.length_te.setSingleStep(0.001)
    toolbox.length_te.setRange(1.e-10, 1.e10)
    toolbox.length_te.setDecimals(8)
    toolbox.length_te.setValue(0.00400)
    toolbox.form_mesh_TE.addRow(label, toolbox.length_te)

    label = make_page_label('Growth rate')
    label.setToolTip('Rate at which 1st cell layer downstream the TE grows')
    toolbox.ratio_te = QtWidgets.QDoubleSpinBox()
    toolbox.ratio_te.setSingleStep(0.01)
    toolbox.ratio_te.setRange(1., 100.)
    toolbox.ratio_te.setValue(1.05)
    toolbox.ratio_te.setDecimals(3)
    toolbox.form_mesh_TE.addRow(label, toolbox.ratio_te)


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


def _build_experimental_c_group(toolbox):
    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    label = make_page_label('Surface points')
    label.setToolTip(
        'Use the prepared contour point count when set to 0, or resample the contour for the experimental C-grid'
    )
    toolbox.experimental_surface_points = QtWidgets.QSpinBox()
    toolbox.experimental_surface_points.setRange(0, 5000)
    toolbox.experimental_surface_points.setValue(0)
    toolbox.experimental_surface_points.setSpecialValueText('Prepared contour')
    form.addRow(label, toolbox.experimental_surface_points)

    label = make_page_label('Normal divisions')
    label.setToolTip('Number of cells between the airfoil and farfield')
    toolbox.experimental_normal_divisions = QtWidgets.QSpinBox()
    toolbox.experimental_normal_divisions.setRange(4, 2000)
    toolbox.experimental_normal_divisions.setValue(100)
    form.addRow(label, toolbox.experimental_normal_divisions)

    label = make_page_label('First layer (m)')
    label.setToolTip('Target first-layer wall spacing for the experimental grid')
    toolbox.experimental_first_layer = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_first_layer.setSingleStep(0.001)
    toolbox.experimental_first_layer.setRange(1.0e-10, 1.0e10)
    toolbox.experimental_first_layer.setDecimals(8)
    toolbox.experimental_first_layer.setValue(0.00400)
    form.addRow(label, toolbox.experimental_first_layer)

    label = make_page_label('Wake points')
    label.setToolTip(
        'Number of points along each wake branch, including the trailing edge and wake cut point'
    )
    toolbox.experimental_wake_points = QtWidgets.QSpinBox()
    toolbox.experimental_wake_points.setRange(4, 2000)
    toolbox.experimental_wake_points.setValue(75)
    form.addRow(label, toolbox.experimental_wake_points)

    label = make_page_label('Farfield wake len')
    label.setToolTip(
        'Outer-boundary wake length ratio relative to the inner wake length'
    )
    toolbox.experimental_farfield_wake_length_ratio = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_farfield_wake_length_ratio.setSingleStep(0.05)
    toolbox.experimental_farfield_wake_length_ratio.setRange(0.05, 1.00)
    toolbox.experimental_farfield_wake_length_ratio.setDecimals(2)
    toolbox.experimental_farfield_wake_length_ratio.setValue(1.00)
    form.addRow(label, toolbox.experimental_farfield_wake_length_ratio)

    label = make_page_label('Farfield wake start')
    label.setToolTip(
        'Initial farfield wake spacing as a multiple of the inner wake spacing near the trailing edge'
    )
    toolbox.experimental_farfield_wake_start_ratio = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_farfield_wake_start_ratio.setSingleStep(0.5)
    toolbox.experimental_farfield_wake_start_ratio.setRange(1.0, 100.0)
    toolbox.experimental_farfield_wake_start_ratio.setDecimals(1)
    toolbox.experimental_farfield_wake_start_ratio.setValue(10.0)
    form.addRow(label, toolbox.experimental_farfield_wake_start_ratio)

    label = make_page_label('Initial smooth')
    label.setToolTip('Initial elliptic smoothing passes before wall-normal respacing')
    toolbox.experimental_initial_smoothing = QtWidgets.QSpinBox()
    toolbox.experimental_initial_smoothing.setRange(0, 5000)
    toolbox.experimental_initial_smoothing.setValue(100)
    form.addRow(label, toolbox.experimental_initial_smoothing)

    label = make_page_label('Final smooth')
    label.setToolTip('Final elliptic smoothing passes after wall-normal respacing')
    toolbox.experimental_final_smoothing = QtWidgets.QSpinBox()
    toolbox.experimental_final_smoothing.setRange(0, 5000)
    toolbox.experimental_final_smoothing.setValue(20)
    form.addRow(label, toolbox.experimental_final_smoothing)

    label = make_page_label('Local TE smooth')
    label.setToolTip(
        'Elliptic smoothing passes for the local finite trailing-edge bridge block'
    )
    toolbox.experimental_local_te_smoothing = QtWidgets.QSpinBox()
    toolbox.experimental_local_te_smoothing.setRange(0, 5000)
    toolbox.experimental_local_te_smoothing.setValue(10)
    form.addRow(label, toolbox.experimental_local_te_smoothing)

    label = make_page_label('Tolerance')
    toolbox.experimental_smoothing_tolerance = QtWidgets.QLineEdit()
    experimental_validator = QtGui.QDoubleValidator()
    experimental_validator.setRange(1.0e-10, 1.0)
    experimental_validator.setDecimals(10)
    toolbox.experimental_smoothing_tolerance.setValidator(experimental_validator)
    toolbox.experimental_smoothing_tolerance.setText('1.e-5')
    form.addRow(label, toolbox.experimental_smoothing_tolerance)

    label = make_page_label('Relaxation')
    label.setToolTip('Under-relaxation for the experimental elliptic update')
    toolbox.experimental_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_relaxation.setSingleStep(0.05)
    toolbox.experimental_relaxation.setRange(0.01, 1.0)
    toolbox.experimental_relaxation.setDecimals(2)
    toolbox.experimental_relaxation.setValue(0.60)
    form.addRow(label, toolbox.experimental_relaxation)

    group = QtWidgets.QGroupBox('Experimental C-grid')
    group.setLayout(form)
    group.setVisible(False)
    return group


def _build_experimental_o_group(toolbox):
    form = QtWidgets.QFormLayout()
    configure_form_layout(form)

    label = make_page_label('Surface points')
    label.setToolTip(
        'Use the prepared contour point count when set to 0, or resample the contour for the experimental O-grid'
    )
    toolbox.experimental_o_surface_points = QtWidgets.QSpinBox()
    toolbox.experimental_o_surface_points.setRange(0, 5000)
    toolbox.experimental_o_surface_points.setValue(0)
    toolbox.experimental_o_surface_points.setSpecialValueText('Prepared contour')
    form.addRow(label, toolbox.experimental_o_surface_points)

    label = make_page_label('Normal divisions')
    label.setToolTip('Number of cells between the airfoil and farfield')
    toolbox.experimental_o_normal_divisions = QtWidgets.QSpinBox()
    toolbox.experimental_o_normal_divisions.setRange(4, 2000)
    toolbox.experimental_o_normal_divisions.setValue(100)
    form.addRow(label, toolbox.experimental_o_normal_divisions)

    label = make_page_label('First layer (m)')
    label.setToolTip('Target first-layer wall spacing for the experimental O-grid')
    toolbox.experimental_o_first_layer = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_o_first_layer.setSingleStep(0.001)
    toolbox.experimental_o_first_layer.setRange(1.0e-10, 1.0e10)
    toolbox.experimental_o_first_layer.setDecimals(8)
    toolbox.experimental_o_first_layer.setValue(0.00400)
    form.addRow(label, toolbox.experimental_o_first_layer)

    label = make_page_label('Farfield')
    label.setToolTip(
        'Choose a wind-tunnel outer boundary or a circular farfield. The circular option uses tunnel height and ignores wake length.'
    )
    toolbox.experimental_o_farfield_shape = QtWidgets.QComboBox()
    toolbox.experimental_o_farfield_shape.addItem(
        'Wind tunnel',
        userData='wind_tunnel',
    )
    toolbox.experimental_o_farfield_shape.addItem(
        'Circle',
        userData='circle',
    )
    form.addRow(label, toolbox.experimental_o_farfield_shape)

    label = make_page_label('Initial smooth')
    label.setToolTip('Initial elliptic smoothing passes before wall-normal respacing')
    toolbox.experimental_o_initial_smoothing = QtWidgets.QSpinBox()
    toolbox.experimental_o_initial_smoothing.setRange(0, 5000)
    toolbox.experimental_o_initial_smoothing.setValue(100)
    form.addRow(label, toolbox.experimental_o_initial_smoothing)

    label = make_page_label('Final smooth')
    label.setToolTip('Final elliptic smoothing passes after wall-normal respacing')
    toolbox.experimental_o_final_smoothing = QtWidgets.QSpinBox()
    toolbox.experimental_o_final_smoothing.setRange(0, 5000)
    toolbox.experimental_o_final_smoothing.setValue(20)
    form.addRow(label, toolbox.experimental_o_final_smoothing)

    label = make_page_label('Tolerance')
    toolbox.experimental_o_smoothing_tolerance = QtWidgets.QLineEdit()
    experimental_validator = QtGui.QDoubleValidator()
    experimental_validator.setRange(1.0e-10, 1.0)
    experimental_validator.setDecimals(10)
    toolbox.experimental_o_smoothing_tolerance.setValidator(experimental_validator)
    toolbox.experimental_o_smoothing_tolerance.setText('1.e-5')
    form.addRow(label, toolbox.experimental_o_smoothing_tolerance)

    label = make_page_label('Relaxation')
    label.setToolTip('Under-relaxation for the experimental elliptic update')
    toolbox.experimental_o_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.experimental_o_relaxation.setSingleStep(0.05)
    toolbox.experimental_o_relaxation.setRange(0.01, 1.0)
    toolbox.experimental_o_relaxation.setDecimals(2)
    toolbox.experimental_o_relaxation.setValue(0.60)
    form.addRow(label, toolbox.experimental_o_relaxation)

    group = QtWidgets.QGroupBox('Experimental O-grid')
    group.setLayout(form)
    group.setVisible(False)
    return group


def _build_smoothing_group(toolbox):
    toolbox.btn_smoother_1 = make_page_radio('Simple')
    toolbox.btn_smoother_2 = make_page_radio('Elliptic')
    toolbox.btn_smoother_3 = make_page_radio('Angle based')
    toolbox.btn_smoother_1.setChecked(True)
    toolbox.smoothing_algorithm = 'simple'

    toolbox.btn_smoother_1.clicked.connect(toolbox.smoother_btn_clicked)
    toolbox.btn_smoother_2.clicked.connect(toolbox.smoother_btn_clicked)
    toolbox.btn_smoother_3.clicked.connect(toolbox.smoother_btn_clicked)

    smoother_settings = QtWidgets.QFormLayout()
    configure_form_layout(smoother_settings)

    label = make_page_label('Iterations')
    toolbox.smoother_iterations = QtWidgets.QSpinBox()
    toolbox.smoother_iterations.setValue(100)
    toolbox.smoother_iterations.setSingleStep(5)
    toolbox.smoother_iterations.setRange(0, 1000)
    toolbox.smoother_iterations.setEnabled(False)
    smoother_settings.addRow(label, toolbox.smoother_iterations)

    label = make_page_label('Tolerance')
    toolbox.smoother_tolerance = QtWidgets.QLineEdit()
    toolbox.onlyFloat = QtGui.QDoubleValidator()
    toolbox.smoother_tolerance.setValidator(toolbox.onlyFloat)
    toolbox.smoother_tolerance.setText('1.e-5')
    toolbox.onlyFloat.setRange(1.e-8, 1.0)
    toolbox.onlyFloat.setDecimals(8)
    toolbox.smoother_tolerance.setEnabled(False)
    smoother_settings.addRow(label, toolbox.smoother_tolerance)

    label = make_page_label('Outer slide')
    label.setToolTip(
        'Allow the farfield boundary to slide tangentially on its exact geometry during elliptic smoothing'
    )
    toolbox.outer_boundary_slide = QtWidgets.QDoubleSpinBox()
    toolbox.outer_boundary_slide.setSingleStep(0.05)
    toolbox.outer_boundary_slide.setRange(0.0, 1.0)
    toolbox.outer_boundary_slide.setValue(1.00)
    toolbox.outer_boundary_slide.setDecimals(2)
    toolbox.outer_boundary_slide.setEnabled(False)
    smoother_settings.addRow(label, toolbox.outer_boundary_slide)

    label = make_page_label('Relaxation')
    label.setToolTip('Under-relaxation of the elliptic interior update')
    toolbox.elliptic_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.elliptic_relaxation.setSingleStep(0.05)
    toolbox.elliptic_relaxation.setRange(0.01, 1.0)
    toolbox.elliptic_relaxation.setValue(1.00)
    toolbox.elliptic_relaxation.setDecimals(2)
    toolbox.elliptic_relaxation.setEnabled(False)
    smoother_settings.addRow(label, toolbox.elliptic_relaxation)

    label = make_page_label('Guide relax')
    label.setToolTip('How strongly the tunnel follows the protected airfoil/TE interface guide')
    toolbox.protected_guide_relaxation = QtWidgets.QDoubleSpinBox()
    toolbox.protected_guide_relaxation.setSingleStep(0.05)
    toolbox.protected_guide_relaxation.setRange(0.0, 1.0)
    toolbox.protected_guide_relaxation.setValue(0.25)
    toolbox.protected_guide_relaxation.setDecimals(2)
    toolbox.protected_guide_relaxation.setEnabled(False)
    smoother_settings.addRow(label, toolbox.protected_guide_relaxation)

    label = make_page_label('Guide layers')
    label.setToolTip('Number of tunnel layers influenced by the protected guide')
    toolbox.protected_guide_layers = QtWidgets.QSpinBox()
    toolbox.protected_guide_layers.setSingleStep(1)
    toolbox.protected_guide_layers.setRange(1, 20)
    toolbox.protected_guide_layers.setValue(8)
    toolbox.protected_guide_layers.setEnabled(False)
    smoother_settings.addRow(label, toolbox.protected_guide_layers)

    label = make_page_label('Guide decay')
    label.setToolTip('Decay of guide influence away from the protected interface')
    toolbox.protected_guide_decay = QtWidgets.QDoubleSpinBox()
    toolbox.protected_guide_decay.setSingleStep(0.05)
    toolbox.protected_guide_decay.setRange(0.0, 1.0)
    toolbox.protected_guide_decay.setValue(0.20)
    toolbox.protected_guide_decay.setDecimals(2)
    toolbox.protected_guide_decay.setEnabled(False)
    smoother_settings.addRow(label, toolbox.protected_guide_decay)

    label = make_page_label('Guide smooth')
    label.setToolTip('Smoothing passes for the protected guide profile along the interface')
    toolbox.protected_guide_smoothing = QtWidgets.QSpinBox()
    toolbox.protected_guide_smoothing.setSingleStep(1)
    toolbox.protected_guide_smoothing.setRange(0, 20)
    toolbox.protected_guide_smoothing.setValue(15)
    toolbox.protected_guide_smoothing.setEnabled(False)
    smoother_settings.addRow(label, toolbox.protected_guide_smoothing)

    radio_layout = QtWidgets.QVBoxLayout()
    radio_layout.addWidget(toolbox.btn_smoother_1)
    radio_layout.addWidget(toolbox.btn_smoother_2)
    radio_layout.addWidget(toolbox.btn_smoother_3)

    group_layout = QtWidgets.QHBoxLayout()
    group_layout.addLayout(radio_layout)
    group_layout.addLayout(smoother_settings)

    group = QtWidgets.QGroupBox('Smoothing')
    group.setLayout(group_layout)
    return group


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
