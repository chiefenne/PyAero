from pathlib import Path

from PySide6 import QtCore, QtGui


ICON_ROOT = Path(__file__).resolve().parent.parent / 'resources' / 'Icons'
PREVIEW_SIZES = (16, 20, 24, 32)


ICON_FILES = {
    'about': 'lucide/info.svg',
    'aerodynamics': 'lucide/wind.svg',
    'airfoil': 'custom/airfoil.svg',
    'airfoil-library': 'custom/airfoil-library.svg',
    'autorun': 'lucide/workflow.svg',
    'calculator': 'lucide/calculator.svg',
    'cfd-inputs': 'lucide/gauge.svg',
    'contour-analysis': 'lucide/chart-line.svg',
    'delete': 'lucide/trash-2.svg',
    'exit': 'lucide/log-out.svg',
    'fit-airfoil': 'lucide/scan-search.svg',
    'fit-all': 'lucide/maximize.svg',
    'folder': 'lucide/folder.svg',
    'geometry-prep': 'lucide/pen-tool.svg',
    'keyboard-shortcuts': 'lucide/keyboard.svg',
    'manual': 'lucide/book-open-text.svg',
    'mesh': 'custom/mesh.svg',
    'open': 'lucide/folder-open.svg',
    'print': 'lucide/printer.svg',
    'print-preview': 'lucide/file-search.svg',
    'save': 'lucide/save.svg',
    'save-as': 'lucide/file-pen-line.svg',
    'settings': 'lucide/settings.svg',
}


def path(name):
    if not name:
        return ''

    key = name.strip()
    if not key:
        return ''

    mapped = ICON_FILES.get(key)
    if mapped:
        candidate = ICON_ROOT / mapped
        if candidate.exists():
            return str(candidate)

    direct_path = Path(key)
    if direct_path.exists():
        return str(direct_path.resolve())

    legacy_path = ICON_ROOT / key
    if legacy_path.exists():
        return str(legacy_path.resolve())

    return ''


def relative_path(name):
    return ICON_FILES.get(name, '')


def family(name):
    rel_path = relative_path(name)
    if '/' in rel_path:
        return rel_path.split('/', 1)[0]
    return 'legacy'


def names():
    return tuple(
        sorted(
            ICON_FILES,
            key=lambda icon_name: (family(icon_name) != 'custom', icon_name),
        )
    )


def names_for_family(icon_family):
    return tuple(name for name in names() if family(name) == icon_family)


def icon(name):
    icon_path = path(name)
    if not icon_path:
        return QtGui.QIcon()
    return QtGui.QIcon(icon_path)


def pixmap(name, size):
    if isinstance(size, int):
        size = QtCore.QSize(size, size)
    return icon(name).pixmap(size)
