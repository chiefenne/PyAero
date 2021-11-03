
import os

from Settings import DIALOGFILTER, OUTPUTDATA, AIRFOILDATA

from PySide6 import QtWidgets


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
        path = os.path.join(OUTPUTDATA, filename)
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            None,
            'Save File As',
            path,
            self.filter,
            selectedFilter='*')

        return filename, selected_filter

    def openFilename(self, directory=AIRFOILDATA):
        """Summary


        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            None,
            'Open File',
            directory,
            self.filter,
            '')

        return filename, selected_filter

    def setFilter(self, filter):
        self.filter = filter
