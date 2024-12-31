"""
The PIconProvider class overwrites QFileIconProvider.

This allows to use custom icons in different
places of the application (e.g. file dialogs)
"""
from PySide6 import QtGui, QtCore, QtWidgets

from Settings import *


class IconProvider(QtWidgets.QFileIconProvider):
    def __init__(self):
        # constructor of QFileIconProvider
        super().__init__()

    # overwrite icon method of QFileIconProvider
    def icon(self, icontype):

        if isinstance(icontype, QtCore.QFileInfo):
            if icontype.isDir():
                return QtGui.QIcon('resources/Icons/24x24/airfoil.png/Folder.png')
            if icontype.isFile():
                return QtGui.QIcon('resources/Icons/24x24/airfoil.png/Fast delivery.png')
        if icontype == QtGui.QFileIconProvider.Folder:
            return QtGui.QIcon('resources/Icons/24x24/airfoil.png/Folder.png')
        if icontype == QtGui.QFileIconProvider.File:
            return QtGui.QIcon('resources/Icons/24x24/airfoil.png/Fast delivery.png')

        return super().icon(icontype)
