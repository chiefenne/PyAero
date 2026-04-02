import os

from PySide6 import QtWidgets

from Utils import get_main_window

class Dialog:

    def __init__(self, mainwindow=None, parent_widget=None):

        # get MainWindow instance (overcomes handling parents)
        self.mw = mainwindow or get_main_window()
        self.parent_widget = parent_widget or self.mw

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

    def _directory_for(self, role, directory, fallback):
        if directory:
            if os.path.isdir(directory):
                return directory
            parent = os.path.dirname(directory)
            if parent:
                return parent

        last_directory = getattr(self.mw, f'_last_{role}_directory', '')
        if last_directory and os.path.isdir(last_directory):
            return last_directory
        return fallback

    def _update_last_directory(self, role, path):
        if not path:
            return
        if os.path.isdir(path):
            directory = path
        else:
            directory = os.path.dirname(path)
        if directory:
            setattr(self.mw, f'_last_{role}_directory', directory)

    def save_filename(self, filename=None, directory=None, title='Save File As',
                      filter=None):
        """Summary

        Args:
            filename (None, optional): If given, then it is displayed as
            default value in the dialog

        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        dialog_filter = filter or self.filter
        base_directory = self._directory_for(
            'save',
            directory,
            self.mw.OUTPUT,
        )
        path = base_directory
        if filename:
            path = os.path.join(base_directory, filename)
        filename, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self.parent_widget,
            title,
            path,
            dialog_filter,
            options=self._dialog_options(),
        )
        self._update_last_directory('save', filename)

        return filename, selected_filter

    def open_filename(self, directory=None, title='Open File', filter=None):
        """Summary


        Returns:
            string: filename inlcuding path to filename
            string: filter which was selected
        """
        dialog_filter = filter or self.filter
        base_directory = self._directory_for(
            'open',
            directory,
            self.mw.AIRFOILS,
        )
        filename, selected_filter = QtWidgets.QFileDialog.getOpenFileName(
            self.parent_widget,
            title,
            base_directory,
            dialog_filter,
            options=self._dialog_options(),
        )
        self._update_last_directory('open', filename)

        return filename, selected_filter

    def choose_directory(self, directory=None, title='Select Folder'):
        base_directory = self._directory_for(
            'save',
            directory,
            self.mw.OUTPUT,
        )
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self.parent_widget,
            title,
            base_directory,
            options=self._dialog_options(),
        )
        self._update_last_directory('save', folder)
        return folder

    def setFilter(self, filter):
        self.filter = filter
