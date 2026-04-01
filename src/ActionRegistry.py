from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

import Icons

import logging
logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parent.parent
MENU_LAYOUT_FILE = ROOT / 'resources' / 'Menus' / 'menu_layout.json'
TOOLBAR_LAYOUT_FILE = ROOT / 'resources' / 'Menus' / 'toolbar_layout.json'
SHORTCUT_OVERRIDE_FILE = ROOT / 'config' / 'shortcuts.json'
SEPARATOR_TOKEN = 'separator'


ActionHandlerFactory = Callable[[object], Callable[[], None]]
ShortcutProvider = Callable[[object], Sequence[str]]


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    text: str
    tooltip: str
    handler_factory: ActionHandlerFactory
    icon_name: str = ''
    default_shortcuts: tuple[str, ...] = ()
    shortcut_context: QtCore.Qt.ShortcutContext = QtCore.Qt.WindowShortcut
    shortcut_targets: tuple[str, ...] = ('mainwindow',)
    help_category: str = 'General'
    shortcut_provider: ShortcutProvider | None = None


@dataclass(frozen=True)
class ShortcutHelpEntry:
    category: str
    text: str
    description: str
    shortcuts: tuple[str, ...]


def _slot(slot_name):
    return lambda mw: getattr(mw.slots, slot_name)


def _view_method(method_name):
    return lambda mw: getattr(mw.view, method_name)


def _quit_application(_mw):
    return lambda: QtCore.QCoreApplication.quit()


def _escape_shortcuts(mw):
    if getattr(mw, 'EXIT_ON_ESCAPE', False):
        return ('Esc',)
    return ()


ACTION_DEFINITIONS = (
    ActionDefinition(
        action_id='file.open',
        text='Open',
        tooltip='Open airfoil contour file',
        icon_name='open',
        default_shortcuts=('Ctrl+O',),
        help_category='File',
        handler_factory=_slot('onOpen'),
    ),
    ActionDefinition(
        action_id='file.save',
        text='Save',
        tooltip='Save airfoil contour file',
        icon_name='save',
        default_shortcuts=('Ctrl+S',),
        help_category='File',
        handler_factory=_slot('onSave'),
    ),
    ActionDefinition(
        action_id='file.save_as',
        text='Save as',
        tooltip='Save airfoil contour file with different name',
        icon_name='save-as',
        default_shortcuts=('Ctrl+Shift+S',),
        help_category='File',
        handler_factory=_slot('onSaveAs'),
    ),
    ActionDefinition(
        action_id='file.print',
        text='Print',
        tooltip='Print current view',
        icon_name='print',
        default_shortcuts=('Ctrl+P',),
        help_category='File',
        handler_factory=_slot('onPrint'),
    ),
    ActionDefinition(
        action_id='file.print_preview',
        text='Print preview',
        tooltip='Print preview',
        icon_name='print-preview',
        default_shortcuts=('Ctrl+Shift+P',),
        help_category='File',
        handler_factory=_slot('onPreview'),
    ),
    ActionDefinition(
        action_id='file.open_predefined',
        text='Open predefined airfoil contour',
        tooltip='Open predefined airfoil contour',
        icon_name='airfoil-library',
        help_category='File',
        handler_factory=_slot('onOpenPredefined'),
    ),
    ActionDefinition(
        action_id='app.exit',
        text='Exit',
        tooltip='Shut down PyAero',
        icon_name='exit',
        default_shortcuts=('Ctrl+X',),
        help_category='Application',
        handler_factory=_slot('onExit'),
    ),
    ActionDefinition(
        action_id='app.exit_on_escape',
        text='Exit',
        tooltip='Close PyAero',
        shortcut_context=QtCore.Qt.ApplicationShortcut,
        shortcut_targets=('mainwindow',),
        help_category='Application',
        shortcut_provider=_escape_shortcuts,
        handler_factory=_quit_application,
    ),
    ActionDefinition(
        action_id='view.fit_airfoil',
        text='Fit airfoil in view',
        tooltip='Set view to selected airfoil',
        icon_name='fit-airfoil',
        default_shortcuts=('Ctrl+F',),
        help_category='View',
        handler_factory=_slot('fitAirfoilInView'),
    ),
    ActionDefinition(
        action_id='view.fit_all',
        text='Fit all in view',
        tooltip='Set view to all items visible',
        icon_name='fit-all',
        default_shortcuts=('Ctrl+Shift+F', 'Home'),
        help_category='View',
        handler_factory=_slot('onViewAll'),
    ),
    ActionDefinition(
        action_id='view.toggle_background',
        text='Toggle background',
        tooltip='Toggle background color',
        default_shortcuts=('Ctrl+B',),
        help_category='View',
        handler_factory=_slot('onBackground'),
    ),
    ActionDefinition(
        action_id='view.toggle_messages',
        text='Toggle message window',
        tooltip='Toggle the message window to have more space for the viewer',
        default_shortcuts=('Ctrl+M',),
        help_category='View',
        handler_factory=_slot('toggleLogDock'),
    ),
    ActionDefinition(
        action_id='view.zoom_in',
        text='Zoom in',
        tooltip='Zoom in the current graphics view',
        default_shortcuts=('+', 'PageDown'),
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Viewer',
        handler_factory=_view_method('zoomIn'),
    ),
    ActionDefinition(
        action_id='view.zoom_out',
        text='Zoom out',
        tooltip='Zoom out the current graphics view',
        default_shortcuts=('-', 'PageUp'),
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Viewer',
        handler_factory=_view_method('zoomOut'),
    ),
    ActionDefinition(
        action_id='airfoil.delete_active',
        text='Delete airfoil',
        tooltip='Delete the active airfoil',
        icon_name='delete',
        default_shortcuts=('Del',),
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Viewer',
        handler_factory=_slot('removeAirfoil'),
    ),
    ActionDefinition(
        action_id='tools.calculator',
        text='Calculator',
        tooltip='Start the internal calculator',
        icon_name='calculator',
        default_shortcuts=('Ctrl+Shift+L',),
        help_category='Tools',
        handler_factory=_slot('onCalculator'),
    ),
    ActionDefinition(
        action_id='tools.settings',
        text='Settings',
        tooltip='Customize PyAero',
        icon_name='settings',
        default_shortcuts=('Ctrl+E',),
        help_category='Tools',
        handler_factory=_slot('onCalculator'),
    ),
    ActionDefinition(
        action_id='tools.icon_preview',
        text='Icon Preview',
        tooltip='Preview semantic icons and app assets',
        help_category='Tools',
        handler_factory=_slot('onIconPreview'),
    ),
    ActionDefinition(
        action_id='help.manual_online',
        text='Manual (online)',
        tooltip='Open PyAero online documentation',
        icon_name='manual',
        default_shortcuts=('Ctrl+Shift+H',),
        help_category='Help',
        handler_factory=_slot('onHelpOnline'),
    ),
    ActionDefinition(
        action_id='help.manual_pdf',
        text='Manual (PDF)',
        tooltip='Open PyAero manual',
        icon_name='manual',
        default_shortcuts=('Ctrl+H',),
        help_category='Help',
        handler_factory=_slot('onHelpPDF'),
    ),
    ActionDefinition(
        action_id='help.shortcuts',
        text='Keyboard shortcuts',
        tooltip='Show available keyboard shortcuts',
        icon_name='keyboard-shortcuts',
        default_shortcuts=('Ctrl+K',),
        help_category='Help',
        handler_factory=_slot('onKeyBd'),
    ),
    ActionDefinition(
        action_id='help.about_qt',
        text='About Qt',
        tooltip='Show the Qt librarys about box',
        help_category='Help',
        handler_factory=_slot('onAboutQt'),
    ),
    ActionDefinition(
        action_id='help.about_pyaero',
        text='About PyAero',
        tooltip='Information about the PyAero and its licensing',
        icon_name='about',
        help_category='Help',
        handler_factory=_slot('onAbout'),
    ),
    ActionDefinition(
        action_id='debug.autorun',
        text='Autorun (for testing)',
        tooltip='Autorun (for testing)',
        icon_name='autorun',
        help_category='Tools',
        handler_factory=_slot('runCommands'),
    ),
)


class ActionRegistry:
    def __init__(self, mainwindow):
        self.mw = mainwindow
        self._actions = {}
        self._definitions = {
            definition.action_id: definition for definition in ACTION_DEFINITIONS
        }
        self._definition_order = tuple(
            definition.action_id for definition in ACTION_DEFINITIONS
        )
        self._menu_layout = None
        self._toolbar_layout = None
        self._shortcut_overrides = self._load_shortcut_overrides()

    def install(self):
        for action_id in self._definition_order:
            self._actions[action_id] = self._create_action(
                self._definitions[action_id]
            )

    def action(self, action_id):
        return self._actions.get(action_id)

    def definition(self, action_id):
        return self._definitions.get(action_id)

    def menu_layout(self):
        if self._menu_layout is None:
            self._menu_layout = self._load_layout(MENU_LAYOUT_FILE, 'menus')
        return self._menu_layout

    def toolbar_layout(self):
        if self._toolbar_layout is None:
            self._toolbar_layout = self._load_layout(
                TOOLBAR_LAYOUT_FILE,
                'toolbars',
            )
        return self._toolbar_layout

    def shortcut_help(self):
        entries = []
        for action_id in self._definition_order:
            action = self.action(action_id)
            if action is None:
                continue
            shortcut_text = tuple(self._format_shortcut_text(action.shortcuts()))
            if not shortcut_text:
                continue

            definition = self.definition(action_id)
            entries.append(
                ShortcutHelpEntry(
                    category=definition.help_category,
                    text=definition.text,
                    description=definition.tooltip or definition.text,
                    shortcuts=shortcut_text,
                )
            )
        return tuple(entries)

    def _load_shortcut_overrides(self):
        if not SHORTCUT_OVERRIDE_FILE.exists():
            return {}

        try:
            with SHORTCUT_OVERRIDE_FILE.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            logger.warning(
                'Failed to read shortcut overrides from %s: %s',
                SHORTCUT_OVERRIDE_FILE,
                error,
            )
            return {}

        if not isinstance(data, dict):
            logger.warning(
                'Ignoring shortcut overrides from %s because the content is not a mapping.',
                SHORTCUT_OVERRIDE_FILE,
            )
            return {}
        return data

    def _load_layout(self, filename, top_level_key):
        with filename.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        layout = data.get(top_level_key, [])
        if not isinstance(layout, list):
            raise ValueError(f'Invalid layout structure in {filename}')

        return tuple(layout)

    def _create_action(self, definition):
        icon = Icons.icon(definition.icon_name) if definition.icon_name else QtGui.QIcon()
        action = QtGui.QAction(icon, definition.text, self.mw)
        action.setObjectName(definition.action_id)
        action.setStatusTip(definition.tooltip or definition.text)
        action.setToolTip(definition.tooltip or definition.text)
        action.setShortcutContext(definition.shortcut_context)

        shortcuts = self._action_shortcuts(definition)
        if shortcuts:
            action.setShortcuts(shortcuts)

        handler = definition.handler_factory(self.mw)
        action.triggered.connect(
            lambda _checked=False, callback=handler: callback()
        )

        for target_name in definition.shortcut_targets:
            target = self._resolve_target(target_name)
            if target is None:
                logger.warning(
                    'Shortcut target %s for action %s is not available.',
                    target_name,
                    definition.action_id,
                )
                continue
            target.addAction(action)

        return action

    def _action_shortcuts(self, definition):
        override = self._shortcut_overrides.get(definition.action_id)
        if override is not None:
            return self._normalize_shortcuts(override)

        if definition.shortcut_provider is not None:
            return self._normalize_shortcuts(definition.shortcut_provider(self.mw))

        return self._normalize_shortcuts(definition.default_shortcuts)

    def _normalize_shortcuts(self, shortcut_value):
        if isinstance(shortcut_value, str):
            values = [shortcut_value]
        elif isinstance(shortcut_value, Sequence):
            values = [value for value in shortcut_value if value]
        else:
            values = []

        normalized = []
        for value in values:
            sequence = QtGui.QKeySequence(str(value))
            if sequence.toString():
                normalized.append(sequence)
        return normalized

    def _resolve_target(self, target_name):
        if target_name == 'mainwindow':
            return self.mw
        if target_name == 'view':
            return getattr(self.mw, 'view', None)
        if target_name == 'toolbox':
            return getattr(getattr(self.mw, 'mainArea', None), 'toolbox', None)
        return None

    @staticmethod
    def _format_shortcut_text(shortcuts):
        texts = []
        for shortcut in shortcuts:
            text = shortcut.toString(QtGui.QKeySequence.NativeText)
            if not text:
                text = shortcut.toString()
            if text:
                texts.append(text)
        return texts
