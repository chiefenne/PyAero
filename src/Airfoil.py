
import numpy as np

from PySide6 import QtGui, QtCore

import GraphicsItemsCollection as gic
import GraphicsItem
from ContourData import CamberData
from Shape import Polygon, Polyline

import logging
logger = logging.getLogger(__name__)


class Airfoil:
    """Class to read airfoil data from file (or use predefined airfoil)

    The Airfoil object carries several graphics items:
        e.g. raw data, chord, camber, etc.

    Attributes:
        brushcolor (QColor): fill color for airfoil
        chord (QGraphicsItem): Description
        item (QGraphicsItem): graphics item derived from QPolygonF object
        name (str): airfoil name (without path)
        pencolor (QColor): color for airoil outline
        penwidth (float): thickness of airfoil outline
        raw_coordinates (numpy array): list of contour points as tuples
    """

    def __init__(self, name, mainwindow=None):

        # MainWindow instance
        self.mw = mainwindow or QtCore.QCoreApplication.instance().mainwindow

        self.name = name
        self.chord = None
        self.has_TE = False
        self.contourPolygon = None
        self.contourSpline = None
        self.polygonMarkersGroup = None
        self.splineMarkersGroup = None
        self.camber_data = None
        self.camberline = None
        self.camber_circles = None
        self.camberCircleMarkers = []
        self.le_circle = None
        self.mesh = None
        self.mesh_blocks = None
        self.mesh_quality = None
        self.mesh_model = None
        self.domain_model = None
        self.curvature_data = None
        self.spline_data = None
        self.spline_fill_enabled = False
        self.raw_coordinates = None
        self.source_path = None
        self.polygonMarkers = []
        self.splineMarkers = []
        self.pencolor = QtGui.QColor('#6f7f90')
        self.penwidth = 2.4
        self.brushcolor = QtGui.QColor(219, 229, 238, 36)

    def _display_palette(self):
        return {
            'raw_pen': QtGui.QColor('#6f7f90'),
            'raw_fill': QtGui.QColor(219, 229, 238, 36),
            'raw_marker_pen': QtGui.QColor('#4e6277'),
            'raw_marker_fill': QtGui.QColor('#e07a94'),
            'spline_pen': QtGui.QColor('#3a7ea1'),
            'spline_fill': QtGui.QColor(58, 126, 161, 34),
            'spline_marker_pen': QtGui.QColor('#35556f'),
            'spline_marker_fill': QtGui.QColor('#93c83e'),
            'chord_pen': QtGui.QColor('#94a4b5'),
            'camber_pen': QtGui.QColor('#d07c4d'),
            'camber_circle_pen': QtGui.QColor('#d07c4d'),
            'camber_circle_fill': QtGui.QColor(208, 124, 77, 22),
        }

    def _apply_spline_fill_style(self):
        if self.contourSpline is None:
            return

        palette = self._display_palette()
        self.contourSpline.brush.setColor(palette['spline_fill'])
        if self.spline_fill_enabled:
            self.contourSpline.brush.setStyle(QtCore.Qt.SolidPattern)
        else:
            self.contourSpline.brush.setStyle(QtCore.Qt.NoBrush)
        self.contourSpline.update()
        if hasattr(self.mw, 'scene') and self.mw.scene is not None:
            self.mw.scene.update()
            for view in self.mw.scene.views():
                view.viewport().update()

    def setSplineFillEnabled(self, enabled):
        self.spline_fill_enabled = bool(enabled)
        self._apply_spline_fill_style()

    @classmethod
    def from_file(cls, filename, comment='#', mainwindow=None):
        fileinfo = QtCore.QFileInfo(filename)
        airfoil = cls(fileinfo.fileName(), mainwindow=mainwindow)
        airfoil.source_path = fileinfo.absoluteFilePath()
        if airfoil.readContour(filename, comment):
            return airfoil
        return None

    @property
    def has_spline(self):
        return self.spline_data is not None

    def current_contour(self, prefer_spline=True):
        if prefer_spline and self.spline_data is not None:
            return self.spline_data.coordinates
        return self.raw_coordinates

    def markerCollections(self):
        collections = []
        if self.raw_coordinates is not None and self.polygonMarkers:
            collections.append((self.raw_coordinates, self.polygonMarkers, 1.0))
        if self.has_spline and self.splineMarkers:
            collections.append((self.spline_data.coordinates, self.splineMarkers, 1.0))
        if self.camber_data is not None and self.camberCircleMarkers:
            collections.append((
                self.camber_data.display_coordinates(),
                self.camberCircleMarkers,
                0.6,
            ))
        return collections

    def to_shape(self, prefer_spline=True, closed=True):
        contour = self.current_contour(prefer_spline=prefer_spline)
        if contour is None:
            return None

        points = list(zip(*contour))
        label = f'{self.name} contour'
        if closed:
            return Polygon(points, name=label)
        return Polyline(points, closed=False, name=label)
 
    def readContour(self, filename, comment):

        try:
            with open(filename, mode='r') as f:
                lines = f.readlines()
        except IOError as error:
            # exc_info=True sends traceback to the logger
            logger.error('Failed to open file {} with error {}'. \
                         format(filename, error), exc_info=True)
            return False

        data = [line for line in lines if comment not in line]

        # find and drop duplicate points (except first and last)
        data_clean = list()
        for index, line in enumerate(data):
            if index == 0:
                data_clean.append(line)
                continue
            elif index == len(data)-1:
                data_clean.append(line)
                break   
            
            if line != data[index-1]:
                data_clean.append(line)
            else:
                logger.info('Dropped duplicate point {}'.format(line))

        # check for correct data
        # specifically important for drag and drop
        try:
            x = [float(l.split()[0]) for l in data_clean]
            y = [float(l.split()[1]) for l in data_clean]
        except (ValueError, IndexError) as error:
            logger.error('Unable to parse file file {}'. \
                         format(filename))
            logger.error('Following error occured: {}'.format(error))
            return False
        except:
            # exc_info=True sends traceback to the logger
            logger.error('Unable to parse file file {}. Unknown error caught'\
                         .format(filename), exc_info=True)
            return False

        # store airfoil coordinates as list of tuples
        self.raw_coordinates = np.array((x, y))

        # normalize airfoil to unit chord
        self.raw_coordinates[0] -= np.min(x)
        divisor = np.max(self.raw_coordinates[0])
        self.raw_coordinates[0] /= divisor
        self.raw_coordinates[1] /= divisor

        self.offset = [np.min(y), np.max(y)]

        return True

    def makeAirfoil(self):
        # make polygon graphicsitem from coordinates
        self.makeContourPolygon()
        self.makeChord()
        self.makePolygonMarkers()

        # Activate checkboxes for contour points, polygon, and chord in viewing options.
        checkboxes = [
            self.mw.mainArea.airfoil_points_checkbox,
            self.mw.mainArea.airfoil_raw_contour_checkbox,
            self.mw.mainArea.airfoil_chord_checkbox,
        ]
        for checkbox in checkboxes:
            checkbox.setChecked(True)
            checkbox.setEnabled(True)

    def addToScene(self, scene):
        """add all items to the scene"""
        scene.addItem(self.contourPolygon)
        scene.addItem(self.chord)
        self.polygonMarkersGroup = scene. \
            createItemGroup(self.polygonMarkers)
        self.contourPolygon.setZValue(20)
        self.chord.setZValue(30)
        self.polygonMarkersGroup.setZValue(120)

    def makeContourPolygon(self):
        """Add airfoil points as GraphicsItem to the scene"""
        palette = self._display_palette()

        # instantiate a graphics item
        contour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*self.raw_coordinates)]
        contour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        contour.pen.setColor(palette['raw_pen'])
        contour.pen.setWidthF(self.penwidth)
        # no pen thickness change when zoomed
        contour.pen.setCosmetic(True)
        contour.brush.setColor(palette['raw_fill'])
        contour.brush.setStyle(QtCore.Qt.NoBrush)

        self.contourPolygon = GraphicsItem.GraphicsItem(contour)
        self.contourPolygon.setAcceptHoverEvents(False)

    def makePolygonMarkers(self):
        """Create marker for polygon contour"""
        palette = self._display_palette()

        self.polygonMarkers = list()

        for x, y in zip(*self.raw_coordinates):

            marker = gic.GraphicsCollection()
            marker.pen.setColor(palette['raw_marker_pen'])
            marker.pen.setWidthF(1.35)
            # no pen thickness change when zoomed
            marker.pen.setCosmetic(True)
            marker.brush.setColor(palette['raw_marker_fill'])
            marker.brush.setStyle(QtCore.Qt.SolidPattern)
            # circle size doesn't do anything here
            # this is indirectly deactivated because we don't want to change
            # marker size during zoom
            # the sizing is thus handled in graphicsview adjustMarkerSize
            # there a fixed markersize in pixels is taken from settings which
            # can be configured by the user

            marker.Circle(x, y, 0.004)

            markerItem = GraphicsItem.GraphicsItem(marker)

            self.polygonMarkers.append(markerItem)

    def makeChord(self):
        palette = self._display_palette()
        line = gic.GraphicsCollection()
        color = palette['chord_pen']
        line.pen.setColor(color)
        line.pen.setWidthF(2.1)
        # no pen thickness change when zoomed
        line.pen.setCosmetic(True)
        line.pen.setCapStyle(QtCore.Qt.RoundCap)
        # setting CustomDashLine not needed as it will be set
        # implicitely by Qt when CustomDashLine is applied
        # put it just for completeness
        line.pen.setStyle(QtCore.Qt.CustomDashLine)
        stroke = 14
        dot = 3
        space = 7
        line.pen.setDashPattern([stroke, space, dot, space])
        index_min = np.argmin(self.raw_coordinates[0])
        index_max = np.argmax(self.raw_coordinates[0])
        x1 = self.raw_coordinates[0][index_min]
        y1 = self.raw_coordinates[1][index_min]
        x2 = self.raw_coordinates[0][index_max]
        y2 = self.raw_coordinates[1][index_max]
        line.Line(x1, y1, x2, y2)

        self.chord = GraphicsItem.GraphicsItem(line)
        self.chord.setZValue(30)
        self.chord.setAcceptHoverEvents(False)

    def makeContourSpline(self):
        """Add splined and refined airfoil points as GraphicsItem to
        the scene
        """
        palette = self._display_palette()
        self.pencolor = palette['spline_pen']
        self.penwidth = 2.7

        # instantiate a graphics item
        splinecontour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*self.spline_data.coordinates)]
        splinecontour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        splinecontour.pen.setColor(self.pencolor)
        splinecontour.pen.setWidthF(self.penwidth)
        # no pen thickness change when zoomed
        splinecontour.pen.setCosmetic(True)
        splinecontour.brush.setColor(palette['spline_fill'])

        # remove items from iterated uses of spline/refine and trailing edge
        if hasattr(self, 'contourSpline') and \
                self.contourSpline in self.mw.scene.items():
            self.mw.scene.removeItem(self.contourSpline)
        self.contourSpline = GraphicsItem.GraphicsItem(splinecontour)
        self.contourSpline.setAcceptHoverEvents(False)
        self.contourSpline.setZValue(40)
        self._apply_spline_fill_style()
        self.mw.scene.addItem(self.contourSpline)

        # remove items from iterated uses of spline/refine and trailing edge
        if hasattr(self, 'splineMarkersGroup') and \
                self.splineMarkersGroup in self.mw.scene.items():
            self.mw.scene.removeItem(self.splineMarkersGroup)
        self.makeSplineMarkers()
        self.splineMarkersGroup = self.mw.scene. \
            createItemGroup(self.splineMarkers)
        self.splineMarkersGroup.setZValue(140)

        self.polygonMarkersGroup.setZValue(120)

        # switch off raw contour and toogle corresponding checkbox
        if self.polygonMarkersGroup.isVisible():
            self.mw.mainArea.airfoil_points_checkbox.click()
        if self.contourPolygon.isVisible():
            self.mw.mainArea.airfoil_raw_contour_checkbox.click()

        # Activate checkboxes for contour points and chord in viewing options.
        checkboxes = [
            self.mw.mainArea.airfoil_spline_points_checkbox,
            self.mw.mainArea.airfoil_spline_contour_checkbox,
        ]
        for checkbox in checkboxes:
            checkbox.setChecked(True)
            checkbox.setEnabled(True)

        self.mw.view.adjustMarkerSize()

    def makeSplineMarkers(self):
        """Create marker for polygon contour"""
        palette = self._display_palette()

        self.splineMarkers = list()

        for x, y in zip(*self.spline_data.coordinates):

            # put airfoil contour points as graphicsitem
            splinemarker = gic.GraphicsCollection()
            splinemarker.pen.setColor(palette['spline_marker_pen'])
            splinemarker.pen.setWidthF(1.35)
            # no pen thickness change when zoomed
            splinemarker.pen.setCosmetic(True)
            splinemarker.brush.setColor(palette['spline_marker_fill'])
            splinemarker.brush.setStyle(QtCore.Qt.SolidPattern)

            splinemarker.Circle(x, y, 0.004)

            splineMarkerItem = GraphicsItem.GraphicsItem(splinemarker)

            self.splineMarkers.append(splineMarkerItem)

    def _removeSceneItem(self, item):
        if item is not None and item.scene() is not None:
            item.scene().removeItem(item)

    def drawCamber(self, camber):
        if isinstance(camber, CamberData):
            self.camber_data = camber
            coordinates = camber.polyline_coordinates(start_at_le_tangency=True)
        else:
            coordinates = camber

        palette = self._display_palette()

        self.pencolor = palette['camber_pen']
        self.penwidth = 2.3

        # instantiate a graphics item
        camberline = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*coordinates)]
        camberline.Polyline(QtGui.QPolygonF(points))
        # set its properties
        camberline.pen.setColor(self.pencolor)
        camberline.pen.setWidthF(self.penwidth)
        camberline.pen.setStyle(QtCore.Qt.CustomDashLine)
        camberline.pen.setCapStyle(QtCore.Qt.RoundCap)
        camberline.pen.setDashPattern([1.2, 6.8])
        # no pen thickness change when zoomed
        camberline.pen.setCosmetic(True)
        camberline.brush.setColor(self.brushcolor)
        # add the spline polygon without filling
        camberline.brush.setStyle(QtCore.Qt.NoBrush)

        # remove items from iterated uses of spline/refine and trailing edge
        self._removeSceneItem(self.camberline)
        self.camberline = GraphicsItem.GraphicsItem(camberline)
        self.camberline.setAcceptHoverEvents(False)
        self.camberline.setZValue(35)
        self.mw.scene.addItem(self.camberline)
        self.mw.mainArea.airfoil_camber_line_checkbox.setChecked(True)
        self.mw.mainArea.airfoil_camber_line_checkbox.setEnabled(True)

    def drawCamberCircles(self, camber_data):
        if not isinstance(camber_data, CamberData):
            return

        palette = self._display_palette()
        self.camber_data = camber_data

        self._removeSceneItem(self.camber_circles)
        self.camberCircleMarkers = []

        circles = []
        center_x, center_y = camber_data.display_coordinates()
        radii = camber_data.display_radius()

        for x, y, radius in zip(center_x, center_y, radii):
            if radius <= 0.0:
                continue

            circle = gic.GraphicsCollection()
            circle.pen.setColor(palette['camber_circle_pen'])
            circle.pen.setWidthF(1.1)
            circle.pen.setCosmetic(True)
            circle.brush.setColor(palette['camber_circle_fill'])
            circle.brush.setStyle(QtCore.Qt.NoBrush)
            circle.Circle(float(x), float(y), float(radius))

            circle_item = GraphicsItem.GraphicsItem(circle)
            circle_item.setAcceptHoverEvents(False)
            circles.append(circle_item)

            center_marker = gic.GraphicsCollection()
            center_marker.pen.setColor(palette['camber_circle_pen'])
            center_marker.pen.setWidthF(0.8)
            center_marker.pen.setCosmetic(True)
            center_marker.brush.setColor(palette['camber_circle_pen'])
            center_marker.brush.setStyle(QtCore.Qt.SolidPattern)
            center_marker.Circle(float(x), float(y), 0.0016)

            center_marker_item = GraphicsItem.GraphicsItem(center_marker)
            center_marker_item.setAcceptHoverEvents(False)
            circles.append(center_marker_item)
            self.camberCircleMarkers.append(center_marker_item)

        if not circles:
            self.camber_circles = None
            return

        self.camber_circles = self.mw.scene.createItemGroup(circles)
        self.camber_circles.setZValue(34)
        self.mw.mainArea.airfoil_camber_circles_checkbox.setChecked(True)
        self.mw.mainArea.airfoil_camber_circles_checkbox.setEnabled(True)
        if hasattr(self.mw, 'view') and self.mw.view is not None:
            self.mw.view.adjustMarkerSize()

    def setPenColor(self, r, g, b, a):
        self.pencolor = QtGui.QColor(r, g, b, a)

    def setBrushColor(self, r, g, b, a):
        self.brushcolor = QtGui.QColor(r, g, b, a)

