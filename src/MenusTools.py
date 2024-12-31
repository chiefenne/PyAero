


import os
import platform
import xml.etree.ElementTree as etree

from PySide6 import QtGui, QtCore, QtWidgets

from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


class MenusTools:
    # call constructor of MenusTools

    def __init__(self):

        # MainWindow instance
        self.mw = get_main_window()

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

            icon = QtGui.QIcon(os.path.join('resources/Icons/16x16', icon))

            logger.debug('HANDLER: {}'.format(handler))

            handler = 'self.mw.slots.' + handler

            action = QtGui.QAction(icon, name, self.mw,
                                       shortcut=short, statusTip=tip,
                                       triggered=eval(handler))

            action.setStatusTip(tip)
            action.setShortcut(short)
            # action.triggered.connect(eval(handler))
            menu.addAction(action)

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
        self.mw.addToolBar(self.toolbar)

        for tip, icon, handler in self.getToolbarData():
            if len(tip) == 0:
                self.toolbar.addSeparator()
                continue
            icon = QtGui.QIcon(os.path.join('resources/Icons/24x24', icon))

            # guislot converts to:
            # self.mw.slots.slotMethod()
            guislot = getattr(self.mw.slots, handler)

            action = QtGui.QAction(icon, tip, parent=self.mw)
            # action.setIcon(icon)
            # action.setToolTip(tip)
            action.triggered.connect(guislot)

            self.toolbar.addAction(action)

    def createDocks(self):
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
