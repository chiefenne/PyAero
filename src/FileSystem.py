import os

from PySide6 import QtGui, QtCore, QtWidgets


from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


class FileSystemModel(QtWidgets.QFileSystemModel):

    def __init__(self):
        super().__init__()

        self.mw = get_main_window()

        self.setFilter(QtCore.QDir.AllDirs |
                       QtCore.QDir.Files |
                       QtCore.QDir.NoDotAndDotDot)
        self.setNameFilters(self.mw.FILE_FILTER)
        # if true, filtered files are shown, but grey
        # if false they are not shown
        self.setNameFilterDisables(False)

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

        # set path for FileSytemModel to location of airfoil data
        path = os.path.abspath(self.mw.AIRFOILS)
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
                return QtGui.QPixmap('resources/Icons/24x24/Folder.png')
            elif fileInfo.isFile():
                return QtGui.QPixmap('resources/Icons/24x24/airfoil.png/airfoil.png')

        # return QtWidgets.QFileSystemModel.data(self, index, role)
        return super().data(index, role)

    # @QtCore.Slot(QtCore.QModelIndex)
    def onFileSelected(self, index):

        fileInfo = self.getFileInfo(index)[4]
        if fileInfo.isDir():
            return
        name = self.getFileInfo(index)[0]
        logger.info('Airfoil {} selected'.format(name))

    # @QtCore.Slot(QtCore.QModelIndex)
    def onFileLoad(self, index):
        fileInfo = self.getFileInfo(index)[4]
        if fileInfo.isDir():
            return

        fullname = self.getFileInfo(index)[2]
        self.mw.slots.loadAirfoil(fullname, comment='#')

    def getFileInfo(self, index):
        fileInfo = self.fileInfo(index)
        path = fileInfo.absolutePath()
        name = fileInfo.fileName()
        ext = fileInfo.suffix()
        fullname = fileInfo.absoluteFilePath()

        logger.debug('FileInfo', [name, path, fullname, ext, fileInfo])

        return [name, path, fullname, ext, fileInfo]
