
import IconProvider
from Settings import DIALOGFILTER, OUTPUTDATA

from PySide2 import QtWidgets, QtGui


class FileDialog:

    def __init__(self, filter=None):

        self.names = []
        self.filter = filter

    def getFilename(self):
        '''
        getSaveFileName([parent=None[, caption=""[, dir=""[, filter=""[,
                    selectedFilter=""[, options=QFileDialog.Options()]]]]]])
        '''
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Save File As',
            '',
            "ReStructuredText Files (*.rst *.txt)"
        )
        if filename:
            text = self.editor.toPlainText()
            try:
                f = open(filename, "wb")
                f.write(text)
                f.close()
                # self.rebuildHTML()
            except IOError:
                QtGui.QMessageBox.information(
                    self,
                    "Unable to open file: %s" % filename
                )

        return filename

    def dialog(self):

        dialog = QtWidgets.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        dialog.setNameFilter(DIALOGFILTER)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(OUTPUTDATA)
        # allow only to select one file
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        # display also size and date
        dialog.setViewMode(QtWidgets.QFileDialog.Detail)
        # make it a save dialog
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        # put default name in the save dialog
        dialog.selectFile(self.lineedit.text())

        # open custom file dialog using custom icons
        if dialog.exec_():
            self.names = dialog.selectedFiles()
            # filter = dialog.selectedFilter()

        if not self.names:
            return
