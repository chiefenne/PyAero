
from Settings import DIALOGFILTER, OUTPUTDATA

from PySide2 import QtWidgets


class Dialog:

    def __init__(self, filter=DIALOGFILTER):

        self.names = []
        # DIALOGFILTER = 'Airfoil contour files (*.dat *.txt)'
        self.filter = filter

    def saveFilename(self, filename=None):
        """Summary

        Args:
            filename (None, optional): If given, then it is displayed as
            default value in the dialog

        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            None,
            'Save File As',
            OUTPUTDATA + filename,
            self.filter,
            '')

        return filename, selected_filter

    def openFilename(self):
        """Summary


        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            None,
            'Open File',
            OUTPUTDATA,
            self.filter,
            '')

        return filename, selected_filter

    def setFilter(self, filter):
        self.filter = filter
