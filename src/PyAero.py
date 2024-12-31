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
import datetime

# Add the directory containing the script to the sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6 import QtGui, QtCore, QtWidgets

import Settings
import MenusTools
import GraphicsView
import GraphicsScene
import GuiSlots
import ContourAnalysis
import ToolBox
import BatchMode
import Logger


__appname__ = 'PyAero'
__author__ = 'Andreas Ennemoser'
__credits__ = 'Internet and open source'
year = str(datetime.date.today().strftime("%Y"))
__copyright__ = '2014-' + year + ' ' + __author__
__license__ = 'MIT'
__version__ = '3.0.0'
__email__ = 'andreas.ennemoser@aon.at'
__status__ = 'Release'



class MainWindow(QtWidgets.QMainWindow):
    """PyAero's main QT window"""

    # Initialize the MainWindow
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.app.mainwindow = self
        self.platform = platform.system()
        self.config = Settings.Config(self)

        self.airfoil = None
        self.airfoils = []

        self.scene = GraphicsScene.GraphicsScene(self)
        self.view = GraphicsView.GraphicsView(self.scene)
        self.view.viewstyle = self.VIEW_STYLE

        self.contourview = ContourAnalysis.ContourAnalysis(canvas=True)
        self.slots = GuiSlots.Slots()

        # The QMainWindow class is designed around a specific architecture that includes
        # dedicated areas for menus, toolbars, dock widgets, a status bar, and a main content area.
        # The central widget is the widget that occupies this main content area.
        self.mainArea = MainContentArea(self)
        self.setCentralWidget(self.mainArea)

        self._setupShortcuts()
        self.checkEnvironment()
        self.init_GUI()

        Logger.log(self)

    def _setupShortcuts(self):
        shortcut_message_dock = QtGui.QShortcut(QtGui.QKeySequence('ALT+m'), self)
        shortcut_message_dock.activated.connect(self.slots.toggleLogDock('shortcut'))
        shortcut_message_dock.setContext(QtCore.Qt.ApplicationShortcut)

    def init_GUI(self):

        # window size, position and title
        self.showMaximized()
        title = __appname__ + ' - Airfoil Contour Analysis and CFD Meshing'
        self.setWindowTitle = title

        # decimal separator used in spin boxes, etc.
        if self.DECIMAL_SEPARATOR == '.':
            QtCore.QLocale.setDefault(QtCore.QLocale.c())
        elif self.DECIMAL_SEPARATOR == ',':
            QtCore.QLocale.setDefault(QtCore.QLocale.German, QtCore.QLocale.Germany)

        # create menus and tools of main window
        menusTools = MenusTools.MenusTools()
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
        """Check if the environment is set up correctly"""

        # check if path is correct
        if not os.path.exists('resources/Menus'):
            error_message = (
            f'\n PyAero-ERROR: Folder "resources/Menus" does not exist.\n'
            ' PyAero-ERROR: Either the installation is incomplete or you are starting from the wrong location.\n'
            )
            print(error_message)
            sys.exit()

        # Ensure output folder exists
        os.makedirs(self.OUTPUT, mode=0o777, exist_ok=True)

        # Ensure logs folder exists
        os.makedirs(self.LOGS, mode=0o777, exist_ok=True)

    def keyPressEvent(self, event):
        """Catch keypress events in main window

        Args:
            event (QKeyEvent): key event sent to the widget with
            keyboard input focus
        """
        key = event.key()

        if key == QtCore.Qt.Key_Escape and self.EXIT_ON_ESCAPE:
            QtCore.QCoreApplication.quit()
        elif key == QtCore.Qt.Key_Home:
            self.slots.onViewAll()
        else:
            # progress event
            super().keyPressEvent(event)


class MainContentArea(QtWidgets.QWidget):
    """
    MainContentArea is a custom QWidget that serves as the central widget for the main window.
    
    It contains a splitter that divides the window into two panes:
    - a toolbox and viewing options pane on the left
    - a tabbed widget for different views on the right.

    """

    def __init__(self, parent=None):
        # call constructor of QWidget
        super().__init__(parent)

        self.parent = parent

        # split main window horizontally into two panes
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # create QToolBox widget
        self.toolbox = ToolBox.Toolbox()

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
    # Check if running in batch mode
    if '-no-gui' in sys.argv:
        app = QtCore.QCoreApplication(sys.argv)

        if sys.argv[-1] == '-no-gui':
            print('No batch control file specified.')
            sys.exit()

        # Prepare logger
        Logger.log('console')

        batch_controlfile = sys.argv[-1]
        batchmode = BatchMode.Batch(app, batch_controlfile, __version__)
        batchmode.run_batch()
        return

    # Run in GUI mode
    app = QtWidgets.QApplication(sys.argv)

    # Set icon for the application
    app_icon = QtGui.QIcon('resources/Icons/app_image.png')
    for size in [24, 256]:
        app_icon.addFile(f'resources/Icons/app_image_{size}x{size}.png'), QtCore.QSize(size, size)
    app.setWindowIcon(app_icon)

    # Window style set in Settings.py
    window = MainWindow(app)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
