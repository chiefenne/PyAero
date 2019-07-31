# -*- coding: utf-8 -*-

import os

from PySide2 import QtGui, QtCore, QtWidgets

import PyAero
import Airfoil
import FileSystem
import IconProvider
import SvpMethod
import SplineRefine
import TrailingEdge
import Meshing
from Settings import ICONS_L, DIALOGFILTER, DIALOGFILTER_MESH, OUTPUTDATA

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

        # set the style
        style = (""" QToolBox::tab:selected {font: bold; } """)
        self.setStyleSheet(style)

        # create toolbox items
        self.itemFileSystem()
        self.itemAeropython()
        self.itemContourAnalysis()
        self.itemSplineRefine()
        self.itemMeshing()

        self.makeToolbox()

        self.currentChanged.connect(self.toolboxChanged)

    def toolboxChanged(self):
        # tb1 = 'Airfoil Database'
        # tb2 = 'Contour Splining and Refinement'
        # tb4 = 'Meshing'
        # tb5 = 'Aerodynamics'
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
        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setSingleStep(0.1)
        self.spin.setDecimals(1)
        self.spin.setRange(-10.0, 10.0)
        self.spin.setValue(0.0)
        form.addRow(label1, self.spin)

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

        label = QtWidgets.QLabel('Thickness normal to Airfoil (%)')
        label.setToolTip('The thickness is specified wrt to the unit chord')
        self.normal_thickness = QtWidgets.QDoubleSpinBox()
        self.normal_thickness.setSingleStep(0.1)
        self.normal_thickness.setRange(1., 10.)
        self.normal_thickness.setValue(4.0)
        self.normal_thickness.setDecimals(1)
        self.form_mesh_airfoil.addRow(label, self.normal_thickness)

        label = QtWidgets.QLabel('Cell Thickness ratio (-)')
        label.setToolTip('Thickness of the last cell vs. the first cell in ' +
                         'the airfoil mesh block' +
                         '\nThe first cell is the one attached to the airfoil')
        self.ratio = QtWidgets.QDoubleSpinBox()
        self.ratio.setSingleStep(0.1)
        self.ratio.setRange(1., 10.)
        self.ratio.setValue(3.0)
        self.ratio.setDecimals(1)
        self.form_mesh_airfoil.addRow(label, self.ratio)

        self.form_mesh_TE = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel(u'Divisions at trailing edge')
        label.setToolTip('Number of subdivisions along the vertical part of the TE')
        self.te_div = QtWidgets.QSpinBox()
        self.te_div.setSingleStep(1)
        self.te_div.setRange(1, 20)
        self.te_div.setValue(3)
        self.form_mesh_TE.addRow(label, self.te_div)

        label = QtWidgets.QLabel(u'Divisions downstream trailing edge')
        self.points_te = QtWidgets.QSpinBox()
        self.points_te.setSingleStep(1)
        self.points_te.setRange(1, 100)
        self.points_te.setValue(6)
        self.form_mesh_TE.addRow(label, self.points_te)

        label = QtWidgets.QLabel('Length behind trailing edge (%)')
        label.setToolTip('The length is specified wrt to the unit chord')
        self.length_te = QtWidgets.QDoubleSpinBox()
        self.length_te.setSingleStep(0.1)
        self.length_te.setRange(0.1, 30.)
        self.length_te.setValue(4.0)
        self.length_te.setDecimals(1)
        self.form_mesh_TE.addRow(label, self.length_te)

        label = QtWidgets.QLabel('Cell Thickness ratio (-)')
        label.setToolTip('Thickness of the last cell vs. the first cell in ' +
                         'the trailing edge mesh block' + '\n'
                         'The first cell is the one attached to the airfoil ' +
                         'trailing edge')
        self.ratio_te = QtWidgets.QDoubleSpinBox()
        self.ratio_te.setSingleStep(0.1)
        self.ratio_te.setRange(1., 10.)
        self.ratio_te.setValue(3.0)
        self.ratio_te.setDecimals(1)
        self.form_mesh_TE.addRow(label, self.ratio_te)

        self.form_mesh_tunnel = QtWidgets.QFormLayout()

        label = QtWidgets.QLabel('Windtunnel Height (chords)')
        label.setToolTip('The height of the windtunnel in units ' +
                         'of chord length')
        self.tunnel_height = QtWidgets.QDoubleSpinBox()
        self.tunnel_height.setSingleStep(0.1)
        self.tunnel_height.setRange(1.0, 10.)
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
        self.tunnel_wake.setRange(0.1, 50.)
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
        label.setToolTip('Equalize vertical the wake line. ' +
                         'Homogeneous vertical distribution x% downstream')
        self.spread = QtWidgets.QDoubleSpinBox()
        self.spread.setSingleStep(5.0)
        self.spread.setRange(10.0, 90.0)
        self.spread.setValue(30.0)
        self.spread.setDecimals(1)
        self.form_mesh_wake.addRow(label, self.spread)

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

        createMeshButton = QtWidgets.QPushButton('Create Mesh')
        hbl_cm = QtWidgets.QHBoxLayout()
        hbl_cm.addStretch(stretch=1)
        hbl_cm.addWidget(createMeshButton, stretch=4)
        hbl_cm.addStretch(stretch=1)

        # export menu
        name = ''
        hbox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel('Filename')
        self.lineedit_mesh = QtWidgets.QLineEdit(name)
        browseMeshButton = QtWidgets.QPushButton('Browse')
        hbox.addWidget(lbl)
        hbox.addWidget(self.lineedit_mesh)
        hbox.addWidget(browseMeshButton)

        exportMeshButton = QtWidgets.QPushButton('Export Mesh')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(exportMeshButton, stretch=4)
        hbl.addStretch(stretch=1)

        rdl = QtWidgets.QHBoxLayout()
        btn_group = QtWidgets.QButtonGroup()
        self.check_FIRE = QtWidgets.QCheckBox('AVL FIRE')
        self.check_SU2 = QtWidgets.QCheckBox('SU2')
        self.check_GMSH = QtWidgets.QCheckBox('GMSH')
        btn_group.addButton(self.check_FIRE)
        btn_group.addButton(self.check_SU2)
        self.check_FIRE.setChecked(True)
        self.check_SU2.setChecked(False)
        self.check_GMSH.setChecked(False)
        rdl.addStretch(5)
        rdl.addWidget(self.check_FIRE)
        rdl.addStretch(1)
        rdl.addWidget(self.check_SU2)
        rdl.addStretch(1)
        rdl.addWidget(self.check_GMSH)
        rdl.addStretch(5)

        vbl1 = QtWidgets.QVBoxLayout()
        vbl1.addLayout(rdl)
        vbl1.addLayout(hbox)
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
        vbl.addLayout(hbl_cm)
        vbl.addStretch(1)
        vbl.addWidget(self.box_meshexport)
        vbl.addStretch(10)

        self.item_msh = QtWidgets.QWidget()
        self.item_msh.setLayout(vbl)

        browseMeshButton.clicked.connect(self.onBrowseMesh)
        createMeshButton.clicked.connect(self.generateMesh)
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

        splineButton = QtWidgets.QPushButton('Spline and Refine')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(splineButton, stretch=4)
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

        trailingButton = QtWidgets.QPushButton('Add Trailing Edge')
        hbl1 = QtWidgets.QHBoxLayout()
        hbl1.addStretch(stretch=1)
        hbl1.addWidget(trailingButton, stretch=4)
        hbl1.addStretch(stretch=1)

        vbox = QtWidgets.QVBoxLayout()
        vbox.addLayout(form1)
        vbox.addLayout(hbl1)
        box1 = QtWidgets.QGroupBox('Airfoil trailing edge')
        box1.setLayout(vbox)

        # export menu
        name = ''
        hbox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel('Filename')
        self.lineedit = QtWidgets.QLineEdit(name)
        exportContourButton = QtWidgets.QPushButton('Export Contour')
        hbox.addWidget(lbl)
        hbox.addWidget(self.lineedit)
        hbox.addWidget(exportContourButton)

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

        splineButton.clicked.connect(self.spline_and_refine)
        trailingButton.clicked.connect(self.makeTrailingEdge)
        splineButton.clicked.connect(lambda: self.updatename('spline'))
        trailingButton.clicked.connect(lambda: self.updatename('trailing'))
        exportContourButton.clicked.connect(self.onBrowse)

    def makeToolbox(self):

        # populate toolbox
        self.tb1 = self.addItem(self.item_fs, 'Airfoil Database')
        self.tb2 = self.addItem(self.item_cm,
                                'Contour Splining and Refinement')
        self.tb4 = self.addItem(self.item_msh, 'Meshing')
        self.tb5 = self.addItem(self.item_ap, 'Aerodynamics')
        self.tb3 = self.addItem(self.item_ca, 'Contour Analysis')

        self.setItemToolTip(0, 'Airfoil database ' +
                            '(browse filesystem)')
        self.setItemToolTip(1, 'Spline and refine the contour')
        self.setItemToolTip(2, 'Generate a 2D mesh around the ' +
                            'selected airfoil')
        self.setItemToolTip(3, 'Compute panel based aerodynamic ' +
                            'coefficients')
        self.setItemToolTip(4, 'Analyze the curvature of the ' +
                            'selected airfoil')

        self.setItemIcon(0, QtGui.QIcon(ICONS_L + 'airfoil.png'))
        self.setItemIcon(1, QtGui.QIcon(ICONS_L + 'Pixel editor.png'))
        self.setItemIcon(2, QtGui.QIcon(ICONS_L + 'mesh.png'))
        self.setItemIcon(3, QtGui.QIcon(ICONS_L + 'Fast delivery.png'))
        self.setItemIcon(4, QtGui.QIcon(ICONS_L + 'Pixel editor.png'))

        # preselect airfoil database box
        self.setCurrentIndex(self.tb1)

    def toggleRawPoints(self):
        """Toggle points of raw airfoil contour (on/off)"""
        if hasattr(self.parent.airfoil, 'polygonMarkersGroup'):
            visible = self.parent.airfoil.polygonMarkersGroup.isVisible()
            self.parent.airfoil.polygonMarkersGroup.setVisible(not visible)

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

    def runPanelMethod(self):
        """Gui callback to run AeroPython panel method in module PSvpMethod"""

        if self.parent.airfoil:
            x, y = self.parent.airfoil.raw_coordinates
            u_inf = self.freestream.value()
            alpha = self.spin.value()
            panels = self.panels.value()
            SvpMethod.runSVP(self.parent.airfoil.name,
                             x, y, u_inf, alpha, panels)
        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def spline_and_refine(self):
        """Spline and refine airfoil"""

        if self.parent.airfoil:
            refine = SplineRefine.SplineRefine()
            refine.doSplineRefine(tolerance=self.tolerance.value(),
                                  points=self.points.value(),
                                  ref_te=self.ref_te.value(),
                                  ref_te_n=self.ref_te_n.value(),
                                  ref_te_ratio=self.ref_te_ratio.value())
        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def makeTrailingEdge(self):

        if self.parent.airfoil:
            if not hasattr(self.parent.airfoil, 'spline_data'):
                message = 'Splining needs to be done first.'
                self.parent.slots.messageBox(message)
                return

            trailing = TrailingEdge.TrailingEdge()
            trailing.trailingEdge(blend=self.blend_u.value()/100.0,
                                  ex=self.exponent_u.value(),
                                  thickness=self.thickness.value(),
                                  side='upper')
            trailing.trailingEdge(blend=self.blend_l.value()/100.0,
                                  ex=self.exponent_l.value(),
                                  thickness=self.thickness.value(),
                                  side='lower')
        else:
            self.parent.slots.messageBox('No airfoil loaded.')
            return

    def generateMesh(self):
        self.wind_tunnel = Meshing.Windtunnel()
        self.wind_tunnel.makeMesh()

    def exportMesh(self, from_browse_mesh=False):

        name = self.lineedit_mesh.text()

        nameroot, extension = os.path.splitext(str(name))

        if from_browse_mesh:
            fullname = name
        else:
            fullname = OUTPUTDATA + nameroot

        mesh = self.wind_tunnel.mesh
        blocks = self.wind_tunnel.blocks

        if self.check_FIRE.isChecked():
            Meshing.BlockMesh.writeFLMA(mesh, blocks, name=fullname)
        elif self.check_SU2.isChecked():
            Meshing.BlockMesh.writeSU2(mesh, blocks, name=fullname)
        elif self.check_GMSH.isChecked():
            Meshing.BlockMesh.writeGMSH(mesh, blocks, name=fullname)

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
                                  self.parent.contourview.drawContour('gradient'))
        self.cpb2.clicked.connect(lambda:
                                  self.parent.contourview.drawContour('curvature'))
        self.cpb3.clicked.connect(lambda:
                                  self.parent.contourview.drawContour('radius'))

    def updatename(self, sender_button):

        name = self.parent.airfoil.name

        nameroot, extension = os.path.splitext(str(name))

        if 'spline' in sender_button:
            nameroot += '_Spline'
            self.lineedit.setText(nameroot + extension)
        if 'trailing' in sender_button:
            nameroot += '_Spline_TE'
            self.lineedit.setText(nameroot + extension)

    def onBrowse(self):

        names = []

        dialog = QtWidgets.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        dialog.setNameFilter(DIALOGFILTER)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(OUTPUTDATA)
        # allow only to select one file
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        # display also size and date
        dialog.setViewMode(QtWidgets.QFileDialog.Detail)
        # make it a save dialog
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        # put default name in the save dialog
        dialog.selectFile(self.lineedit.text())

        # open custom file dialog using custom icons
        if dialog.exec_():
            names = dialog.selectedFiles()
            # filter = dialog.selectedFilter()

        if not names:
            return

        # names is a list of QStrings
        filename = str(names[0])

        # get coordinates of modified contour
        x, y = self.parent.airfoil.spline_data[0]
        airfoil_name = self.parent.airfoil.name

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
            for i, xx in enumerate(x):
                f.write(2*'{:10.6f}'.format(x[i], y[i]) + '\n')

    def onBrowseMesh(self):

        names = []

        dialog = QtWidgets.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        dialog.setOptions(options)
        dialog.setNameFilter(DIALOGFILTER_MESH)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(OUTPUTDATA)
        # allow only to select one file
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        # display also size and date
        dialog.setViewMode(QtWidgets.QFileDialog.Detail)
        # make it a save dialog
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        # put default name in the save dialog
        dialog.selectFile(self.lineedit_mesh.text())

        # open custom file dialog using custom icons
        if dialog.exec_():
            names = dialog.selectedFiles()
            # filter = dialog.selectedFilter()

        if not names:
            return

        # names is a list of QStrings
        filename = str(names[0])

        self.lineedit_mesh.setText(filename)

        self.exportMesh(from_browse_mesh=True)


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
                Airfoil.Airfoil.addToScene(airfoil, self.parent.scene)
                # make double clicked airfoil the currently active airfoil
                self.parent.airfoil = airfoil
                # adjust the marker size again
                self.mainwindow.view.adjustMarkerSize()
                break
