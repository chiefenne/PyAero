


import os
import platform
import xml.etree.ElementTree as etree

from PySide6 import QtGui, QtCore, QtWidgets

from Settings import ICONS_S, ICONS_L, MENUDATA

import logging
logger = logging.getLogger(__name__)


class MenusTools:
    # call constructor of MenusTools

    def __init__(self, parent=None):

        self.parent = parent

    def getMenuData(self):
        """get all menus and pulldowns from the external XML file"""

        menudata = list()

        xml_file = os.path.join(MENUDATA, 'PMenu.xml')
        xml = etree.parse(xml_file)
        menu_structure = xml.getroot()

        for menu in menu_structure.findall('Menubar'):
            mname = menu.attrib['name']
            items = menu.findall('Submenu')
            pulldowns = self.getPullDownData(items)
            menudata.append((mname, [s for s in pulldowns]))

        # attach available pulldowns to the mainwindow
        # so it can be used elsewhere (e.g. Guislots)
        self.parent.menudata = menudata
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
        self.menubar = self.parent.menuBar()

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

            icon = QtGui.QIcon(os.path.join(ICONS_S, icon))

            logger.debug('HANDLER: {}'.format(handler))

            handler = 'self.parent.slots.' + handler

            action = QtGui.QAction(icon, name, self.parent,
                                       shortcut=short, statusTip=tip,
                                       triggered=eval(handler))

            action.setStatusTip(tip)
            action.setShortcut(short)
            # action.triggered.connect(eval(handler))
            menu.addAction(action)

    def getToolbarData(self):
        """get all menus and submenus from the external XML file"""

        xml_file = os.path.join(MENUDATA, 'PToolBar.xml')
        xml = etree.parse(xml_file)
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
        self.parent.addToolBar(self.toolbar)

        for tip, icon, handler in self.getToolbarData():
            if len(tip) == 0:
                self.toolbar.addSeparator()
                continue
            icon = QtGui.QIcon(os.path.join(ICONS_L, icon))

            # guislot converts to:
            # self.parent.slots.slotMethod()
            guislot = getattr(self.parent.slots, handler)

            action = QtGui.QAction(icon, tip, parent=self.parent)
            # action.setIcon(icon)
            # action.setToolTip(tip)
            action.triggered.connect(guislot)

            self.toolbar.addAction(action)

    def createDocks(self):
        self.parent.messagedock = QtWidgets.QDockWidget(self.parent)
        self.parent.messagedock. \
            setFeatures(QtWidgets.QDockWidget.DockWidgetMovable |
                        QtWidgets.QDockWidget.DockWidgetFloatable)
        self.parent.messagedock.setWindowTitle('Messages')
        self.parent.messagedock.setMinimumSize(100, 50)
        # connect messagedock to slot
        self.parent.messagedock.topLevelChanged.connect(
            self.parent.slots.onLevelChanged)

        self.parent.messages = QtWidgets.QTextEdit(self.parent)
        self.parent.messages. \
            setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse |
                                    QtCore.Qt.TextSelectableByKeyboard)
        # connect messages to scrollhandler
        self.parent.messages.textChanged.connect(
            self.parent.slots.onTextChanged)

        self.parent.messagedock.setWidget(self.parent.messages)

        place = QtCore.Qt.BottomDockWidgetArea
        self.parent.addDockWidget(
            QtCore.Qt.DockWidgetArea(place), self.parent.messagedock)

    def onPass(self):
        pass
