# -*- coding: utf-8 -*-

import os

from PySide2 import QtGui, QtCore, QtWidgets

import PyAero
import FileSystem
import IconProvider
import SvpMethod
import GraphicsItemsCollection as gc
import GraphicsItem
import SplineRefine
import TrailingEdge
import Logger as logger
import Meshing
import Connect
from Settings import ICONS_L, DIALOGFILTER, DIALOGFILTER_MESH, OUTPUTDATA


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
        self.itemContourModification()
        self.itemMeshing()
        self.itemViewingOptions()

        self.makeToolbox()

        self.currentChanged.connect(self.toolboxChanged)

    def toolboxChanged(self):

        if self.currentIndex() == self.tb4:
            self.updatePoints()

    def updatePoints(self):

        for airfoil in self.parent.airfoils or len(self.parent.airfoils) == 1:
            if airfoil.contourPolygon.isSelected():
                pts = len(airfoil.spline_data[0][0])
                break

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
        # allow multiple selections
        self.listwidget.setSelectionMode(QtWidgets.QAbstractItemView.
                                         ExtendedSelection)
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

        runbtn = QtWidgets.QPushButton('Calculate lift coefficient')
        form.addRow(runbtn)

        self.item_ap = QtWidgets.QGroupBox('AeroPython Panel Method')
        self.item_ap.setLayout(form)

        runbtn.clicked.connect(self.runPanelMethod)

    def itemContourAnalysis(self):

        box = QtWidgets.QVBoxLayout()

        hlayout = QtWidgets.QHBoxLayout()
        gb = QtWidgets.QGroupBox('Select contour to analyse')
        self.b1 = QtWidgets.QRadioButton('Original')
        self.b2 = QtWidgets.QRadioButton('Refined')
        self.b1.setChecked(True)
        hlayout.addWidget(self.b1)
        hlayout.addWidget(self.b2)
        gb.setLayout(hlayout)
        box.addWidget(gb)

        hlayout = QtWidgets.QHBoxLayout()
        self.cgb = QtWidgets.QGroupBox('Select plot quantity')
        self.cpb1 = QtWidgets.QRadioButton('Gradient')
        self.cpb2 = QtWidgets.QRadioButton('Curvature')
        self.cpb3 = QtWidgets.QRadioButton('Radius of Curvature')
        self.cpb1.setChecked(True)
        hlayout.addWidget(self.cpb1)
        hlayout.addWidget(self.cpb2)
        hlayout.addWidget(self.cpb3)
        self.cgb.setLayout(hlayout)
        self.cgb.setEnabled(False)
        box.addWidget(self.cgb)

        button1 = QtWidgets.QPushButton('Analyze')
        button1.setGeometry(10, 10, 200, 50)
        box.addWidget(button1)

        box.addStretch(1)

        self.item_ca = QtWidgets.QWidget()
        self.item_ca.setLayout(box)

        button1.clicked.connect(self.analyzeAirfoil)

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

        button = QtWidgets.QPushButton('Create Mesh')
        hbl_cm = QtWidgets.QHBoxLayout()
        hbl_cm.addStretch(stretch=1)
        hbl_cm.addWidget(button, stretch=4)
        hbl_cm.addStretch(stretch=1)

        # export menu
        name = ''
        hbox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel('Filename')
        self.lineedit_mesh = QtWidgets.QLineEdit(name)
        btn = QtWidgets.QPushButton('Browse')
        hbox.addWidget(lbl)
        hbox.addWidget(self.lineedit_mesh)
        hbox.addWidget(btn)

        button1 = QtWidgets.QPushButton('Export Mesh')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(button1, stretch=4)
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

        btn.clicked.connect(self.onBrowseMesh)
        button.clicked.connect(self.makeMesh)
        button1.clicked.connect(self.exportMesh)

    def itemViewingOptions(self):

        self.item_vo = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        self.item_vo.setLayout(layout)
        self.cb1 = QtWidgets.QCheckBox('Message Window')
        self.cb1.setChecked(True)
        self.cb2 = QtWidgets.QCheckBox('Airfoil Points')
        self.cb2.setChecked(True)
        self.cb3 = QtWidgets.QCheckBox('Airfoil Spline Points')
        self.cb3.setChecked(True)
        self.cb4 = QtWidgets.QCheckBox('Airfoil Spline Contour')
        self.cb4.setChecked(True)
        self.cb5 = QtWidgets.QCheckBox('Airfoil Chord')
        self.cb5.setChecked(True)
        layout.addWidget(self.cb1)
        layout.addWidget(self.cb2)
        layout.addWidget(self.cb3)
        layout.addWidget(self.cb4)
        layout.addWidget(self.cb5)
        layout.setAlignment(QtCore.Qt.AlignTop)

        # connect signals to slots
        # lambda allows to easily send extra parameters to the slot
        self.cb1.clicked.connect(lambda: self.parent.slots.toggleLogDock('tick'))
        self.cb2.clicked.connect(self.toggleRawPoints)
        self.cb3.clicked.connect(self.toggleSplinePoints)
        self.cb4.clicked.connect(self.toggleSpline)
        self.cb5.clicked.connect(self.toggleChord)

    def itemContourModification(self):

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

        button = QtWidgets.QPushButton('Spline and Refine')
        hbl = QtWidgets.QHBoxLayout()
        hbl.addStretch(stretch=1)
        hbl.addWidget(button, stretch=4)
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

        button1 = QtWidgets.QPushButton('Add Trailing Edge')
        hbl1 = QtWidgets.QHBoxLayout()
        hbl1.addStretch(stretch=1)
        hbl1.addWidget(button1, stretch=4)
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
        btn = QtWidgets.QPushButton('Browse')
        hbox.addWidget(lbl)
        hbox.addWidget(self.lineedit)
        hbox.addWidget(btn)

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

        button.clicked.connect(self.spline_and_refine)
        button1.clicked.connect(self.makeTrailingEdge)
        button.clicked.connect(self.updatename)
        button1.clicked.connect(self.updatename)
        btn.clicked.connect(self.onBrowse)

    def makeToolbox(self):

        # populate toolbox
        self.tb1 = self.addItem(self.item_fs, 'Airfoil Database')
        self.tb2 = self.addItem(self.item_cm,
                                        'Contour Splining and Refinement')
        self.tb4 = self.addItem(self.item_msh, 'Meshing')
        self.tb5 = self.addItem(self.item_ap, 'Aerodynamics')
        self.tb3 = self.addItem(self.item_ca, 'Contour Analysis')
        self.setItemEnabled(self.tb3, False)
        self.tb6 = self.addItem(self.item_vo, 'Viewing options')

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
        self.setItemIcon(5, QtGui.QIcon(ICONS_L + 'Configuration.png'))

        # preselect airfoil database box
        self.setCurrentIndex(0)

    # @QtCore.pyqtSlot()
    def toggleRawPoints(self):
        """Toggle points of raw airfoil contour (on/off)"""
        for airfoil in self.parent.airfoils:
            if hasattr(airfoil, 'markers') and \
              airfoil.contourPolygon.isSelected():
                visible = airfoil.markers.isVisible()
                airfoil.markers.setVisible(not visible)
                self.cb2.setChecked(not self.cb2.isChecked())

    # @QtCore.	()
    def toggleSplinePoints(self):
        """Toggle points of raw airfoil contour (on/off)"""
        for airfoil in self.parent.airfoils:
            if hasattr(airfoil, 'markersSpline') and \
              airfoil.contourPolygon.isSelected():
                visible = airfoil.markersSpline.isVisible()
                airfoil.markersSpline.setVisible(not visible)
                self.cb3.setChecked(not self.cb3.isChecked())

    # @QtCore.pyqtSlot()
    def toggleSpline(self):
        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                visible = airfoil.contourSpline.isVisible()
                airfoil.contourSpline.setVisible(not visible)
                self.cb4.setChecked(not self.cb4.isChecked())

    # @QtCore.pyqtSlot()
    def toggleChord(self):
        """Toggle visibility of the airfoil chord"""
        for airfoil in self.parent.airfoils:
            if hasattr(airfoil, 'chord') and airfoil.contourPolygon.isSelected():
                visible = airfoil.chord.isVisible()
                airfoil.chord.setVisible(not visible)
                self.cb5.setChecked(not self.cb5.isChecked())

    # @QtCore.pyqtSlot()
    def runPanelMethod(self):
        """Gui callback to run AeroPython panel method in module PSvpMethod"""
        if not self.parent.airfoils:
            self.noairfoilWarning('Can\'t run AeroPython')
            return

        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():

                x, y = airfoil.raw_coordinates
                u_inf = self.freestream.value()
                alpha = self.spin.value()
                panels = self.panels.value()
                SvpMethod.runSVP(airfoil.name, x, y, u_inf, alpha, panels)

    # @QtCore.pyqtSlot()
    def spline_and_refine(self):
        """Spline and refine airfoil"""

        # print('I am in Spline and Refine, filnally.\n')

        if not self.parent.airfoils:
            self.noairfoilWarning('Can\'t do splining and refining')
            return

        # print('Number of airfoils %s \n' % len(self.parent.airfoils))

        for airfoil in self.parent.airfoils:
            # print('Before IF\n')
            if airfoil.contourPolygon.isSelected():
                # print('Inside IF\n')
                id = self.parent.airfoils.index(airfoil)

                refine = SplineRefine.SplineRefine(id)
                # print('\n Tolerance', self.tolerance.value())
                refine.doSplineRefine(tolerance=self.tolerance.value(),
                                      points=self.points.value(),
                                      ref_te=self.ref_te.value(),
                                      ref_te_n=self.ref_te_n.value(),
                                      ref_te_ratio=self.ref_te_ratio.value())

    # @QtCore.pyqtSlot()
    def makeTrailingEdge(self):

        if not self.parent.airfoils:
            self.noairfoilWarning('Can\'t make trailing edge')
            return

        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                # check if splining already available
                if not hasattr(airfoil, 'spline_data'):
                    QtGui.QMessageBox. \
                        information(self.parent, 'Information',
                                    'Splining needs to be done first. %s.' %
                                    ('Can\'t make trailing edge'),
                                    QtGui.QMessageBox.Ok,
                                    QtGui.QMessageBox.NoButton,
                                    QtGui.QMessageBox.NoButton)
                    return

                id = self.parent.airfoils.index(airfoil)

                trailing = TrailingEdge.TrailingEdge(id)
                trailing.trailingEdge(blend=self.blend_u.value()/100.0,
                                      ex=self.exponent_u.value(),
                                      thickness=self.thickness.value(),
                                      side='upper')
                trailing.trailingEdge(blend=self.blend_l.value()/100.0,
                                      ex=self.exponent_l.value(),
                                      thickness=self.thickness.value(),
                                      side='lower')

    # @QtCore.pyqtSlot()
    def makeMesh(self):

        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                contour = airfoil.spline_data[0]
                break
            else:
                return

        progdialog = QtGui.QProgressDialog(
            "", "Cancel", 0, 4, self.parent)
        progdialog.setWindowTitle('Generating the CFD mesh')
        progdialog.setWindowModality(QtCore.Qt.WindowModal)
        progdialog.show()

        self.tunnel = Meshing.Windtunnel()

        progdialog.setValue(0)
        progdialog.setLabelText('making part 1/4')

        self.tunnel.AirfoilMesh(name='block_airfoil',
                                contour=contour,
                                divisions=self.points_n.value(),
                                ratio=self.ratio.value(),
                                thickness=self.normal_thickness.value()/100.0)
        progdialog.setValue(1)

        if progdialog.wasCanceled():
            return
        progdialog.setLabelText('making part 2/4')

        self.tunnel.TrailingEdgeMesh(name='block_TE',
                                     te_divisions=self.te_div.value(),
                                     length=self.length_te.value()/100.0,
                                     divisions=self.points_te.value(),
                                     ratio=self.ratio_te.value())
        progdialog.setValue(2)

        if progdialog.wasCanceled():
            return
        progdialog.setLabelText('making part 3/4')

        self.tunnel.TunnelMesh(name='block_tunnel',
                               tunnel_height=self.tunnel_height.value(),
                               divisions_height=self.divisions_height.value(),
                               ratio_height=self.ratio_height.value(),
                               dist=self.dist.currentText())
        progdialog.setValue(3)

        if progdialog.wasCanceled():
            return
        progdialog.setLabelText('making part 4/4')

        self.tunnel.TunnelMeshWake(name='block_tunnel_wake',
                                   tunnel_wake=self.tunnel_wake.value(),
                                   divisions=self.divisions_wake.value(),
                                   ratio=self.ratio_wake.value(),
                                   spread=self.spread.value()/100.0)
        progdialog.setValue(4)

        if progdialog.wasCanceled():
            return

        # connect mesh blocks
        connect = Connect.Connect()
        self.tunnel.mesh = connect.connectAllBlocks(self.tunnel.blocks)
        vertices, connectivity = self.tunnel.mesh

        logger.log.info('Mesh has %s vertices' % (len(vertices)))
        logger.log.info('Mesh has %s cells' % (len(connectivity)))

        self.drawMesh(airfoil)

        # enable mesh export and set filename
        self.box_meshexport.setEnabled(True)
        nameroot, extension = os.path.splitext(str(airfoil.name))
        self.lineedit_mesh.setText(nameroot + '_mesh')

    def drawMesh(self, airfoil):

        self.toggleSplinePoints()

        # delete old mesh if existing
        if hasattr(airfoil, 'mesh'):
            self.parent.scene.removeItem(airfoil.mesh)

        airfoil.mesh = QtWidgets.QGraphicsItemGroup(parent=airfoil.contourPolygon)
        self.parent.scene.addItem(airfoil.mesh)

        for block in self.tunnel.blocks:
            for lines in [block.getULines(),
                          block.getVLines()]:
                for line in lines:

                    # instantiate a graphics item
                    contour = gc.GraphicsCollection()
                    # make it polygon type and populate its points
                    points = [QtCore.QPointF(x, y) for x, y in line]
                    contour.Polyline(QtGui.QPolygonF(points), '')
                    # set its properties
                    contour.pen.setColor(QtGui.QColor(0, 0, 0, 255))
                    contour.pen.setWidth(0.8)
                    contour.pen.setCosmetic(True)
                    contour.brush.setStyle(QtCore.Qt.NoBrush)

                    # add contour as a GraphicsItem to the scene
                    # these are the objects which are drawn in the GraphicsView
                    meshline = GraphicsItem.GraphicsItem(contour)

                    airfoil.mesh.addToGroup(meshline)

        airfoil.contourGroup.addToGroup(airfoil.mesh)

    # @QtCore.pyqtSlot()
    def exportMesh(self, from_browse_mesh=False):

        name = self.lineedit_mesh.text()

        nameroot, extension = os.path.splitext(str(name))

        if from_browse_mesh:
            fullname = name
        else:
            fullname = OUTPUTDATA + nameroot

        mesh = self.tunnel.mesh

        if self.check_FIRE.isChecked():
            Meshing.BlockMesh.writeFLMA(mesh, name=fullname, depth=0.3)

        if self.check_SU2.isChecked():
            Meshing.BlockMesh.writeSU2(mesh, name=fullname)

        if self.check_GMSH.isChecked():
            Meshing.BlockMesh.writeGMSH(mesh, name=fullname)

    # @QtCore.pyqtSlot()
    def analyzeAirfoil(self):
        """Airfoil contour analysis with respect to geometric features"""

        if not self.parent.airfoils:
            self.noairfoilWarning('Can\'t do contour analysis')
            return

        # switch tab and toolbox to contour analysis
        self.parent.centralwidget.tabs.setCurrentIndex(1)
        self.setCurrentIndex(1)

        # enable radio buttons for plotting when analysis starts
        self.cgb.setEnabled(True)

        # select plot variable based on radio button state
        plot = 1*self.cpb1.isChecked() + 2*self.cpb2.isChecked() + \
            3*self.cpb3.isChecked()
        # analyse contour
        self.parent.contourview.analyze(plot)

        # connect signals to slots
        self.cpb1.clicked.connect(lambda:
                                  self.parent.contourview.drawContour(1))
        self.cpb2.clicked.connect(lambda:
                                  self.parent.contourview.drawContour(2))
        self.cpb3.clicked.connect(lambda:
                                  self.parent.contourview.drawContour(3))

    def noairfoilWarning(self, action):
        QtGui.QMessageBox. \
            information(self.parent, 'Information',
                        'No airfoil loaded. %s.' % (action),
                        QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton,
                        QtGui.QMessageBox.NoButton)
        return

    # @QtCore.pyqtSlot()
    def updatename(self):

        name = ' '

        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                name = airfoil.name
                break

        if name == ' ':
            return

        sending_button = self.parent.sender()
        nameroot, extension = os.path.splitext(str(name))

        if 'Spline' in sending_button.text():
            nameroot += '_Spline'
            self.lineedit.setText(nameroot + extension)
        if 'Trailing' in sending_button.text():
            nameroot += '_Spline_TE'
            self.lineedit.setText(nameroot + extension)

    def onBrowse(self):

        names = []

        dialog = QtGui.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        dialog.setNameFilter(DIALOGFILTER)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(OUTPUTDATA)
        # allow only to select one file
        dialog.setFileMode(QtGui.QFileDialog.AnyFile)
        # display also size and date
        dialog.setViewMode(QtGui.QFileDialog.Detail)
        # make it a save dialog
        dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
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
        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                x, y = airfoil.spline_data[0]

        # export modified contour
        with open(filename, 'w') as f:
            f.write('#\n')
            f.write('# File created with ' + PyAero.__appname__ + '\n')
            f.write('# Version: ' + PyAero.__version__ + '\n')
            f.write('# Author: ' + PyAero.__author__ + '\n')
            f.write('#\n')
            f.write('# Derived from: %s\n' % (str(airfoil.name).strip()))
            f.write('# Number of points: %s\n' % (len(x)))
            f.write('#\n')
            for i, xx in enumerate(x):
                f.write(2*'{:10.6f}'.format(x[i], y[i]) + '\n')

    def onBrowseMesh(self):

        names = []

        dialog = QtGui.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        dialog.setNameFilter(DIALOGFILTER_MESH)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(OUTPUTDATA)
        # allow only to select one file
        dialog.setFileMode(QtGui.QFileDialog.AnyFile)
        # display also size and date
        dialog.setViewMode(QtGui.QFileDialog.Detail)
        # make it a save dialog
        dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
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

        self.itemClicked.connect(self.handleActivated)

    def keyPressEvent(self, event):
        key = event.key()

        if key == QtCore.Qt.Key_Delete:
            items = self.selectedItems()
            for item in items:
                row = self.row(item)
                self.takeItem(row)
                delete = False
                for airfoil in self.parent.airfoils:
                    if item.text() == airfoil.name:
                        delete = True
                        break
                if delete:
                    self.parent.slots.removeAirfoil()

        # call original implementation of QListWidget keyPressEvent handler
        super().keyPressEvent(event)

    # @QtCore.pyqtSlot() commented here because otherewise
    # "item" is not available
    def handleActivated(self, item):

        for airfoil in self.parent.airfoils:
            airfoil.contourPolygon.setSelected(False)

        for selecteditem in self.selectedItems():
            for airfoil in self.parent.airfoils:
                if airfoil.name == selecteditem.text():
                    airfoil.contourPolygon.setSelected(True)
