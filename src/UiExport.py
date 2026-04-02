import logging
import re

from PySide6 import QtCore, QtGui, QtWidgets

import FileDialog


logger = logging.getLogger(__name__)


def slugify_text(text, fallback='widget'):
    slug = re.sub(r'[^a-z0-9]+', '_', str(text).lower())
    return slug.strip('_') or fallback


def export_widget_as_png(
    mainwindow,
    widget,
    default_name,
    dialog_title,
    success_label,
    rounded_radius=None,
):
    parent_widget = widget.window() if widget is not None else mainwindow
    dialog = FileDialog.Dialog(
        mainwindow=mainwindow,
        parent_widget=parent_widget,
    )
    filename, _selected_filter = dialog.save_filename(
        filename=default_name,
        title=dialog_title,
        filter='PNG images (*.png)',
    )
    if not filename:
        logger.info('No file selected. %s export canceled.', success_label)
        return False

    if not filename.lower().endswith('.png'):
        filename = f'{filename}.png'

    try:
        save_widget_png(
            widget=widget,
            filename=filename,
            rounded_radius=rounded_radius,
            fallback_widget=mainwindow,
        )
    except OSError as error:
        logger.error(
            'Failed to export %s to %s: %s',
            success_label.lower(),
            filename,
            error,
            exc_info=True,
        )
        QtWidgets.QMessageBox.information(
            parent_widget,
            'Information',
            f'Failed to export {success_label.lower()}:\n{filename}\n\n{error}',
            QtWidgets.QMessageBox.Ok,
        )
        return False

    logger.info('%s exported to %s', success_label, filename)
    return True


def save_widget_png(widget, filename, rounded_radius=None, fallback_widget=None):
    if widget is None:
        raise OSError('No widget was provided for export.')

    widget.ensurePolished()
    if widget.layout() is not None:
        widget.layout().activate()
    if widget.size().width() <= 0 or widget.size().height() <= 0:
        size_hint = widget.sizeHint()
        if size_hint.width() > 0 and size_hint.height() > 0:
            widget.resize(size_hint)
            if widget.layout() is not None:
                widget.layout().activate()

    QtWidgets.QApplication.processEvents()

    logical_size = widget.size()
    if logical_size.width() <= 0 or logical_size.height() <= 0:
        raise OSError('The widget has no visible size to export.')

    screen = widget.screen()
    if screen is None and fallback_widget is not None:
        screen = fallback_widget.screen()
    if screen is None:
        screen = QtWidgets.QApplication.primaryScreen()

    scale = 1.0
    if screen is not None:
        try:
            scale = max(1.0, float(screen.devicePixelRatio()))
        except (TypeError, ValueError):
            scale = 1.0

    image = QtGui.QImage(
        max(1, int(round(logical_size.width() * scale))),
        max(1, int(round(logical_size.height() * scale))),
        QtGui.QImage.Format_ARGB32_Premultiplied,
    )
    image.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.scale(scale, scale)

        if rounded_radius is not None:
            clip_path = QtGui.QPainterPath()
            clip_path.addRoundedRect(
                QtCore.QRectF(
                    0.0,
                    0.0,
                    float(logical_size.width()),
                    float(logical_size.height()),
                ),
                rounded_radius,
                rounded_radius,
            )
            painter.setClipPath(clip_path)

        if isinstance(widget, QtWidgets.QGraphicsView):
            widget.render(
                painter,
                target=QtCore.QRectF(
                    0.0,
                    0.0,
                    float(logical_size.width()),
                    float(logical_size.height()),
                ),
                source=widget.viewport().rect(),
                aspectRatioMode=QtCore.Qt.IgnoreAspectRatio,
            )
        else:
            widget.render(
                painter,
                QtCore.QPoint(),
                QtGui.QRegion(),
                QtWidgets.QWidget.DrawWindowBackground
                | QtWidgets.QWidget.DrawChildren,
            )
    finally:
        painter.end()

    if not image.save(filename):
        raise OSError('Qt could not save the PNG image.')


def install_dialog_export_button(
    button_box,
    mainwindow,
    widget,
    default_name,
    dialog_title,
    success_label,
    rounded_radius=18.0,
):
    button = button_box.addButton(
        'Export PNG...',
        QtWidgets.QDialogButtonBox.ActionRole,
    )
    button.clicked.connect(
        lambda *_: export_widget_as_png(
            mainwindow=mainwindow,
            widget=widget,
            default_name=default_name,
            dialog_title=dialog_title,
            success_label=success_label,
            rounded_radius=rounded_radius,
        )
    )
    return button
