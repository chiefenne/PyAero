# -*- coding: utf-8 -*-

import os
import numpy as np

from PySide6 import QtGui, QtCore, QtWidgets

import PyAero
import Airfoil
import FileDialog
import FileSystem
import SvpMethod
import SplineRefine
import TrailingEdge
import Meshing
import ContourAnalysis as ca
from Settings import ICONS_L

import logging
logger = logging.getLogger(__name__)


class Toolbox(QtWidgets.QToolBox):

    def __init__(self, parent):
        """Main menus for PyAero functionality.
        Inserted in left pane of splitter window which in turn is the app's
        CentralWidget.

        Args:
            parent (QWidget): MainWindow from PyAero.py
        """
        super().__init__()

        self.parent = parent

        # set the style (css)
        style = """
            QToolBox::tab {
                border: 3px;
                background-color: #DDDDDD;
                color: black;
            }
            QToolBox::tab:pressed {
                background-color: #CCCCCD;
            }
            QToolBox::tab:selected {
                font: bold;
            }
        """
        self.setStyleSheet(style)

        # create toolbox items
        self.itemFileSystem()
        self.itemAeropython()
        self.itemBoundaryCondtions()
        self.itemContourAnalysis()
        self.itemSplineRefine()
        self.itemMeshing()

        self.makeToolbox()

        self.currentChanged.connect(self.toolboxChanged)

    def toolboxChanged(self):
        # tb1 = 'Airfoil Database'
        # tb2 = 'Contour Splining and Refinement'
        # tb4 = 'Meshing'
        # tb6 = 'Aerodynamics Boundary Conditions'
        # tb5 = 'Aerodynamics (Panel Code)'
        # tb3 = 'Contour Analysis'

        if self.currentIndex() == self.tb1:
            self.parent.centralwidget.tabs.setCurrentIndex(0)

        if self.currentIndex() == self.tb3:
            self.parent.centralwidget.tabs.setCurrentIndex(1)

        # update points on airfoil when toolbox changed to meshing
        if self.currentIndex() == self.tb4 and self.parent.airfoil:
            pts = len(self.parent.airfoil.spline_data[0][0])
            self.points_on_airfoil.setText(str(pts))

    def itemFileSystem(self):

        self.item_fs = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self.item_fs.setLayout(layout)

        # instance of QFileSystemModel
        filesystem_model = FileSystem.FileSystemModel()
        root_path = filesystem_model.rootPath()

        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(filesystem_model)
        self.tree.setRootIndex(filesystem_model.index(root_path))
        self.tree.setAnimated(True)

        # hide size column
        self.tree.setColumnHidden(1, True)
        # hide type column
        self.tree.setColumnHidden(2, True)
        # hide date modified column
        self.tree.setColumnHidden(3, True)

        # hide the header line of the filesystem tree
        # the header line would consist of name, date, type, size
        # the latter three are hidden anyway (see above)
        header = self.tree.header()
        header.hide()

        # handler
        self.tree.clicked.connect(filesystem_model.onFileSelected)
        self.tree.doubleClicked.connect(filesystem_model.onFileLoad)

        layout.addWidget(self.tree, stretch=12)
        # layout.setAlignment(QtCore.Qt.AlignTop)

        self.header = QtWidgets.QLabel('Loaded airfoil(s)')
        self.header.setEnabled(False)
        layout.addStretch(stretch=2)
        layout.addWidget(self.header)

        self.listwidget = ListWidget(self.parent)
        self.listwidget.setEnabled(False)
        # allow only single selections
        self.listwidget.setSelectionMode(QtWidgets.QAbstractItemView.
                                         SingleSelection)
        layout.addWidget(self.listwidget, stretch=5)
        layout.addStretch(stretch=1)

    def itemAeropython(self):

        form = QtWidgets.QFormLayout()

        label1 = QtWidgets.QLabel(u'Angle of attack (°)')
        self.aoaAP = QtWidgets.QDoubleSpinBox()
        self.aoaAP.setSingleStep(0.1)
        self.aoaAP.setDecimals(1)
        self.aoaAP.setRange(-10.0, 10.0)
        self.aoaAP.setValue(0.0)
        form.addRow(label1, self.aoaAP)

        label2 = QtWidgets.QLabel('Freestream velocity (m/s)')
        self.freestream = QtWidgets.QDoubleSpinBox()
        self.freestream.setSingleStep(0.1)
        self.freestream.setDecimals(2)
        self.freestream.setRange(0.0, 100.0)
        self.freestream.setValue(10.0)
        form.addRow(label2, self.freestream)

        label3 = QtWidgets.QLabel('Number of panels (-)')
        self.panels = QtWidgets.QSpinBox()
        self.panels.setRange(10, 500)
        self.panels.setValue(40)
        form.addRow(label3, self.panels)

        panelMethodButton = QtWidgets.QPushButton('Calculate lift coefficient')
        form.addRow(panelMethodButton)

        self.item_ap = QtWidgets.QGroupBox('AeroPython Panel Method')
        self.item_ap.setLayout(form)

        panelMethodButton.clicked.connect(self.runPanelMethod)

    def itemBoundaryCondtions(self):

        form = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Reynolds Number (-)')
        self.reynolds = QtWidgets.QDoubleSpinBox()
        self.reynolds.setSingleStep(10000.0)
        self.reynolds.setDecimals(2)
        self.reynolds.setRange(0.0, 1.0e10)
        self.reynolds.setValue(100000.0)
        self.reynolds.valueChanged.connect(self.valuechange)
        form.addRow(label, self.reynolds)

        label = QtWidgets.QLabel(u'Chord Length (m)')
        self.chord = QtWidgets.QDoubleSpinBox()
        self.chord.setSingleStep(0.01)
        self.chord.setDecimals(2)
        self.chord.setRange(0.0, 1.0e10)
        self.chord.setValue(1.0)
        self.chord.valueChanged.connect(self.valuechange)
        form.addRow(label, self.chord)

        # angle of attack (from, to, step)
        # from
        label = QtWidgets.QLabel(u'Angle of Attack (from) (°)')
        self.aoaf = QtWidgets.QDoubleSpinBox()
        self.aoaf.setSingleStep(0.1)
        self.aoaf.setDecimals(2)
        self.aoaf.setRange(-90.0, 90.0)
        self.aoaf.setValue(-10.0)
        form.addRow(label, self.aoaf)
        # to
        label = QtWidgets.QLabel(u'Angle of Attack (to) (°)')
        self.aoat = QtWidgets.QDoubleSpinBox()
        self.aoat.setSingleStep(0.1)
        self.aoat.setDecimals(2)
        self.aoat.setRange(-90.0, 90.0)
        self.aoat.setValue(10.0)
        form.addRow(label, self.aoat)
        # step
        label = QtWidgets.QLabel(u'Angle of Attack (step) (°)')
        self.aoas = QtWidgets.QDoubleSpinBox()
        self.aoas.setSingleStep(0.1)
        self.aoas.setDecimals(2)
        self.aoas.setRange(0.0, 90.0)
        self.aoas.setValue(1.0)
        form.addRow(label, self.aoas)

        self.aoaf.valueChanged.connect(self.valuechange)
        self.aoat.valueChanged.connect(self.valuechange)
        self.aoas.valueChanged.connect(self.valuechange)

        label = QtWidgets.QLabel(u'Freestream Turbulence Intensity (%)')
        self.turbulence = QtWidgets.QDoubleSpinBox()
        self.turbulence.setSingleStep(0.1)
        self.turbulence.setDecimals(2)
        self.turbulence.setRange(0.0, 100.0)
        self.turbulence.setValue(2.0)
        self.turbulence.valueChanged.connect(self.valuechange)
        form.addRow(label, self.turbulence)

        label = QtWidgets.QLabel(u'Freestream Length Scale (m)')
        self.length_sc = QtWidgets.QDoubleSpinBox()
        self.length_sc.setSingleStep(0.01)
        self.length_sc.setDecimals(3)
        self.length_sc.setRange(1.e-6, 1.0e10)
        self.length_sc.setValue(0.05)
        self.length_sc.valueChanged.connect(self.valuechange)
        form.addRow(label, self.length_sc)

        label = QtWidgets.QLabel(u'Pressure (Pa)')
        self.pressure = QtWidgets.QDoubleSpinBox()
        self.pressure.setSingleStep(1000.0)
        self.pressure.setDecimals(2)
        self.pressure.setRange(0.0, 1.0e10)
        self.pressure.setValue(101325.0)
        self.pressure.valueChanged.connect(self.valuechange)
        form.addRow(label, self.pressure)

        label = QtWidgets.QLabel(u'Temperature (°C)')
        self.temperature = QtWidgets.QDoubleSpinBox()
        self.temperature.setSingleStep(1.0)
        self.temperature.setDecimals(2)
        self.temperature.setRange(-273.15, 1.0e10)
        self.temperature.setValue(20.0)
        self.temperature.valueChanged.connect(self.valuechange)
        form.addRow(label, self.temperature)

        label = QtWidgets.QLabel(u'Flat plate y\u207a (-)')
        self.yplus = QtWidgets.QDoubleSpinBox()
        self.yplus.setSingleStep(1.0)
        self.yplus.setDecimals(2)
        self.yplus.setRange(1e-6, 1.0e10)
        self.yplus.setValue(30.0)
        self.yplus.valueChanged.connect(self.valuechange)
        form.addRow(label, self.yplus)

        self.textedit = QtWidgets.QTextEdit()
        self.textedit.setReadOnly(True)
        self.textedit.selectionChanged.connect(self.copy_to_clipboard)
        # update text box (so everything is computed from initial values)
        self.valuechange()

        copy_button = QtWidgets.QPushButton('Copy to clipboard')
        copy_button.setGeometry(10, 10, 200, 50)
        copy_button.clicked.connect(self.copy_all_to_clipboard)

        text_and_button = QtWidgets.QHBoxLayout()
        text_and_button.addWidget(self.textedit, stretch=10)
        text_and_button.addWidget(copy_button)

        form.addRow(text_and_button)

        self.item_abc = QtWidgets.QGroupBox(
            'Aerodynamic boundary conditions for CFD')
        self.item_abc.setLayout(form)

    def copy_to_clipboard(self):
        """ Copy any selected text in the self.textedit to the clipboard """
        self.textedit.copy()

    def copy_all_to_clipboard(self):
        """ Copy any selected text in the self.textedit to the clipboard """
        self.textedit.selectAll()
        self.textedit.copy()
        # weird way to unselect the text again
        # https://stackoverflow.com/a/25348576/2264936
        cursor = self.textedit.textCursor()
        cursor.clearSelection()
        self.textedit.setTextCursor(cursor)
        vsb = self.textedit.verticalScrollBar()
        vsb.setValue(QtWidgets.QAbstractSlider.SliderToMaximum)

    def valuechange(self):
        # checks that from and to do not overlap
        if self.aoaf.value() >= self.aoat.value():
            self.aoaf.setValue(self.aoat.value() - self.aoas.value())
        if self.aoat.value() <= self.aoaf.value():
            self.aoat.setValue(self.aoaf.value() + self.aoas.value())

        gas_constant = 287.14
        temperature = self.temperature.value() + 273.15
        self.density = self.pressure.value() / gas_constant / temperature
        num = int((self.aoat.value() - self.aoaf.value()) / self.aoas.value() + 1)
        self.aoa = np.linspace(self.aoaf.value(), self.aoat.value(),
                               num=num, endpoint=True)

        def dynamic_viscosity(temperature):
            # Sutherland formula for air
            C = 120.0
            lamb = 1.512041288e-6
            vis = lamb * temperature**1.5 / (temperature + C)
            return vis

        # calculate results wrt given inputs
        self.dynamic_viscosity = dynamic_viscosity(temperature)
        self.kinematic_viscosity = self.dynamic_viscosity / self.density
        velocity = self.reynolds.value() / self.chord.value() * \
            self.kinematic_viscosity
        uprime = velocity * self.turbulence.value() / 100.0
        tke = 3.0 / 2.0 * uprime**2
        self.u_velocity = velocity * np.cos(self.aoa * np.pi / 180.0)
        self.v_velocity = velocity * np.sin(self.aoa * np.pi / 180.0)

        # calculate 1st cell thickness from y-plus and Reynolds, etc.
        RE = self.reynolds.value()
        log10 = np.log10(RE)
        logRE = np.power(log10, 2.58)
        if RE < 5.1e6:
            friction_coefficient = 0.455 / logRE
        else:
            friction_coefficient = 0.455 / logRE - 1700.0 / RE
        wall_shear_stress = friction_coefficient * 0.5 * self.density * velocity**2
        friction_velocity = np.sqrt(wall_shear_stress / self.density)
        wall_distance = self.yplus.value() * self.dynamic_viscosity / self.density / friction_velocity

        # text for displaying the results
        newline = '<br>'
        self.te_text = '<b>CFD Boundary Conditions</b>' + newline
        self.te_text += f'Reynolds (-): {self.reynolds.value()}' + newline
        self.te_text += f'Pressure (Pa): {self.pressure.value()}' + newline
        self.te_text += f'Temperature (C): {self.temperature.value()}' + newline
        self.te_text += f'Temperature (K): {self.temperature.value()+273.15}' + newline
        self.te_text += f'Density (kg/(m<sup>3</sup>)): {self.density}' + newline
        self.te_text += f'Dynamic viscosity (kg/(m.s)): {self.dynamic_viscosity}' + newline
        self.te_text += f'Kinematic viscosity (m/s) {self.kinematic_viscosity}:' + newline
        self.te_text += f'<b>1st cell layer thickness (m)</b>, for y<sup>+</sup>={self.yplus.value()}' + newline
        self.te_text += '{:16.8f}'.format(wall_distance) + newline
        self.te_text += '<b>TKE (m<sup>2</sup>/s<sup>2</sup>), Length-scale (m)</b>' + newline
        self.te_text += '{:16.8f} {:16.8f}'.\
            format(tke, self.length_sc.value()) + newline
        self.te_text += '<b>AOA (°)   u-velocity (m/s)   v-velocity (m/s)</b>' + newline
        for i, _ in enumerate(self.u_velocity):
            self.te_text += '{: >5.2f} {: >16.8f} {: >16.8f}{}'.format(
                self.aoa[i],
                self.u_velocity[i],
                self.v_velocity[i],
                newline)
        self.textedit.setStyleSheet('font-family: Courier; font-size: 12px; ')

        # update the text boxwith the current values
        self.textedit.setHtml(self.te_text)

    def itemContourAnalysis(self):

        box = QtWidgets.QVBoxLayout()

        vlayout = QtWidgets.QVBoxLayout()
        gb = QtWidgets.QGroupBox('Select contour to analyze')
        self.b1 = QtWidgets.QRadioButton('Original')
        self.b2 = QtWidgets.QRadioButton('Refined')
        self.b2.setChecked(True)
        vlayout.addWidget(self.b1)
        vlayout.addWidget(self.b2)
        gb.setLayout(vlayout)
        box.addWidget(gb)

        vlayout = QtWidgets.QVBoxLayout()
        self.cgb = QtWidgets.QGroupBox('Select plot quantity')
        self.cpb1 = QtWidgets.QRadioButton('Gradient')
        self.cpb2 = QtWidgets.QRadioButton('Curvature')
        self.cpb3 = QtWidgets.QRadioButton('Radius of Curvature')
        self.cpb1.setChecked(True)
        vlayout.addWidget(self.cpb1)
        vlayout.addWidget(self.cpb2)
        vlayout.addWidget(self.cpb3)
        self.cgb.setLayout(vlayout)
        self.cgb.setEnabled(False)
        box.addWidget(self.cgb)

        analyzeButton = QtWidgets.QPushButton('Analyze Contour')
        analyzeButton.setGeometry(10, 10, 200, 50)
        box.addWidget(analyzeButton)

        box.addStretch(1)

        self.item_ca = QtWidgets.QWidget()
        self.item_ca.setLayout(box)

        analyzeButton.clicked.connect(self.analyzeAirfoil)

    def itemMeshing(self):

        self.form_mesh_airfoil = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Gridpoints along airfoil')
        label.setToolTip('Number of points as derived from splining')
        points = 0
        self.points_on_airfoil = QtWidgets.QLineEdit(str(points))
        self.points_on_airfoil.setEnabled(False)
        self.form_mesh_airfoil.addRow(label, self.points_on_airfoil)

        label = QtWidgets.QLabel(u'Divisions normal to airfoil')
        label.setToolTip('Number of points in the mesh which is constructed ' +
                         ' normal to the airfoil contour')
        self.points_n = QtWidgets.QSpinBox()
        self.points_n.setSingleStep(1)
        self.points_n.setRange(1, 500)
        self.points_n.setValue(15)
        self.form_mesh_airfoil.addRow(label, self.points_n)

        label = QtWidgets.QLabel('1st cell layer thickness (m)')
        label.setToolTip('Thickness of 1st cell layer perpendicular to the airfoil')
        self.normal_thickness = QtWidgets.QDoubleSpinBox()
        self.normal_thickness.setSingleStep(0.001)
        self.normal_thickness.setRange(1.e-10, 1.e10)
        self.normal_thickness.setDecimals(8)
        self.normal_thickness.setValue(0.00400)
        self.form_mesh_airfoil.addRow(label, self.normal_thickness)

        label = QtWidgets.QLabel('Cell growth rate (-)')
        label.setToolTip('Rate at which 1st cell layer grows')
        self.ratio = QtWidgets.QDoubleSpinBox()
        self.ratio.setSingleStep(0.01)
        self.ratio.setRange(1., 100.)
        self.ratio.setValue(1.05)
        self.ratio.setDecimals(3)
        self.form_mesh_airfoil.addRow(label, self.ratio)

        self.form_mesh_TE = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Divisions at trailing edge')
        label.setToolTip('Number of subdivisions along the vertical part of the TE')
        self.te_div = QtWidgets.QSpinBox()
        self.te_div.setSingleStep(1)
        self.te_div.setRange(1, 20)
        self.te_div.setValue(3)
        self.form_mesh_TE.addRow(label, self.te_div)

        label = QtWidgets.QLabel(u'Divisions downstream')
        label.setToolTip('Number of subdivisions downstream within the TE block')
        self.points_te = QtWidgets.QSpinBox()
        self.points_te.setSingleStep(1)
        self.points_te.setRange(1, 100)
        self.points_te.setValue(15)
        self.form_mesh_TE.addRow(label, self.points_te)

        label = QtWidgets.QLabel('1st cell layer thickness (m)')
        label.setToolTip('Thickness of first cell layer in downstream direction')
        self.length_te = QtWidgets.QDoubleSpinBox()
        self.length_te.setSingleStep(0.001)
        self.length_te.setRange(1.e-10, 1.e10)
        self.length_te.setDecimals(8)
        self.length_te.setValue(0.00400)
        self.form_mesh_TE.addRow(label, self.length_te)

        label = QtWidgets.QLabel('Cell growth rate (-)')
        label.setToolTip('Rate at which 1st cell layer downstream the TE grows')
        self.ratio_te = QtWidgets.QDoubleSpinBox()
        self.ratio_te.setSingleStep(0.01)
        self.ratio_te.setRange(1., 100.)
        self.ratio_te.setValue(1.05)
        self.ratio_te.setDecimals(3)
        self.form_mesh_TE.addRow(label, self.ratio_te)

        self.form_mesh_tunnel = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel('Windtunnel Height (chords)')
        label.setToolTip('The height of the windtunnel in units ' +
                         'of chord length')
        self.tunnel_height = QtWidgets.QDoubleSpinBox()
        self.tunnel_height.setSingleStep(0.1)
        self.tunnel_height.setRange(0.1, 100.)
        self.tunnel_height.setValue(3.5)
        self.tunnel_height.setDecimals(1)
        self.form_mesh_tunnel.addRow(label, self.tunnel_height)

        label = QtWidgets.QLabel(u'Divisions of Tunnel Height')
        self.divisions_height = QtWidgets.QSpinBox()
        self.divisions_height.setSingleStep(10)
        self.divisions_height.setRange(1, 1000)
        self.divisions_height.setValue(100)
        self.form_mesh_tunnel.addRow(label, self.divisions_height)

        label = QtWidgets.QLabel('Cell Thickness ratio (-)')
        self.ratio_height = QtWidgets.QDoubleSpinBox()
        self.ratio_height.setSingleStep(1.0)
        self.ratio_height.setRange(0.1, 100.)
        self.ratio_height.setValue(10.0)
        self.ratio_height.setDecimals(1)
        self.form_mesh_tunnel.addRow(label, self.ratio_height)

        label = QtWidgets.QLabel('Distribution biasing')
        self.dist = QtWidgets.QComboBox()
        self.dist.addItems(['symmetric', 'lower', 'upper'])
        self.dist.setCurrentIndex(0)
        self.form_mesh_tunnel.addRow(label, self.dist)

        self.form_mesh_wake = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel('Windtunnel Wake (chords)')
        label.setToolTip('The length of the wake of the windtunnel in ' +
                         'units of chord length')
        self.tunnel_wake = QtWidgets.QDoubleSpinBox()
        self.tunnel_wake.setSingleStep(0.1)
        self.tunnel_wake.setRange(0.1, 100.)
        self.tunnel_wake.setValue(7.0)
        self.tunnel_wake.setDecimals(1)
        self.form_mesh_wake.addRow(label, self.tunnel_wake)

        label = QtWidgets.QLabel(u'Divisions in the wake')
        self.divisions_wake = QtWidgets.QSpinBox()
        self.divisions_wake.setSingleStep(10)
        self.divisions_wake.setRange(1, 1000)
        self.divisions_wake.setValue(100)
        self.form_mesh_wake.addRow(label, self.divisions_wake)

        label = QtWidgets.QLabel('Cell Thickness ratio (-)')
        label.setToolTip('Thickness of the last cell vs. the first cell in ' +
                         'the wake mesh block')
        self.ratio_wake = QtWidgets.QDoubleSpinBox()
        self.ratio_wake.setSingleStep(0.1)
        self.ratio_wake.setRange(0.01, 100.0)
        self.ratio_wake.setValue(15.0)
        self.ratio_wake.setDecimals(1)
        self.form_mesh_wake.addRow(label, self.ratio_wake)

        label = QtWidgets.QLabel('Equalize vertical wake line at (%)')
        label.setToolTip('Equalize  the wake line vertically. ' +
                         'Homogeneous vertical distribution at x% downstream')
        self.spread = QtWidgets.QDoubleSpinBox()
        self.spread.setSingleStep(5.0)
        self.spread.setRange(10.0, 90.0)
        self.spread.setValue(30.0)
        self.spread.setDecimals(1)
        self.form_mesh_wake.addRow(label, self.spread)

        # smoothing parameters
        label = QtWidgets.QLabel('Smoothing')
        label.setToolTip('Specify algorithm and parameters for smoothing')
        self.btn_smoother_1 = QtWidgets.QRadioButton('Simple (fast)')
        self.btn_smoother_2 = QtWidgets.QRadioButton('Elliptic (medium)')
        self.btn_smoother_3 = QtWidgets.QRadioButton('Angle based (slow)')
        # initialize simple smoother
        self.btn_smoother_1.setChecked(True)
        self.smoothing_algorithm = 'simple'

        self.btn_smoother_1.clicked.connect(self.smoother_btn_clicked)
        self.btn_smoother_2.clicked.connect(self.smoother_btn_clicked)
        self.btn_smoother_3.clicked.connect(self.smoother_btn_clicked)

        smoother_settings = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel('Iterations')
        self.smoother_iterations = QtWidgets.QSpinBox()
        self.smoother_iterations.setValue(20)
        self.smoother_iterations.setSingleStep(5)
        self.smoother_iterations.setRange(0, 1000)
        self.smoother_iterations.setEnabled(False)
        smoother_settings.addRow(label, self.smoother_iterations)

        label = QtWidgets.QLabel('Tolerance')
        self.smoother_tolerance = QtWidgets.QLineEdit()
        self.onlyFloat = QtGui.QDoubleValidator()
        self.smoother_tolerance.setValidator(self.onlyFloat)
        self.smoother_tolerance.setText('1.e-5')
        self.onlyFloat.setRange(1.e-8, 1.0)
        self.onlyFloat.setDecimals(8)
        self.smoother_tolerance.setEnabled(False)
        smoother_settings.addRow(label, self.smoother_tolerance)

        hbox_smoothing = QtWidgets.QHBoxLayout()
        vbox1 = QtWidgets.QVBoxLayout()
        vbox2 = QtWidgets.QVBoxLayout()
        vbox1.addWidget(self.btn_smoother_1)
        vbox1.addWidget(self.btn_smoother_2)
        vbox1.addWidget(self.btn_smoother_3)
        vbox2.addLayout(smoother_settings)
        hbox_smoothing.addLayout(vbox1)
        hbox_smoothing.addLayout(vbox2)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(self.form_mesh_airfoil)
        box_airfoil = QtWidgets.QGroupBox('Airfoil contour mesh')
        box_airfoil.setLayout(vbox)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(self.form_mesh_TE)
        box_TE = QtWidgets.QGroupBox('Airfoil trailing edge mesh')
        box_TE.setLayout(vbox)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(self.form_mesh_tunnel)
        box_tunnel = QtWidgets.QGroupBox('Windtunnel mesh (around airfoil)')
        box_tunnel.setLayout(vbox)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(self.form_mesh_wake)
        box_wake = QtWidgets.QGroupBox('Windtunnel mesh (wake)')
        box_wake.setLayout(vbox)

        box_smoothing = QtWidgets.QGroupBox('Smoothing')
        box_smoothing.setLayout(hbox_smoothing)

        self.createMeshButton = QtWidgets.QPushButton('Create Mesh')
        hbl_cm = QtWidgets.QHBoxLayout()
        hbl_cm.addStretch(stretch=1)
        hbl_cm.addWidget(self.createMeshButton, stretch=4)
        hbl_cm.addStretch(stretch=1)

        # boundary definitions
        label = QtWidgets.QLabel('Boundary definitions:')
        label.setToolTip('Here you can define the names of the boundaries ' +
                         'for the mesh export')

        grid1 = QtWidgets.QGridLayout()
        grid1.addWidget(label, 0, 0)

        # export menu and boundary definitions
        self.form_bnd = QtWidgets.QFormLayout()
        header_1 = QtWidgets.QLabel('Boundary')
        header_1.setStyleSheet('font-weight: bold;')
        header_2 = QtWidgets.QLabel('Name')
        header_2.setStyleSheet('font-weight: bold;')
        self.form_bnd.addRow(header_1, header_2)

        label = QtWidgets.QLabel('Airfoil')
        label.setToolTip('Name of the boundary definition for the airfoil')
        self.lineedit_airfoil = QtWidgets.QLineEdit('Airfoil')
        self.form_bnd.addRow(label, self.lineedit_airfoil)

        label = QtWidgets.QLabel('Inlet (C-arc)')
        label.setToolTip('Name of the boundary definition for the inlet')
        self.lineedit_inlet = QtWidgets.QLineEdit('Inlet')
        self.form_bnd.addRow(label, self.lineedit_inlet)

        label = QtWidgets.QLabel('Outlet')
        label.setToolTip('Name of the boundary definition for the outlet')
        self.lineedit_outlet = QtWidgets.QLineEdit('Outlet')
        self.form_bnd.addRow(label, self.lineedit_outlet)

        label = QtWidgets.QLabel('Top')
        label.setToolTip('Name of the boundary definition for the top of the windtunnel')
        self.lineedit_top = QtWidgets.QLineEdit('Top')
        self.form_bnd.addRow(label, self.lineedit_top)

        label = QtWidgets.QLabel('Bottom')
        label.setToolTip('Name of the boundary definition for the bottom of the windtunnel')
        self.lineedit_bottom = QtWidgets.QLineEdit('Bottom')
        self.form_bnd.addRow(label, self.lineedit_bottom)

        self.check_FIRE = QtWidgets.QCheckBox('AVL FIRE')
        self.check_SU2 = QtWidgets.QCheckBox('SU2')
        self.check_GMSH = QtWidgets.QCheckBox('GMSH')
        self.check_VTK = QtWidgets.QCheckBox('VTK (VTU)')
        self.check_FIRE.setChecked(True)
        self.check_SU2.setChecked(True)
        self.check_GMSH.setChecked(False)
        self.check_VTK.setChecked(False)

        label = QtWidgets.QLabel('Export format:')
        label.setToolTip('Check format to be exported')
        grid = QtWidgets.QGridLayout()
        grid.addWidget(label, 0, 0)
        grid.addWidget(self.check_FIRE, 1, 1)
        grid.addWidget(self.check_SU2, 1, 2)
        grid.addWidget(self.check_GMSH, 1, 3)
        grid.addWidget(self.check_VTK, 2, 1)

        exportMeshButton = QtWidgets.QPushButton('Export Mesh')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(exportMeshButton, stretch=4)
        hbl.addStretch(stretch=1)

        vbl1 = QtWidgets.QVBoxLayout()
        vbl1.addLayout(grid1)
        vbl1.addLayout(self.form_bnd)
        vbl1.addLayout(grid)
        vbl1.addLayout(hbl)

        self.box_meshexport = QtWidgets.QGroupBox('Mesh Export')
        self.box_meshexport.setLayout(vbl1)
        self.box_meshexport.setEnabled(False)

        vbl = QtWidgets.QVBoxLayout()
        vbl.addStretch(1)
        vbl.addWidget(box_airfoil)
        vbl.addWidget(box_TE)
        vbl.addWidget(box_tunnel)
        vbl.addWidget(box_wake)
        vbl.addWidget(box_smoothing)
        vbl.addLayout(hbl_cm)
        vbl.addStretch(1)
        vbl.addWidget(self.box_meshexport)
        vbl.addStretch(10)

        self.item_msh = QtWidgets.QWidget()
        self.item_msh.setLayout(vbl)

        self.createMeshButton.clicked.connect(self.generateMesh)
        exportMeshButton.clicked.connect(self.exportMesh)

    def itemSplineRefine(self):

        form = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Refinement tolerance (°)')
        self.tolerance = QtWidgets.QDoubleSpinBox()
        self.tolerance.setSingleStep(0.1)
        self.tolerance.setDecimals(1)
        self.tolerance.setRange(50.0, 177.0)
        self.tolerance.setValue(172.0)
        form.addRow(label, self.tolerance)

        label = QtWidgets.QLabel(u'Refine trailing edge (old segments)')
        label.setToolTip('Specify the number of segments at the trailing edge which should be refined.')
        self.ref_te = QtWidgets.QSpinBox()
        self.ref_te.setSingleStep(1)
        self.ref_te.setRange(1, 50)
        self.ref_te.setValue(3)
        form.addRow(label, self.ref_te)

        label = QtWidgets.QLabel(u'Refine trailing edge (new segments)')
        self.ref_te_n = QtWidgets.QSpinBox()
        self.ref_te_n.setSingleStep(1)
        self.ref_te_n.setRange(1, 100)
        self.ref_te_n.setValue(6)
        form.addRow(label, self.ref_te_n)

        label = QtWidgets.QLabel(u'Refine trailing edge ratio')
        self.ref_te_ratio = QtWidgets.QDoubleSpinBox()
        self.ref_te_ratio.setSingleStep(0.1)
        self.ref_te_ratio.setDecimals(1)
        self.ref_te_ratio.setRange(1., 10.)
        self.ref_te_ratio.setValue(3.0)
        form.addRow(label, self.ref_te_ratio)

        label = QtWidgets.QLabel('Number points on spline (-)')
        self.points = QtWidgets.QSpinBox()
        self.points.setSingleStep(10)
        self.points.setRange(10, 1000)
        self.points.setValue(200)
        form.addRow(label, self.points)

        self.splineButton = QtWidgets.QPushButton('Spline and Refine')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(self.splineButton, stretch=4)
        hbl.addStretch(stretch=1)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(form)
        vbox.addLayout(hbl)
        box = QtWidgets.QGroupBox('Airfoil contour refinement')
        box.setLayout(vbox)

        form1 = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Upper side blending length (%)')
        self.blend_u = QtWidgets.QDoubleSpinBox()
        self.blend_u.setSingleStep(1.0)
        self.blend_u.setDecimals(1)
        self.blend_u.setRange(0.1, 100.0)
        self.blend_u.setValue(30.0)
        form1.addRow(label, self.blend_u)
        label = QtWidgets.QLabel(u'Lower side blending length (%)')
        self.blend_l = QtWidgets.QDoubleSpinBox()
        self.blend_l.setSingleStep(1.0)
        self.blend_l.setDecimals(1)
        self.blend_l.setRange(0.1, 100.0)
        self.blend_l.setValue(30.0)
        form1.addRow(label, self.blend_l)

        label = QtWidgets.QLabel(u'Upper blending polynomial exponent (-)')
        self.exponent_u = QtWidgets.QDoubleSpinBox()
        self.exponent_u.setSingleStep(0.1)
        self.exponent_u.setDecimals(1)
        self.exponent_u.setRange(1.0, 10.0)
        self.exponent_u.setValue(3.0)
        form1.addRow(label, self.exponent_u)
        label = QtWidgets.QLabel(u'Lower blending polynomial exponent (-)')
        self.exponent_l = QtWidgets.QDoubleSpinBox()
        self.exponent_l.setSingleStep(0.1)
        self.exponent_l.setDecimals(1)
        self.exponent_l.setRange(1.0, 10.0)
        self.exponent_l.setValue(3.0)
        form1.addRow(label, self.exponent_l)

        label = QtWidgets.QLabel(u'Trailing edge thickness relative to chord (%)')
        self.thickness = QtWidgets.QDoubleSpinBox()
        self.thickness.setSingleStep(0.05)
        self.thickness.setDecimals(2)
        self.thickness.setRange(0.0, 10.0)
        self.thickness.setValue(0.4)
        form1.addRow(label, self.thickness)

        self.trailingButton = QtWidgets.QPushButton('Add Trailing Edge')
        self.trailingButton.setEnabled(False)
        hbl1 = QtWidgets.QHBoxLayout()
        hbl1.addStretch(stretch=1)
        hbl1.addWidget(self.trailingButton, stretch=4)
        hbl1.addStretch(stretch=1)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(form1)
        vbox.addLayout(hbl1)
        box1 = QtWidgets.QGroupBox('Airfoil trailing edge')
        box1.setLayout(vbox)

        # export menu
        name = ''
        hbox = QtWidgets.QHBoxLayout()
        self.exportContourButton = QtWidgets.QPushButton('Export Contour')
        self.exportContourButton.setEnabled(False)
        hbox.addWidget(self.exportContourButton)

        box2 = QtWidgets.QGroupBox('Export modified contour')
        box2.setLayout(hbox)

        vbl = QtWidgets.QVBoxLayout()
        vbl.addStretch(1)
        vbl.addWidget(box)
        vbl.addStretch(1)
        vbl.addWidget(box1)
        vbl.addStretch(1)
        vbl.addWidget(box2)
        vbl.addStretch(10)

        self.item_cm = QtWidgets.QWidget()
        self.item_cm.setLayout(vbl)

        self.splineButton.clicked.connect(self.spline_and_refine)
        self.trailingButton.clicked.connect(self.makeTrailingEdge)
        self.exportContourButton.clicked.connect(self.exportContour)

    def makeToolbox(self):

        # populate toolbox
        self.tb1 = self.addItem(self.item_fs, 'Airfoil Database')
        self.tb2 = self.addItem(self.item_cm,
                                'Contour Splining and Refinement')
        self.tb4 = self.addItem(self.item_msh, 'Meshing')
        self.tb6 = self.addItem(self.item_abc,
                                'CFD Boundary Conditions')
        self.tb5 = self.addItem(self.item_ap, 'Aerodynamics (Panel Code)')
        self.tb3 = self.addItem(self.item_ca, 'Contour Analysis')

        self.setItemToolTip(0, 'Airfoil database ' +
                            '(browse filesystem)')
        self.setItemToolTip(1, 'Spline and refine the contour')
        self.setItemToolTip(2, 'Generate a 2D mesh around the ' +
                            'selected airfoil')
        self.setItemToolTip(3,
                            'Compute aerodynamic boundary conditions based' +
                            ' on Reynolds number and thermodynamics')
        self.setItemToolTip(4, 'Compute panel based aerodynamic ' +
                            'coefficients')
        self.setItemToolTip(5, 'Analyze the curvature of the ' +
                            'selected airfoil')

        self.setItemIcon(0, QtGui.QIcon(os.path.join(ICONS_L, 'airfoil.png')))
        self.setItemIcon(1, QtGui.QIcon(os.path.join(ICONS_L, 'Pixel editor.png')))
        self.setItemIcon(2, QtGui.QIcon(os.path.join(ICONS_L, 'mesh.png')))
        self.setItemIcon(3, QtGui.QIcon(os.path.join(ICONS_L, 'Fast delivery.png')))
        self.setItemIcon(4, QtGui.QIcon(os.path.join(ICONS_L, 'Fast delivery.png')))
        self.setItemIcon(5, QtGui.QIcon(os.path.join(ICONS_L, 'Pixel editor.png')))

        # preselect airfoil database box
        self.setCurrentIndex(self.tb1)

    def smoother_btn_clicked(self):
        if self.btn_smoother_1.isChecked():
            self.smoothing_algorithm = 'simple'
            self.smoother_iterations.setEnabled(False)
            self.smoother_tolerance.setEnabled(False)
        elif self.btn_smoother_2.isChecked():
            self.smoothing_algorithm = 'elliptic'
            self.smoother_iterations.setEnabled(True)
            self.smoother_tolerance.setEnabled(True)
        elif self.btn_smoother_3.isChecked():
            self.smoothing_algorithm = 'angle_based'
            self.smoother_iterations.setEnabled(True)
            self.smoother_tolerance.setEnabled(True)

    def toggleRawPoints(self):
        """Toggle points of raw airfoil contour (on/off)"""
        if hasattr(self.parent.airfoil, 'polygonMarkersGroup'):
            visible = self.parent.airfoil.polygonMarkersGroup.isVisible()
            self.parent.airfoil.polygonMarkersGroup.setVisible(not visible)

    def toggleRawContour(self):
        """Toggle contour polygon of raw airfoil contour (on/off)"""
        if hasattr(self.parent.airfoil, 'contourPolygon'):
            visible = self.parent.airfoil.contourPolygon.isVisible()
            self.parent.airfoil.contourPolygon.setVisible(not visible)

    def toggleSplinePoints(self):
        """Toggle points of raw airfoil contour (on/off)"""
        if hasattr(self.parent.airfoil, 'splineMarkersGroup'):
            visible = self.parent.airfoil.splineMarkersGroup.isVisible()
            self.parent.airfoil.splineMarkersGroup.setVisible(not visible)

    def toggleSpline(self):
        if hasattr(self.parent.airfoil, 'contourSpline'):
            visible = self.parent.airfoil.contourSpline.isVisible()
            self.parent.airfoil.contourSpline.setVisible(not visible)

    def toggleChord(self):
        """Toggle visibility of the airfoil chord"""
        if hasattr(self.parent.airfoil, 'chord'):
            visible = self.parent.airfoil.chord.isVisible()
            self.parent.airfoil.chord.setVisible(not visible)

    def toggleMesh(self):
        """Toggle visibility of the mesh lines"""
        if hasattr(self.parent.airfoil, 'mesh'):
            visible = self.parent.airfoil.mesh.isVisible()
            self.parent.airfoil.mesh.setVisible(not visible)

    def toggleLeCircle(self):
        """Toggle visibility of the leading edge circle"""
        if hasattr(self.parent.airfoil, 'le_circle'):
            visible = self.parent.airfoil.le_circle.isVisible()
            self.parent.airfoil.le_circle.setVisible(not visible)

    def toggleMeshBlocks(self):
        """Toggle visibility of the mesh blocking structure"""
        if hasattr(self.parent.airfoil, 'mesh_blocks'):
            visible = self.parent.airfoil.mesh_blocks.isVisible()
            self.parent.airfoil.mesh_blocks.setVisible(not visible)

    def toggleCamberLine(self):
        """Toggle visibility of the airfoil camber line"""
        if hasattr(self.parent.airfoil, 'camberline'):
            visible = self.parent.airfoil.camberline.isVisible()
            self.parent.airfoil.camberline.setVisible(not visible)

    def runPanelMethod(self):
        """Gui callback to run AeroPython panel method in module PSvpMethod"""

        if self.parent.airfoil:
            # get coordinates of airfoil (raw data or if available spline)
            if self.parent.airfoil.spline_data:
                x, y = self.parent.airfoil.spline_data[0]
            else:
                x, y = self.parent.airfoil.raw_coordinates

            u_inf = self.freestream.value()
            alpha = self.aoaAP.value()
            panels = self.panels.value()
            SvpMethod.runSVP(self.parent.airfoil.name,
                             x, y, u_inf, alpha, panels)
        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def spline_and_refine(self):
        """Spline and refine airfoil"""

        if self.parent.airfoil:

            self.parent.airfoil.has_TE = False

            refine = SplineRefine.SplineRefine()
            refine.doSplineRefine(tolerance=self.tolerance.value(),
                                  points=self.points.value(),
                                  ref_te=self.ref_te.value(),
                                  ref_te_n=self.ref_te_n.value(),
                                  ref_te_ratio=self.ref_te_ratio.value())

            # add splined and refined contour to the airfoil contourGroup
            # makeSplineMarkers call within makeContourSpline
            self.parent.airfoil.makeContourSpline()

            # get LE radius, etc.
            spline_data = self.parent.airfoil.spline_data
            curvature_data = ca.ContourAnalysis.getCurvature(spline_data)
            rc, xc, yc, xle, yle, le_id = \
                ca.ContourAnalysis.getLeRadius(spline_data, curvature_data)
            refine.makeLeCircle(rc, xc, yc, xle, yle)

            # calculate thickness and camber
            camber = refine.getCamberThickness(spline_data, le_id)
            # draw camber
            self.parent.airfoil.drawCamber(camber)

            logger.info('Leading edge radius: {:11.8f}'.format(rc))
            logger.info('Leading edge circle tangent at point: {}'.format(le_id))

            # enable trailing edge button
            self.trailingButton.setEnabled(True)
            
            # enable export button
            self.exportContourButton.setEnabled(True)

        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def makeTrailingEdge(self):

        if self.parent.airfoil:

            self.parent.airfoil.has_TE = True

            if not hasattr(self.parent.airfoil, 'spline_data'):
                message = 'Splining needs to be done first.'
                self.parent.slots.messageBox(message)
                return

            trailing = TrailingEdge.TrailingEdge()
            trailing.trailingEdge(blend=self.blend_u.value() / 100.0,
                                  ex=self.exponent_u.value(),
                                  thickness=self.thickness.value(),
                                  side='upper')
            self.addTEtoScene()

            trailing.trailingEdge(blend=self.blend_l.value() / 100.0,
                                  ex=self.exponent_l.value(),
                                  thickness=self.thickness.value(),
                                  side='lower')
            self.addTEtoScene()
        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def addTEtoScene(self):
            
        # add modified spline contour to the airfoil contourGroup
        # makeSplineMarkers call within makeContourSpline
        self.parent.airfoil.makeContourSpline()
        self.parent.airfoil.contourSpline.brush.setStyle(QtCore.Qt.SolidPattern)
        color = QtGui.QColor()
        color.setNamedColor('#7c8696')
        self.parent.airfoil.contourSpline.brush.setColor(color)
        # FIXME
        # FIXME check if redundant, because already set elsewhere
        # FIXME
        self.parent.airfoil.polygonMarkersGroup.setZValue(100)
        self.parent.airfoil.chord.setZValue(99)
        self.parent.airfoil.camberline.setZValue(99)

        self.parent.view.adjustMarkerSize()

    def generateMesh(self):
        self.wind_tunnel = Meshing.Windtunnel()
        self.wind_tunnel.makeMesh()

    def analyzeAirfoil(self):
        """Airfoil contour analysis with respect to geometric features"""

        if not self.parent.airfoil:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

        # switch tab contour analysis
        self.parent.centralwidget.tabs.setCurrentIndex(1)
        # keep tab 'Contour Analysis'
        self.setCurrentIndex(self.tb3)

        # enable radio buttons for plotting when analysis starts
        self.cgb.setEnabled(True)

        # analyse contour
        self.parent.contourview.analyze()

        # connect signals to slots
        # lambda allows to send extra parameters
        self.cpb1.clicked.connect(lambda:
                                  self.parent.contourview
                                  .drawContour('gradient'))
        self.cpb2.clicked.connect(lambda:
                                  self.parent.contourview
                                  .drawContour('curvature'))
        self.cpb3.clicked.connect(lambda:
                                  self.parent.contourview
                                  .drawContour('radius'))

    def exportMesh(self):

        file_dialog = FileDialog.Dialog()
        file_dialog.setFilter('Mesh files (*.flma *.su2 *.msh *.inp *.cgns *.vtk)')
        filename, extension = os.path.splitext(self.parent.airfoil.name)
        filename, _ = file_dialog.saveFilename(filename)

        if not filename:
            logger.info('No file selected. Nothing saved.')
            return

        # clean extension again (because added by file_dialog return)
        filename, extension = os.path.splitext(filename)

        # add boundary definition attributes to mesh object
        self.wind_tunnel.boundary_airfoil = self.lineedit_airfoil.text()
        self.wind_tunnel.boundary_inlet = self.lineedit_inlet.text()
        self.wind_tunnel.boundary_outlet = self.lineedit_outlet.text()
        self.wind_tunnel.boundary_top = self.lineedit_top.text()
        self.wind_tunnel.boundary_bottom = self.lineedit_bottom.text()

        if self.check_FIRE.isChecked():
            name = filename + '.flma'
            Meshing.BlockMesh.writeFLMA(self.wind_tunnel,
                                        name=name)
        if self.check_SU2.isChecked():
            name = filename + '.su2'
            Meshing.BlockMesh.writeSU2_nolib(self.wind_tunnel, name=name)
        if self.check_GMSH.isChecked():
            name = filename + '.msh'
            Meshing.BlockMesh.writeGMSH_nolib(self.wind_tunnel, name=name)
        if self.check_VTK.isChecked():
            name = filename + '.vtu'
            Meshing.BlockMesh.writeVTK_nolib(self.wind_tunnel, name=name)

    def exportContour(self):

        file_dialog = FileDialog.Dialog()
        file_dialog.setFilter('Airfoil contour files (*.dat *.txt)')
        filename, _ = file_dialog.saveFilename(self.parent.airfoil.name)

        if not filename:
            logger.info('No file selected. Nothing saved.')
            return

        # get coordinates of modified contour
        x, y = self.parent.airfoil.spline_data[0]
        airfoil_name = self.parent.airfoil.name

        try:
            # export modified contour
            with open(filename, 'w') as f:
                f.write('#\n')
                f.write('# File created with ' + PyAero.__appname__ + '\n')
                f.write('# Version: ' + PyAero.__version__ + '\n')
                f.write('# Author: ' + PyAero.__author__ + '\n')
                f.write('#\n')
                f.write('# Derived from: %s\n' % (str(airfoil_name).strip()))
                f.write('# Number of points: %s\n' % (len(x)))
                f.write('#\n')
                for i, _ in enumerate(x):
                    f.write('{:10.6f} {:10.6f}\n'.format(x[i], y[i]))
        except IOError as error:
            logger.info('IO error: {}'.format(error))

        # log to message window
        logger.info('Contour saved as {}'.format(filename))


class ListWidget(QtWidgets.QListWidget):
    """Subclassing QListWidget in order to be able to catch key press
    events
    """
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

        self.itemClicked.connect(self.listItemClicked)
        self.itemDoubleClicked.connect(self.listItemDoubleClicked)

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_Delete:
            item = self.selectedItems()[0]
            row = self.row(item)
            self.takeItem(row)

            for airfoil in self.parent.airfoils:
                if item.text() == airfoil.name:
                    name = airfoil.name
                    self.parent.slots.removeAirfoil(name=name)
                    break

        # call original implementation of QListWidget keyPressEvent handler
        super().keyPressEvent(event)

    def listItemClicked(self, item):
        """show information of airfoil in message window"""
        pass

    def listItemDoubleClicked(self, item):
        """make double clicked name in listwidget new active airfoil"""
        for airfoil in self.parent.airfoils:
            if airfoil.name == item.text():
                # first clear all items from the scene
                self.parent.scene.clear()
                # activate double clicked airfoil
                airfoil.makeAirfoil()
                # add all airfoil items (contour markers) to the scene
                airfoil.addToScene(self.parent.scene)
                # make double clicked airfoil the currently active airfoil
                self.parent.airfoil = airfoil
                # adjust the marker size again
                self.mainwindow.view.adjustMarkerSize()
                break
