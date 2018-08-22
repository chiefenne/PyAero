"""
The PIconProvider class overwrites QFileIconProvider.

This allows to use custom icons in different
places of the application (e.g. file dialogs)
"""
from PySide2 import QtGui, QtCore, QtWidgets

from Settings import *


class IconProvider(QtWidgets.QFileIconProvider):
    # call constructor of IconProvider
    def __init__(self):
        # call constructor of QFileIconProvider
        super(IconProvider, self).__init__()

    # overwrite icon method of QFileIconProvider
    def icon(self, icontype):

        if isinstance(icontype, QtCore.QFileInfo):
            if icontype.isDir():
                return QtGui.QIcon(ICONS_L + 'Folder.png')
            if icontype.isFile():
                return QtGui.QIcon(ICONS_L + 'Fast delivery.png')
        if icontype == QtGui.QFileIconProvider.Folder:
            return QtGui.QIcon(ICONS_L + 'Folder.png')
        if icontype == QtGui.QFileIconProvider.File:
            return QtGui.QIcon(ICONS_L + 'Fast delivery.png')

        return super(IconProvider, self).icon(icontype)
