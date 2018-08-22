import os

from PySide2 import QtGui, QtCore, QtWidgets

from Settings import AIRFOILDATA, FILEFILTER, ICONS_L
import Logger as logger


class FileSystemModel(QtWidgets.QFileSystemModel):

    def __init__(self):
        super().__init__()

        self.setFilter(QtCore.QDir.AllDirs |
                       QtCore.QDir.Files |
                       QtCore.QDir.NoDotAndDotDot)
        self.setNameFilters(FILEFILTER)
        # if true, filtered files are shown, but grey
        # if false they are not shown
        self.setNameFilterDisables(False)

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

        path = os.path.abspath(AIRFOILDATA)
        self.setRootPath(path)

    # inherited from QAbstractItemModel
    def data(self, index, role):
        """
        This function partly overrides the standard QFileSystemModel data
        function to return custom file and folder icons
        """
        
        fileInfo = self.getFileInfo(index)[4]

        if role == QtCore.Qt.DecorationRole:
            if fileInfo.isDir():
                return QtGui.QPixmap(ICONS_L + 'Folder.png')
            elif fileInfo.isFile():
                return QtGui.QPixmap(ICONS_L + 'airfoil.png')

        # return QtWidgets.QFileSystemModel.data(self, index, role)
        # more pythonic ???
        return super().data(index, role)

    # @QtCore.Slot(QtCore.QModelIndex)
    def onFileSelected(self, index):

        return

        fileInfo = self.getFileInfo(index)[4]
        if fileInfo.isDir():
            return
        name = self.getFileInfo(index)[0]
        logger.info('<b><font color="#2784CB">%s</b> selected' % (name))

    # @QtCore.Slot(QtCore.QModelIndex)
    def onFileLoad(self, index):
        fullname = self.getFileInfo(index)[2]
        fileInfo = self.getFileInfo(index)[4]
        if fileInfo.isDir():
            return
        self.mainwindow.slots.loadAirfoil(fullname, '#')

    def getFileInfo(self, index):
        fileInfo = self.fileInfo(index)
        path = fileInfo.absolutePath()
        name = fileInfo.fileName()
        ext = fileInfo.suffix()
        fullname = fileInfo.absoluteFilePath()
        print('FileInfo', [name, path, fullname, ext, fileInfo])
        return [name, path, fullname, ext, fileInfo]
