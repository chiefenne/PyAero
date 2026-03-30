
import numpy as np

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QPushButton
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtGui import QPainter

from ContourData import CurvatureData
from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


class ContourAnalysis(QFrame):
    """Summary

    Attributes:
        canvas (TYPE): Description
        figure (TYPE): Description
        raw_coordinates (list): contour points as tuples
        toolbar (TYPE): Description
    """
    def __init__(self, canvas=False):
        super().__init__()

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

        # run the gui part only when canvas set to true
        if canvas:
            self.initUI()

    def initUI(self):
        self.setFrameShape(QFrame.NoFrame)

        self.lineSeries = QLineSeries()
        # legend name
        # self.lineSeries.setName("trend")
        self.lineSeries.append(QtCore.QPoint(0, 0))

        pen = QtGui.QPen(QtCore.Qt.red, 6, QtCore.Qt.SolidLine)
        self.lineSeries.setPen(pen)

        self.chart = QChart()
        self.chart.setAnimationOptions(QChart.AllAnimations)
        self.chart.setTitle("Airfoil contour analysis")
        self.chart.addSeries(self.lineSeries)

        self.chart.legend().setVisible(False)
        self.chart.legend().setAlignment(QtCore.Qt.AlignBottom)

        self.axisX = QValueAxis()
        self.axisY = QValueAxis()
        self.chart.setAxisX(self.axisX, self.lineSeries)
        self.chart.setAxisY(self.axisY, self.lineSeries)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setRubberBand(QChartView.RectangleRubberBand)
        self.chart_view.setDragMode(QChartView.ScrollHandDrag)
        self.chart_view.setFrameShape(QFrame.NoFrame)
        self.chart_view.setStyleSheet('background: transparent; border: none;')

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.chart_view)
        self.setLayout(vlayout)

        # Add buttons for zoom and home
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.home_button = QPushButton("Home")

        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.home_button.clicked.connect(self.home)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.zoom_in_button)
        button_layout.addWidget(self.zoom_out_button)
        button_layout.addWidget(self.home_button)

        vlayout.addLayout(button_layout)
        self.setLayout(vlayout)

    def zoom_in(self):
        self.chart_view.chart().zoomIn()

    def zoom_out(self):
        self.chart_view.chart().zoomOut()

    def home(self):
        self.chart_view.chart().zoomReset()

    @staticmethod
    def getCurvature(spline_data):
        """Curvature and radius of curvature of a parametric curve

        der1 is dx/dt and dy/dt at each point
        der2 is d2x/dt2 and d2y/dt2 at each point

        Returns:
            float: Tuple of numpy arrays carrying gradient of the curve,
                   the curvature, radiusses of curvature circles and
                   curvature circle centers for each point of the curve
        """

        xd, yd = spline_data.first_derivative
        x2d, y2d = spline_data.second_derivative
        speed_squared = xd**2 + yd**2
        curvature_numerator = xd * y2d - yd * x2d
        speed = np.sqrt(speed_squared)
        curvature_denominator = speed_squared**(3.0 / 2.0)

        with np.errstate(divide='ignore', invalid='ignore'):
            gradient = np.divide(
                yd,
                xd,
                out=np.full_like(yd, np.inf, dtype=float),
                where=xd != 0.0,
            )
            radius = np.divide(
                curvature_denominator,
                np.abs(curvature_numerator),
                out=np.full_like(curvature_numerator, np.inf, dtype=float),
                where=curvature_numerator != 0.0,
            )
            curvature = np.divide(
                curvature_numerator,
                curvature_denominator,
                out=np.zeros_like(curvature_numerator, dtype=float),
                where=curvature_denominator != 0.0,
            )
            normal_x = np.divide(
                yd,
                speed,
                out=np.zeros_like(yd, dtype=float),
                where=speed != 0.0,
            )
            normal_y = np.divide(
                xd,
                speed,
                out=np.zeros_like(xd, dtype=float),
                where=speed != 0.0,
            )

        center_x = spline_data.coordinates[0] - radius * normal_x
        center_y = spline_data.coordinates[1] + radius * normal_y

        return CurvatureData(
            gradient=gradient,
            curvature=curvature,
            radius=radius,
            center_x=center_x,
            center_y=center_y,
        )

    @staticmethod
    def getLeRadius(spline_data, curvature_data):
        """Identify leading edge radius, i.e. smallest radius of
        parametric curve

        Returns:
            FLOAT: leading edge radius, its center and related contour
            point and id
        """

        radius = curvature_data.radius
        le_id = int(np.argmin(radius))
        rc = radius[le_id]
        # leading edge curvature circle center
        xc = curvature_data.center_x[le_id]
        yc = curvature_data.center_y[le_id]
        xr, yr = spline_data.coordinates
        xle = xr[le_id]
        yle = yr[le_id]

        return rc, xc, yc, xle, yle, le_id

    def analyze(self):
        """get specific curve properties"""

        if not self.mw.airfoil.spline_data:
            self.mw.slots.messageBox('Please do splining first')
            return

        spline_data = self.mw.airfoil.spline_data
        curvature_data = self.getCurvature(spline_data)

        # add new attributes to airfoil instance
        self.mw.airfoil.curvature_data = curvature_data

        self.drawContour()

    def drawContour(self, quantity='gradient'):
        """quantity is one of 'gradient', 'curvature', 'radius' """

        spline_data = self.mw.airfoil.spline_data
        curvature_data = self.mw.airfoil.curvature_data

        series = curvature_data.series(quantity)
        points = [
            QtCore.QPointF(x, y)
            for x, y in zip(spline_data.coordinates[0], series)
        ]

        self.lineSeries = QLineSeries()
        self.lineSeries.append(points)
        self.chart.removeAllSeries()
        self.chart.addSeries(self.lineSeries)
        self.chart.setAxisX(self.axisX, self.lineSeries)
        self.chart.setAxisY(self.axisY, self.lineSeries)
