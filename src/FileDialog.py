
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

    def _dialog_options(self):
        options = QtWidgets.QFileDialog.Options()
        if getattr(self.mw, 'platform', '') == 'Darwin':
            # Use the Qt dialog on macOS to avoid the recurring NSOpenPanel
            # warning path from the native file dialog wrapper.
            options |= QtWidgets.QFileDialog.DontUseNativeDialog
        return options

    def save_filename(self, filename=None):
        """Summary

        Args:
            filename (None, optional): If given, then it is displayed as
            default value in the dialog

        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        path = self.mw.OUTPUT if filename is None else os.path.join(self.mw.OUTPUT, filename)
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self.mw,
            'Save File As',
            path,
            self.filter,
            selectedFilter='*',
            options=self._dialog_options(),
        )

        return filename, selected_filter

    def open_filename(self):
        """Summary


        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self.mw,
            'Open File',
            self.mw.AIRFOILS,
            self.filter,
            '',
            options=self._dialog_options(),
        )

        return filename, selected_filter

    def setFilter(self, filter):
        self.filter = filter
