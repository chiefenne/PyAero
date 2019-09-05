
import numpy as np

from PySide2 import QtGui, QtCore

import GraphicsItemsCollection as gic
import GraphicsItem

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

    def __init__(self, name):

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

        self.name = name
        self.chord = None
        self.has_TE = False
        self.contourPolygon = None
        # self.contourSpline = None
        self.spline_data = None
        self.raw_coordinates = None
        self.pencolor = QtGui.QColor(80, 150, 220, 255)
        self.penwidth = 2.0
        self.brushcolor = QtGui.QColor()
        self.brushcolor.setNamedColor('#7c8696')

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

        # check for correct data
        # specifically important for drag and drop
        try:
            x = [float(l.split()[0]) for l in data]
            y = [float(l.split()[1]) for l in data]
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
        self.chord = np.max(x) - np.min(x)

        return True

    def makeAirfoil(self):
        # make polygon graphicsitem from coordinates
        self.makeContourPolygon(self.raw_coordinates)
        self.makeChord()
        self.makePolygonMarkers()

        # activate ckeck boxes for contour points and chord in viewing options
        self.mainwindow.centralwidget.cb2.setChecked(True)
        self.mainwindow.centralwidget.cb2.setEnabled(True)
        self.mainwindow.centralwidget.cb5.setChecked(True)
        self.mainwindow.centralwidget.cb5.setEnabled(True)

    @staticmethod
    def addToScene(airfoil, scene):
        """add all items to the scene"""
        scene.addItem(airfoil.contourPolygon)
        scene.addItem(airfoil.chord)
        airfoil.polygonMarkersGroup = scene. \
            createItemGroup(airfoil.polygonMarkers)

    def makeContourPolygon(self, coordinates):
        """Add airfoil points as GraphicsItem to the scene"""

        # instantiate a graphics item
        contour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*coordinates)]
        contour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        contour.pen.setColor(self.pencolor)
        contour.pen.setWidthF(self.penwidth)
        # no pen thickness change when zoomed
        contour.pen.setCosmetic(True)
        contour.brush.setColor(self.brushcolor)

        self.contourPolygon = GraphicsItem.GraphicsItem(contour)

    def makePolygonMarkers(self):
        """Create marker for polygon contour"""

        self.polygonMarkers = list()

        for x, y in zip(*self.raw_coordinates):

            marker = gic.GraphicsCollection()
            marker.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            marker.pen.setWidthF(1.6)
            # no pen thickness change when zoomed
            marker.pen.setCosmetic(True)
            marker.brush.setColor(QtGui.QColor(217, 63, 122, 150))
            # circle size doesn't do anything here
            # this is indirectly deactivated because we don't want to change
            # marker size during zoom
            # the sizing is thus handled in graphicsview adjustMarkerSize
            # there a fixed markersize in pixels is taken from settings which
            # can be configured by the user

            # FIXME
            # FIXME this size still affects the items size for the scene.itemsBoundingRect()
            # FIXME this is affecting slots.onViewAll()
            # FIXME there it is not directly visible as adjustMarkerSize is called
            # FIXME the fit acts to the size that shows up when adjustMarkerSize
            # FIXME would not be called
            # FIXME
            marker.Circle(x, y, 0.004)

            markerItem = GraphicsItem.GraphicsItem(marker)

            self.polygonMarkers.append(markerItem)

    def makeChord(self):
        line = gic.GraphicsCollection()
        color = QtGui.QColor(70, 70, 70, 255)
        line.pen.setColor(color)
        line.pen.setWidthF(0.8)
        # no pen thickness change when zoomed
        line.pen.setCosmetic(True)
        # setting CustomDashLine not needed as it will be set
        # implicitely by Qt when CustomDashLine is applied
        # put it just for completness
        line.pen.setStyle(QtCore.Qt.CustomDashLine)
        stroke = 10
        dot = 2
        space = 5
        line.pen.setDashPattern([stroke, space, dot, space])
        index_min = np.argmin(self.raw_coordinates[0])
        index_max = np.argmax(self.raw_coordinates[0])
        line.Line(self.raw_coordinates[0][index_min],
                  self.raw_coordinates[1][index_min],
                  self.raw_coordinates[0][index_max],
                  self.raw_coordinates[1][index_max])

        self.chord = GraphicsItem.GraphicsItem(line)
        self.chord.setAcceptHoverEvents(False)

    def makeContourSpline(self):
        """Add splined and refined airfoil points as GraphicsItem to
        the scene
        """
        self.pencolor = QtGui.QColor(80, 80, 220, 255)
        self.penwidth = 3.5

        # instantiate a graphics item
        splinecontour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*self.spline_data[0])]
        splinecontour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        splinecontour.pen.setColor(self.pencolor)
        splinecontour.pen.setWidthF(self.penwidth)
        # no pen thickness change when zoomed
        splinecontour.pen.setCosmetic(True)
        splinecontour.brush.setColor(self.brushcolor)
        # add the pline polygon without filling
        splinecontour.brush.setStyle(QtCore.Qt.NoBrush)

        # remove items from iterated uses of spline/refine and trailing edge
        if hasattr(self, 'contourSpline'):
            self.mainwindow.scene.removeItem(self.contourSpline)
        self.contourSpline = GraphicsItem.GraphicsItem(splinecontour)
        self.mainwindow.scene.addItem(self.contourSpline)

        # remove items from iterated uses of spline/refine and trailing edge
        if hasattr(self, 'splineMarkersGroup'):
            self.mainwindow.scene.removeItem(self.splineMarkersGroup)
        self.makeSplineMarkers()
        self.splineMarkersGroup = self.mainwindow.scene. \
            createItemGroup(self.splineMarkers)

        self.mainwindow.airfoil.contourSpline.brush. \
            setStyle(QtCore.Qt.SolidPattern)
        color = QtGui.QColor()
        color.setNamedColor('#7c8696')
        self.contourSpline.brush.setColor(color)
        self.polygonMarkersGroup.setZValue(100)
        self.chord.setZValue(99)

        # switch off raw contour and toogle corresponding checkbox
        if self.polygonMarkersGroup.isVisible():
            self.mainwindow.centralwidget.cb2.click()

        # activate ckeck boxes for contour points and chord in viewing options
        self.mainwindow.centralwidget.cb3.setChecked(True)
        self.mainwindow.centralwidget.cb3.setEnabled(True)
        self.mainwindow.centralwidget.cb4.setChecked(True)
        self.mainwindow.centralwidget.cb4.setEnabled(True)

        self.contourPolygon.brush.setStyle(QtCore.Qt.NoBrush)
        self.contourPolygon.pen.setStyle(QtCore.Qt.NoPen)
        self.mainwindow.view.adjustMarkerSize()

    def makeSplineMarkers(self):
        """Create marker for polygon contour"""

        self.splineMarkers = list()

        for x, y in zip(*self.spline_data[0]):

            # put airfoil contour points as graphicsitem
            splinemarker = gic.GraphicsCollection()
            splinemarker.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            splinemarker.brush.setColor(QtGui.QColor(180, 180, 50, 230))
            splinemarker.pen.setWidthF(1.6)
            # no pen thickness change when zoomed
            splinemarker.pen.setCosmetic(True)

            splinemarker.Circle(x, y, 0.004)

            splineMarkerItem = GraphicsItem.GraphicsItem(splinemarker)

            self.splineMarkers.append(splineMarkerItem)

    def camber(self):
        pass

    def setPenColor(self, r, g, b, a):
        self.pencolor = QtGui.QColor(r, g, b, a)

    def setBrushColor(self, r, g, b, a):
        self.brushcolor = QtGui.QColor(r, g, b, a)

