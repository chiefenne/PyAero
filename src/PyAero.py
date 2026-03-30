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
import Icons


__appname__ = 'PyAero'
__author__ = 'Andreas Ennemoser'
year = str(datetime.date.today().strftime("%Y"))
__copyright__ = '2014-' + year + ' ' + __author__
__license__ = 'MIT'
__version__ = '3.0.0'
__email__ = 'andreas.ennemoser@aon.at'


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
        self.slots = GuiSlots.Slots(self)

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
        self.shortcut_message_dock = QtGui.QShortcut(
            QtGui.QKeySequence('ALT+m'), self
        )
        self.shortcut_message_dock.activated.connect(
            lambda: self.slots.toggleLogDock('shortcut')
        )
        self.shortcut_message_dock.setContext(QtCore.Qt.ApplicationShortcut)

    def init_GUI(self):

        # window size, position and title
        self.showMaximized()
        title = __appname__ + ' - Airfoil Contour Analysis and CFD Meshing'
        self.setWindowTitle(title)

        # decimal separator used in spin boxes, etc.
        if self.DECIMAL_SEPARATOR == '.':
            QtCore.QLocale.setDefault(QtCore.QLocale.c())
        elif self.DECIMAL_SEPARATOR == ',':
            QtCore.QLocale.setDefault(QtCore.QLocale.German, QtCore.QLocale.Germany)

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
    - a workflow sidebar on the left
    - a viewer workspace on the right.

    """

    WORKSPACE_VIEWER_INDEX = 0
    WORKSPACE_ANALYSIS_INDEX = 1

    def __init__(self, parent=None):
        # call constructor of QWidget
        super().__init__(parent)

        self.parent = parent
        self._applyWorkspaceStyles()

        # split main window horizontally into two panes
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # create workflow sidebar widget
        self.toolbox = ToolBox.Toolbox()

        self.left_pane = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.toolbox)
        self.left_pane.setLayout(vbox)
        self.left_pane.setMinimumWidth(420)

        self.createWorkspacePanel()
        self.createMessagePanel()
        self.createViewerControlsPanel()

        self.utility_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.utility_splitter.setChildrenCollapsible(False)
        self.utility_splitter.addWidget(self.message_panel)
        self.utility_splitter.addWidget(self.viewer_controls_panel)
        self.utility_splitter.setStretchFactor(0, 1)
        self.utility_splitter.setStretchFactor(1, 1)
        self.utility_splitter.setSizes([560, 560])

        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(True)
        self.right_splitter.addWidget(self.viewer_panel)
        self.right_splitter.addWidget(self.utility_splitter)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 0)
        self.right_splitter.setSizes([900, 170])

        self.right_pane = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.right_splitter)
        self.right_pane.setLayout(right_layout)

        # add splitter panes
        self.splitter.addWidget(self.left_pane)
        self.splitter.addWidget(self.right_pane)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([420, 1180])

        # put splitter in a layout box
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.splitter)
        self.setLayout(hbox)

        self.updateWorkspaceChrome(self.tabs.currentIndex())

    def _applyWorkspaceStyles(self):
        self.setStyleSheet(
            """
            QFrame[chromePanel="true"] {
                background: #f7f8fa;
                border: 1px solid #dbe3ee;
                border-radius: 8px;
            }
            QLabel[chromeLabel="true"] {
                color: #6b7788;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.08em;
            }
            QFrame[chromeInner="true"] {
                background: #ffffff;
                border: 1px solid #d6dfeb;
                border-radius: 6px;
            }
            QLabel[workspaceHint="true"] {
                color: #6b7788;
                font-size: 12px;
                line-height: 1.4em;
            }
            QTextEdit#messageTextEdit {
                background: transparent;
                border: none;
                font-family: "Menlo", "Monaco", "Courier New";
                font-size: 12px;
                padding: 0px;
            }
            QToolButton[workspaceMode="true"] {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: #425468;
                font-weight: 600;
                padding: 6px 10px;
            }
            QToolButton[workspaceMode="true"]:hover {
                background: #eef3f8;
                border-color: #d6dfeb;
            }
            QToolButton[workspaceMode="true"]:checked {
                background: #e8eef5;
                border-color: #b8c8db;
                color: #223041;
            }
            QToolButton[viewToggle="true"] {
                background: #ffffff;
                border: 1px solid #d6dfeb;
                border-radius: 4px;
                color: #223041;
                font-weight: 600;
                padding: 7px 10px;
            }
            QToolButton[viewToggle="true"]:hover {
                background: #f3f6fa;
                border-color: #9fb7d7;
            }
            QToolButton[viewToggle="true"]:checked {
                background: #e7edf4;
                border-color: #7e95b4;
                color: #1c2c40;
            }
            QToolButton[viewAction="true"] {
                background: #f8fafc;
                border: 1px solid #d6dfeb;
                border-radius: 4px;
                color: #425468;
                font-weight: 600;
                padding: 7px 10px;
            }
            QToolButton[viewAction="true"]:hover {
                background: #f3f6fa;
                border-color: #b8c8db;
            }
            """
        )

    def _createChromePanel(self, title, object_name):
        panel = QtWidgets.QFrame()
        panel.setObjectName(object_name)
        panel.setProperty('chromePanel', 'true')

        panel_layout = QtWidgets.QVBoxLayout()
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(8)
        panel.setLayout(panel_layout)

        header = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header.setLayout(header_layout)

        label = QtWidgets.QLabel(title)
        label.setProperty('chromeLabel', 'true')
        header_layout.addWidget(label)
        panel_layout.addWidget(header)

        inner = QtWidgets.QFrame()
        inner.setProperty('chromeInner', 'true')
        inner_layout = QtWidgets.QVBoxLayout()
        inner_layout.setContentsMargins(12, 12, 12, 12)
        inner_layout.setSpacing(10)
        inner.setLayout(inner_layout)
        panel_layout.addWidget(inner, stretch=1)

        return panel, header_layout, inner_layout

    def createWorkspacePanel(self):
        self.viewer_panel, header_layout, inner_layout = self._createChromePanel(
            'VIEWER',
            'viewerPanel',
        )

        self.viewer_workspace_button = self._makeWorkspaceModeButton('Viewer')
        self.analysis_workspace_button = self._makeWorkspaceModeButton(
            'Contour Analysis'
        )
        self.viewer_workspace_button.clicked.connect(
            lambda: self.tabs.setCurrentIndex(0)
        )
        self.analysis_workspace_button.clicked.connect(
            lambda: self.tabs.setCurrentIndex(1)
        )
        header_layout.addSpacing(10)
        header_layout.addWidget(self.viewer_workspace_button)
        header_layout.addWidget(self.analysis_workspace_button)
        header_layout.addStretch(1)

        self.tabs = QtWidgets.QStackedWidget()
        self.tabs.setObjectName('workspaceStack')
        self.tabs.addWidget(self.parent.view)
        self.tabs.addWidget(self.parent.contourview)
        self.tabs.currentChanged.connect(self.parent.slots.onTabChanged)
        inner_layout.addWidget(self.tabs, stretch=1)

    def createMessagePanel(self):
        self.message_panel, header_layout, inner_layout = self._createChromePanel(
            'MESSAGES',
            'messagePanel',
        )
        self.message_panel.setMinimumHeight(120)
        self.message_panel.setMinimumWidth(320)
        header_layout.addStretch(1)

        self.parent.messages = QtWidgets.QTextEdit(self.parent)
        self.parent.messages.setObjectName('messageTextEdit')
        self.parent.messages.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
        )
        self.parent.messages.setAcceptRichText(True)
        self.parent.messages.textChanged.connect(self.parent.slots.onTextChanged)
        inner_layout.addWidget(self.parent.messages, stretch=1)

        self.parent.messagedock = self.message_panel

    def createViewerControlsPanel(self):
        self.viewer_controls_panel, header_layout, inner_layout = self._createChromePanel(
            'VIEWER CONTROLS',
            'viewerControlsPanel',
        )
        self.viewer_controls_panel.setMinimumWidth(360)
        header_layout.addStretch(1)

        self.viewer_controls_stack = QtWidgets.QStackedWidget()
        inner_layout.addWidget(self.viewer_controls_stack, stretch=1)

        controls_page = QtWidgets.QWidget()
        controls_page_layout = QtWidgets.QVBoxLayout()
        controls_page_layout.setContentsMargins(0, 0, 0, 0)
        controls_page_layout.setSpacing(0)
        controls_grid = QtWidgets.QGridLayout()
        controls_grid.setContentsMargins(0, 0, 0, 0)
        controls_grid.setHorizontalSpacing(8)
        controls_grid.setVerticalSpacing(8)
        controls_page_layout.addLayout(controls_grid)
        controls_page_layout.addStretch(1)
        controls_page.setLayout(controls_page_layout)
        controls_columns = 4

        controls = [
            ('Messages', 'message_window_checkbox', True, True,
             self.parent.slots.toggleLogDock, 'Message Window', 'tick'),
            ('Raw Pts', 'airfoil_points_checkbox', False, False,
             self.toolbox.toggleRawPoints, 'Airfoil Points'),
            ('Raw', 'airfoil_raw_contour_checkbox', False, False,
             self.toolbox.toggleRawContour, 'Airfoil Raw Contour'),
            ('Spline Pts', 'airfoil_spline_points_checkbox', False, False,
             self.toolbox.toggleSplinePoints, 'Airfoil Spline Points'),
            ('Spline', 'airfoil_spline_contour_checkbox', False, False,
             self.toolbox.toggleSpline, 'Airfoil Spline Contour'),
            ('Fill', 'airfoil_spline_fill_checkbox', False, False,
             self.toolbox.toggleSplineFill, 'Spline Preview Fill'),
            ('Chord', 'airfoil_chord_checkbox', False, False,
             self.toolbox.toggleChord, 'Airfoil Chord'),
            ('Mesh', 'mesh_checkbox', False, False,
             self.toolbox.toggleMesh, 'Mesh'),
            ('LE Circle', 'leading_edge_circle_checkbox', False, False,
             self.toolbox.toggleLeCircle, 'Leading Edge Circle'),
            ('Blocks', 'mesh_blocks_checkbox', False, False,
             self.toolbox.toggleMeshBlocks, 'Mesh Blocks'),
            ('Camber', 'airfoil_camber_line_checkbox', False, False,
             self.toolbox.toggleCamberLine, 'Airfoil Camber Line'),
            ('C Circles', 'airfoil_camber_circles_checkbox', False, False,
             self.toolbox.toggleCamberCircles, 'Airfoil Camber Inscribed Circles'),
        ]

        for index, control in enumerate(controls):
            short_label, attribute_name, checked, enabled, slot, tooltip, *args = control
            button = self._makeViewerToggleButton(
                short_label,
                checked=checked,
                enabled=enabled,
                slot=slot,
                tooltip=tooltip,
                argument=args[0] if args else None,
            )
            setattr(self, attribute_name, button)
            controls_grid.addWidget(button, index // controls_columns, index % controls_columns)

        fit_airfoil_button = self._makeViewerActionButton(
            'Fit Airfoil',
            self.parent.slots.fitAirfoilInView,
        )
        fit_button = self._makeViewerActionButton(
            'Fit View',
            self.parent.slots.onViewAll,
        )
        background_button = self._makeViewerActionButton(
            'Background',
            self.parent.slots.onBackground,
        )
        action_index = len(controls)
        controls_grid.addWidget(
            fit_airfoil_button,
            action_index // controls_columns,
            action_index % controls_columns,
        )
        action_index += 1
        controls_grid.addWidget(
            fit_button,
            action_index // controls_columns,
            action_index % controls_columns,
        )
        action_index += 1
        controls_grid.addWidget(
            background_button,
            action_index // controls_columns,
            action_index % controls_columns,
        )

        placeholder_page = QtWidgets.QWidget()
        placeholder_layout = QtWidgets.QVBoxLayout()
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.setSpacing(8)
        placeholder_page.setLayout(placeholder_layout)

        placeholder_label = QtWidgets.QLabel(
            'Switch back to Airfoil Viewer to adjust contour, mesh, and view overlays.'
        )
        placeholder_label.setProperty('workspaceHint', 'true')
        placeholder_label.setWordWrap(True)
        placeholder_layout.addWidget(placeholder_label)
        placeholder_layout.addStretch(1)

        self.viewer_controls_stack.addWidget(controls_page)
        self.viewer_controls_stack.addWidget(placeholder_page)

    def _makeWorkspaceModeButton(self, text):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.setProperty('workspaceMode', 'true')
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _makeViewerToggleButton(self, text, checked, enabled, slot, tooltip, argument=None):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setEnabled(enabled)
        button.setProperty('viewToggle', 'true')
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        button.setMinimumWidth(94)
        button.setMaximumWidth(116)
        if argument is None:
            button.clicked.connect(slot)
        else:
            button.clicked.connect(lambda _, s=slot, a=argument: s(a))
        return button

    def _makeViewerActionButton(self, text, slot):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setProperty('viewAction', 'true')
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed,
            QtWidgets.QSizePolicy.Fixed,
        )
        button.setMinimumWidth(94)
        button.setMaximumWidth(116)
        button.clicked.connect(slot)
        return button

    def updateWorkspaceChrome(self, tab_index=None):
        if tab_index is None:
            tab_index = self.tabs.currentIndex()
        viewer_tab = tab_index == self.WORKSPACE_VIEWER_INDEX

        for index, button in enumerate(
            (self.viewer_workspace_button, self.analysis_workspace_button)
        ):
            blocker = QtCore.QSignalBlocker(button)
            button.setChecked(index == tab_index)
            del blocker

        self.viewer_controls_stack.setCurrentIndex(0 if viewer_tab else 1)

    def setMessagePanelVisible(self, visible):
        self.message_panel.setVisible(visible)
        utility_width = max(self.utility_splitter.width(), 1)
        if visible:
            self.utility_splitter.setSizes([utility_width // 2, utility_width // 2])
        else:
            self.utility_splitter.setSizes([0, utility_width])

        total_height = max(self.right_splitter.height(), 1)
        utility_height = min(170, max(128, total_height // 5))
        self.right_splitter.setSizes([total_height - utility_height, utility_height])


class MessagePanel(QtWidgets.QFrame):
    def isFloating(self):
        return False


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
    app_icon = Icons.app_icon()
    app.setWindowIcon(app_icon)

    # Window style set in Settings.py
    window = MainWindow(app)
    window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
