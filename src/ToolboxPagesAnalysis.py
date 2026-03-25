from PySide6 import QtWidgets

from ToolboxWidgets import make_page_radio, right_aligned_row


def build_contour_analysis_panel(toolbox):
    box = QtWidgets.QVBoxLayout()

    vlayout = QtWidgets.QVBoxLayout()
    gb = QtWidgets.QGroupBox('Contour Source')
    toolbox.b1 = make_page_radio('Raw')
    toolbox.b2 = make_page_radio('Refined')
    toolbox.b2.setChecked(True)
    vlayout.addWidget(toolbox.b1)
    vlayout.addWidget(toolbox.b2)
    gb.setLayout(vlayout)
    box.addWidget(gb)

    vlayout = QtWidgets.QVBoxLayout()
    toolbox.cgb = QtWidgets.QGroupBox('Plot Quantity')
    toolbox.cpb1 = make_page_radio('Gradient')
    toolbox.cpb2 = make_page_radio('Curvature')
    toolbox.cpb3 = make_page_radio('Radius')
    toolbox.cpb1.setChecked(True)
    vlayout.addWidget(toolbox.cpb1)
    vlayout.addWidget(toolbox.cpb2)
    vlayout.addWidget(toolbox.cpb3)
    toolbox.cgb.setLayout(vlayout)
    toolbox.cgb.setEnabled(False)
    box.addWidget(toolbox.cgb)

    analyze_button = QtWidgets.QPushButton('Analyze Contour')
    analyze_button.setObjectName('pagePrimaryActionButton')
    box.addLayout(right_aligned_row(analyze_button))
    box.addStretch(1)

    toolbox.item_ca = QtWidgets.QWidget()
    toolbox.item_ca.setLayout(box)

    analyze_button.clicked.connect(toolbox.analyzeAirfoil)
    toolbox.cpb1.clicked.connect(toolbox.drawContourAnalysis)
    toolbox.cpb2.clicked.connect(toolbox.drawContourAnalysis)
    toolbox.cpb3.clicked.connect(toolbox.drawContourAnalysis)
