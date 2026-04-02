from __future__ import annotations

import configparser
from collections import OrderedDict

from PySide6 import QtCore, QtWidgets

import Settings
import UiExport


CHOICE_FIELDS = {
    ('Application', 'DECIMAL_SEPARATOR'): ('.', ','),
    ('Graphics', 'ZOOM_ANCHOR'): ('mouse', 'center'),
    ('Graphics', 'VIEW_STYLE'): ('solid', 'gradient'),
    ('Window', 'WINDOW_STARTUP_MODE'): Settings.WINDOW_STARTUP_MODES,
}

BOOLEAN_STRINGS = {'true', 'false', 'yes', 'no', 'on', 'off', '1', '0'}
CONFIG_HEADER = '; ****************\n; PyAero Settings\n; ****************\n\n'


class SettingsEditorDialog(QtWidgets.QDialog):
    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self.mw = mainwindow
        self._fields = OrderedDict()
        self._parser = self._load_parser()

        self._build_ui()
        self._populate_tabs()

    def _build_ui(self):
        self.setWindowTitle('Settings')
        self.setModal(True)
        self.resize(760, 620)
        self.setMinimumSize(700, 560)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel('Application Settings')
        heading.setStyleSheet('font-size: 20px; font-weight: 700; color: #1d3148;')
        layout.addWidget(heading)

        note = QtWidgets.QLabel(
            'These values are stored in config/config.ini. '
            'Visual and shortcut-related changes are applied immediately where possible. '
            'Some settings are still best treated as taking effect on the next app start.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #506274;')
        layout.addWidget(note)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        UiExport.install_dialog_export_button(
            self.button_box,
            mainwindow=self.mw,
            widget=self,
            default_name='settings_dialog.png',
            dialog_title='Export Settings Dialog As',
            success_label='Settings dialog',
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_tabs(self):
        for section in self._parser.sections():
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.setContentsMargins(14, 14, 14, 14)
            page_layout.setSpacing(10)

            form = QtWidgets.QFormLayout()
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
            form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(10)

            for key in self._parser.options(section):
                raw_value = self._parser.get(section, key, raw=True)
                widget = self._make_editor(section, key, raw_value)
                form.addRow(self._display_label(section, key), widget)
                self._fields[(section, key)] = widget

            page_layout.addLayout(form)
            page_layout.addStretch(1)
            self.tabs.addTab(page, section)

    def _make_editor(self, section, key, raw_value):
        field_key = (section, key)
        normalized = raw_value.strip()
        lower_value = normalized.lower()

        if field_key in CHOICE_FIELDS:
            combo = QtWidgets.QComboBox()
            combo.addItems(CHOICE_FIELDS[field_key])
            index = combo.findText(normalized)
            combo.setCurrentIndex(max(index, 0))
            return combo

        if lower_value in BOOLEAN_STRINGS:
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(lower_value in {'true', 'yes', 'on', '1'})
            return checkbox

        line_edit = QtWidgets.QLineEdit(normalized)
        line_edit.setClearButtonEnabled(True)
        return line_edit

    def _save_and_accept(self):
        updated_values = OrderedDict()

        for (section, key), widget in self._fields.items():
            try:
                updated_values[(section, key)] = self._read_widget_value(
                    section,
                    key,
                    widget,
                )
            except ValueError as error:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Invalid setting value',
                    str(error),
                )
                return

        for (section, key), value in updated_values.items():
            self._parser.set(section, key, value)

        try:
            self._write_parser()
        except OSError as error:
            QtWidgets.QMessageBox.critical(
                self,
                'Failed to save settings',
                str(error),
            )
            return

        self.mw.config.reload()
        self.mw.applyRuntimeSettings(apply_window_mode=True)
        self.accept()

    def _read_widget_value(self, section, key, widget):
        original_raw = self._parser.get(section, key, raw=True).strip()
        original_kind = self._infer_kind(original_raw)

        if isinstance(widget, QtWidgets.QComboBox):
            value = widget.currentText().strip()
            if not value:
                raise ValueError(f'{section}.{key} cannot be empty.')
            return value

        if isinstance(widget, QtWidgets.QCheckBox):
            return 'True' if widget.isChecked() else 'False'

        value = widget.text().strip()
        if not value:
            raise ValueError(f'{section}.{key} cannot be empty.')

        if section == 'Window' and key.startswith('WINDOW_PRESET_'):
            try:
                Settings.parse_window_geometry(value)
            except ValueError as error:
                raise ValueError(f'{section}.{key} {error}') from error
            return ', '.join(part.strip() for part in value.split(','))

        if original_kind == 'int':
            try:
                int(value)
            except ValueError as error:
                raise ValueError(f'{section}.{key} must be an integer.') from error
        elif original_kind == 'float':
            try:
                float(value)
            except ValueError as error:
                raise ValueError(f'{section}.{key} must be a number.') from error

        return value

    def _load_parser(self):
        parser = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        parser.optionxform = str
        parser.read(Settings.CONFIG_FILE, encoding='utf-8')
        return parser

    def _write_parser(self):
        with Settings.CONFIG_FILE.open('w', encoding='utf-8') as handle:
            handle.write(CONFIG_HEADER)
            self._parser.write(handle)

    @staticmethod
    def _display_label(section, key):
        section_prefix = f'{section.upper()}_'
        if key.startswith(section_prefix):
            key = key[len(section_prefix):]
        return key.replace('_', ' ').title()

    @staticmethod
    def _infer_kind(raw_value):
        value = raw_value.strip()
        lower_value = value.lower()

        if lower_value in BOOLEAN_STRINGS:
            return 'bool'

        try:
            int(value)
            return 'int'
        except ValueError:
            pass

        try:
            float(value)
            return 'float'
        except ValueError:
            return 'string'
