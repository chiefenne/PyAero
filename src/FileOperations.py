import logging
import os
import re

import FileDialog
from Utils import get_main_window


logger = logging.getLogger(__name__)


CONTOUR_FILTER = 'Airfoil contour files (*.dat *.txt)'
SUPPORTED_AIRFOIL_EXTENSIONS = ('.dat', '.txt')
MESH_EXPORT_EXTENSIONS = {
    'flma': '.flma',
    'su2': '.su2',
    'gmsh': '.msh',
    'vtu': '.vtu',
}


def _selected_extension(selected_filter, fallback):
    matches = re.findall(r'\*\.([A-Za-z0-9]+)', selected_filter or '')
    if matches:
        return f'.{matches[0]}'
    return fallback


def _default_contour_location(airfoil, mainwindow=None):
    mw = mainwindow or get_main_window()
    default_directory = mw.OUTPUT
    source_path = getattr(airfoil, 'source_path', None)
    if source_path:
        default_directory = os.path.dirname(source_path)

    default_name = getattr(airfoil, 'name', '') or 'airfoil.dat'
    return default_directory, default_name


def choose_contour_save_filename(airfoil, title='Save Contour As',
                                 mainwindow=None):
    mw = mainwindow or get_main_window()
    directory, default_name = _default_contour_location(airfoil, mw)
    dialog = FileDialog.Dialog(mainwindow=mw)
    filename, selected_filter = dialog.save_filename(
        filename=default_name,
        directory=directory,
        title=title,
        filter=CONTOUR_FILTER,
    )
    if not filename:
        return None

    default_extension = os.path.splitext(default_name)[1] or '.dat'
    if not os.path.splitext(filename)[1]:
        filename += _selected_extension(selected_filter, default_extension)
    return filename


def choose_mesh_export_basename(airfoil, formats, title='Export Mesh Files',
                                mainwindow=None):
    mw = mainwindow or get_main_window()
    directory, default_name = _default_contour_location(airfoil, mw)
    basename, _ = os.path.splitext(default_name)
    basename = basename or 'mesh'

    extensions = [
        MESH_EXPORT_EXTENSIONS[mesh_format]
        for mesh_format in formats
        if mesh_format in MESH_EXPORT_EXTENSIONS
    ]
    filter_extensions = ' '.join(f'*{extension}' for extension in extensions)
    dialog_filter = (
        f'Mesh files ({filter_extensions})'
        if filter_extensions else
        'Mesh files (*)'
    )

    dialog = FileDialog.Dialog(mainwindow=mw)
    filename, _ = dialog.save_filename(
        filename=basename,
        directory=directory,
        title=title,
        filter=dialog_filter,
    )
    if not filename:
        return None

    root, extension = os.path.splitext(filename)
    if extension.lower() in {item.lower() for item in extensions}:
        return root
    return filename


def report_io_error(action, filename, error, mainwindow=None):
    mw = mainwindow or get_main_window()
    logger.error('Failed to %s %s: %s', action, filename, error, exc_info=True)
    message = f'Failed to {action}:\n{filename}\n\n{error}'
    if hasattr(mw, 'slots'):
        mw.slots.messageBox(message)
    return None


def write_contour(airfoil, filename, prefer_spline=True, mainwindow=None):
    mw = mainwindow or get_main_window()
    contour = airfoil.current_contour(prefer_spline=prefer_spline)
    if contour is None:
        if hasattr(mw, 'slots'):
            mw.slots.messageBox('No airfoil contour available to save.')
        return None

    try:
        import PyAero
    except ImportError:
        PyAero = None

    x_values, y_values = contour
    contour_type = 'spline' if prefer_spline and airfoil.has_spline else 'raw'
    source_name = os.path.basename(
        getattr(airfoil, 'source_path', '') or airfoil.name
    ).strip()

    try:
        with open(filename, 'w', encoding='utf-8') as handle:
            handle.write('#\n')
            if PyAero is not None:
                handle.write(f'# File created with {PyAero.__appname__}\n')
                handle.write(f'# Version: {PyAero.__version__}\n')
                handle.write(f'# Author: {PyAero.__author__}\n')
                handle.write('#\n')
            handle.write(f'# Derived from: {source_name}\n')
            handle.write(f'# Contour type: {contour_type}\n')
            handle.write(f'# Number of points: {len(x_values)}\n')
            handle.write('#\n')
            for x_value, y_value in zip(x_values, y_values):
                handle.write(f'{x_value:10.6f} {y_value:10.6f}\n')
    except OSError as error:
        return report_io_error('save contour', filename, error, mainwindow=mw)

    logger.info('Contour saved as %s', filename)
    return filename
