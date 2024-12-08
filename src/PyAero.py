#! /usr/bin/env python

"""
PyAero is an airfoil CFD meshing (2D) and contour analysis tool.

The meshing tool provides features to be able to create 2D CFD meshes
for numerical airfoil analysis (virtual wind tunnel).

The purpose of the contour analysis tool is to be able to read airfoil contour
data and analyze them with respect to smoothness and similar properties.
Functions allow splining, refinement, smoothing, etc. in order to provide
accurate input to the subsequent meshing process.
"""

import os
import sys
import platform

path_of_this_file = os.path.dirname(__file__)
sys.path.append(path_of_this_file)

import datetime

from PySide6 import QtGui, QtCore, QtWidgets

import MenusTools
import GraphicsView
import GraphicsScene
import GuiSlots
import ContourAnalysis
import ToolBox
from Settings import ICONS, LOCALE, EXITONESCAPE, \
                      OUTPUTDATA, MENUDATA, VIEWSTYLE, LOGDATA
import Logger
import ShortCuts
import BatchMode


__appname__ = 'PyAero'
__author__ = 'Andreas Ennemoser'
__credits__ = 'Internet and open source'
year = str(datetime.date.today().strftime("%Y"))
__copyright__ = '2014-' + year + ' ' + __author__
__license__ = 'MIT'
__version__ = '2.1.7'
__email__ = 'andreas.ennemoser@aon.at'
__status__ = 'Release'


class MainWindow(QtWidgets.QMainWindow):
    """PyAero's main QT window"""
    # constructor of MainWindow
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.app.mainwindow = self
        self.platform = platform.system()

        self.airfoil = None
        self.airfoils = []

        self.scene = GraphicsScene.GraphicsScene(self)
        self.view = GraphicsView.GraphicsView(self, self.scene)
        self.view.viewstyle = VIEWSTYLE

        self.contourview = ContourAnalysis.ContourAnalysis(canvas=True)
        self.slots = GuiSlots.Slots(self)
        self.centralwidget = CentralWidget(self)

        self.setCentralWidget(self.centralwidget)
        self._setupShortcuts()
        self.testitems = False

        self.checkEnvironment()
        self.init_GUI()
        Logger.log(self)

    def _setupShortcuts(self):
        sc = ShortCuts.ShortCuts(self)
        sc.addShortcut('ALT+m', 'toggleLogDock', 'shortcut')
        sc.addShortcut('ALT+t', 'toggleTestObjects')

    def init_GUI(self):

        # window size, position and title
        # self.setGeometry(700, 100, 1200, 900)
        self.showMaximized()
        title = __appname__ + ' - Airfoil Contour Analysis and CFD Meshing'
        self.setWindowTitle = title

        # create menus and tools of main window
        menusTools = MenusTools.MenusTools(self)
        menusTools.createMenus()
        menusTools.createTools()
        menusTools.createDocks()

        # create statusbar in main window
        self.statusbar = self.statusBar()
        self.statusbar.setFixedHeight(22)
        style = """
            QStatusBar {
            background-color: rgb(232, 232, 232);
            border: 1px solid grey;
            }
        """
        self.statusbar.setStyleSheet(style)
        self.statusbar.setSizeGripEnabled(False)
        self.statusbar.showMessage('Ready', 3000)

        # show the GUI
        self.show()

    def checkEnvironment(self):

        # check if path is correct
        if not os.path.exists(MENUDATA):
            error_message = (
            f'\n PyAero ERROR: Folder {MENUDATA} does not exist.\n'
            ' PyAero ERROR: Maybe you are starting PyAero from the wrong location.\n'
            )
            print(error_message)
            sys.exit()

        # check if output folder does exist
        if not os.path.exists(OUTPUTDATA):
            os.mkdir(OUTPUTDATA, mode=0o777)
            print('Folder %s created.' % (OUTPUTDATA))

        # check if logs folder does exist
        if not os.path.exists(LOGDATA):
            os.mkdir(LOGDATA, mode=0o777)
            print('Folder %s created.' % (LOGDATA))

    def keyPressEvent(self, event):
        """Catch keypress events in main window

        Args:
            event (QKeyEvent): key event sent to the widget with
            keyboard input focus
        """
        key = event.key()

        if key == QtCore.Qt.Key_Escape and EXITONESCAPE:
            sys.exit(self.app.exit(retcode=0))
        elif key == QtCore.Qt.Key_Home:
            self.slots.onViewAll()
        else:
            # progress event
            super().keyPressEvent(event)


class CentralWidget(QtWidgets.QWidget):
    """
    CentralWidget is a custom QWidget that serves as the central widget for the main window.
    It contains a splitter that divides the window into two panes: a toolbox and viewing options pane on the left,
    and a tabbed widget for different views on the right.

    Attributes:
        parent (QWidget): The parent widget.
        splitter (QSplitter): The main splitter dividing the window horizontally.
        toolbox (ToolBox.Toolbox): A toolbox widget for various tools.
        viewing_options (QGroupBox): A group box containing viewing options checkboxes.
        left_pane (QWidget): The left pane containing the toolbox and viewing options.
        tabs (QTabWidget): The tabbed widget containing different views.

    Methods:
        __init__(self, parent=None):
            Initializes the CentralWidget, sets up the layout, and connects signals.
        
        viewingOptions(self):
            Creates and configures the viewing options group box with checkboxes.
    """
    # call constructor of CentralWidget
    def __init__(self, parent=None):
        # call constructor of QWidget
        super().__init__(parent)

        self.parent = parent

        # split main window horizontally into two panes
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # create QToolBox widget
        self.toolbox = ToolBox.Toolbox(self.parent)

        # create box where viewing options are placed
        self.viewingOptions()

        horizontal_line = QtWidgets.QFrame()
        horizontal_line.setFrameShape(QtWidgets.QFrame.HLine)
        horizontal_line.setFrameShadow(QtWidgets.QFrame.Sunken)

        self.left_pane = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.toolbox)
        vbox.addStretch(5)
        vbox.addWidget(horizontal_line)
        vbox.addSpacing(15)
        vbox.addWidget(self.viewing_options)
        self.left_pane.setLayout(vbox)

        # create tabbed windows for viewing
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.parent.view, 'Airfoil Viewer')
        self.tabs.addTab(self.parent.contourview, 'Contour Analysis')

        # connect tab changed signal to slot
        self.tabs.currentChanged.connect(self.parent.slots.onTabChanged)

        # add splitter panes
        self.splitter.addWidget(self.left_pane)
        self.splitter.addWidget(self.tabs)
        self.splitter.setSizes([100, 1300])  # initial hint for splitter spacing

        # put splitter in a layout box
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.splitter)
        self.setLayout(hbox)

    def viewingOptions(self):
        self.viewing_options = QtWidgets.QGroupBox('Viewing Options')

        # Set font size via CSS workaround
        font = self.viewing_options.font()
        font.setPointSize(13)
        self.viewing_options.setFont(font)

        # Layouts for organizing checkboxes
        hbox = QtWidgets.QHBoxLayout()
        vbox1 = QtWidgets.QVBoxLayout()
        vbox2 = QtWidgets.QVBoxLayout()
        self.viewing_options.setLayout(hbox)

        # Checkboxes for viewing options
        checkboxes = [
            ('Message Window', True, True, self.parent.slots.toggleLogDock, 'tick'),
            ('Airfoil Points', False, False, self.toolbox.toggleRawPoints),
            ('Airfoil Raw Contour', False, False, self.toolbox.toggleRawContour),
            ('Airfoil Spline Points', False, False, self.toolbox.toggleSplinePoints),
            ('Airfoil Spline Contour', False, False, self.toolbox.toggleSpline),
            ('Airfoil Chord', False, False, self.toolbox.toggleChord),
            ('Mesh', False, False, self.toolbox.toggleMesh),
            ('Leading Edge Circle', False, False, self.toolbox.toggleLeCircle),
            ('Mesh Blocks', False, False, self.toolbox.toggleMeshBlocks),
            ('Airfoil Camber Line', False, False, self.toolbox.toggleCamberLine)
        ]

        # Create and add checkboxes to layouts
        for i, (label, checked, enabled, slot, *args) in enumerate(checkboxes):
            checkbox = QtWidgets.QCheckBox(label)
            checkbox.setChecked(checked)
            checkbox.setEnabled(enabled)
            if args:
                checkbox.clicked.connect(lambda _, s=slot, a=args[0]: s(a))
            else:
                checkbox.clicked.connect(slot)
            if i == 0:
                vbox2.addWidget(checkbox)
            else:
                vbox1.addWidget(checkbox)

            # Set attribute for each checkbox with a meaningful name
            attribute_name = label.lower().replace(' ', '_') + '_checkbox'
            setattr(self, attribute_name, checkbox)

        hbox.addLayout(vbox1)
        hbox.addLayout(vbox2)
        hbox.setAlignment(QtCore.Qt.AlignTop)


def main():

    # check if the user is running the program in batch mode
    batchmode = '-no-gui' in sys.argv

    # run PyAero in batch mode
    if batchmode:
        app = QtCore.QCoreApplication(sys.argv)

        # FIXME
        # FIXME check for proper batch control file
        # FIXME
        if sys.argv[-1] == '-no-gui':
            print('No batch control file specified.')
            sys.exit()

        # prepare logger
        Logger.log('file_only')

        batch_controlfile = sys.argv[-1]
        batchmode = BatchMode.Batch(app, batch_controlfile, __version__)
        batchmode.run_batch()

        return

    # main application (contains the main event loop)
    # run PyAero in GUI mode
    app = QtWidgets.QApplication(sys.argv)

    # set icon for the application ( upper left window icon and taskbar icon)
    # and add specialization icons per size
    # (needed depending on the operating system)
    app_icon = QtGui.QIcon(os.path.join(ICONS, 'app_image.png'))
    icon_sizes = [16, 24, 32, 48, 256]
    for size in icon_sizes:
        app_icon.addFile(os.path.join(ICONS, f'app_image_{size}x{size}.png'), QtCore.QSize(size, size))

    app.setWindowIcon(app_icon)

    if LOCALE == 'C':
        # set default locale to C, so that decimal separator is a
        # dot in spin boxes, etc.
        QtCore.QLocale.setDefault(QtCore.QLocale.c())

    # window style set in Settings.py
    window = MainWindow(app)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
