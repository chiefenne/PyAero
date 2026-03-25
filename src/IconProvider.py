"""
The PIconProvider class overwrites QFileIconProvider.

This allows to use custom icons in different
places of the application (e.g. file dialogs)
"""
from PySide6 import QtCore, QtWidgets

import Icons


class IconProvider(QtWidgets.QFileIconProvider):
    def __init__(self):
        # constructor of QFileIconProvider
        super().__init__()

    # overwrite icon method of QFileIconProvider
    def icon(self, icontype):

        if isinstance(icontype, QtCore.QFileInfo):
            if icontype.isDir():
                return Icons.icon('folder')
            if icontype.isFile():
                return Icons.icon('airfoil')
        if icontype == QtWidgets.QFileIconProvider.Folder:
            return Icons.icon('folder')
        if icontype == QtWidgets.QFileIconProvider.File:
            return Icons.icon('airfoil')

        return super().icon(icontype)
