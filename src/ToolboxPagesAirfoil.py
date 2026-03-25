from PySide6 import QtCore, QtWidgets

import FileSystem
from ToolboxWidgets import (
    configure_form_layout,
    make_page_label,
    right_aligned_row,
)


def build_file_system_panel(toolbox):
    toolbox.item_fs = QtWidgets.QWidget()
    toolbox.item_fs.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Expanding,
    )
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    toolbox.item_fs.setLayout(layout)

    local_root = FileSystem.local_library_root(toolbox.mw)
    source_row = QtWidgets.QHBoxLayout()
    source_row.setSpacing(8)

    toolbox.airfoil_library_source_buttons = {}
    source_group = QtWidgets.QButtonGroup(toolbox.item_fs)
    for label, key, checked in (
        ('Bundled', 'bundled', True),
        ('Local', 'local', False),
        ('All', 'all', False),
    ):
        button = QtWidgets.QRadioButton(label)
        button.setProperty('librarySource', 'true')
        button.setChecked(checked)
        source_group.addButton(button)
        toolbox.airfoil_library_source_buttons[key] = button
        source_row.addWidget(button)
    source_row.addStretch(1)
    layout.addLayout(source_row)

    toolbox.airfoil_library_search = QtWidgets.QLineEdit()
    toolbox.airfoil_library_search.setObjectName('librarySearch')
    toolbox.airfoil_library_search.setPlaceholderText(
        'Search airfoils'
    )
    layout.addWidget(toolbox.airfoil_library_search)

    toolbox.airfoil_library_list = QtWidgets.QListWidget()
    toolbox.airfoil_library_list.setObjectName('airfoilLibraryList')
    toolbox.airfoil_library_list.setSelectionMode(
        QtWidgets.QAbstractItemView.SingleSelection
    )
    layout.addWidget(toolbox.airfoil_library_list, stretch=1)

    footer = QtWidgets.QWidget()
    footer_layout = QtWidgets.QVBoxLayout()
    footer_layout.setContentsMargins(0, 0, 0, 0)
    footer_layout.setSpacing(8)
    footer.setLayout(footer_layout)

    toolbox.airfoil_library_status_label = QtWidgets.QLabel('')
    toolbox.airfoil_library_status_label.setObjectName('libraryMeta')
    toolbox.airfoil_library_status_label.setWordWrap(True)
    toolbox.airfoil_library_status_label.setVisible(False)
    footer_layout.addWidget(toolbox.airfoil_library_status_label)

    action_row = QtWidgets.QHBoxLayout()
    action_row.setSpacing(8)
    toolbox.airfoil_library_open_button = QtWidgets.QPushButton('Open File...')
    toolbox.airfoil_library_open_button.setObjectName('libraryActionButton')
    toolbox.airfoil_library_import_button = QtWidgets.QPushButton('Add To Local...')
    toolbox.airfoil_library_import_button.setObjectName('libraryActionButton')
    toolbox.airfoil_library_import_button.setToolTip(
        f'Copy an external airfoil into {local_root}'
    )
    toolbox.airfoil_library_load_button = QtWidgets.QPushButton('Load Selected')
    toolbox.airfoil_library_load_button.setObjectName('libraryPrimaryButton')
    toolbox.airfoil_library_load_button.setEnabled(False)

    action_row.addWidget(toolbox.airfoil_library_open_button)
    action_row.addWidget(toolbox.airfoil_library_import_button)
    action_row.addStretch(1)
    action_row.addWidget(toolbox.airfoil_library_load_button)
    footer_layout.addLayout(action_row)

    layout.addWidget(footer)

    toolbox.airfoil_library_open_button.clicked.connect(toolbox.mw.slots.onOpen)
    toolbox.airfoil_library_import_button.clicked.connect(
        toolbox.importAirfoilToLocalLibrary
    )
    toolbox.airfoil_library_load_button.clicked.connect(
        toolbox.loadSelectedLibraryAirfoil
    )
    toolbox.airfoil_library_search.textChanged.connect(
        lambda *_: toolbox.refreshAirfoilLibrary()
    )
    for button in toolbox.airfoil_library_source_buttons.values():
        button.toggled.connect(lambda checked, *_: checked and toolbox.refreshAirfoilLibrary())
    toolbox.airfoil_library_list.currentItemChanged.connect(
        toolbox.updateAirfoilLibraryDetails
    )
    toolbox.airfoil_library_list.itemDoubleClicked.connect(
        toolbox.loadSelectedLibraryAirfoil
    )

    toolbox.refreshAirfoilLibrary()


def build_spline_refine_panel(toolbox):
    refine_card, refine_layout = _create_section_card(
        'Refine Contour',
        'Create a smoother working contour before meshing.',
    )

    refine_form = QtWidgets.QFormLayout()
    configure_form_layout(refine_form)

    label = make_page_label(u'Refine tolerance (°)')
    toolbox.tolerance = QtWidgets.QDoubleSpinBox()
    toolbox.tolerance.setSingleStep(0.1)
    toolbox.tolerance.setDecimals(1)
    toolbox.tolerance.setRange(50.0, 177.0)
    toolbox.tolerance.setValue(172.0)
    refine_form.addRow(label, toolbox.tolerance)

    label = make_page_label('Spline points')
    toolbox.points = QtWidgets.QSpinBox()
    toolbox.points.setSingleStep(10)
    toolbox.points.setRange(10, 1000)
    toolbox.points.setValue(200)
    refine_form.addRow(label, toolbox.points)
    refine_layout.addLayout(refine_form)

    refine_advanced_form = QtWidgets.QFormLayout()
    configure_form_layout(refine_advanced_form)

    label = make_page_label(u'TE old segments')
    label.setToolTip(
        'Specify the number of segments at the trailing edge which should be refined.'
    )
    toolbox.ref_te = QtWidgets.QSpinBox()
    toolbox.ref_te.setSingleStep(1)
    toolbox.ref_te.setRange(1, 50)
    toolbox.ref_te.setValue(3)
    refine_advanced_form.addRow(label, toolbox.ref_te)

    label = make_page_label(u'TE new segments')
    toolbox.ref_te_n = QtWidgets.QSpinBox()
    toolbox.ref_te_n.setSingleStep(1)
    toolbox.ref_te_n.setRange(1, 100)
    toolbox.ref_te_n.setValue(6)
    refine_advanced_form.addRow(label, toolbox.ref_te_n)

    label = make_page_label(u'TE ratio')
    toolbox.ref_te_ratio = QtWidgets.QDoubleSpinBox()
    toolbox.ref_te_ratio.setSingleStep(0.1)
    toolbox.ref_te_ratio.setDecimals(1)
    toolbox.ref_te_ratio.setRange(1., 10.)
    toolbox.ref_te_ratio.setValue(3.0)
    refine_advanced_form.addRow(label, toolbox.ref_te_ratio)

    refine_advanced = _create_advanced_widget(refine_advanced_form)
    refine_toggle = _create_advanced_toggle(
        'More refine options',
        refine_advanced,
    )
    refine_layout.addWidget(refine_toggle)
    refine_layout.addWidget(refine_advanced)

    toolbox.splineButton = QtWidgets.QPushButton('Spline and Refine')
    toolbox.splineButton.setObjectName('pagePrimaryActionButton')
    refine_layout.addLayout(right_aligned_row(toolbox.splineButton))

    trailing_card, trailing_layout = _create_section_card(
        'Trailing Edge',
        'Add finite thickness only when the mesh needs it.',
    )

    trailing_form = QtWidgets.QFormLayout()
    configure_form_layout(trailing_form)

    label = make_page_label(u'TE thickness (% chord)')
    toolbox.thickness = QtWidgets.QDoubleSpinBox()
    toolbox.thickness.setSingleStep(0.05)
    toolbox.thickness.setDecimals(2)
    toolbox.thickness.setRange(0.0, 10.0)
    toolbox.thickness.setValue(0.4)
    trailing_form.addRow(label, toolbox.thickness)
    trailing_layout.addLayout(trailing_form)

    trailing_advanced_form = QtWidgets.QFormLayout()
    configure_form_layout(trailing_advanced_form)

    label = make_page_label(u'Upper blend (% chord)')
    toolbox.blend_u = QtWidgets.QDoubleSpinBox()
    toolbox.blend_u.setSingleStep(1.0)
    toolbox.blend_u.setDecimals(1)
    toolbox.blend_u.setRange(0.1, 100.0)
    toolbox.blend_u.setValue(30.0)
    trailing_advanced_form.addRow(label, toolbox.blend_u)

    label = make_page_label(u'Lower blend (% chord)')
    toolbox.blend_l = QtWidgets.QDoubleSpinBox()
    toolbox.blend_l.setSingleStep(1.0)
    toolbox.blend_l.setDecimals(1)
    toolbox.blend_l.setRange(0.1, 100.0)
    toolbox.blend_l.setValue(30.0)
    trailing_advanced_form.addRow(label, toolbox.blend_l)

    label = make_page_label(u'Upper blend exponent')
    toolbox.exponent_u = QtWidgets.QDoubleSpinBox()
    toolbox.exponent_u.setSingleStep(0.1)
    toolbox.exponent_u.setDecimals(1)
    toolbox.exponent_u.setRange(1.0, 10.0)
    toolbox.exponent_u.setValue(3.0)
    trailing_advanced_form.addRow(label, toolbox.exponent_u)

    label = make_page_label(u'Lower blend exponent')
    toolbox.exponent_l = QtWidgets.QDoubleSpinBox()
    toolbox.exponent_l.setSingleStep(0.1)
    toolbox.exponent_l.setDecimals(1)
    toolbox.exponent_l.setRange(1.0, 10.0)
    toolbox.exponent_l.setValue(3.0)
    trailing_advanced_form.addRow(label, toolbox.exponent_l)

    trailing_advanced = _create_advanced_widget(trailing_advanced_form)
    trailing_toggle = _create_advanced_toggle(
        'More TE options',
        trailing_advanced,
    )
    trailing_layout.addWidget(trailing_toggle)
    trailing_layout.addWidget(trailing_advanced)

    toolbox.trailingButton = QtWidgets.QPushButton('Add Trailing Edge')
    toolbox.trailingButton.setObjectName('pagePrimaryActionButton')
    toolbox.trailingButton.setEnabled(False)
    trailing_layout.addLayout(right_aligned_row(toolbox.trailingButton))

    export_card, export_layout = _create_section_card(
        'Export Contour',
        'Save the refined working contour after geometry changes are complete.',
    )
    toolbox.exportContourButton = QtWidgets.QPushButton('Export Contour')
    toolbox.exportContourButton.setObjectName('pageSecondaryActionButton')
    toolbox.exportContourButton.setEnabled(False)
    export_layout.addLayout(right_aligned_row(toolbox.exportContourButton))

    vbl = QtWidgets.QVBoxLayout()
    vbl.setContentsMargins(0, 0, 0, 0)
    vbl.setSpacing(12)
    vbl.addWidget(refine_card)
    vbl.addWidget(trailing_card)
    vbl.addWidget(export_card)
    vbl.addStretch(1)

    toolbox.item_cm = QtWidgets.QWidget()
    toolbox.item_cm.setLayout(vbl)

    toolbox.splineButton.clicked.connect(toolbox.spline_and_refine)
    toolbox.trailingButton.clicked.connect(toolbox.makeTrailingEdge)
    toolbox.exportContourButton.clicked.connect(toolbox.exportContour)


def _create_section_card(title, hint=''):
    card = QtWidgets.QFrame()
    card.setProperty('pageSectionCard', 'true')

    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)
    card.setLayout(layout)

    title_label = QtWidgets.QLabel(title)
    title_label.setProperty('pageSectionTitle', 'true')
    layout.addWidget(title_label)

    if hint:
        hint_label = QtWidgets.QLabel(hint)
        hint_label.setProperty('pageSectionHint', 'true')
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

    return card, layout


def _create_advanced_widget(form_layout):
    widget = QtWidgets.QWidget()
    widget.setVisible(False)
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addLayout(form_layout)
    widget.setLayout(layout)
    return widget


def _create_advanced_toggle(text, target_widget):
    button = QtWidgets.QToolButton()
    button.setText(text)
    button.setCheckable(True)
    button.setChecked(False)
    button.setArrowType(QtCore.Qt.RightArrow)
    button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
    button.setProperty('sectionToggle', 'true')

    def _sync(checked):
        target_widget.setVisible(checked)
        button.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)

    button.toggled.connect(_sync)
    return button
