
import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

import GraphicsItemsCollection as gc
import GraphicsItem
import Logger as logger


class Airfoil:
    """Class to read airfoil data from file (or use predefined airfoil)

    The Airfoil object carries several graphics items:
        e.g. raw data, chord, camber, etc.

    Attributes:
        brushcolor (QColor): fill color for airfoil
        chord (QGraphicsItem): Description
        contourGroup (QGraphicsItemGroup): Container for all items
            which belong to the airfoil contour
        item (QGraphicsItem): graphics item derived from QPolygonF object
        markers (QGraphicsItem): color for airoil outline points
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
        self.pencolor = QtGui.QColor(10, 10, 20, 255)
        self.penwidth = 2.5
        self.brushcolor = QtGui.QColor()
        self.brushcolor.setNamedColor('#7c8696')

        # create groups of items that carry contour, markers, etc.
        self.makeItemGroups()

    def makeItemGroups(self):
        """Containers that treat a group of items as a single item"""

        self.contourGroup = QtWidgets.QGraphicsItemGroup()
        self.markersGroup = QtWidgets.QGraphicsItemGroup()       
        self.polygonMarkersGroup = QtWidgets.QGraphicsItemGroup()
        self.splineMarkersGroup = QtWidgets.QGraphicsItemGroup()

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
        self.contourGroup.addToGroup(self.contourPolygon)
        self.contourGroup.addToGroup(self.chord)
        self.markersGroup.addToGroup(self.polygonMarkersGroup)

        # add everything to the scene
        self.mainwindow.scene.addItem(self.contourGroup)
        self.mainwindow.scene.addItem(self.markersGroup)

    def makeContourPolygon(self, coordinates):
        """Add airfoil points as GraphicsItem to the scene"""

        # instantiate a graphics item
        contour = gc.GraphicsCollection()
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

        for x, y in zip(*self.raw_coordinates):

            # put airfoil contour points as graphicsitem
            points = gc.GraphicsCollection()
            points.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            points.brush.setColor(QtGui.QColor(217, 63, 122, 255))
            points.pen.setCosmetic(True)  # no pen thickness change when zoomed

            points.Circle(x, y, 0.003, marker=True)

            marker = GraphicsItem.GraphicsItem(points)
            self.polygonMarkersGroup.addToGroup(marker)

    def makeChord(self):
        line = gc.GraphicsCollection()
        color = QtGui.QColor(70, 70, 70, 255)
        line.pen.setColor(color)
        line.pen.setWidth(1.)
        line.pen.setCosmetic(True)  # no pen thickness change when zoomed
        line.pen.setJoinStyle(QtCore.Qt.RoundJoin)
        line.pen.setStyle(QtCore.Qt.CustomDashLine)
        # pattern is 1px dash, 4px space, 7px dash, 4px
        line.pen.setDashPattern([1, 4, 10, 4])
        line.Line(np.min(self.raw_coordinates[0]), 0.0,
                  np.max(self.raw_coordinates[0]), 0.0)

        self.chord = GraphicsItem.GraphicsItem(line)

    def makeContourSpline(self, spline_coordinates):
        """Add splined and refined airfoil points as GraphicsItem to
        the scene
        """
        self.pencolor = QtGui.QColor(80, 80, 220, 255)
        self.penwidth = 3.5

        # instantiate a graphics item
        contour = gc.GraphicsCollection()
        # make it polygon type and populate its points
        points = [QtCore.QPointF(x, y) for x, y in zip(*spline_coordinates)]
        contour.Polygon(QtGui.QPolygonF(points), self.name)
        # set its properties
        contour.pen.setColor(self.pencolor)
        contour.pen.setWidth(self.penwidth)
        contour.pen.setCosmetic(True)  # no pen thickness change when zoomed
        contour.brush.setColor(self.brushcolor)
        # add the pline polygon without filling
        contour.brush.setStyle(QtCore.Qt.NoBrush)

        # remove spline from the contourgroup if any
        if self.contourSpline:
            self.scene.removeItem(self.contourSpline)
            self.scene.removeItem(self.splineMarkers)

        self.contourSpline = GraphicsItem.GraphicsItem(contour)

    def makeSplineMarkers(self):
        """Create marker for polygon contour"""

        for x, y in zip(*self.spline_data[0]):

            # put airfoil contour points as graphicsitem
            points = gc.GraphicsCollection()
            points.pen.setColor(QtGui.QColor(60, 60, 80, 255))
            points.brush.setColor(QtGui.QColor(180, 180, 50, 230))
            points.pen.setCosmetic(True)  # no pen thickness change when zoomed

            points.Circle(x, y, 0.003, marker=True)

            marker = GraphicsItem.GraphicsItem(points)
            self.splineMarkersGroup.addToGroup(marker)

    def camber(self):
        pass

    def setPenColor(self, r, g, b, a):
        self.pencolor = QtGui.QColor(r, g, b, a)

    def setBrushColor(self, r, g, b, a):
        self.brushcolor = QtGui.QColor(r, g, b, a)
