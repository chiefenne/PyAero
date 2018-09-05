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

path_of_this_file = os.path.dirname(__file__)
sys.path.append(path_of_this_file)

import datetime

from PySide2 import QtGui, QtCore, QtWidgets

import MenusTools
import GraphicsView
import GraphicsScene
import GuiSlots
import ContourAnalysis
import ToolBox
from Settings import ICONS, LOCALE, STYLE, EXITONESCAPE, \
                      OUTPUTDATA, MENUDATA, VIEWSTYLE, LOGDATA
import Logger
import ShortCuts

try:
    import VtkView
    VTK_installed = True
except ImportError:
    VTK_installed = False

# VTK needs to be extra investigated by me as the old
VTK_installed = False

__appname__ = 'PyAero'
__author__ = 'Andreas Ennemoser'
__credits__ = 'Internet and open source'
__copyright__ = '2014-' + str(datetime.date.today().strftime("%Y")) + \
                ' ' + __author__
__license__ = 'MIT'
__version__ = '1.1.0'
__email__ = 'andreas.ennemoser@aon.at'
__status__ = 'Release'


class MainWindow(QtWidgets.QMainWindow):
    """PyAero's main QT window"""
    # constructor of MainWindow
    def __init__(self, app, style):
        # constructor of QMainWindow
        super().__init__()

        self.checkEnvironment()

        # set application wide attributes
        # access via "QtCore.QCoreApplication.instance().xxx"
        # helps to overcome nested usage of "parent"
        self.app = app
        self.app.mainwindow = self

        self.style = style        
        ### styles do not work anymore; need to come back      
        # style_keys = [x.lower() for x in QtWidgets.QStyleFactory.keys()]
        # FIXME
        # FIXME currently leads to segmentation faults
        # FIXME
        # if self.style.lower() in style_keys:
        #     QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create(style))

        # holds active airfoil
        self.airfoil = None
        # container for all loaded airfoils
        self.airfoils = list()

        self.scene = GraphicsScene.GraphicsScene(self)

        self.view = GraphicsView.GraphicsView(self, self.scene)
        self.view.viewstyle = VIEWSTYLE

        # prepare additional views for tabs in right splitter window
        self.contourview = ContourAnalysis.ContourAnalysis()

        # send same scene to meshingview as above
        # self.meshingview = GraphicsView.GraphicsView(self, self.scene)

        if VTK_installed:
            self.postview = VtkView.VtkWindow(self)
        # self.htmlview = PHtmlView.HtmlView(self)

        # create slots (i.e. handlers or callbacks)
        self.slots = GuiSlots.Slots(self)

        # set central widget for the application
        self.centralwidget = CentralWidget(self)

        self.setCentralWidget(self.centralwidget)

        # add a shortcut for toggling the message window
        sc = ShortCuts.ShortCuts(self)
        sc.addShortcut('ALT+m', 'toggleLogDock', 'shortcut')

        # shortcut for test items
        sc.addShortcut('ALT+t', 'toggleTestObjects')

        # initialize test items (checked in toggleTestObjects)
        self.testitems = False

        # setup user interface and menus
        self.init_GUI()

        # prepare logger
        Logger.log(self)

    def init_GUI(self):

        # window size, position and title
        # self.setGeometry(700, 100, 1200, 900)
        self.showMaximized()
        self.setWindowTitle(__appname__ +
                            ' - Airfoil Contour Analysis and CFD Meshing')

        # create menus and tools of main window
        menusTools = MenusTools.MenusTools(self)
        menusTools.createMenus()
        menusTools.createTools()
        menusTools.createStatusBar()
        menusTools.createDocks()

        # show the GUI
        self.show()

    def checkEnvironment(self):

        # check if path is correct
        if not os.path.exists(MENUDATA):
            print ('\n PyAero ERROR: Folder %s does not exist.' % (MENUDATA))
            print (' PyAero ERROR: Maybe you are starting PyAero from the wrong location.\n')
            sys.exit()

        # check if output folder does exist
        if not os.path.exists(OUTPUTDATA):
            os.mkdir(OUTPUTDATA, mode=0o777)
            print ('Folder %s created.' % (OUTPUTDATA))

        # check if logs folder does exist
        if not os.path.exists(LOGDATA):
            os.mkdir(LOGDATA, mode=0o777)
            print ('Folder %s created.' % (LOGDATA))

    # ********************************
    # slots which are not in PGuiSlots
    # ********************************

    def keyPressEvent(self, event):
        """Catch keypress events in main window

        Args:
            event (QKeyEvent): key event sent to the widget with
            keyboard input focus
        """
        key = event.key()

        if key == QtCore.Qt.Key_Escape and EXITONESCAPE:
            sys.exit(QtGui.qApp.quit())
        elif key == QtCore.Qt.Key_Home:
            self.slots.onViewAll()
        else:
            # progress event
            super().keyPressEvent(event)


class CentralWidget(QtWidgets.QWidget):
    # call constructor of CentralWidget
    def __init__(self, parent=None):
        # call constructor of QWidget
        super().__init__(parent)

        self.parent = parent

        # split main window horizontally into two panes
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # add QToolBox widget to the left pane
        self.toolbox = ToolBox.Toolbox(self.parent)
        self.splitter.addWidget(self.toolbox)

        # create tabbed windows for viewing
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.parent.view, 'Airfoil Viewer')
        self.tabs.addTab(self.parent.contourview, 'Contour Analysis')
        # self.tabs.addTab(self.parent.meshingview, 'Meshing')
        # self.tabs.addTab(self.parent.htmlview, 'HTML View')
        if VTK_installed:
            self.tabs.addTab(self.parent.postview, 'Post Processing')

        # connect tab changed signal to slot
        self.tabs.currentChanged.connect(self.parent.slots.onTabChanged)

        # add Tabs to the right pane of the splitter
        self.splitter.addWidget(self.tabs)

        self.splitter.setSizes([100, 400])  # initial hint for splitter spacing

        # put splitter in a layout box
        hbox = QtWidgets.QHBoxLayout(self)
        hbox.addWidget(self.splitter)
        self.setLayout(hbox)


def main():

    # main application (contains the main event loop)
    app = QtWidgets.QApplication(sys.argv)

    # set icon for the application ( upper left window icon and taskbar icon)
    # and add specialization icons per size
    # (needed depending on the operating system)
    app_icon = QtGui.QIcon(ICONS+'app_image.png')
    app_icon.addFile(ICONS+'app_image_16x16.png', QtCore.QSize(16, 16))
    app_icon.addFile(ICONS+'app_image_24x24.png', QtCore.QSize(24, 24))
    app_icon.addFile(ICONS+'app_image_32x32.png', QtCore.QSize(32, 32))
    app_icon.addFile(ICONS+'app_image_48x48.png', QtCore.QSize(48, 48))
    app_icon.addFile(ICONS+'app_image_256x256.png', QtCore.QSize(256, 256))
    app.setWindowIcon(app_icon)

    if LOCALE == 'C':
        # set default locale to C, so that decimal separator is a
        # dot in spin boxes, etc.
        QtCore.QLocale.setDefault(QtCore.QLocale.c())

    # window style set in Settings.py
    window = MainWindow(app, STYLE)
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

