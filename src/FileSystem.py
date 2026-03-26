import os
from dataclasses import dataclass

from PySide6 import QtGui, QtCore, QtWidgets

import Icons

from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


AIRFOIL_LIBRARY_EXTENSIONS = ('.dat', '.txt')


@dataclass(frozen=True)
class AirfoilLibraryEntry:
    name: str
    path: str
    relative_path: str
    collection: str
    source: str
    source_label: str


def library_root(mainwindow=None):
    mw = mainwindow or get_main_window()
    return os.path.abspath(mw.AIRFOILS)


def local_library_root(mainwindow=None):
    root = os.path.join(library_root(mainwindow), 'Local')
    os.makedirs(root, exist_ok=True)
    return root


def _iter_library_files(root_path):
    for current_root, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(dirnames, key=str.lower)
        for filename in sorted(filenames, key=str.lower):
            _, extension = os.path.splitext(filename)
            if extension.lower() not in AIRFOIL_LIBRARY_EXTENSIONS:
                continue
            yield current_root, filename


def list_airfoil_library_entries(source='bundled', mainwindow=None):
    bundled_root = library_root(mainwindow)
    local_root = local_library_root(mainwindow)
    entries = []

    if source in ('bundled', 'all'):
        for current_root, filename in _iter_library_files(bundled_root):
            current_root_abs = os.path.abspath(current_root)
            if (
                current_root_abs == local_root or
                current_root_abs.startswith(local_root + os.sep)
            ):
                continue
            path = os.path.join(current_root, filename)
            relative_path = os.path.relpath(path, bundled_root)
            collection = os.path.dirname(relative_path) or 'Bundled'
            entries.append(
                AirfoilLibraryEntry(
                    name=filename,
                    path=path,
                    relative_path=relative_path,
                    collection=collection,
                    source='bundled',
                    source_label='Bundled',
                )
            )

    if source in ('local', 'all'):
        for current_root, filename in _iter_library_files(local_root):
            path = os.path.join(current_root, filename)
            relative_path = os.path.relpath(path, local_root)
            collection = os.path.dirname(relative_path) or 'Local'
            entries.append(
                AirfoilLibraryEntry(
                    name=filename,
                    path=path,
                    relative_path=relative_path,
                    collection=collection,
                    source='local',
                    source_label='Local',
                )
            )

    return sorted(
        entries,
        key=lambda entry: (
            entry.source_label.lower(),
            entry.name.lower(),
            entry.relative_path.lower(),
        ),
    )


def describe_airfoil_source(path, mainwindow=None):
    if not path:
        return ''

    airfoil_path = os.path.abspath(path)
    bundled_root = library_root(mainwindow)
    local_root = local_library_root(mainwindow)

    if airfoil_path.startswith(local_root + os.sep) or airfoil_path == local_root:
        relative_path = os.path.relpath(airfoil_path, local_root)
        return f'Local library: {relative_path}'

    if airfoil_path.startswith(bundled_root + os.sep) or airfoil_path == bundled_root:
        relative_path = os.path.relpath(airfoil_path, bundled_root)
        return f'Bundled library: {relative_path}'

    return f'External file: {os.path.basename(airfoil_path)}'


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
                return Icons.pixmap('folder', 20)
            elif fileInfo.isFile():
                return Icons.pixmap('airfoil', 20)

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
        self.mw.slots.openFile(fullname)

    def getFileInfo(self, index):
        fileInfo = self.fileInfo(index)
        path = fileInfo.absolutePath()
        name = fileInfo.fileName()
        ext = fileInfo.suffix()
        fullname = fileInfo.absoluteFilePath()

        logger.debug('FileInfo', [name, path, fullname, ext, fileInfo])

        return [name, path, fullname, ext, fileInfo]
