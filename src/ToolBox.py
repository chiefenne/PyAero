# -*- coding: utf-8 -*-

import os
import shutil
from string import Template

from PySide6 import QtCore, QtGui, QtWidgets

from CSTAirfoil import (
    METHOD_BSPLINE,
    METHOD_CST_MODIFIED,
    cst_parameters_from_spline_data,
    format_cst_parameters_text,
)
import FileSystem
import FileDialog
import FileOperations
import Icons
import Meshing
import MeshBuilders
import ToolboxBoundaryConditions
import ToolboxPages
import ToolboxServices
from ToolboxWidgets import PAGE_BODY_WIDTH, WorkflowStepButton
from Utils import get_main_window

import logging
logger = logging.getLogger(__name__)


class Toolbox(QtWidgets.QWidget):
    currentChanged = QtCore.Signal(int)

    def __init__(self):
        """Workflow-oriented sidebar for PyAero."""
        super().__init__()

        self.mw = get_main_window()
        self.wind_tunnel = None
        self.workflow = None
        self._current_index = -1
        self._last_workflow_index = 0
        self._page_titles = []
        self._page_descriptions = []
        self._page_buttons = []

        self._buildShell()

        ToolboxPages.build_file_system_panel(self)
        ToolboxPages.build_aerodynamics_panel(self)
        ToolboxPages.build_boundary_conditions_panel(self)
        ToolboxPages.build_contour_analysis_panel(self)
        ToolboxPages.build_spline_refine_panel(self)
        ToolboxPages.build_meshing_panel(self)

        self.makeToolbox()
        self.workflow = ToolboxServices.ToolboxWorkflowController(self, self.mw)

        self.currentChanged.connect(self.toolboxChanged)
        self.refreshWorkflowState()

    def _buildShell(self):
        palette = {
            'airfoil_bg': '#fdf8fb',
            'airfoil_border': '#e7dae4',
            'airfoil_inner_bg': '#f6edf3',
            'airfoil_inner_border': '#dccad6',
            'airfoil_title': '#926178',
            'airfoil_hover_border': '#c9a7b8',
            'workflow_bg': '#f5fbfc',
            'workflow_border': '#d6e8ea',
            'workflow_title': '#4f7e84',
            'workflow_hover': '#edf7f8',
            'current_bg': '#f7fbf5',
            'current_border': '#d8e4d0',
            'current_title': '#667d52',
            'current_subtitle': '#718562',
            'current_nav_bg': '#eef5e8',
            'current_nav_border': '#cadabf',
            'current_nav_accent': '#84aa67',
            'current_nav_text': '#4b623d',
        }
        style = Template("""
            QWidget {
                color: #1f2933;
            }
            QLabel#sectionTitle,
            QLabel#summaryEyebrow,
            QLabel#pageTitle {
                color: #6b7788;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.08em;
            }
            QFrame#workflowSummaryCard[paneTone="airfoil"] {
                background: $airfoil_bg;
                border: 1px solid $airfoil_border;
                border-radius: 12px;
            }
            QFrame#workflowSummaryCard[paneTone="airfoil"] QLabel#summaryEyebrow {
                color: $airfoil_title;
            }
            QFrame#workflowSummaryCard[paneTone="airfoil"] QPushButton#summaryActionButton {
                border-color: $airfoil_inner_border;
            }
            QFrame#workflowSummaryCard[paneTone="airfoil"] QPushButton#summaryActionButton:hover {
                background: #fffafc;
                border-color: $airfoil_hover_border;
            }
            QFrame#summaryNameCard[paneTone="airfoil"] {
                background: $airfoil_inner_bg;
                border: 1px solid $airfoil_inner_border;
                border-radius: 10px;
            }
            QLabel#summaryName {
                color: #203244;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#summaryMeta {
                color: #5f6c78;
                font-size: 12px;
            }
            QLabel#summaryStatus {
                color: #314154;
                font-size: 12px;
            }
            QPushButton#summaryActionButton {
                background: #ffffff;
                border: 1px solid #d8e3ee;
                border-radius: 8px;
                color: #223041;
                font-weight: 600;
                padding: 6px 10px;
            }
            QPushButton#summaryActionButton:hover {
                background: #f6fafc;
                border-color: #abc3d9;
            }
            QPushButton#summaryActionButton:disabled {
                color: #8a97a8;
                background: #f5f7fa;
                border-color: #e5ebf1;
            }
            QFrame#workflowNavCard[paneTone="workflow"] {
                background: $workflow_bg;
                border: 1px solid $workflow_border;
                border-radius: 12px;
            }
            QFrame#workflowNavCard[paneTone="workflow"] QLabel#sectionTitle {
                color: $workflow_title;
            }
            QFrame#workflowNavCard[paneTone="workflow"] QPushButton[navRole="step"] {
                background: transparent;
                border: none;
                border-radius: 8px;
                border-left: 0px solid transparent;
                color: #6b7788;
                font-weight: 600;
                text-align: left;
                padding: 11px 12px 11px 18px;
            }
            QFrame#workflowNavCard[paneTone="workflow"] QPushButton[navRole="step"]:hover {
                background: $workflow_hover;
            }
            QFrame#workflowNavCard[paneTone="workflow"] QPushButton[navRole="step"]:checked {
                background: $current_nav_bg;
                border-top: 1px solid $current_nav_border;
                border-right: 1px solid $current_nav_border;
                border-bottom: 1px solid $current_nav_border;
                border-left: 10px solid $current_nav_accent;
                color: $current_nav_text;
                font-weight: 700;
                padding: 11px 12px 11px 10px;
            }
            QFrame#workflowNavCard[paneTone="workflow"] QPushButton[navRole="step"][workflowStatus="disabled"] {
                color: #6b7788;
            }
            QFrame#workflowPageCard[paneTone="current"] {
                background: $current_bg;
                border: 1px solid $current_border;
                border-radius: 12px;
            }
            QFrame#workflowPageCard[paneTone="current"] QLabel#pageTitle {
                color: $current_title;
            }
            QFrame#workflowPageCard[paneTone="current"] QLabel#pageSubtitle {
                color: $current_subtitle;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #e1e9f0;
                border-radius: 10px;
                margin-top: 15px;
                padding: 14px 14px 12px 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 4px;
                color: #62778b;
                font-size: 12px;
                font-weight: 700;
            }
            QLineEdit,
            QTextEdit,
            QSpinBox,
            QDoubleSpinBox,
            QComboBox {
                background: #fbfdff;
                border: 1px solid #d7e2ed;
                border-radius: 6px;
                padding: 6px 8px;
                selection-background-color: #dcecf7;
                selection-color: #1d3248;
            }
            QLineEdit:focus,
            QTextEdit:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QComboBox:focus {
                background: #ffffff;
                border-color: #9fbfda;
            }
            QLabel#pageSubtitle {
                color: #66778c;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel[pageFieldLabel="true"] {
                color: #506273;
                font-size: 12px;
                font-weight: 600;
            }
            QCheckBox[pageOption="true"],
            QRadioButton[pageChoice="true"] {
                color: #31475c;
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }
            QCheckBox[pageOption="true"]::indicator,
            QRadioButton[pageChoice="true"]::indicator {
                width: 14px;
                height: 14px;
            }
            QTextEdit#pageTextPanel {
                background: #fcfdff;
                border: 1px solid #d7e2ed;
                border-radius: 8px;
                color: #213142;
            }
            QLabel#librarySelection {
                color: #16212d;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#libraryMeta {
                color: #5e6d7f;
                font-size: 12px;
            }
            QRadioButton[librarySource="true"] {
                background: #ffffff;
                border: 1px solid #d7e2ed;
                border-radius: 8px;
                color: #223041;
                font-weight: 600;
                padding: 6px 12px;
            }
            QRadioButton[librarySource="true"]::indicator {
                width: 0px;
                height: 0px;
            }
            QRadioButton[librarySource="true"]:hover {
                border-color: #abc3d9;
            }
            QRadioButton[librarySource="true"]:checked {
                background: #eef6fb;
                border-color: #bdd3e3;
                color: #1c2c40;
            }
            QComboBox#librarySourceCombo {
                background: #ffffff;
                border: 1px solid #d9d7d1;
                border-radius: 4px;
                color: #223041;
                font-weight: 600;
                min-width: 120px;
                padding: 6px 30px 6px 10px;
            }
            QComboBox#librarySourceCombo:hover {
                border-color: #bca88d;
            }
            QLineEdit#librarySearch {
                background: #ffffff;
                border: 1px solid #d7e2ed;
                border-radius: 8px;
                padding: 8px 10px;
            }
            QListWidget#airfoilLibraryList {
                background: #fdfefd;
                border: 1px solid #dbe7ef;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget#airfoilLibraryList::item {
                border-bottom: 1px solid #e7eff5;
                padding: 8px 10px;
            }
            QListWidget#airfoilLibraryList::item:selected {
                background: #edf6fb;
                color: #1c2c40;
            }
            QPushButton#libraryActionButton,
            QPushButton#libraryPrimaryButton {
                background: #ffffff;
                border: 1px solid #d7e2ed;
                border-radius: 8px;
                color: #223041;
                font-weight: 600;
                padding: 7px 12px;
            }
            QPushButton#libraryActionButton:hover,
            QPushButton#libraryPrimaryButton:hover {
                border-color: #abc3d9;
                background: #f7fbfe;
            }
            QPushButton#libraryPrimaryButton {
                background: #eef6fb;
                border-color: #bdd3e3;
                color: #1c2c40;
            }
            QPushButton#libraryPrimaryButton:disabled {
                background: #f5f7fa;
                border-color: #e5ebf1;
                color: #8a97a8;
            }
            QFrame[pageSectionCard="true"] {
                background: #ffffff;
                border: 1px solid #e1e9f0;
                border-radius: 10px;
            }
            QLabel[pageSectionTitle="true"] {
                color: #1b2a3a;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel[pageSectionHint="true"] {
                color: #66778c;
                font-size: 12px;
            }
            QToolButton[sectionToggle="true"] {
                background: transparent;
                border: none;
                color: #4f6174;
                font-weight: 600;
                padding: 4px 0;
                text-align: left;
            }
            QToolButton[sectionToggle="true"]:hover {
                color: #223041;
            }
            QPushButton#pagePrimaryActionButton,
            QPushButton#pageSecondaryActionButton {
                border-radius: 8px;
                font-weight: 600;
                padding: 8px 14px;
            }
            QPushButton#pagePrimaryActionButton {
                background: #eef6fb;
                border: 1px solid #bdd3e3;
                color: #1c2c40;
            }
            QPushButton#pagePrimaryActionButton:hover {
                background: #f7fbfe;
                border-color: #9ebbd3;
            }
            QPushButton#pageSecondaryActionButton {
                background: #ffffff;
                border: 1px solid #d7e2ed;
                color: #223041;
            }
            QPushButton#pageSecondaryActionButton:hover {
                border-color: #abc3d9;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QWidget#workflowPageBody {
                background: transparent;
            }
        """).substitute(palette)
        self.setStyleSheet(style)

        self.summary_card = self._buildSummaryCard()
        self.summary_card.setProperty('paneTone', 'airfoil')

        self.workflow_steps = QtWidgets.QWidget()
        self.workflow_steps_layout = QtWidgets.QVBoxLayout()
        self.workflow_steps_layout.setContentsMargins(0, 0, 0, 0)
        self.workflow_steps_layout.setSpacing(4)
        self.workflow_steps.setLayout(self.workflow_steps_layout)

        self.workflow_card = QtWidgets.QFrame()
        self.workflow_card.setObjectName('workflowNavCard')
        self.workflow_card.setProperty('paneTone', 'workflow')
        workflow_card_layout = QtWidgets.QVBoxLayout()
        workflow_card_layout.setContentsMargins(14, 14, 14, 14)
        workflow_card_layout.setSpacing(8)
        self.workflow_card.setLayout(workflow_card_layout)

        workflow_title = QtWidgets.QLabel('WORKFLOW')
        workflow_title.setObjectName('sectionTitle')
        workflow_card_layout.addWidget(workflow_title)
        workflow_card_layout.addWidget(self.workflow_steps)

        self.page_card = QtWidgets.QFrame()
        self.page_card.setObjectName('workflowPageCard')
        self.page_card.setProperty('paneTone', 'current')
        page_layout = QtWidgets.QVBoxLayout()
        page_layout.setContentsMargins(18, 16, 18, 18)
        page_layout.setSpacing(8)
        self.page_card.setLayout(page_layout)

        self.page_title_label = QtWidgets.QLabel('')
        self.page_title_label.setObjectName('pageTitle')
        self.page_description_label = QtWidgets.QLabel('')
        self.page_description_label.setObjectName('pageSubtitle')
        self.page_description_label.setWordWrap(True)

        self.page_stack = QtWidgets.QStackedWidget()
        self.page_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding,
        )

        page_layout.addWidget(self.page_title_label)
        page_layout.addWidget(self.page_description_label)
        page_layout.addWidget(self.page_stack, stretch=1)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.summary_card)
        layout.addWidget(self.workflow_card)
        layout.addWidget(self.page_card, stretch=1)
        self.setLayout(layout)

    def _buildSummaryCard(self):
        card = QtWidgets.QFrame()
        card.setObjectName('workflowSummaryCard')

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        card.setLayout(layout)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        eyebrow = QtWidgets.QLabel('ACTIVE AIRFOIL')
        eyebrow.setObjectName('summaryEyebrow')
        header.addWidget(eyebrow)
        header.addStretch(1)

        self.summary_remove_button = self._makeSummaryActionButton('Remove')
        self.summary_remove_button.clicked.connect(
            lambda *_: self.mw.slots.removeAirfoil()
        )
        header.addWidget(self.summary_remove_button)
        layout.addLayout(header)

        self.summary_name_card = QtWidgets.QFrame()
        self.summary_name_card.setObjectName('summaryNameCard')
        self.summary_name_card.setProperty('paneTone', 'airfoil')
        summary_name_layout = QtWidgets.QHBoxLayout()
        summary_name_layout.setContentsMargins(12, 9, 12, 9)
        summary_name_layout.setSpacing(0)
        self.summary_name_card.setLayout(summary_name_layout)

        self.summary_name_label = QtWidgets.QLabel('No airfoil loaded')
        self.summary_name_label.setObjectName('summaryName')
        summary_name_layout.addWidget(self.summary_name_label)
        summary_name_layout.addStretch(1)
        layout.addWidget(self.summary_name_card)

        self.summary_meta_label = QtWidgets.QLabel('Open an airfoil to begin')
        self.summary_meta_label.setObjectName('summaryMeta')
        self.summary_meta_label.setWordWrap(True)
        layout.addWidget(self.summary_meta_label)

        self.summary_geometry_label = QtWidgets.QLabel('Geometry: waiting')
        self.summary_geometry_label.setObjectName('summaryStatus')
        self.summary_geometry_label.setWordWrap(True)
        layout.addWidget(self.summary_geometry_label)

        self.summary_mesh_label = QtWidgets.QLabel('Mesh: not available')
        self.summary_mesh_label.setObjectName('summaryStatus')
        self.summary_mesh_label.setWordWrap(True)
        layout.addWidget(self.summary_mesh_label)

        return card

    def _makeSummaryActionButton(self, text):
        button = QtWidgets.QPushButton(text)
        button.setObjectName('summaryActionButton')
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def addPage(self, widget, title, description, icon, scrollable=True):
        index = self.page_stack.count()
        if scrollable:
            widget.setMaximumWidth(PAGE_BODY_WIDTH)
            widget.setSizePolicy(
                QtWidgets.QSizePolicy.Preferred,
                QtWidgets.QSizePolicy.Maximum,
            )
            page_body = QtWidgets.QWidget()
            page_body.setObjectName('workflowPageBody')
            body_layout = QtWidgets.QHBoxLayout()
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(0)
            body_layout.addWidget(widget, 0, QtCore.Qt.AlignTop)
            body_layout.addStretch(1)
            page_body.setLayout(body_layout)

            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            scroll.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            scroll.setWidget(page_body)
            page_widget = scroll
        else:
            page_widget = widget
        self.page_stack.addWidget(page_widget)

        button = WorkflowStepButton(title=title, subtitle=description)
        if icon:
            button.setIcon(Icons.icon(icon))
            button.setIconSize(QtCore.QSize(20, 20))
        button.clicked.connect(
            lambda _checked=False, idx=index: self.setCurrentIndex(idx)
        )
        self.workflow_steps_layout.addWidget(button)

        self._page_buttons.append(button)
        self._page_titles.append(title)
        self._page_descriptions.append(description)
        return index

    def currentIndex(self):
        return self._current_index

    def lastWorkflowIndex(self):
        return self._last_workflow_index

    def setCurrentIndex(self, index):
        if index < 0 or index >= self.page_stack.count():
            return
        if index == self._current_index:
            return

        self._current_index = index
        if hasattr(self, 'tb3') and index != self.tb3:
            self._last_workflow_index = index

        self.page_stack.setCurrentIndex(index)
        for page_index, button in enumerate(self._page_buttons):
            blocker = QtCore.QSignalBlocker(button)
            button.setChecked(page_index == index)
            del blocker

        self._updateCurrentPageHeader()
        self.currentChanged.emit(index)

    def _updateCurrentPageHeader(self):
        if self._current_index < 0:
            self.page_title_label.setText('')
            self.page_description_label.setText('')
            return

        button = self._page_buttons[self._current_index]
        self.page_title_label.setText(self._pageTitleText(self._current_index))
        self.page_description_label.setText(
            self._pageHeaderSubtitle(self._current_index, button)
        )

    def _pageTitleText(self, index):
        title = self._page_titles[index]
        if hasattr(self, 'tb1') and index == self.tb1:
            count = getattr(self, '_airfoil_library_visible_count', None)
            if count is not None:
                return f'{title} ({count})'.upper()
        return title.upper()

    def _pageHeaderSubtitle(self, index, button):
        if hasattr(self, 'tb1') and index == self.tb1:
            return self._page_descriptions[index]
        return button.subtitle or self._page_descriptions[index]

    def refreshWorkflowState(self):
        airfoil = self._active_airfoil()

        self.summary_remove_button.setEnabled(airfoil is not None)
        self.summary_remove_button.setVisible(airfoil is not None)

        if airfoil is None:
            self.summary_name_label.setText('No airfoil loaded')
            self.summary_meta_label.setText(
                'Choose an airfoil from the library below to begin.'
            )
            self.summary_geometry_label.setText('Geometry: waiting for an airfoil')
            self.summary_mesh_label.setText('Mesh: not generated')
        else:
            self.summary_name_label.setText(airfoil.name)
            source_path = getattr(airfoil, 'source_path', None)
            source_text = FileSystem.describe_airfoil_source(
                source_path,
                mainwindow=self.mw,
            )
            self.summary_meta_label.setText(source_text or 'Working airfoil ready')
            self.summary_geometry_label.setText(
                f'Geometry: {self._geometryStatusText(airfoil)}'
            )
            self.summary_mesh_label.setText(
                f'Mesh: {self._meshStatusText(airfoil)}'
            )

        fill_toggle = getattr(
            getattr(self.mw, 'mainArea', None),
            'airfoil_spline_fill_checkbox',
            None,
        )
        if fill_toggle is not None:
            can_fill_spline = airfoil is not None and airfoil.has_spline
            fill_toggle.setEnabled(can_fill_spline)
            if can_fill_spline:
                self.applySplineFillPreference(airfoil)

        self._updateGeometryActionButtons(airfoil)

        if not hasattr(self, 'tb1'):
            return

        if airfoil is None:
            self._setPageStatus(
                self.tb1,
                'ready',
                'Open or drag in an airfoil contour',
            )
            self._setPageStatus(self.tb2, 'disabled', 'Select an airfoil first')
            self._setPageStatus(self.tb4, 'disabled', 'Prepare contour first')
            self._setPageStatus(self.tb6, 'info', 'Freestream helper inputs')
            self._setPageStatus(self.tb5, 'info', 'Reserved for quick aero tools')
            self._setPageStatus(self.tb3, 'disabled', 'Secondary analysis workspace')
            self._updateCurrentPageHeader()
            return

        self._setPageStatus(self.tb1, 'done', 'Working airfoil selected')

        method_label = self._geometryMethodLabel(airfoil)
        if airfoil.has_TE:
            geometry_status = ('done', f'{method_label} ready, trailing edge adjusted')
        elif airfoil.has_spline:
            geometry_status = ('done', f'{method_label} ready for meshing')
        else:
            geometry_status = ('ready', 'Raw contour ready for refinement')
        self._setPageStatus(self.tb2, *geometry_status)

        if airfoil.mesh_model is not None:
            stats = airfoil.mesh_model.mesh_statistics()
            mesh_detail = f'{stats.cell_count} cells / {stats.block_count} blocks'
            self._setPageStatus(self.tb4, 'done', mesh_detail)
        elif airfoil.has_spline:
            self._setPageStatus(self.tb4, 'ready', 'Ready to generate the mesh')
        else:
            self._setPageStatus(self.tb4, 'disabled', 'Prepare contour first')

        self._setPageStatus(self.tb6, 'ready', 'Freestream and y+ helper inputs')
        self._setPageStatus(self.tb5, 'info', 'Future quick-aero workspace')
        contour_status = 'ready' if airfoil.has_spline else 'disabled'
        contour_detail = (
            'Secondary analysis workspace'
            if airfoil.has_spline else
            'Prepare contour first'
        )
        self._setPageStatus(self.tb3, contour_status, contour_detail)
        self._updateCurrentPageHeader()

    def _setPageStatus(self, index, status, detail):
        self._page_buttons[index].set_status(status, detail)

    def _updateGeometryActionButtons(self, airfoil):
        has_spline = airfoil is not None and airfoil.has_spline
        has_camber = has_spline and getattr(airfoil, 'camber_data', None) is not None
        has_cst = self._activeCstParameterData(airfoil) is not None

        for attribute_name, enabled in (
            ('trailingButton', has_spline),
            ('exportContourButton', has_spline),
            ('exportCamberButton', has_camber),
            ('exportCstButton', has_cst),
            ('cstParametersButton', has_cst),
        ):
            button = getattr(self, attribute_name, None)
            if button is not None:
                button.setEnabled(enabled)

    def _geometryStatusText(self, airfoil):
        method_label = self._geometryMethodLabel(airfoil)
        if airfoil.has_TE:
            return f'{method_label} ready, trailing edge adjusted'
        if airfoil.has_spline:
            return f'{method_label} ready'
        return 'raw contour loaded'

    def _meshStatusText(self, airfoil):
        if airfoil.mesh_model is None:
            return 'not generated'
        stats = airfoil.mesh_model.mesh_statistics()
        return f'{stats.cell_count} cells across {stats.block_count} blocks'

    def toolboxChanged(self, _index=None):
        if self.currentIndex() == self.tb3:
            self.mw.mainArea.tabs.setCurrentIndex(1)
        else:
            self.mw.mainArea.tabs.setCurrentIndex(0)

        if self.currentIndex() == self.tb4:
            points = 0
            if self.mw.airfoil and self.mw.airfoil.has_spline:
                points = self.mw.airfoil.spline_data.point_count
            self.points_on_airfoil.setText(str(points))

    def selectedAirfoilLibrarySource(self):
        if not hasattr(self, 'airfoil_library_source_buttons'):
            return 'bundled'
        for source, button in self.airfoil_library_source_buttons.items():
            if button.isChecked():
                return source
        return 'bundled'

    def currentAirfoilLibraryPath(self):
        if not hasattr(self, 'airfoil_library_list'):
            return None
        item = self.airfoil_library_list.currentItem()
        if item is None:
            return None
        return item.data(QtCore.Qt.UserRole)

    def refreshAirfoilLibrary(self):
        if not hasattr(self, 'airfoil_library_list'):
            return

        selected_path = self.currentAirfoilLibraryPath()
        search_text = self.airfoil_library_search.text().strip().lower()
        source = self.selectedAirfoilLibrarySource()
        entries = FileSystem.list_airfoil_library_entries(
            source=source,
            mainwindow=self.mw,
        )

        if search_text:
            entries = [
                entry for entry in entries
                if search_text in entry.name.lower() or
                search_text in entry.relative_path.lower()
            ]

        blocker = QtCore.QSignalBlocker(self.airfoil_library_list)
        self.airfoil_library_list.clear()
        selected_item = None

        for entry in entries:
            label = entry.name
            if source == 'all':
                label = f'{entry.name}  [{entry.source_label}]'
            item = QtWidgets.QListWidgetItem(label)
            item.setToolTip(entry.path)
            item.setData(QtCore.Qt.UserRole, entry.path)
            item.setData(QtCore.Qt.UserRole + 1, entry.relative_path)
            item.setData(QtCore.Qt.UserRole + 2, entry.source_label)
            item.setData(QtCore.Qt.UserRole + 3, entry.name)
            item.setSizeHint(QtCore.QSize(0, 34))
            self.airfoil_library_list.addItem(item)

            if selected_path and os.path.abspath(entry.path) == os.path.abspath(selected_path):
                selected_item = item

        if selected_item is not None:
            self.airfoil_library_list.setCurrentItem(selected_item)
        elif self.airfoil_library_list.count() > 0:
            self.airfoil_library_list.setCurrentRow(0)
        del blocker

        self._airfoil_library_visible_count = len(entries)
        source_label = {
            'bundled': 'Bundled library',
            'local': 'Local library',
            'all': 'All airfoils',
        }[source]
        if entries:
            self._airfoil_library_status_text = ''
        elif search_text:
            self._airfoil_library_status_text = f'No matches for "{search_text}".'
        elif source == 'local':
            self._airfoil_library_status_text = (
                'No local airfoils yet. Use Add To Local... to build your library.'
            )
        else:
            self._airfoil_library_status_text = (
                f'No airfoils available in {source_label.lower()}.'
            )

        self.updateAirfoilLibraryDetails(self.airfoil_library_list.currentItem())
        self._updateCurrentPageHeader()

    def selectAirfoilLibraryPath(self, path):
        if not hasattr(self, 'airfoil_library_list'):
            return

        blocker = QtCore.QSignalBlocker(self.airfoil_library_list)
        if not path:
            self.airfoil_library_list.setCurrentRow(-1)
            del blocker
            self.updateAirfoilLibraryDetails(None)
            return

        target_path = os.path.abspath(path)
        self.airfoil_library_list.setCurrentRow(-1)

        for row in range(self.airfoil_library_list.count()):
            item = self.airfoil_library_list.item(row)
            item_path = item.data(QtCore.Qt.UserRole)
            if item_path and os.path.abspath(item_path) == target_path:
                self.airfoil_library_list.setCurrentItem(item)
                break

        del blocker
        self.updateAirfoilLibraryDetails(self.airfoil_library_list.currentItem())

    def updateAirfoilLibraryDetails(self, current=None, _previous=None):
        if not hasattr(self, 'airfoil_library_status_label'):
            return

        self.airfoil_library_load_button.setEnabled(current is not None)
        status_text = getattr(self, '_airfoil_library_status_text', '')
        self.airfoil_library_status_label.setVisible(bool(status_text))
        self.airfoil_library_status_label.setText(status_text)

    def loadSelectedLibraryAirfoil(self, item=None):
        selected_item = item or self.airfoil_library_list.currentItem()
        if selected_item is None:
            return

        path = selected_item.data(QtCore.Qt.UserRole)
        if not path:
            return
        self.mw.slots.openFile(path)

    def importAirfoilToLocalLibrary(self):
        file_dialog = FileDialog.Dialog()
        filename, _ = file_dialog.open_filename(
            title='Import Airfoil To Local Library',
            filter=FileOperations.CONTOUR_FILTER,
        )

        if not filename:
            logger.info('No file selected. Nothing imported.')
            return

        local_root = FileSystem.local_library_root(self.mw)
        destination = os.path.join(local_root, os.path.basename(filename))

        if os.path.abspath(filename) != os.path.abspath(destination):
            if os.path.exists(destination):
                answer = QtWidgets.QMessageBox.question(
                    self.mw,
                    'Replace Airfoil?',
                    f'{os.path.basename(destination)} already exists in the local library. Replace it?',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
                if answer != QtWidgets.QMessageBox.Yes:
                    return
            try:
                shutil.copy2(filename, destination)
            except OSError as error:
                FileOperations.report_io_error(
                    'import airfoil to local library',
                    destination,
                    error,
                    mainwindow=self.mw,
                )
                return
            logger.info(f'Imported airfoil to local library: {destination}')
        else:
            logger.info(f'Airfoil already in local library: {destination}')

        local_button = getattr(self, 'airfoil_library_source_buttons', {}).get('local')
        if local_button is not None:
            local_button.setChecked(True)
        self.refreshAirfoilLibrary()
        self.selectAirfoilLibraryPath(destination)

    def copy_to_clipboard(self):
        """Copy any selected text in the boundary-condition view."""
        self.textedit.copy()

    def copy_all_to_clipboard(self):
        """Copy the full boundary-condition view to the clipboard."""
        self.textedit.selectAll()
        self.textedit.copy()
        cursor = self.textedit.textCursor()
        cursor.clearSelection()
        self.textedit.setTextCursor(cursor)
        vsb = self.textedit.verticalScrollBar()
        vsb.setValue(QtWidgets.QAbstractSlider.SliderToMaximum)

    def boundary_condition_inputs(self):
        return ToolboxBoundaryConditions.BoundaryConditionInputs(
            reynolds=self.reynolds.value(),
            chord=self.chord.value(),
            aoa_from=self.aoaf.value(),
            aoa_to=self.aoat.value(),
            aoa_step=self.aoas.value(),
            turbulence=self.turbulence.value(),
            length_scale=self.length_sc.value(),
            pressure=self.pressure.value(),
            temperature_c=self.temperature.value(),
            yplus=self.yplus.value(),
        )

    def valuechange(self):
        if self.aoaf.value() >= self.aoat.value():
            self.aoaf.setValue(self.aoat.value() - self.aoas.value())
        if self.aoat.value() <= self.aoaf.value():
            self.aoat.setValue(self.aoaf.value() + self.aoas.value())

        inputs = self.boundary_condition_inputs()
        results = ToolboxBoundaryConditions.calculate_boundary_conditions(inputs)

        self.density = results.density
        self.dynamic_viscosity = results.dynamic_viscosity
        self.kinematic_viscosity = results.kinematic_viscosity
        self.aoa = results.aoa
        self.u_velocity = results.u_velocity
        self.v_velocity = results.v_velocity
        self.wall_distance = results.wall_distance
        self.tke = results.tke
        self.temperature_k = results.temperature_k
        self.te_text = ToolboxBoundaryConditions.format_boundary_conditions_html(
            inputs,
            results,
        )
        self.textedit.setStyleSheet(
            'font-family: "Menlo", "Monaco", "Courier New"; font-size: 12px; '
        )
        self.textedit.setHtml(self.te_text)

    def makeToolbox(self):
        self.tb1 = self.addPage(
            self.item_fs,
            title='Airfoil Library',
            description='Pick an airfoil and bring it into the workspace.',
            icon='airfoil-library',
            scrollable=False,
        )
        self.tb2 = self.addPage(
            self.item_cm,
            title='Geometry Prep',
            description='Refine the contour and prepare the trailing edge.',
            icon='geometry-prep',
        )
        self.tb4 = self.addPage(
            self.item_msh,
            title='Mesh',
            description='Set block sizes and export the tunnel mesh.',
            icon='mesh',
        )
        self.tb6 = self.addPage(
            self.item_abc,
            title='CFD Inputs',
            description='Prepare freestream and wall-distance inputs.',
            icon='cfd-inputs',
        )
        self.tb5 = self.addPage(
            self.item_ap,
            title='Aerodynamics',
            description='Run a quick panel-method estimate.',
            icon='aerodynamics',
        )
        self.tb3 = self.addPage(
            self.item_ca,
            title='Contour Analysis',
            description='Inspect gradient, curvature, and radius.',
            icon='contour-analysis',
        )

        self.setCurrentIndex(self.tb1)

    def smoother_btn_clicked(self):
        elliptic_controls = [
            self.outer_boundary_slide,
            self.elliptic_relaxation,
            self.protected_guide_relaxation,
            self.protected_guide_layers,
            self.protected_guide_decay,
            self.protected_guide_smoothing,
        ]

        if self.btn_smoother_1.isChecked():
            self.smoothing_algorithm = 'simple'
            self.smoother_iterations.setEnabled(False)
            self.smoother_tolerance.setEnabled(False)
            for control in elliptic_controls:
                control.setEnabled(False)
        elif self.btn_smoother_2.isChecked():
            self.smoothing_algorithm = 'elliptic'
            self.smoother_iterations.setEnabled(True)
            self.smoother_tolerance.setEnabled(True)
            for control in elliptic_controls:
                control.setEnabled(True)
        elif self.btn_smoother_3.isChecked():
            self.smoothing_algorithm = 'angle_based'
            self.smoother_iterations.setEnabled(True)
            self.smoother_tolerance.setEnabled(True)
            for control in elliptic_controls:
                control.setEnabled(False)

    def _active_airfoil(self):
        return getattr(self.mw, 'airfoil', None)

    def _toggleAirfoilItem(self, attribute_name):
        airfoil = self._active_airfoil()
        if airfoil is None:
            return

        item = getattr(airfoil, attribute_name, None)
        if item is None:
            return

        item.setVisible(not item.isVisible())

    def _smootherToleranceValue(self):
        text = self.smoother_tolerance.text().strip()
        if not text:
            return 1.0e-5
        return float(text)

    def selectedSplineMethod(self):
        method_selector = getattr(self, 'spline_method', None)
        if method_selector is None:
            return METHOD_CST_MODIFIED
        method = method_selector.currentData()
        return method or METHOD_CST_MODIFIED

    def selectedSplineMethodLabel(self):
        if self.selectedSplineMethod() == METHOD_CST_MODIFIED:
            return 'CST'
        return 'B-spline'

    def _activeCstParameterData(self, airfoil=None):
        airfoil = airfoil or self._active_airfoil()
        if airfoil is None or not getattr(airfoil, 'has_spline', False):
            return None

        spline_data = getattr(airfoil, 'spline_data', None)
        if spline_data is None:
            return None

        try:
            return cst_parameters_from_spline_data(spline_data)
        except ValueError:
            return None

    def updateSplineMethodControls(self):
        cst_enabled = self.selectedSplineMethod() == METHOD_CST_MODIFIED
        cst_order = getattr(self, 'cst_order', None)
        if cst_order is not None:
            cst_order.setEnabled(cst_enabled)

    def _geometryMethodLabel(self, airfoil):
        spline_data = getattr(airfoil, 'spline_data', None)
        if spline_data is None:
            return self.selectedSplineMethodLabel()

        metadata = getattr(spline_data, 'metadata', {}) or {}
        label = metadata.get('label')
        if label:
            return label
        if getattr(spline_data, 'method', METHOD_BSPLINE) == METHOD_CST_MODIFIED:
            return 'CST'
        return 'B-spline'

    def spline_refine_settings(self):
        return ToolboxServices.SplineRefineSettings(
            tolerance=self.tolerance.value(),
            points=self.points.value(),
            ref_te=self.ref_te.value(),
            ref_te_n=self.ref_te_n.value(),
            ref_te_ratio=self.ref_te_ratio.value(),
            method=self.selectedSplineMethod(),
            cst_order=self.cst_order.value(),
        )

    def trailing_edge_settings(self):
        return ToolboxServices.TrailingEdgeSettings(
            upper_blend=self.blend_u.value() / 100.0,
            lower_blend=self.blend_l.value() / 100.0,
            upper_exponent=self.exponent_u.value(),
            lower_exponent=self.exponent_l.value(),
            thickness=self.thickness.value(),
        )

    def mesh_generation_settings(self):
        return Meshing.WindtunnelMeshSettings(
            airfoil=MeshBuilders.AirfoilBlockSettings(
                name='block_airfoil',
                divisions=self.points_n.value(),
                growth=self.ratio.value(),
                thickness=self.normal_thickness.value(),
            ),
            trailing_edge=MeshBuilders.TrailingEdgeBlockSettings(
                name='block_TE',
                trailing_edge_divisions=self.te_div.value(),
                thickness=self.length_te.value(),
                divisions=self.points_te.value(),
                growth=self.ratio_te.value(),
            ),
            tunnel=MeshBuilders.TunnelBlockSettings(
                name='block_tunnel',
                tunnel_height=self.tunnel_height.value(),
                divisions_height=self.divisions_height.value(),
                height_growth=self.ratio_height.value(),
                distribution=self.dist.currentText(),
                smoothing_algorithm=self.smoothing_algorithm,
                smoothing_iterations=self.smoother_iterations.value(),
                smoothing_tolerance=self._smootherToleranceValue(),
                outer_boundary_slide=self.outer_boundary_slide.value(),
                elliptic_relaxation=self.elliptic_relaxation.value(),
                protected_guide_relaxation=self.protected_guide_relaxation.value(),
                protected_guide_layers=self.protected_guide_layers.value(),
                protected_guide_decay=self.protected_guide_decay.value(),
                protected_guide_smoothing=self.protected_guide_smoothing.value(),
            ),
            wake=MeshBuilders.WakeBlockSettings(
                name='block_tunnel_wake',
                tunnel_wake=self.tunnel_wake.value(),
                divisions=self.divisions_wake.value(),
                growth=self.ratio_wake.value(),
                spread=self.spread.value() / 100.0,
            ),
        )

    def mesh_export_settings(self):
        formats = []
        if self.check_FIRE.isChecked():
            formats.append('flma')
        if self.check_SU2.isChecked():
            formats.append('su2')
        if self.check_GMSH.isChecked():
            formats.append('gmsh')
        if self.check_VTK.isChecked():
            formats.append('vtu')

        return ToolboxServices.MeshExportSettings(
            boundary_definitions={
                'airfoil': self.lineedit_airfoil.text(),
                'inlet': self.lineedit_inlet.text(),
                'outlet': self.lineedit_outlet.text(),
                'top': self.lineedit_top.text(),
                'bottom': self.lineedit_bottom.text(),
            },
            formats=formats,
        )

    def selected_contour_analysis_quantity(self):
        if self.cpb2.isChecked():
            return 'curvature'
        if self.cpb3.isChecked():
            return 'radius'
        return 'gradient'

    def toggleRawPoints(self):
        self._toggleAirfoilItem('polygonMarkersGroup')

    def toggleRawContour(self):
        self._toggleAirfoilItem('contourPolygon')

    def toggleSplinePoints(self):
        self._toggleAirfoilItem('splineMarkersGroup')

    def toggleSpline(self):
        self._toggleAirfoilItem('contourSpline')

    def toggleChord(self):
        self._toggleAirfoilItem('chord')

    def toggleMesh(self):
        self._toggleAirfoilItem('mesh')

    def toggleLeCircle(self):
        self._toggleAirfoilItem('le_circle')

    def toggleMeshBlocks(self):
        self._toggleAirfoilItem('mesh_blocks')

    def toggleCamberLine(self):
        self._toggleAirfoilItem('camberline')

    def toggleCamberCircles(self):
        self._toggleAirfoilItem('camber_circles')

    def toggleMaxThicknessMarker(self):
        self._toggleAirfoilItem('max_thickness_marker')

    def toggleMaxCamberMarker(self):
        self._toggleAirfoilItem('max_camber_marker')

    def splineFillEnabled(self):
        fill_toggle = getattr(
            getattr(self.mw, 'mainArea', None),
            'airfoil_spline_fill_checkbox',
            None,
        )
        return bool(fill_toggle and fill_toggle.isChecked())

    def applySplineFillPreference(self, airfoil=None):
        target = airfoil or self._active_airfoil()
        if target is None:
            return
        target.setSplineFillEnabled(self.splineFillEnabled())

    def toggleSplineFill(self, _checked=None):
        self.applySplineFillPreference()

    def showCstParameters(self, _checked=None):
        airfoil = self._active_airfoil()
        if airfoil is None:
            self.mw.slots.messageBox('No airfoil loaded.')
            return

        parameter_data = self._activeCstParameterData(airfoil)
        if parameter_data is None:
            self.mw.slots.messageBox(
                'The current prepared contour does not have CST parameters.'
            )
            return

        dialog = QtWidgets.QDialog(self.mw)
        dialog.setWindowTitle('CST Parameters')
        dialog.resize(760, 560)

        layout = QtWidgets.QVBoxLayout()
        textedit = QtWidgets.QTextEdit()
        textedit.setReadOnly(True)
        textedit.setAcceptRichText(False)
        textedit.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        textedit.setFont(
            QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont
            )
        )
        textedit.setPlainText(
            f'Airfoil: {airfoil.name}\n\n'
            f'{format_cst_parameters_text(parameter_data)}'
        )
        layout.addWidget(textedit)

        button_row = QtWidgets.QHBoxLayout()
        copy_button = QtWidgets.QPushButton('Copy')
        export_json_button = QtWidgets.QPushButton('Export JSON...')
        export_csv_button = QtWidgets.QPushButton('Export CSV...')
        close_button = QtWidgets.QPushButton('Close')

        copy_button.clicked.connect(
            lambda *_: QtGui.QGuiApplication.clipboard().setText(
                textedit.toPlainText()
            )
        )
        export_json_button.clicked.connect(
            lambda *_: self.exportCst(default_extension='.json')
        )
        export_csv_button.clicked.connect(
            lambda *_: self.exportCst(default_extension='.csv')
        )
        close_button.clicked.connect(dialog.accept)

        button_row.addWidget(copy_button)
        button_row.addStretch(1)
        button_row.addWidget(export_json_button)
        button_row.addWidget(export_csv_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        dialog.setLayout(layout)
        dialog.exec()

    def spline_and_refine(self):
        self.workflow.spline_and_refine(self.spline_refine_settings())
        self.refreshWorkflowState()

    def makeTrailingEdge(self):
        self.workflow.add_trailing_edge(self.trailing_edge_settings())
        self.refreshWorkflowState()

    def generateMesh(self):
        wind_tunnel = self.workflow.generate_mesh(
            self.mesh_generation_settings()
        )
        if wind_tunnel is not None:
            self.wind_tunnel = wind_tunnel
        self.refreshWorkflowState()

    def analyzeAirfoil(self):
        self.workflow.prepare_contour_analysis()

    def drawContourAnalysis(self):
        self.workflow.draw_contour_analysis(
            self.selected_contour_analysis_quantity()
        )

    def exportMesh(self):
        airfoil = self._active_airfoil()
        if airfoil is None:
            self.mw.slots.messageBox('No airfoil loaded.')
            return
        if self.wind_tunnel is None:
            self.mw.slots.messageBox('Please generate a mesh first.')
            return

        export_settings = self.mesh_export_settings()
        if not export_settings.formats:
            self.mw.slots.messageBox('Please select at least one export format.')
            return

        filename = FileOperations.choose_mesh_export_basename(
            airfoil,
            export_settings.formats,
            mainwindow=self.mw,
        )
        if not filename:
            logger.info('No file selected. Nothing saved.')
            return

        self.workflow.export_mesh(
            self.wind_tunnel,
            filename,
            export_settings,
        )

    def exportContour(self, _checked=None):
        airfoil = self._active_airfoil()
        if airfoil is None:
            self.mw.slots.messageBox('No airfoil loaded.')
            return

        filename = FileOperations.choose_contour_save_filename(
            airfoil,
            title='Export Contour',
            mainwindow=self.mw,
        )
        if not filename:
            logger.info('No file selected. Nothing saved.')
            return
        self.workflow.export_contour(filename)

    def exportCamber(self, _checked=None):
        airfoil = self._active_airfoil()
        if airfoil is None:
            self.mw.slots.messageBox('No airfoil loaded.')
            return

        filename = FileOperations.choose_camber_save_filename(
            airfoil,
            title='Export Camber',
            mainwindow=self.mw,
        )
        if not filename:
            logger.info('No file selected. Nothing saved.')
            return
        self.workflow.export_camber(filename)

    def exportCst(self, _checked=None, default_extension='.json'):
        airfoil = self._active_airfoil()
        if airfoil is None:
            self.mw.slots.messageBox('No airfoil loaded.')
            return

        filename = FileOperations.choose_cst_save_filename(
            airfoil,
            title='Export CST Parameters',
            default_extension=default_extension,
            mainwindow=self.mw,
        )
        if not filename:
            logger.info('No file selected. Nothing saved.')
            return
        self.workflow.export_cst(filename)
