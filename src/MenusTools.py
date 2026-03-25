import platform
import xml.etree.ElementTree as etree

from PySide6 import QtGui, QtCore, QtWidgets

import Icons
from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


class MenusTools:
    # call constructor of MenusTools

    def __init__(self, mainwindow=None):

        # MainWindow instance
        self.mw = mainwindow or get_main_window()

    def getMenuData(self):
        """populate menus and pulldowns from the external XML file"""

        menudata = list()

        xml = etree.parse('resources/Menus/PMenu.xml')
        menu_structure = xml.getroot()

        for menu in menu_structure.findall('Menubar'):
            mname = menu.attrib['name']
            items = menu.findall('Submenu')
            pulldowns = self.getPullDownData(items)
            menudata.append((mname, [s for s in pulldowns]))

        # attach available pulldowns to the mainwindow
        # so it can be used elsewhere (e.g. Guislots)
        self.mw.menudata = menudata
        return tuple(menudata)

    def getPullDownData(self, items):

        pulldowns = list()
        for sub in items:
            sname = sub.attrib['name']
            if sname == 'Separator':
                pulldowns.append(('', '', '', '', self.onPass))
                continue
            tip = sub.attrib['tip']
            icon = sub.attrib['icon']
            shortcut = sub.attrib['short']
            handler = sub.attrib['handler']
            pulldowns.append((sname, tip, shortcut, icon, handler))

        return pulldowns

    def createMenus(self):
        """create the menubar and populate it automatically"""
        # create a menu bar
        # self.menubar = QtWidgets.QMenuBar()
        self.menubar = self.mw.menuBar()

        # for MacOS in order that the menu stays with the window
        pltf = platform.system()
        if 'Darwin' in pltf:
            self.menubar.setNativeMenuBar(False)

        for eachMenu in self.getMenuData():
            name = eachMenu[0]
            menu = self.menubar.addMenu(name)

            pulldown = eachMenu[1]
            self.createPullDown(menu, pulldown)
        return

    def createPullDown(self, menu, eachPullDown):
        """create the submenu structure to method createMenus"""
        for name, tip, short, icon, handler in eachPullDown:

            if len(name) == 0:
                menu.addSeparator()
                continue

            logger.debug('HANDLER: {}'.format(handler))
            action = self.createAction(
                text=name,
                tip=tip,
                shortcut=short,
                icon_name=icon,
                handler_name=handler,
            )
            if action is None:
                continue
            menu.addAction(action)

    def createAction(self, text, tip, shortcut, icon_name, handler_name):
        handler = getattr(self.mw.slots, handler_name, None)
        if handler is None:
            logger.error('No slot named %s found for action %s',
                         handler_name, text)
            return None

        if icon_name and icon_name.strip():
            icon = Icons.icon(icon_name)
            action = QtGui.QAction(icon, text, self.mw)
        else:
            action = QtGui.QAction(text, self.mw)

        action.setStatusTip(tip)
        if shortcut and shortcut.strip():
            action.setShortcut(shortcut)
        action.triggered.connect(handler)
        return action

    def getToolbarData(self):
        """get all menus and submenus from the external XML file"""

        xml = etree.parse('resources/Menus/PToolBar.xml')
        tool_structure = xml.getroot()

        tooldata = list()

        for toolbar in tool_structure.findall('Toolbar'):
            for tool in toolbar.findall('Tool'):
                if tool.attrib['handler'] == 'self.onPass':
                    tooldata.append(('', '', '', '', self.onPass))
                    continue
                tip = tool.attrib['tip']
                icon = tool.attrib['icon']
                handler = tool.attrib['handler']
                tooldata.append((tip, icon, handler))

        return tuple(tooldata)

    def createTools(self):
        """create the toolbar and populate it automatically
         from  method toolData
        """
        # create a toolbar
        self.toolbar = QtWidgets.QToolBar('Toolbar')
        self.toolbar.setIconSize(QtCore.QSize(20, 20))
        self.mw.addToolBar(self.toolbar)

        for tip, icon, handler in self.getToolbarData():
            if len(tip) == 0:
                self.toolbar.addSeparator()
                continue
            action = self.createAction(
                text=tip,
                tip=tip,
                shortcut='',
                icon_name=icon,
                handler_name=handler,
            )
            if action is None:
                continue
            self.toolbar.addAction(action)

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

    def onPass(self):
        pass
