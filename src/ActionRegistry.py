from __future__ import annotations

import copy
import json
import platform
from collections.abc import Mapping, Sequence
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
DEFAULT_SHORTCUT_FILE = ROOT / 'resources' / 'Shortcuts' / 'shortcuts.json'
USER_SHORTCUT_FILE = ROOT / 'config' / 'shortcuts_user.json'
LEGACY_SHORTCUT_FILE = ROOT / 'config' / 'shortcuts.json'
SEPARATOR_TOKEN = 'separator'
SHORTCUT_CONFIG_VERSION = 1
PLATFORM_KEYS = ('all', 'windows', 'macos', 'linux')
PLATFORM_LABELS = {
    'all': 'All platforms',
    'windows': 'Windows',
    'macos': 'macOS',
    'linux': 'Linux',
}


ActionHandlerFactory = Callable[[object], Callable[[], None]]
ShortcutProvider = Callable[[object], Sequence[object]]


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    text: str
    tooltip: str
    handler_factory: ActionHandlerFactory
    icon_name: str = ''
    shortcut_context: QtCore.Qt.ShortcutContext = QtCore.Qt.WindowShortcut
    shortcut_targets: tuple[str, ...] = ('mainwindow',)
    help_category: str = 'General'
    user_editable: bool = True
    shortcut_provider: ShortcutProvider | None = None


@dataclass(frozen=True)
class ShortcutHelpEntry:
    category: str
    text: str
    description: str
    shortcuts: tuple[str, ...]


@dataclass(frozen=True)
class ShortcutEditorEntry:
    action_id: str
    category: str
    text: str
    description: str
    current_shortcuts: tuple[str, ...]
    default_shortcuts: tuple[str, ...]
    scope: str
    source: str
    editable: bool


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
        help_category='File',
        handler_factory=_slot('onOpen'),
    ),
    ActionDefinition(
        action_id='file.save',
        text='Save',
        tooltip='Save airfoil contour file',
        icon_name='save',
        help_category='File',
        handler_factory=_slot('onSave'),
    ),
    ActionDefinition(
        action_id='file.save_as',
        text='Save as',
        tooltip='Save airfoil contour file with different name',
        icon_name='save-as',
        help_category='File',
        handler_factory=_slot('onSaveAs'),
    ),
    ActionDefinition(
        action_id='file.print',
        text='Print',
        tooltip='Print current view',
        icon_name='print',
        help_category='File',
        handler_factory=_slot('onPrint'),
    ),
    ActionDefinition(
        action_id='file.print_preview',
        text='Print preview',
        tooltip='Print preview',
        icon_name='print-preview',
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
        help_category='Application',
        handler_factory=_slot('onExit'),
    ),
    ActionDefinition(
        action_id='app.exit_on_escape',
        text='Exit on Escape',
        tooltip='Close PyAero when Exit on Escape is enabled',
        shortcut_context=QtCore.Qt.ApplicationShortcut,
        shortcut_targets=('mainwindow',),
        help_category='Application',
        user_editable=False,
        shortcut_provider=_escape_shortcuts,
        handler_factory=_quit_application,
    ),
    ActionDefinition(
        action_id='view.fit_airfoil',
        text='Fit airfoil in view',
        tooltip='Set view to selected airfoil',
        icon_name='fit-airfoil',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='View',
        handler_factory=_slot('fitAirfoilInView'),
    ),
    ActionDefinition(
        action_id='view.fit_all',
        text='Fit all in view',
        tooltip='Set view to all items visible',
        icon_name='fit-all',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='View',
        handler_factory=_slot('onViewAll'),
    ),
    ActionDefinition(
        action_id='view.toggle_background',
        text='Toggle background',
        tooltip='Toggle background color',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='View',
        handler_factory=_slot('onBackground'),
    ),
    ActionDefinition(
        action_id='view.toggle_magnifier',
        text='Toggle magnifier',
        tooltip='Turn the magnifier lens on or off',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Magnifier',
        handler_factory=_view_method('toggleMagnifier'),
    ),
    ActionDefinition(
        action_id='view.toggle_messages',
        text='Toggle message window',
        tooltip='Toggle the message window to have more space for the viewer',
        help_category='View',
        handler_factory=_slot('toggleLogDock'),
    ),
    ActionDefinition(
        action_id='view.zoom_in',
        text='Zoom in',
        tooltip='Zoom in the current graphics view',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Viewer',
        handler_factory=_view_method('zoomIn'),
    ),
    ActionDefinition(
        action_id='view.zoom_out',
        text='Zoom out',
        tooltip='Zoom out the current graphics view',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Viewer',
        handler_factory=_view_method('zoomOut'),
    ),
    ActionDefinition(
        action_id='view.magnifier_zoom_in',
        text='Magnifier zoom in',
        tooltip='Increase the magnifier zoom level',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Magnifier',
        handler_factory=_view_method('magnifierZoomIn'),
    ),
    ActionDefinition(
        action_id='view.magnifier_zoom_out',
        text='Magnifier zoom out',
        tooltip='Decrease the magnifier zoom level',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Magnifier',
        handler_factory=_view_method('magnifierZoomOut'),
    ),
    ActionDefinition(
        action_id='view.magnifier_size_up',
        text='Magnifier size up',
        tooltip='Increase the magnifier lens size',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Magnifier',
        handler_factory=_view_method('magnifierIncreaseSize'),
    ),
    ActionDefinition(
        action_id='view.magnifier_size_down',
        text='Magnifier size down',
        tooltip='Decrease the magnifier lens size',
        shortcut_context=QtCore.Qt.WidgetWithChildrenShortcut,
        shortcut_targets=('view',),
        help_category='Magnifier',
        handler_factory=_view_method('magnifierDecreaseSize'),
    ),
    ActionDefinition(
        action_id='airfoil.delete_active',
        text='Delete airfoil',
        tooltip='Delete the active airfoil',
        icon_name='delete',
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
        help_category='Tools',
        handler_factory=_slot('onCalculator'),
    ),
    ActionDefinition(
        action_id='tools.settings',
        text='Settings',
        tooltip='Edit PyAero application settings',
        icon_name='settings',
        help_category='Tools',
        handler_factory=_slot('onSettings'),
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
        help_category='Help',
        handler_factory=_slot('onHelpOnline'),
    ),
    ActionDefinition(
        action_id='help.manual_pdf',
        text='Manual (PDF)',
        tooltip='Open PyAero manual',
        icon_name='manual',
        help_category='Help',
        handler_factory=_slot('onHelpPDF'),
    ),
    ActionDefinition(
        action_id='help.shortcuts',
        text='Keyboard shortcuts',
        tooltip='Edit keyboard shortcuts',
        icon_name='keyboard-shortcuts',
        help_category='Help',
        handler_factory=_slot('onKeyBd'),
    ),
    ActionDefinition(
        action_id='help.about_qt',
        text='About Qt',
        tooltip='Show the Qt libraries about box',
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
        self._default_shortcut_config = self._load_shortcut_config(
            DEFAULT_SHORTCUT_FILE,
            require_platform_sections=True,
        )
        self._user_shortcut_config = self._load_user_shortcut_config()

    def install(self):
        for action_id in self._definition_order:
            self._actions[action_id] = self._create_action(
                self._definitions[action_id]
            )

    def action(self, action_id):
        return self._actions.get(action_id)

    def action_ids(self):
        return self._definition_order

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

    def platform_key(self):
        platform_name = getattr(self.mw, 'platform', '') or platform.system()
        platform_name = str(platform_name).lower()
        if platform_name.startswith('win'):
            return 'windows'
        if platform_name.startswith('darwin') or platform_name.startswith('mac'):
            return 'macos'
        return 'linux'

    def platform_label(self):
        return PLATFORM_LABELS.get(self.platform_key(), self.platform_key())

    def shortcut_help(self):
        entries = []
        for action_id in self._definition_order:
            definition = self.definition(action_id)
            shortcut_text = self.active_shortcut_text(action_id)
            if not shortcut_text:
                continue

            entries.append(
                ShortcutHelpEntry(
                    category=definition.help_category,
                    text=definition.text,
                    description=definition.tooltip or definition.text,
                    shortcuts=shortcut_text,
                )
            )
        return tuple(entries)

    def shortcut_editor_entries(self, platform_overrides=None):
        entries = []
        user_config = self._user_config_with_platform_overrides(platform_overrides)
        for action_id in self._definition_order:
            definition = self.definition(action_id)
            entries.append(
                ShortcutEditorEntry(
                    action_id=action_id,
                    category=definition.help_category,
                    text=definition.text,
                    description=definition.tooltip or definition.text,
                    current_shortcuts=self.active_shortcut_text(
                        action_id,
                        user_config=user_config,
                    ),
                    default_shortcuts=self.default_shortcut_text(action_id),
                    scope=self._scope_label(definition),
                    source=self._shortcut_source_label(
                        action_id,
                        user_config=user_config,
                    ),
                    editable=definition.user_editable,
                )
            )
        return tuple(entries)

    def platform_override_specs(self):
        section = self._section_mapping(
            self._user_shortcut_config,
            self.platform_key(),
        )
        overrides = {}
        for action_id, value in section.items():
            overrides[action_id] = tuple(self._normalize_shortcut_specs(value))
        return overrides

    def active_shortcut_text(self, action_id, user_config=None):
        return tuple(
            self._format_shortcut_text(
                self.active_shortcuts(action_id, user_config=user_config)
            )
        )

    def default_shortcut_text(self, action_id):
        return tuple(
            self._format_shortcut_text(self.default_shortcuts(action_id))
        )

    def active_shortcuts(self, action_id, user_config=None):
        return tuple(
            self._resolve_shortcuts(action_id, user_config=user_config)
        )

    def default_shortcuts(self, action_id):
        return tuple(
            self._specs_to_sequences(
                self._default_shortcut_specs(action_id),
            )
        )

    def active_portable_shortcuts(self, action_id, user_config=None):
        return tuple(
            self._portable_texts(
                self.active_shortcuts(action_id, user_config=user_config)
            )
        )

    def active_portable_shortcuts_for_overrides(self, action_id, platform_overrides=None):
        user_config = self._user_config_with_platform_overrides(platform_overrides)
        return self.active_portable_shortcuts(action_id, user_config=user_config)

    def detect_shortcut_conflicts(self, platform_overrides=None):
        user_config = self._user_config_with_platform_overrides(platform_overrides)
        usage = {}
        for action_id in self._definition_order:
            seen = set()
            for portable_text in self.active_portable_shortcuts(
                action_id,
                user_config=user_config,
            ):
                if not portable_text or portable_text in seen:
                    continue
                usage.setdefault(portable_text, []).append(action_id)
                seen.add(portable_text)

        return {
            shortcut: tuple(action_ids)
            for shortcut, action_ids in usage.items()
            if len(action_ids) > 1
        }

    def save_platform_overrides(self, platform_overrides):
        config = copy.deepcopy(self._user_shortcut_config)
        platform_key = self.platform_key()
        normalized_platform_section = {}

        inherited_user_config = copy.deepcopy(config)
        inherited_user_config[platform_key] = {}

        for action_id, value in platform_overrides.items():
            definition = self.definition(action_id)
            if definition is None or not definition.user_editable:
                continue

            specs = tuple(self._normalize_shortcut_specs(value))
            sequences = self._specs_to_sequences(specs)
            inherited_sequences = self._resolve_shortcuts(
                action_id,
                user_config=inherited_user_config,
            )

            if self._portable_texts(sequences) == self._portable_texts(inherited_sequences):
                continue

            normalized_platform_section[action_id] = list(specs)

        config[platform_key] = normalized_platform_section
        self._write_shortcut_config(USER_SHORTCUT_FILE, config)
        self._user_shortcut_config = config
        self.apply_shortcuts()

    def apply_shortcuts(self):
        for action_id, action in self._actions.items():
            if action is None:
                continue
            action.setShortcuts(self.active_shortcuts(action_id))

    def _load_user_shortcut_config(self):
        user_config = self._load_shortcut_config(
            USER_SHORTCUT_FILE,
            require_platform_sections=False,
        )
        legacy_section = self._load_legacy_shortcut_section()
        if not legacy_section:
            return user_config

        platform_key = self.platform_key()
        platform_section = self._section_mapping(user_config, platform_key)
        if platform_section:
            return user_config

        user_config[platform_key] = legacy_section
        self._write_shortcut_config(USER_SHORTCUT_FILE, user_config)
        logger.info(
            'Migrated legacy shortcuts from %s to %s',
            LEGACY_SHORTCUT_FILE,
            USER_SHORTCUT_FILE,
        )
        return user_config

    def _load_legacy_shortcut_section(self):
        if not LEGACY_SHORTCUT_FILE.exists():
            return {}

        try:
            with LEGACY_SHORTCUT_FILE.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            logger.warning(
                'Failed to read legacy shortcuts from %s: %s',
                LEGACY_SHORTCUT_FILE,
                error,
            )
            return {}

        if not isinstance(data, Mapping):
            return {}

        if any(key in PLATFORM_KEYS for key in data.keys()):
            return {}

        section = {}
        for action_id, value in data.items():
            section[action_id] = list(self._normalize_shortcut_specs(value))
        return section

    def _load_shortcut_config(self, filename, require_platform_sections):
        base = self._empty_shortcut_config()
        if not filename.exists():
            return base

        try:
            with filename.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:
            logger.warning(
                'Failed to read shortcuts from %s: %s',
                filename,
                error,
            )
            return base

        if not isinstance(data, Mapping):
            logger.warning(
                'Ignoring shortcuts in %s because the content is not a mapping.',
                filename,
            )
            return base

        config = self._empty_shortcut_config()
        if isinstance(data.get('version'), int):
            config['version'] = data['version']

        for key in PLATFORM_KEYS:
            section = data.get(key, {})
            if not isinstance(section, Mapping):
                if require_platform_sections and key in data:
                    logger.warning(
                        'Ignoring invalid shortcut section %s in %s',
                        key,
                        filename,
                    )
                continue

            normalized_section = {}
            for action_id, value in section.items():
                normalized_section[action_id] = list(
                    self._normalize_shortcut_specs(value)
                )
            config[key] = normalized_section

        return config

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
        action.setShortcuts(self.active_shortcuts(definition.action_id))

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

    def _resolve_shortcuts(self, action_id, user_config=None):
        definition = self.definition(action_id)
        if definition is None:
            return []

        if definition.shortcut_provider is not None:
            return self._specs_to_sequences(definition.shortcut_provider(self.mw))

        specs = self._effective_shortcut_specs(
            action_id,
            user_config=user_config,
        )
        return self._specs_to_sequences(specs)

    def _effective_shortcut_specs(self, action_id, user_config=None):
        config = user_config or self._user_shortcut_config
        platform_key = self.platform_key()
        platform_user = self._section_mapping(config, platform_key)
        all_user = self._section_mapping(config, 'all')
        platform_default = self._section_mapping(
            self._default_shortcut_config,
            platform_key,
        )
        all_default = self._section_mapping(self._default_shortcut_config, 'all')

        if action_id in platform_user:
            return platform_user[action_id]
        if action_id in all_user:
            return all_user[action_id]
        if action_id in platform_default:
            return platform_default[action_id]
        if action_id in all_default:
            return all_default[action_id]
        return ()

    def _default_shortcut_specs(self, action_id):
        platform_key = self.platform_key()
        platform_default = self._section_mapping(
            self._default_shortcut_config,
            platform_key,
        )
        all_default = self._section_mapping(self._default_shortcut_config, 'all')
        if action_id in platform_default:
            return platform_default[action_id]
        if action_id in all_default:
            return all_default[action_id]
        return ()

    def _shortcut_source_label(self, action_id, user_config=None):
        definition = self.definition(action_id)
        if definition.shortcut_provider is not None:
            active = self.active_shortcut_text(action_id, user_config=user_config)
            if active:
                return 'Managed by application setting'
            return 'Disabled by application setting'

        config = user_config or self._user_shortcut_config
        platform_key = self.platform_key()
        platform_user = self._section_mapping(config, platform_key)
        all_user = self._section_mapping(config, 'all')
        platform_default = self._section_mapping(
            self._default_shortcut_config,
            platform_key,
        )
        all_default = self._section_mapping(self._default_shortcut_config, 'all')

        if action_id in platform_user:
            return f'User override ({self.platform_label()})'
        if action_id in all_user:
            return 'User override (all platforms)'
        if action_id in platform_default:
            return f'Built-in default ({self.platform_label()})'
        if action_id in all_default:
            return 'Built-in default'
        return 'No shortcut'

    def _user_config_with_platform_overrides(self, platform_overrides):
        if platform_overrides is None:
            return self._user_shortcut_config

        config = copy.deepcopy(self._user_shortcut_config)
        platform_key = self.platform_key()
        config[platform_key] = {}
        for action_id, value in platform_overrides.items():
            config[platform_key][action_id] = list(
                self._normalize_shortcut_specs(value)
            )
        return config

    def _normalize_shortcut_specs(self, shortcut_value):
        if shortcut_value is None:
            return ()

        if isinstance(shortcut_value, str):
            values = [shortcut_value]
        elif isinstance(shortcut_value, Mapping):
            values = [shortcut_value]
        elif isinstance(shortcut_value, Sequence):
            values = list(shortcut_value)
        else:
            values = []

        normalized = []
        for value in values:
            if isinstance(value, str):
                text = value.strip()
                if text:
                    normalized.append(text)
                continue

            if not isinstance(value, Mapping):
                continue

            standard_key = value.get('standard_key')
            if isinstance(standard_key, str) and standard_key.strip():
                normalized.append({'standard_key': standard_key.strip()})
                continue

            sequence_text = value.get('sequence')
            if isinstance(sequence_text, str) and sequence_text.strip():
                normalized.append(sequence_text.strip())

        return tuple(normalized)

    def _specs_to_sequences(self, specs):
        sequences = []
        seen = set()
        for spec in self._normalize_shortcut_specs(specs):
            if isinstance(spec, Mapping):
                standard_key = self._resolve_standard_key(spec.get('standard_key'))
                if standard_key is None:
                    continue
                candidates = QtGui.QKeySequence.keyBindings(standard_key)
            else:
                sequence = QtGui.QKeySequence.fromString(
                    str(spec),
                    QtGui.QKeySequence.PortableText,
                )
                candidates = [sequence] if not sequence.isEmpty() else []

            for candidate in candidates:
                portable = candidate.toString(QtGui.QKeySequence.PortableText)
                if not portable or portable in seen:
                    continue
                sequences.append(candidate)
                seen.add(portable)
        return sequences

    def _resolve_standard_key(self, name):
        if not isinstance(name, str) or not name:
            return None

        enum_type = getattr(QtGui.QKeySequence, 'StandardKey', None)
        if enum_type is not None and hasattr(enum_type, name):
            return getattr(enum_type, name)

        if hasattr(QtGui.QKeySequence, name):
            return getattr(QtGui.QKeySequence, name)

        logger.warning('Unknown standard shortcut key %s', name)
        return None

    def _portable_texts(self, shortcuts):
        texts = []
        for shortcut in shortcuts:
            text = shortcut.toString(QtGui.QKeySequence.PortableText)
            if not text:
                text = shortcut.toString()
            if text and text not in texts:
                texts.append(text)
        return tuple(texts)

    def _resolve_target(self, target_name):
        if target_name == 'mainwindow':
            return self.mw
        if target_name == 'view':
            return getattr(self.mw, 'view', None)
        if target_name == 'toolbox':
            return getattr(getattr(self.mw, 'mainArea', None), 'toolbox', None)
        return None

    def _scope_label(self, definition):
        if definition.shortcut_context == QtCore.Qt.ApplicationShortcut:
            return 'Application'
        if definition.shortcut_targets == ('view',):
            return 'Viewer'
        if definition.shortcut_targets == ('toolbox',):
            return 'Toolbox'
        return 'Window'

    def _section_mapping(self, config, key):
        section = config.get(key, {})
        if isinstance(section, Mapping):
            return section
        return {}

    def _empty_shortcut_config(self):
        return {
            'version': SHORTCUT_CONFIG_VERSION,
            'all': {},
            'windows': {},
            'macos': {},
            'linux': {},
        }

    def _write_shortcut_config(self, filename, config):
        with filename.open('w', encoding='utf-8') as handle:
            json.dump(config, handle, indent=2)
            handle.write('\n')

    @staticmethod
    def _format_shortcut_text(shortcuts):
        texts = []
        for shortcut in shortcuts:
            text = shortcut.toString(QtGui.QKeySequence.NativeText)
            if not text:
                text = shortcut.toString()
            if text and text not in texts:
                texts.append(text)
        return texts
