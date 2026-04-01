import csv
import json
import logging
import os
import re

from CSTAirfoil import cst_parameters_from_spline_data
import FileDialog
import Mesh as MeshModel
from Utils import get_main_window


logger = logging.getLogger(__name__)


CONTOUR_FILTER = 'Airfoil contour files (*.dat *.txt)'
CAMBER_FILTER = 'Camber files (*.dat *.txt)'
CST_FILTER = 'JSON files (*.json);;CSV files (*.csv)'
SUPPORTED_AIRFOIL_EXTENSIONS = ('.dat', '.txt')


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
    _directory, default_name = _default_contour_location(airfoil, mainwindow)
    return choose_data_save_filename(
        airfoil,
        default_name=default_name,
        title=title,
        filter=CONTOUR_FILTER,
        mainwindow=mainwindow,
    )


def choose_data_save_filename(airfoil, default_name, title='Save File As',
                              filter=None, mainwindow=None):
    mw = mainwindow or get_main_window()
    directory, _ = _default_contour_location(airfoil, mw)
    dialog = FileDialog.Dialog(mainwindow=mw)
    filename, selected_filter = dialog.save_filename(
        filename=default_name,
        directory=directory,
        title=title,
        filter=filter or CONTOUR_FILTER,
    )
    if not filename:
        return None

    default_extension = os.path.splitext(default_name)[1] or '.dat'
    if not os.path.splitext(filename)[1]:
        filename += _selected_extension(selected_filter, default_extension)
    return filename


def choose_camber_save_filename(airfoil, title='Export Camber',
                                mainwindow=None):
    _directory, default_name = _default_contour_location(airfoil, mainwindow)
    basename, _extension = os.path.splitext(default_name)
    basename = basename or 'airfoil'
    return choose_data_save_filename(
        airfoil,
        default_name=f'{basename}_camber.dat',
        title=title,
        filter=CAMBER_FILTER,
        mainwindow=mainwindow,
    )


def choose_cst_save_filename(airfoil, title='Export CST Parameters',
                             default_extension='.json', mainwindow=None):
    _directory, default_name = _default_contour_location(airfoil, mainwindow)
    basename, _extension = os.path.splitext(default_name)
    basename = basename or 'airfoil'
    extension = default_extension if default_extension in ('.json', '.csv') else '.json'
    return choose_data_save_filename(
        airfoil,
        default_name=f'{basename}_cst{extension}',
        title=title,
        filter=CST_FILTER,
        mainwindow=mainwindow,
    )


def choose_mesh_export_basename(airfoil, formats, title='Export Mesh Files',
                                mainwindow=None):
    mw = mainwindow or get_main_window()
    directory, default_name = _default_contour_location(airfoil, mw)
    basename, _ = os.path.splitext(default_name)
    basename = basename or 'mesh'

    extensions = [
        MeshModel.MeshExportRegistry.extension_for(mesh_format)
        for mesh_format in formats
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
    if prefer_spline and airfoil.has_spline:
        metadata = getattr(airfoil.spline_data, 'metadata', {}) or {}
        contour_type = metadata.get('label', 'prepared contour')
    else:
        contour_type = 'raw'
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


def write_camber(airfoil, filename, mainwindow=None):
    mw = mainwindow or get_main_window()
    camber_data = getattr(airfoil, 'camber_data', None)
    if camber_data is None:
        if hasattr(mw, 'slots'):
            mw.slots.messageBox('No camber data available to save.')
        return None

    try:
        import PyAero
    except ImportError:
        PyAero = None

    x_values, y_values = camber_data.polyline_coordinates(
        start_at_le_tangency=True
    )
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
            handle.write(f'# Camber method: {camber_data.method}\n')
            handle.write(f'# Number of points: {len(x_values)}\n')
            handle.write('#\n')
            for x_value, y_value in zip(x_values, y_values):
                handle.write(f'{x_value:10.6f} {y_value:10.6f}\n')
    except OSError as error:
        return report_io_error('save camber', filename, error, mainwindow=mw)

    logger.info('Camber saved as %s', filename)
    return filename


def write_cst_parameters(airfoil, filename, mainwindow=None):
    mw = mainwindow or get_main_window()
    spline_data = getattr(airfoil, 'spline_data', None)
    if spline_data is None:
        if hasattr(mw, 'slots'):
            mw.slots.messageBox('No prepared contour available to export.')
        return None

    try:
        parameter_data = cst_parameters_from_spline_data(spline_data)
    except ValueError as error:
        if hasattr(mw, 'slots'):
            mw.slots.messageBox(str(error))
        return None

    source_name = os.path.basename(
        getattr(airfoil, 'source_path', '') or airfoil.name
    ).strip()
    payload = {
        'derived_from': source_name,
        'leading_edge_parameter': parameter_data['leading_edge_parameter'],
        'upper_surface': parameter_data['upper_surface'],
        'lower_surface': parameter_data['lower_surface'],
    }

    extension = os.path.splitext(filename)[1].lower()
    if extension == '.json':
        try:
            with open(filename, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, indent=2)
                handle.write('\n')
        except OSError as error:
            return report_io_error(
                'save CST parameters',
                filename,
                error,
                mainwindow=mw,
            )
        logger.info('CST parameters saved as %s', filename)
        return filename

    if extension == '.csv':
        rows = [
            ('global', 'derived_from', '', source_name),
            (
                'global',
                'leading_edge_parameter',
                '',
                payload['leading_edge_parameter'],
            ),
        ]
        for surface_key in ('upper_surface', 'lower_surface'):
            surface = payload[surface_key]
            name = surface['name']
            rows.append((name, 'order', '', surface['order']))
            rows.append(
                (name, 'nose_coefficient', '', surface['nose_coefficient'])
            )
            rows.append(
                (name, 'trailing_edge_offset', '', surface['trailing_edge_offset'])
            )
            for index, value in enumerate(surface['coefficients']):
                rows.append((name, 'coefficient', index, value))

        try:
            with open(filename, 'w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(('section', 'name', 'index', 'value'))
                writer.writerows(rows)
        except OSError as error:
            return report_io_error(
                'save CST parameters',
                filename,
                error,
                mainwindow=mw,
            )
        logger.info('CST parameters saved as %s', filename)
        return filename

    if hasattr(mw, 'slots'):
        mw.slots.messageBox('Unsupported CST export format. Use .json or .csv.')
    return None
