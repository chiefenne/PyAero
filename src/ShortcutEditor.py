from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class ShortcutEditorDialog(QtWidgets.QDialog):
    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self.mw = mainwindow
        self.registry = mainwindow.action_registry
        self.platform_overrides = dict(self.registry.platform_override_specs())
        self._entry_map = {}
        self._action_items = {}
        self._syncing_details = False

        self._build_ui()
        self._populate_tree()
        self._refresh()

    def _build_ui(self):
        self.setWindowTitle('Keyboard Shortcuts')
        self.setModal(True)
        self.resize(980, 700)
        self.setMinimumSize(860, 620)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel('Keyboard Shortcuts')
        heading.setStyleSheet('font-size: 20px; font-weight: 700; color: #1d3148;')
        layout.addWidget(heading)

        note = QtWidgets.QLabel(
            'Built-in defaults come from resources/Shortcuts/shortcuts.json. '
            f'Saving writes {self.registry.platform_label()} overrides to '
            'config/shortcuts_user.json.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #506274;')
        layout.addWidget(note)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Command', 'Current', 'Default'])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        splitter.addWidget(self.tree)

        details = QtWidgets.QFrame()
        details.setStyleSheet(
            'QFrame { background: #f6f9fc; border: 1px solid #d7e3ef; border-radius: 12px; }'
        )
        details_layout = QtWidgets.QVBoxLayout(details)
        details_layout.setContentsMargins(14, 14, 14, 14)
        details_layout.setSpacing(10)

        self.title_label = QtWidgets.QLabel('Select a command')
        self.title_label.setStyleSheet('font-size: 18px; font-weight: 700; color: #1d3148;')
        details_layout.addWidget(self.title_label)

        self.description_label = QtWidgets.QLabel('')
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet('color: #516274;')
        details_layout.addWidget(self.description_label)

        meta_grid = QtWidgets.QGridLayout()
        meta_grid.setHorizontalSpacing(12)
        meta_grid.setVerticalSpacing(6)
        self.scope_value = QtWidgets.QLabel('')
        self.default_value = QtWidgets.QLabel('')
        self.current_value = QtWidgets.QLabel('')
        for label in (self.scope_value, self.default_value, self.current_value):
            label.setWordWrap(True)
            label.setStyleSheet('color: #21374f; font-weight: 600;')
        meta_grid.addWidget(QtWidgets.QLabel('Scope'), 0, 0)
        meta_grid.addWidget(self.scope_value, 0, 1)
        meta_grid.addWidget(QtWidgets.QLabel('Built-in default'), 1, 0)
        meta_grid.addWidget(self.default_value, 1, 1)
        meta_grid.addWidget(QtWidgets.QLabel('Current shortcut'), 2, 0)
        meta_grid.addWidget(self.current_value, 2, 1)
        meta_grid.setColumnStretch(1, 1)
        details_layout.addLayout(meta_grid)

        self.use_default_radio = QtWidgets.QRadioButton('Use built-in shortcut(s)')
        self.use_custom_radio = QtWidgets.QRadioButton(
            f'Use one custom shortcut for {self.registry.platform_label()}'
        )
        self.use_default_radio.toggled.connect(self._on_mode_changed)
        self.use_custom_radio.toggled.connect(self._on_mode_changed)
        details_layout.addWidget(self.use_default_radio)
        details_layout.addWidget(self.use_custom_radio)

        self.record_edit = QtWidgets.QKeySequenceEdit()
        self.record_edit.keySequenceChanged.connect(self._on_recording_changed)
        details_layout.addWidget(self.record_edit)

        helper = QtWidgets.QLabel(
            'Selecting a custom shortcut replaces the current platform override for this command. '
            'Switch back to built-in to remove the override.'
        )
        helper.setWordWrap(True)
        helper.setStyleSheet('color: #66788c;')
        details_layout.addWidget(helper)
        details_layout.addStretch(1)

        self.message_label = QtWidgets.QLabel('')
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet('color: #506274;')
        details_layout.addWidget(self.message_label)

        splitter.addWidget(details)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._save_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_tree(self):
        category_items = {}
        for entry in self.registry.shortcut_editor_entries():
            category_item = category_items.get(entry.category)
            if category_item is None:
                category_item = QtWidgets.QTreeWidgetItem([entry.category])
                category_item.setFirstColumnSpanned(True)
                category_item.setFlags(category_item.flags() & ~QtCore.Qt.ItemIsSelectable)
                category_item.setExpanded(True)
                self.tree.addTopLevelItem(category_item)
                category_items[entry.category] = category_item

            item = QtWidgets.QTreeWidgetItem(category_item)
            item.setData(0, QtCore.Qt.UserRole, entry.action_id)
            self._action_items[entry.action_id] = item

        self.tree.expandAll()

    def _refresh(self):
        self._entry_map = {
            entry.action_id: entry
            for entry in self.registry.shortcut_editor_entries(self.platform_overrides)
        }
        current_action_id = self.current_action_id()

        for action_id, item in self._action_items.items():
            entry = self._entry_map[action_id]
            item.setText(0, entry.text)
            item.setText(1, ' / '.join(entry.current_shortcuts) or 'None')
            item.setText(2, ' / '.join(entry.default_shortcuts) or 'None')

            if entry.editable:
                brush = QtGui.QBrush()
            else:
                brush = QtGui.QBrush(QtGui.QColor('#8998a8'))
            for column in range(3):
                item.setForeground(column, brush)

        self._restore_selection(current_action_id)
        self._refresh_details()

    def _refresh_entry_preview(self, action_id):
        self._entry_map = {
            entry.action_id: entry
            for entry in self.registry.shortcut_editor_entries(self.platform_overrides)
        }

        entry = self._entry_map[action_id]
        item = self._action_items[action_id]
        item.setText(0, entry.text)
        item.setText(1, ' / '.join(entry.current_shortcuts) or 'None')
        item.setText(2, ' / '.join(entry.default_shortcuts) or 'None')
        self.current_value.setText(' / '.join(entry.current_shortcuts) or 'None')
        self.default_value.setText(' / '.join(entry.default_shortcuts) or 'None')

    def _restore_selection(self, action_id):
        if action_id and action_id in self._action_items:
            self.tree.setCurrentItem(self._action_items[action_id])
            return

        for item in self._action_items.values():
            self.tree.setCurrentItem(item)
            return

        self.tree.setCurrentItem(None)

    def _on_current_item_changed(self, _current, _previous):
        self._refresh_details()

    def _refresh_details(self):
        action_id = self.current_action_id()
        self._syncing_details = True
        try:
            if action_id is None:
                self.title_label.setText('Select a command')
                self.description_label.setText('')
                self.scope_value.setText('')
                self.default_value.setText('')
                self.current_value.setText('')
                self.use_default_radio.setChecked(False)
                self.use_custom_radio.setChecked(False)
                self.use_default_radio.setEnabled(False)
                self.use_custom_radio.setEnabled(False)
                self.record_edit.setEnabled(False)
                self.record_edit.setKeySequence(QtGui.QKeySequence())
                self.message_label.setText('')
                return

            entry = self._entry_map[action_id]
            self.title_label.setText(entry.text)
            self.description_label.setText(entry.description)
            self.scope_value.setText(entry.scope)
            self.default_value.setText(' / '.join(entry.default_shortcuts) or 'None')
            self.current_value.setText(' / '.join(entry.current_shortcuts) or 'None')

            editable = entry.editable
            self.use_default_radio.setEnabled(editable)
            self.use_custom_radio.setEnabled(editable)

            override_specs = self.platform_overrides.get(action_id)
            if editable and override_specs:
                self.use_custom_radio.setChecked(True)
                self.record_edit.setEnabled(True)
                self.record_edit.setKeySequence(
                    self._sequence_from_override_specs(override_specs)
                )
                self.message_label.setText(
                    f'This command has a {self.registry.platform_label()} override.'
                )
            elif editable:
                self.use_default_radio.setChecked(True)
                self.record_edit.setEnabled(False)
                self.record_edit.setKeySequence(QtGui.QKeySequence())
                self.message_label.setText(
                    f'This command currently uses the built-in shortcut for {self.registry.platform_label()}.'
                )
            else:
                self.use_default_radio.setChecked(False)
                self.use_custom_radio.setChecked(False)
                self.record_edit.setEnabled(False)
                self.record_edit.setKeySequence(QtGui.QKeySequence())
                self.message_label.setText(
                    'This shortcut is managed by the application and cannot be edited here.'
                )
        finally:
            self._syncing_details = False

    def current_action_id(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, QtCore.Qt.UserRole)

    def _on_mode_changed(self):
        if self._syncing_details:
            return

        action_id = self.current_action_id()
        if action_id is None:
            return

        entry = self._entry_map.get(action_id)
        if entry is None or not entry.editable:
            return

        if self.use_default_radio.isChecked():
            self.platform_overrides.pop(action_id, None)
            self.record_edit.setEnabled(False)
            self.record_edit.setKeySequence(QtGui.QKeySequence())
            self._refresh_entry_preview(action_id)
            self.message_label.setText(
                f'This command currently uses the built-in shortcut for {self.registry.platform_label()}.'
            )
            return

        if self.use_custom_radio.isChecked():
            override_specs = self.platform_overrides.get(action_id)
            self.record_edit.setEnabled(True)
            self.record_edit.setKeySequence(
                self._sequence_from_override_specs(override_specs)
            )
            self.record_edit.setFocus(QtCore.Qt.TabFocusReason)
            self.message_label.setText('Press the new shortcut now.')

    def _on_recording_changed(self, _sequence):
        if self._syncing_details:
            return

        action_id = self.current_action_id()
        if action_id is None or not self.use_custom_radio.isChecked():
            return

        self._store_recorded_shortcut(action_id)
        self._refresh_entry_preview(action_id)
        self.message_label.setText(
            f'Pending shortcut: {self.current_value.text()}'
        )

    def _store_recorded_shortcut(self, action_id):
        sequence = self.record_edit.keySequence()
        if sequence.isEmpty():
            self.platform_overrides.pop(action_id, None)
            return

        portable_text = sequence.toString(QtGui.QKeySequence.PortableText)
        if not portable_text:
            self.platform_overrides.pop(action_id, None)
            return

        self.platform_overrides[action_id] = (portable_text,)

    def _save_and_accept(self):
        conflicts = self.registry.detect_shortcut_conflicts(self.platform_overrides)
        if conflicts:
            lines = []
            for portable_text, action_ids in sorted(conflicts.items()):
                sequence = QtGui.QKeySequence.fromString(
                    portable_text,
                    QtGui.QKeySequence.PortableText,
                )
                label = sequence.toString(QtGui.QKeySequence.NativeText) or portable_text
                commands = ', '.join(
                    self.registry.definition(action_id).text
                    for action_id in action_ids
                )
                lines.append(f'{label}: {commands}')

            QtWidgets.QMessageBox.warning(
                self,
                'Shortcut conflict',
                'Please resolve conflicting shortcuts before saving.\n\n'
                + '\n'.join(lines),
            )
            return

        try:
            self.registry.save_platform_overrides(self.platform_overrides)
        except OSError as error:
            QtWidgets.QMessageBox.critical(
                self,
                'Failed to save shortcuts',
                str(error),
            )
            return

        self.accept()

    @staticmethod
    def _sequence_from_override_specs(specs):
        if not specs:
            return QtGui.QKeySequence()

        first = specs[0]
        if isinstance(first, dict):
            return QtGui.QKeySequence()

        return QtGui.QKeySequence.fromString(
            str(first),
            QtGui.QKeySequence.PortableText,
        )
