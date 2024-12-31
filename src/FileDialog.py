
import os

from PySide6 import QtWidgets

from Utils import get_main_window

class Dialog:

    def __init__(self):

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

        self.names = []

        # DIALOG_FILTER = 'Airfoil contour files (*.dat *.txt)'
        self.filter = self.mw.DIALOG_FILTER

    def save_filename(self, filename=None):
        """Summary

        Args:
            filename (None, optional): If given, then it is displayed as
            default value in the dialog

        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        path = os.path.join(self.mw.OUTPUT, filename)
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            None,
            'Save File As',
            path,
            self.filter,
            selectedFilter='*')

        return filename, selected_filter

    def open_filename(self):
        """Summary


        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            None,
            'Open File',
            self.mw.AIRFOILS,
            self.filter,
            '')

        return filename, selected_filter

    def setFilter(self, filter):
        self.filter = filter
