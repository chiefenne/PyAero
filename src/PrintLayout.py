from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import getpass

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from CSTAirfoil import split_airfoil_surfaces


FRAME_MODE_NONE = 'none'
FRAME_MODE_FRAME = 'frame'
FRAME_MODES = (
    FRAME_MODE_NONE,
    FRAME_MODE_FRAME,
)

PAPER_SIZE_A4 = 'A4'
PAPER_SIZE_A3 = 'A3'
PAPER_SIZES = (
    PAPER_SIZE_A4,
    PAPER_SIZE_A3,
)

FRAME_MARGIN_MM = 10.0
FRAME_LINE_MM = 0.22
DATA_BOX_WIDTH_MM = 54.0
INNER_MARGIN_MM = 4.0
FOOTER_WIDTH_MM = 54.0


def normalize_frame_mode(value):
    normalized = str(value or '').strip().lower()
    legacy_map = {
        'simple': FRAME_MODE_FRAME,
        'frame': FRAME_MODE_FRAME,
        'iso': FRAME_MODE_FRAME,
    }
    normalized = legacy_map.get(normalized, normalized)
    if normalized in FRAME_MODES:
        return normalized
    raise ValueError(
        'Frame mode must be one of: ' + ', '.join(FRAME_MODES)
    )


def normalize_paper_size(value):
    normalized = str(value or '').strip().upper()
    if normalized in PAPER_SIZES:
        return normalized
    raise ValueError(
        'Paper size must be one of: ' + ', '.join(PAPER_SIZES)
    )


def current_creator_name():
    try:
        creator = getpass.getuser().strip()
    except (OSError, KeyError):
        creator = ''
    return creator or 'PyAero user'


def mm_to_pixels(mm_value, resolution):
    return float(mm_value) * float(resolution) / 25.4


@dataclass(slots=True)
class PrintFooterData:
    show_author: bool = False
    author: str = ''
    show_date: bool = False
    date_of_issue: str = ''


@dataclass(slots=True)
class PrintLayoutOptions:
    frame_mode: str = FRAME_MODE_NONE
    paper_size: str = PAPER_SIZE_A4
    show_data_box: bool = True
    show_position_line: bool = True
    footer: PrintFooterData = field(default_factory=PrintFooterData)


@dataclass(slots=True)
class AirfoilPrintMetrics:
    name: str
    contour_label: str
    contour_coordinates: tuple[np.ndarray, np.ndarray]
    chord: float
    minimum_x: float
    maximum_x: float
    minimum_y: float
    maximum_y: float
    max_thickness: float | None
    max_thickness_position: float | None
    max_thickness_marker_y: float | None
    max_camber: float | None
    max_camber_position: float | None
    max_camber_marker_y: float | None


@dataclass(slots=True)
class PageGeometry:
    page_rect: QtCore.QRectF
    frame_rect: QtCore.QRectF
    drawing_rect: QtCore.QRectF
    data_box_rect: QtCore.QRectF
    footer_rect: QtCore.QRectF


def clone_print_layout_options(options):
    return PrintLayoutOptions(
        frame_mode=options.frame_mode,
        paper_size=options.paper_size,
        show_data_box=bool(options.show_data_box),
        show_position_line=bool(options.show_position_line),
        footer=PrintFooterData(
            show_author=bool(options.footer.show_author),
            author=options.footer.author,
            show_date=bool(options.footer.show_date),
            date_of_issue=options.footer.date_of_issue,
        ),
    )


def default_print_layout_options(_airfoil=None, previous=None):
    options = (
        clone_print_layout_options(previous)
        if previous is not None
        else PrintLayoutOptions()
    )
    if previous is None:
        options.frame_mode = FRAME_MODE_NONE
        options.paper_size = PAPER_SIZE_A4
        options.show_data_box = True
        options.show_position_line = True
        options.footer.show_author = False
        options.footer.show_date = False

    if not options.footer.author.strip():
        options.footer.author = current_creator_name()
    if not options.footer.date_of_issue.strip():
        options.footer.date_of_issue = date.today().isoformat()
    return options


def _metric_value(values, stations, centerline, minimum_value):
    finite = np.isfinite(values)
    if not np.any(finite):
        return None, None, None

    masked = np.where(finite, values, -np.inf)
    index = int(np.argmax(masked))
    value = float(masked[index])
    if not np.isfinite(value) or value <= minimum_value:
        return None, None, None
    return (
        value,
        float(stations[index]),
        float(centerline[index]),
    )


def build_metrics_from_contour(coordinates, name='Airfoil', contour_label='contour'):
    x_coordinates = np.asarray(coordinates[0], dtype=float)
    y_coordinates = np.asarray(coordinates[1], dtype=float)
    if x_coordinates.size == 0 or y_coordinates.size == 0:
        raise ValueError('No contour coordinates available for printing.')

    contour_coordinates = (
        np.array(x_coordinates, copy=True, dtype=float),
        np.array(y_coordinates, copy=True, dtype=float),
    )
    minimum_x = float(np.min(x_coordinates))
    maximum_x = float(np.max(x_coordinates))
    minimum_y = float(np.min(y_coordinates))
    maximum_y = float(np.max(y_coordinates))
    chord = float(maximum_x - minimum_x)

    max_thickness = None
    max_thickness_position = None
    max_thickness_marker_y = None
    max_camber = None
    max_camber_position = None
    max_camber_marker_y = None

    try:
        upper_surface, lower_surface = split_airfoil_surfaces(contour_coordinates)
        x_start = max(
            float(np.min(upper_surface[:, 0])),
            float(np.min(lower_surface[:, 0])),
        )
        x_end = min(
            float(np.max(upper_surface[:, 0])),
            float(np.max(lower_surface[:, 0])),
        )
        if x_end > x_start:
            stations = np.linspace(x_start, x_end, 401)
            upper_y = np.interp(stations, upper_surface[:, 0], upper_surface[:, 1])
            lower_y = np.interp(stations, lower_surface[:, 0], lower_surface[:, 1])
            thickness = upper_y - lower_y
            camber = 0.5 * (upper_y + lower_y)

            max_thickness, max_thickness_position, max_thickness_marker_y = (
                _metric_value(
                    thickness,
                    stations,
                    camber,
                    minimum_value=1.0e-9,
                )
            )
            max_camber, max_camber_position, max_camber_marker_y = _metric_value(
                camber,
                stations,
                camber,
                minimum_value=1.0e-6,
            )
    except ValueError:
        pass

    return AirfoilPrintMetrics(
        name=name,
        contour_label=contour_label,
        contour_coordinates=contour_coordinates,
        chord=chord,
        minimum_x=minimum_x,
        maximum_x=maximum_x,
        minimum_y=minimum_y,
        maximum_y=maximum_y,
        max_thickness=max_thickness,
        max_thickness_position=max_thickness_position,
        max_thickness_marker_y=max_thickness_marker_y,
        max_camber=max_camber,
        max_camber_position=max_camber_position,
        max_camber_marker_y=max_camber_marker_y,
    )


def build_airfoil_print_metrics(airfoil, prefer_spline=True):
    contour = airfoil.current_contour(prefer_spline=prefer_spline)
    if contour is None and prefer_spline:
        contour = airfoil.current_contour(prefer_spline=False)
    if contour is None:
        raise ValueError('No airfoil contour available for printing.')

    contour_label = (
        'prepared contour'
        if getattr(airfoil, 'has_spline', False)
        else 'raw contour'
    )
    return build_metrics_from_contour(
        contour,
        name=getattr(airfoil, 'name', 'Airfoil'),
        contour_label=contour_label,
    )


def configure_printer_for_layout(printer, options):
    page_size_id = (
        QtGui.QPageSize.A3
        if options.paper_size == PAPER_SIZE_A3
        else QtGui.QPageSize.A4
    )
    page_size = QtGui.QPageSize(page_size_id)
    printer.setPageSize(page_size)
    printer.setPageOrientation(QtGui.QPageLayout.Landscape)
    layout = printer.pageLayout()
    layout.setPageSize(page_size)
    layout.setOrientation(QtGui.QPageLayout.Landscape)
    printer.setPageLayout(layout)


def _set_font_pixel_size(font, pixel_size):
    font.setPixelSize(max(1, int(round(pixel_size))))
    return font


def _scaled_font(font, scale):
    scaled = QtGui.QFont(font)
    pixel_size = font.pixelSize()
    if pixel_size > 0:
        scaled.setPixelSize(max(1, int(round(pixel_size * float(scale)))))
        return scaled

    point_size = font.pointSizeF()
    if point_size > 0.0:
        scaled.setPointSizeF(max(1.0, point_size * float(scale)))
        return scaled

    return _set_font_pixel_size(scaled, 12.0 * float(scale))


class PrintLayoutDialog(QtWidgets.QDialog):
    def __init__(self, airfoil, options=None, parent=None):
        super().__init__(parent)
        self._airfoil = airfoil
        self._options = default_print_layout_options(airfoil, previous=options)
        self._control_height = 34
        self._combo_width = 170
        self._field_width = 320

        self.setWindowTitle('Print Layout')
        self.setModal(True)
        self.resize(620, 390)
        self.setMinimumSize(580, 360)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)

        self._build_ui()
        self._load_options()
        self._update_footer_controls()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QtWidgets.QLabel('Print Layout')
        heading.setStyleSheet('font-size: 18px; font-weight: 700; color: #1d3148;')
        layout.addWidget(heading)

        note = QtWidgets.QLabel(
            'Use the current viewer contents inside an optional A4 or A3 sheet layout.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #506274;')
        layout.addWidget(note)

        layout_group = QtWidgets.QGroupBox('Layout')
        layout_form = QtWidgets.QFormLayout(layout_group)
        layout_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        layout_form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        layout_form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout_form.setHorizontalSpacing(16)
        layout_form.setVerticalSpacing(10)

        self.frame_mode_combo = QtWidgets.QComboBox()
        self.frame_mode_combo.addItem('No frame', FRAME_MODE_NONE)
        self.frame_mode_combo.addItem('Frame', FRAME_MODE_FRAME)
        self.frame_mode_combo.setMinimumHeight(self._control_height)
        self.frame_mode_combo.setMinimumWidth(self._combo_width)
        layout_form.addRow('Frame mode', self.frame_mode_combo)

        self.paper_size_combo = QtWidgets.QComboBox()
        self.paper_size_combo.addItem('A4', PAPER_SIZE_A4)
        self.paper_size_combo.addItem('A3', PAPER_SIZE_A3)
        self.paper_size_combo.setMinimumHeight(self._control_height)
        self.paper_size_combo.setMinimumWidth(self._combo_width)
        layout_form.addRow('Paper size', self.paper_size_combo)

        self.show_data_box_checkbox = QtWidgets.QCheckBox('Show airfoil data box')
        layout_form.addRow('', self.show_data_box_checkbox)

        self.show_position_line_checkbox = QtWidgets.QCheckBox(
            'Show max-position guide line'
        )
        layout_form.addRow('', self.show_position_line_checkbox)

        layout.addWidget(layout_group)

        footer_group = QtWidgets.QGroupBox('Lower Right Info')
        footer_form = QtWidgets.QFormLayout(footer_group)
        footer_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        footer_form.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        footer_form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        footer_form.setHorizontalSpacing(16)
        footer_form.setVerticalSpacing(10)

        self.show_author_checkbox = QtWidgets.QCheckBox('Show')
        self.show_author_checkbox.toggled.connect(self._update_footer_controls)
        self.author_edit = QtWidgets.QLineEdit()
        self.author_edit.setClearButtonEnabled(True)
        self.author_edit.setMinimumHeight(self._control_height)
        self.author_edit.setMinimumWidth(self._field_width)
        author_row = QtWidgets.QHBoxLayout()
        author_row.setContentsMargins(0, 0, 0, 0)
        author_row.setSpacing(10)
        author_row.addWidget(self.show_author_checkbox)
        author_row.addWidget(self.author_edit, 1)
        author_widget = QtWidgets.QWidget()
        author_widget.setLayout(author_row)
        footer_form.addRow('Author:', author_widget)

        self.show_date_checkbox = QtWidgets.QCheckBox('Show')
        self.show_date_checkbox.toggled.connect(self._update_footer_controls)
        self.date_edit = QtWidgets.QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('yyyy-MM-dd')
        self.date_edit.setMinimumHeight(self._control_height)
        self.date_edit.setMinimumWidth(self._combo_width)
        date_row = QtWidgets.QHBoxLayout()
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.setSpacing(10)
        date_row.addWidget(self.show_date_checkbox)
        date_row.addWidget(self.date_edit)
        date_row.addStretch(1)
        date_widget = QtWidgets.QWidget()
        date_widget.setLayout(date_row)
        footer_form.addRow('Date:', date_widget)

        layout.addWidget(footer_group)
        layout.addStretch(1)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_options(self):
        frame_index = self.frame_mode_combo.findData(
            normalize_frame_mode(self._options.frame_mode)
        )
        self.frame_mode_combo.setCurrentIndex(max(frame_index, 0))

        paper_index = self.paper_size_combo.findData(self._options.paper_size)
        self.paper_size_combo.setCurrentIndex(max(paper_index, 0))

        self.show_data_box_checkbox.setChecked(bool(self._options.show_data_box))
        self.show_position_line_checkbox.setChecked(
            bool(self._options.show_position_line)
        )

        self.show_author_checkbox.setChecked(bool(self._options.footer.show_author))
        self.author_edit.setText(self._options.footer.author)

        title_date = QtCore.QDate.fromString(
            self._options.footer.date_of_issue,
            'yyyy-MM-dd',
        )
        if not title_date.isValid():
            title_date = QtCore.QDate.currentDate()
        self.date_edit.setDate(title_date)
        self.show_date_checkbox.setChecked(bool(self._options.footer.show_date))

    def _update_footer_controls(self):
        self.author_edit.setEnabled(self.show_author_checkbox.isChecked())
        self.date_edit.setEnabled(self.show_date_checkbox.isChecked())

    def selected_options(self):
        return PrintLayoutOptions(
            frame_mode=normalize_frame_mode(self.frame_mode_combo.currentData()),
            paper_size=normalize_paper_size(self.paper_size_combo.currentData()),
            show_data_box=self.show_data_box_checkbox.isChecked(),
            show_position_line=self.show_position_line_checkbox.isChecked(),
            footer=PrintFooterData(
                show_author=self.show_author_checkbox.isChecked(),
                author=self.author_edit.text().strip() or current_creator_name(),
                show_date=self.show_date_checkbox.isChecked(),
                date_of_issue=self.date_edit.date().toString('yyyy-MM-dd'),
            ),
        )


class AirfoilPrintRenderer:
    def render(self, painter, printer, airfoil, view, options):
        metrics = build_airfoil_print_metrics(airfoil)
        resolution = printer.resolution()

        page_rect = QtCore.QRectF(
            printer.pageLayout().paintRectPixels(resolution)
        )
        if page_rect.isNull():
            page_rect = QtCore.QRectF(
                printer.pageLayout().fullRectPixels(resolution)
            )
        if page_rect.isNull():
            raise ValueError('Printer page layout is not available.')

        geometry = self._page_geometry(page_rect, resolution, options)

        painter.save()
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
            painter.fillRect(page_rect, QtCore.Qt.white)

            if options.frame_mode == FRAME_MODE_FRAME:
                self._draw_frame(painter, geometry.frame_rect, resolution)

            self._draw_view_plot(
                painter,
                geometry.drawing_rect,
                metrics,
                view,
                resolution,
                options,
            )

            if not geometry.data_box_rect.isNull():
                self._draw_data_box(
                    painter,
                    geometry.data_box_rect,
                    metrics,
                    resolution,
                )

            if not geometry.footer_rect.isNull():
                self._draw_footer(
                    painter,
                    geometry.footer_rect,
                    options,
                    resolution,
                )
        finally:
            painter.restore()

    def _page_geometry(self, page_rect, resolution, options):
        inset = mm_to_pixels(12.0, resolution)
        frame_rect = QtCore.QRectF()
        content_rect = QtCore.QRectF(page_rect).adjusted(inset, inset, -inset, -inset)

        if options.frame_mode == FRAME_MODE_FRAME:
            margin = mm_to_pixels(FRAME_MARGIN_MM, resolution)
            frame_rect = QtCore.QRectF(page_rect).adjusted(
                margin,
                margin,
                -margin,
                -margin,
            )
            content_rect = QtCore.QRectF(frame_rect)

        padding = mm_to_pixels(INNER_MARGIN_MM, resolution)
        drawing_rect = QtCore.QRectF(content_rect).adjusted(
            padding,
            padding,
            -padding,
            -padding,
        )

        data_box_rect = QtCore.QRectF()
        if options.show_data_box:
            data_box_width = min(
                mm_to_pixels(DATA_BOX_WIDTH_MM, resolution),
                drawing_rect.width() * 0.34,
            )
            data_box_height = min(
                max(mm_to_pixels(38.0, resolution), drawing_rect.height() * 0.28),
                drawing_rect.height() * 0.5,
            )
            if data_box_width > 0.0 and data_box_height > 0.0:
                data_box_rect = QtCore.QRectF(
                    drawing_rect.right() - data_box_width,
                    drawing_rect.top(),
                    data_box_width,
                    data_box_height,
                )
                lowered_top = (
                    data_box_rect.bottom() +
                    padding +
                    mm_to_pixels(2.0, resolution)
                )
                if lowered_top < drawing_rect.bottom():
                    drawing_rect.setTop(lowered_top)

        footer_rect = self._footer_rect(
            content_rect,
            drawing_rect,
            data_box_rect,
            resolution,
            options,
        )
        if not footer_rect.isNull():
            drawing_rect.setBottom(footer_rect.top() - padding)

        return PageGeometry(
            page_rect=QtCore.QRectF(page_rect),
            frame_rect=frame_rect,
            drawing_rect=drawing_rect,
            data_box_rect=data_box_rect,
            footer_rect=footer_rect,
        )

    def _footer_rect(self, content_rect, drawing_rect, data_box_rect, resolution, options):
        lines = self._footer_lines(options)
        if not lines:
            return QtCore.QRectF()

        footer_width = (
            data_box_rect.width()
            if not data_box_rect.isNull()
            else min(
                mm_to_pixels(FOOTER_WIDTH_MM, resolution),
                drawing_rect.width() * 0.34,
            )
        )
        line_height = mm_to_pixels(5.4, resolution)
        footer_height = (
            mm_to_pixels(2.0, resolution) +
            len(lines) * line_height
        )
        left = (
            data_box_rect.left()
            if not data_box_rect.isNull()
            else content_rect.right() - footer_width
        )
        right = left + footer_width
        bottom = content_rect.bottom() - mm_to_pixels(2.0, resolution)
        return QtCore.QRectF(
            left,
            bottom - footer_height,
            right - left,
            footer_height,
        )

    def _draw_frame(self, painter, rect, resolution):
        if rect.isNull():
            return

        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidthF(mm_to_pixels(FRAME_LINE_MM, resolution))
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(rect)

    def _draw_data_box(self, painter, rect, metrics, resolution):
        rows = [
            ('Airfoil', metrics.name),
            ('Contour', metrics.contour_label),
            ('Chord', f'{metrics.chord:.3f}'),
            ('Max thickness', self._percent_text(metrics.max_thickness)),
            ('x/c @ max t', self._station_text(metrics, metrics.max_thickness_position)),
            ('Max camber', self._percent_text(metrics.max_camber)),
            ('x/c @ max c', self._station_text(metrics, metrics.max_camber_position)),
            ('Units', 'normalized to chord'),
        ]

        border_pen = QtGui.QPen(QtCore.Qt.black)
        border_pen.setWidthF(mm_to_pixels(0.25, resolution))
        painter.setPen(border_pen)
        painter.setBrush(QtCore.Qt.white)
        painter.drawRect(rect)

        header_height = rect.height() / (len(rows) + 1)
        header_rect = QtCore.QRectF(rect.left(), rect.top(), rect.width(), header_height)
        painter.fillRect(header_rect, QtGui.QColor(238, 241, 245))
        painter.drawRect(header_rect)

        header_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(header_font, mm_to_pixels(3.8, resolution))
        header_font.setBold(True)
        painter.setFont(header_font)
        self._draw_text(
            painter,
            header_rect.adjusted(
                mm_to_pixels(1.2, resolution),
                0.0,
                -mm_to_pixels(1.2, resolution),
                0.0,
            ),
            'AIRFOIL DATA',
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
        )

        label_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(label_font, mm_to_pixels(2.8, resolution))
        value_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(value_font, mm_to_pixels(3.3, resolution))

        row_height = (rect.height() - header_height) / len(rows)
        split_x = rect.left() + rect.width() * 0.46
        for index, (label, value) in enumerate(rows):
            top = header_rect.bottom() + index * row_height
            row_rect = QtCore.QRectF(rect.left(), top, rect.width(), row_height)
            painter.drawRect(row_rect)
            painter.drawLine(
                QtCore.QPointF(split_x, row_rect.top()),
                QtCore.QPointF(split_x, row_rect.bottom()),
            )

            painter.setFont(label_font)
            self._draw_text(
                painter,
                QtCore.QRectF(
                    row_rect.left() + mm_to_pixels(1.2, resolution),
                    row_rect.top(),
                    split_x - row_rect.left() - mm_to_pixels(2.0, resolution),
                    row_rect.height(),
                ),
                label,
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            )

            painter.setFont(value_font)
            self._draw_text(
                painter,
                QtCore.QRectF(
                    split_x + mm_to_pixels(1.2, resolution),
                    row_rect.top(),
                    row_rect.right() - split_x - mm_to_pixels(2.0, resolution),
                    row_rect.height(),
                ),
                value,
                QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            )

    def _draw_footer(self, painter, rect, options, resolution):
        lines = self._footer_lines(options)
        if not lines:
            return

        label_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(label_font, mm_to_pixels(2.7, resolution))
        label_font.setBold(True)
        value_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(value_font, mm_to_pixels(3.0, resolution))

        line_height = rect.height() / len(lines)
        split_ratio = 0.28
        split_x = rect.left() + rect.width() * split_ratio

        for index, (label, value) in enumerate(lines):
            row_rect = QtCore.QRectF(
                rect.left(),
                rect.top() + index * line_height,
                rect.width(),
                line_height,
            )

            painter.setFont(label_font)
            self._draw_text(
                painter,
                QtCore.QRectF(
                    row_rect.left(),
                    row_rect.top(),
                    split_x - row_rect.left() - mm_to_pixels(2.0, resolution),
                    row_rect.height(),
                ),
                label,
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            )

            painter.setFont(value_font)
            self._draw_text(
                painter,
                QtCore.QRectF(
                    split_x,
                    row_rect.top(),
                    row_rect.right() - split_x,
                    row_rect.height(),
                ),
                value,
                QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
            )

    def _footer_lines(self, options):
        lines = []
        if options.footer.show_author and options.footer.author.strip():
            lines.append(('Author', options.footer.author.strip()))
        if options.footer.show_date and options.footer.date_of_issue.strip():
            lines.append(('Date', options.footer.date_of_issue.strip()))
        return lines

    def _draw_view_plot(self, painter, rect, metrics, view, resolution, options):
        if rect.isNull():
            return

        baseline_strip = (
            mm_to_pixels(18.0, resolution)
            if options.show_position_line
            else mm_to_pixels(6.0, resolution)
        )
        plot_rect = QtCore.QRectF(rect).adjusted(
            mm_to_pixels(2.0, resolution),
            mm_to_pixels(2.0, resolution),
            -mm_to_pixels(2.0, resolution),
            -baseline_strip,
        )
        if plot_rect.width() <= 0.0 or plot_rect.height() <= 0.0:
            return

        source_rect = self._visible_view_source_rect(view, metrics)
        target_size = QtCore.QSizeF(source_rect.size())
        target_size.scale(plot_rect.size(), QtCore.Qt.KeepAspectRatio)
        target_rect = QtCore.QRectF(
            0.0,
            0.0,
            target_size.width(),
            target_size.height(),
        )
        target_rect.moveCenter(
            QtCore.QPointF(
                plot_rect.left() + 0.5 * plot_rect.width(),
                plot_rect.top() + 0.5 * plot_rect.height(),
            )
        )

        view.render(
            painter,
            target=target_rect,
            source=source_rect,
            aspectRatioMode=QtCore.Qt.KeepAspectRatio,
        )

        if not options.show_position_line:
            return

        contour_bounds = self._map_scene_rect_to_target(
            metrics,
            view,
            source_rect,
            target_rect,
        )
        if contour_bounds.isNull():
            contour_bounds = QtCore.QRectF(target_rect)

        baseline_y = min(
            rect.bottom() - mm_to_pixels(4.0, resolution),
            contour_bounds.bottom() + mm_to_pixels(5.0, resolution),
        )
        chord_start_x = self._map_scene_x_to_target(
            view,
            source_rect,
            target_rect,
            metrics.minimum_x,
        )
        chord_end_x = self._map_scene_x_to_target(
            view,
            source_rect,
            target_rect,
            metrics.maximum_x,
        )

        baseline_pen = QtGui.QPen(QtGui.QColor(75, 75, 75))
        baseline_pen.setWidthF(mm_to_pixels(0.18, resolution))
        baseline_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(baseline_pen)
        painter.drawLine(
            QtCore.QPointF(chord_start_x, baseline_y),
            QtCore.QPointF(chord_end_x, baseline_y),
        )
        self._draw_baseline_tick(
            painter,
            resolution,
            chord_start_x,
            baseline_y,
        )
        self._draw_baseline_tick(
            painter,
            resolution,
            chord_end_x,
            baseline_y,
        )

        label_font = QtGui.QFont('Helvetica')
        _set_font_pixel_size(label_font, mm_to_pixels(2.9, resolution))
        painter.setFont(label_font)

        self._draw_position_marker(
            painter,
            resolution,
            metrics,
            view,
            source_rect,
            target_rect,
            baseline_y,
            metrics.max_thickness_position,
            metrics.max_thickness_marker_y,
            'T',
            dash_pattern=[4.0, 2.0],
            label_offset_mm=2.0,
        )
        self._draw_position_marker(
            painter,
            resolution,
            metrics,
            view,
            source_rect,
            target_rect,
            baseline_y,
            metrics.max_camber_position,
            metrics.max_camber_marker_y,
            'C',
            dash_pattern=[1.4, 2.2],
            label_offset_mm=7.0,
        )

    def _draw_position_marker(
        self,
        painter,
        resolution,
        metrics,
        view,
        source_rect,
        target_rect,
        baseline_y,
        x_position,
        marker_y,
        label,
        dash_pattern,
        label_offset_mm,
    ):
        if x_position is None or marker_y is None:
            return

        mapped_point = self._map_scene_point_to_target(
            view,
            source_rect,
            target_rect,
            QtCore.QPointF(float(x_position), float(marker_y)),
        )
        x_pixel = mapped_point.x()
        y_pixel = mapped_point.y()

        guide_pen = QtGui.QPen(QtGui.QColor(90, 90, 90))
        guide_pen.setWidthF(mm_to_pixels(0.16, resolution))
        guide_pen.setStyle(QtCore.Qt.CustomDashLine)
        guide_pen.setDashPattern(dash_pattern)
        guide_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(guide_pen)
        painter.drawLine(
            QtCore.QPointF(x_pixel, baseline_y),
            QtCore.QPointF(x_pixel, y_pixel),
        )

        self._draw_baseline_tick(
            painter,
            resolution,
            x_pixel,
            baseline_y,
        )
        marker_pen = QtGui.QPen(QtGui.QColor(55, 55, 55))
        marker_pen.setWidthF(mm_to_pixels(0.22, resolution))
        painter.setPen(marker_pen)
        painter.drawEllipse(
            QtCore.QPointF(x_pixel, y_pixel),
            mm_to_pixels(0.62, resolution),
            mm_to_pixels(0.62, resolution),
        )

        text_rect = QtCore.QRectF(
            x_pixel - mm_to_pixels(12.0, resolution),
            baseline_y + mm_to_pixels(label_offset_mm, resolution),
            mm_to_pixels(24.0, resolution),
            mm_to_pixels(4.5, resolution),
        )
        self._draw_position_label(
            painter,
            text_rect,
            label,
            self._station_text(metrics, x_position),
        )

    def _draw_text(self, painter, rect, text, flags):
        painter.drawText(rect, int(flags), text)

    def _draw_position_label(self, painter, rect, label, station_text):
        painter.save()

        base_font = QtGui.QFont(painter.font())
        base_metrics = QtGui.QFontMetricsF(base_font)
        sub_font = _scaled_font(base_font, 0.62)
        sub_metrics = QtGui.QFontMetricsF(sub_font)

        subscript = 'max'
        gap_width = base_metrics.horizontalAdvance(' ')
        label_width = base_metrics.horizontalAdvance(label)
        subscript_width = sub_metrics.horizontalAdvance(subscript)
        value_width = base_metrics.horizontalAdvance(station_text)
        total_width = label_width + subscript_width + gap_width + value_width

        origin_x = rect.left() + max(0.0, 0.5 * (rect.width() - total_width))
        baseline_y = rect.top() + base_metrics.ascent()
        subscript_baseline = baseline_y + base_metrics.height() * 0.22

        painter.setFont(base_font)
        painter.drawText(QtCore.QPointF(origin_x, baseline_y), label)

        painter.setFont(sub_font)
        painter.drawText(
            QtCore.QPointF(origin_x + label_width, subscript_baseline),
            subscript,
        )

        painter.setFont(base_font)
        painter.drawText(
            QtCore.QPointF(
                origin_x + label_width + subscript_width + gap_width,
                baseline_y,
            ),
            station_text,
        )
        painter.restore()

    def _percent_text(self, value):
        if value is None:
            return 'n/a'
        return f'{value * 100.0:.2f} %'

    def _station_text(self, metrics, x_position):
        if x_position is None or metrics.chord <= 0.0:
            return 'n/a'
        station = (float(x_position) - metrics.minimum_x) / metrics.chord
        return f'{station * 100.0:.2f} %'

    def _draw_baseline_tick(self, painter, resolution, x_value, baseline_y):
        tick_pen = QtGui.QPen(QtGui.QColor(70, 70, 70))
        tick_pen.setWidthF(mm_to_pixels(0.22, resolution))
        tick_pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(tick_pen)
        tick_half = mm_to_pixels(1.5, resolution)
        painter.drawLine(
            QtCore.QPointF(x_value, baseline_y - tick_half),
            QtCore.QPointF(x_value, baseline_y + tick_half),
        )

    def _map_scene_rect_to_target(self, metrics, view, source_rect, target_rect):
        x_values, y_values = metrics.contour_coordinates
        if len(x_values) == 0:
            return QtCore.QRectF()

        mapped_points = [
            self._map_scene_point_to_target(
                view,
                source_rect,
                target_rect,
                QtCore.QPointF(float(x_value), float(y_value)),
            )
            for x_value, y_value in zip(x_values, y_values)
        ]
        polygon = QtGui.QPolygonF(mapped_points)
        return polygon.boundingRect()

    def _map_scene_point_to_target(self, view, source_rect, target_rect, scene_point):
        viewport_point = view.mapFromScene(scene_point)
        if source_rect.width() == 0 or source_rect.height() == 0:
            return QtCore.QPointF(target_rect.left(), target_rect.top())

        scale_x = target_rect.width() / source_rect.width()
        scale_y = target_rect.height() / source_rect.height()
        return QtCore.QPointF(
            target_rect.left() + (viewport_point.x() - source_rect.left()) * scale_x,
            target_rect.top() + (viewport_point.y() - source_rect.top()) * scale_y,
        )

    def _map_scene_x_to_target(self, view, source_rect, target_rect, x_value):
        point = self._map_scene_point_to_target(
            view,
            source_rect,
            target_rect,
            QtCore.QPointF(float(x_value), 0.0),
        )
        return point.x()

    def _visible_view_source_rect(self, view, metrics):
        viewport_rect = view.viewport().rect()
        scene = view.scene()
        if scene is None:
            return QtCore.QRect(viewport_rect)

        visible_scene_rect = QtCore.QRectF()
        for item in scene.items():
            if not item.isVisible():
                continue
            item_rect = item.sceneBoundingRect()
            if item_rect.isNull() or not item_rect.isValid():
                continue
            if visible_scene_rect.isNull():
                visible_scene_rect = QtCore.QRectF(item_rect)
            else:
                visible_scene_rect = visible_scene_rect.united(item_rect)

        if visible_scene_rect.isNull():
            x_values, y_values = metrics.contour_coordinates
            if len(x_values):
                polygon = QtGui.QPolygonF(
                    [QtCore.QPointF(float(x), float(y)) for x, y in zip(x_values, y_values)]
                )
                visible_scene_rect = polygon.boundingRect()

        if visible_scene_rect.isNull():
            return QtCore.QRect(viewport_rect)

        mapped_rect = view.mapFromScene(visible_scene_rect).boundingRect()
        mapped_rect = mapped_rect.intersected(viewport_rect)
        if mapped_rect.isNull() or not mapped_rect.isValid():
            return QtCore.QRect(viewport_rect)

        horizontal_padding = max(8, int(round(viewport_rect.width() * 0.01)))
        vertical_padding = max(8, int(round(viewport_rect.height() * 0.02)))
        padded_rect = mapped_rect.adjusted(
            -horizontal_padding,
            -vertical_padding,
            horizontal_padding,
            vertical_padding,
        )
        padded_rect = padded_rect.intersected(viewport_rect)
        if padded_rect.isNull() or not padded_rect.isValid():
            return QtCore.QRect(viewport_rect)
        return QtCore.QRect(padded_rect)
