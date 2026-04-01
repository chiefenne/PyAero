import platform

from PySide6 import QtCore, QtWidgets

from ActionRegistry import SEPARATOR_TOKEN
from Utils import get_main_window


class MenusTools:
    def __init__(self, mainwindow=None):
        self.mw = mainwindow or get_main_window()

    def createMenus(self):
        self.menubar = self.mw.menuBar()

        if platform.system() == 'Darwin':
            self.menubar.setNativeMenuBar(False)

        self.mw.menudata = self.mw.action_registry.menu_layout()
        for menu_definition in self.mw.menudata:
            menu = self.menubar.addMenu(menu_definition['name'])
            self._populate_action_container(menu, menu_definition['items'])

    def createTools(self):
        self.mw.tooldata = self.mw.action_registry.toolbar_layout()
        self.toolbars = []
        for toolbar_definition in self.mw.tooldata:
            toolbar = QtWidgets.QToolBar(toolbar_definition.get('name', 'Toolbar'))
            toolbar.setIconSize(QtCore.QSize(20, 20))
            self.mw.addToolBar(toolbar)
            self._populate_action_container(toolbar, toolbar_definition['items'])
            self.toolbars.append(toolbar)

        self.toolbar = self.toolbars[0] if self.toolbars else None

    def _populate_action_container(self, container, items):
        for item in items:
            if item == SEPARATOR_TOKEN:
                container.addSeparator()
                continue

            action = self.mw.action_registry.action(item)
            if action is not None:
                container.addAction(action)

    def createDocks(self):
        if hasattr(self.mw, 'messagedock') and hasattr(self.mw, 'messages'):
            return

        messagedock = QtWidgets.QDockWidget(self.mw)
        messagedock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                                QtWidgets.QDockWidget.DockWidgetFloatable)
        messagedock.setWindowTitle('Messages')
        messagedock.setMinimumSize(100, 50)
        messagedock.topLevelChanged.connect(self.mw.slots.onLevelChanged)

        self.mw.messages = QtWidgets.QTextEdit(self.mw)
        self.mw.messages.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
        )
        self.mw.messages.setAcceptRichText(True)
        self.mw.messages.textChanged.connect(self.mw.slots.onTextChanged)

        messagedock.setWidget(self.mw.messages)
        self.mw.addDockWidget(QtCore.Qt.BottomDockWidgetArea, messagedock)

        self.mw.messagedock = messagedock
