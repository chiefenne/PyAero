
import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

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
        contourItemGroup (QGraphicsItemGroup): Container for all items
            which belong to the airfoil contour
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
        self.contourPolygon = None
        self.contourSpline = None
        self.raw_coordinates = None
        self.pencolor = QtGui.QColor(10, 255, 20, 255)
        self.penwidth = 3.0
        self.brushcolor = QtGui.QColor()
        self.brushcolor.setNamedColor('#7c8696')

        #
        # QGraphicsItemGroup do not seem to completely act like
        # individual items. Therefore no groups are used for the time being.
        # Status from 24.8. 2018
        #
        # self.contourItemGroup = QtWidgets.QGraphicsItemGroup()        
        # self.markersItemGroup = QtWidgets.QGraphicsItemGroup()       
        # self.polygonMarkersItemGroup = QtWidgets.QGraphicsItemGroup()
        # self.splineMarkersItemGroup = QtWidgets.QGraphicsItemGroup()
        # set flags for QGraphicsItemGroup
        # these flags seem to be default for QGraphicsItem but not for group
        # self.contourItemGroup.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        # self.contourItemGroup.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        # self.contourItemGroup.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable, True)
        #
        # hover events do not seem to work for the group, even if set to accepted
        # according to the docs (link split on 3 lines):
        # http://doc.qt.io/qtforpython/PySide2/QtWidgets/QGraphicsItem.html?
        # highlight=setaccepthoverevents#PySide2.QtWidgets.PySide2.QtWidgets.
        # QGraphicsItem.setAcceptHoverEvents
        # it seems that the group is a parent item to the items which are grouped.
        # Therefore it does not receive hover events
        # self.contourItemGroup.setAcceptHoverEvents(True)

    def readContour(self, filename, comment):

        try:
            with open(filename, mode='r') as f:
                lines = f.readlines()
        except IOError as error:
            logger.log.error('Unable to open file %s. Error was: %s' %
                             (filename, error))
            return False

        data = [line for line in lines if comment not in line]

        # check for correct data
        # specifically important for drag and drop
        try:
            x = [float(l.split()[0]) for l in data]
            y = [float(l.split()[1]) for l in data]
        except (ValueError, IndexError) as error:
            logger.log.error('Unable to parse file %s. Error was: %s' %
                             (filename, error))
            logger.log.info('Maybe not a valid airfoil file was used.')
            return False
        except:
            logger.log.error('Unable to parse file %s. Unknown error caught.' %
                             (filename))
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
        
        # add all items to the scene
        self.mainwindow.scene.addItem(self.contourPolygon)
        self.mainwindow.scene.addItem(self.chord)
        ### for marker in self.polygonMarkers:
        ###    self.mainwindow.scene.addItem(marker)
        self.mainwindow.scene.createItemGroup(self.polygonMarkers)

    def makeContourPolygon(self, coordinates):
        """Add airfoil points as GraphicsItem to the scene"""

        # instantiate a graphics item
        contour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*coordinates)]
        contour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        contour.pen.setColor(self.pencolor)
        contour.pen.setWidth(self.penwidth)
        contour.pen.setCosmetic(True)  # no pen thickness change when zoomed
        contour.brush.setColor(self.brushcolor)

        self.contourPolygon = GraphicsItem.GraphicsItem(contour)

    def makePolygonMarkers(self):
        """Create marker for polygon contour"""
        
        self.polygonMarkers = list()

        for x, y in zip(*self.raw_coordinates):

            marker = gic.GraphicsCollection()
            marker.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            marker.pen.setWidth(0.01)
            marker.pen.setCosmetic(True)  # no pen thickness change when zoomed
            marker.brush.setColor(QtGui.QColor(217, 63, 122, 255))

            marker.Circle(x, y, 0.02)

            markerItem = GraphicsItem.GraphicsItem(marker)
            markerItem.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
            markerItem.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
            markerItem.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable, False)

            self.polygonMarkers.append(markerItem)

    def makeChord(self):
        line = gic.GraphicsCollection()
        color = QtGui.QColor(70, 70, 70, 255)
        line.pen.setColor(color)
        line.pen.setWidth(0.4)
        line.pen.setCosmetic(True)  # no pen thickness change when zoomed
        line.pen.setJoinStyle(QtCore.Qt.RoundJoin)
        line.pen.setStyle(QtCore.Qt.CustomDashLine)
        # pattern is 1px dash, 4px space, 7px dash, 4px
        line.pen.setDashPattern([1, 4, 10, 4])
        line.Line(np.min(self.raw_coordinates[0]), 0.0,
                  np.max(self.raw_coordinates[0]), 0.0)

        self.chord = GraphicsItem.GraphicsItem(line)
        self.chord.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        self.chord.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        self.chord.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable, False)


    def makeContourSpline(self, spline_coordinates):
        """Add splined and refined airfoil points as GraphicsItem to
        the scene
        """
        self.pencolor = QtGui.QColor(80, 80, 220, 255)
        self.penwidth = 3.5

        # instantiate a graphics item
        splinecontour = gic.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*spline_coordinates)]
        splinecontour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        splinecontour.pen.setColor(self.pencolor)
        splinecontour.pen.setWidth(self.penwidth)
        splinecontour.pen.setCosmetic(True)  # no pen thickness change when zoomed
        splinecontour.brush.setColor(self.brushcolor)
        # add the pline polygon without filling
        splinecontour.brush.setStyle(QtCore.Qt.NoBrush)

        # remove spline from the contourgroup if any
        if self.contourSpline:
            self.scene.removeItem(self.contourSpline)
            self.scene.removeItem(self.splineMarkers)

        self.contourSpline = GraphicsItem.GraphicsItem(splinecontour)

    def makeSplineMarkers(self):
        """Create marker for polygon contour"""

        for x, y in zip(*self.spline_data[0]):

            # put airfoil contour points as graphicsitem
            splinemarker = gic.GraphicsCollection()
            splinemarker.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            splinemarker.brush.setColor(QtGui.QColor(180, 180, 50, 230))
            splinemarker.pen.setCosmetic(True)  # no pen thickness change when zoomed

            splinemarker.Circle(x, y, 0.03)

            splineMarkerItem = GraphicsItem.GraphicsItem(splinemarker)
            self.splineMarkersGroup.addToGroup(splineMarkerItem)

    def camber(self):
        pass

    def setPenColor(self, r, g, b, a):
        self.pencolor = QtGui.QColor(r, g, b, a)

    def setBrushColor(self, r, g, b, a):
        self.brushcolor = QtGui.QColor(r, g, b, a)
