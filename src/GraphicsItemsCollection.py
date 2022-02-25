from PySide6 import QtGui, QtCore


class GraphicsCollection:
    """Collection of custom graphics items which can be used to draw
    QGraphicsItems within a scene.

    The custom items are being made a QGraphicsItem in GraphicsItem.
    There each method needs 4 attributes:
        self.rect ... bounding rectangle of the item (drawn when selected)
        self.shape ... more accurate results for collision detection
                       wrt to bounding rect
        self.method ... draw method of QPainter (e.g. drawEllipse)
        self.args ... list of arguments to self.method
    """

    def __init__(self, name=None):

        pen = QtGui.QPen(QtCore.Qt.SolidLine)
        pen.setColor(QtGui.QColor(0, 0, 0, 255))
        pen.setWidthF(0.2)
        pen.setJoinStyle(QtCore.Qt.MiterJoin)
        self.pen = pen

        self.brush = QtGui.QBrush(QtGui.QColor(255, 255, 0, 255))
        self.font = QtGui.QFont('Decorative', 12)

        self.rect = QtCore.QRectF()
        self.shape = QtGui.QPainterPath()
        self.path = QtGui.QPainterPath()

        self.scale = (1, 1)
        self.tooltip = ''

        self.method = ''
        self.args = []

    def Point(self, x, y):
        # add some pixels to the point rect, so that it can be selected
        eps = 0.02
        self.rect = QtCore.QRectF(x-eps, y-eps, 2.*eps, 2.*eps)
        self.shape.addRect(self.rect)
        self.method = 'drawPoint'
        self.args = [x, y]

    def Line(self, x1, y1, x2, y2):
        eps = 0.01
        p1 = QtCore.QPointF(x1, y1)
        p2 = QtCore.QPointF(x2, y2)
        p1e = QtCore.QPointF(x1-eps, y1-eps)
        p2e = QtCore.QPointF(x2+eps, y2+eps)
        self.rect = QtCore.QRectF(p1e, p2e)
        self.shape.addRect(self.rect)
        self.method = 'drawLine'
        self.args = [p1, p2]

    def Circle(self, x, y, r):
        self.rect = QtCore.QRectF(x-r, y-r, 2.*r, 2.*r)
        self.shape.addEllipse(self.rect)
        self.method = 'drawEllipse'
        self.args = [self.rect]

    def Rectangle(self, x, y, w, h):
        self.rect = QtCore.QRectF(x, y, w, h)
        self.shape.addRect(self.rect)
        self.method = 'drawRect'
        self.args = [self.rect]

    def Polygon(self, polygon, name=None):
        """Custom polygon graphics item pre-populated for PGraphicsItem

        Args:
            polygon (QPolygonF): x, y coordinates of points
        """
        self.rect = polygon.boundingRect()
        self.shape.addPolygon(polygon)
        self.method = 'drawPolygon'
        self.args = [polygon]
        # in case of an airfoil its the airfoil name (Airfoil.py)
        self.name = name
        self.tooltip = name

    def Polyline(self, polygon, name=None):
        """Custom polyline graphics item pre-populated for PGraphicsItem

        Args:
            polygon (QPolygonF): x, y coordinates of points
        """
        self.rect = polygon.boundingRect()
        self.shape.addPolygon(polygon)
        self.method = 'drawPolyline'
        self.args = [polygon]

    def Mesh(self, mesh):
        self.method = 'drawPath'
        self.args = []

    def Path(self, path):
        rect = path.boundingRect()
        self.shape.addRect(rect)
        self.method = 'drawPath'
        self.args = [path]

    def Text(self, x, y, text, font):
        # since GraphicsView swaps already y-coordinate, text needs to be
        # flipped back
        self.scale = (1, -1)
        thetext = QtGui.QStaticText(text)
        size = thetext.size()
        self.rect = QtCore.QRectF(x, y, size.width(), size.height())
        self.font = font
        self.method = 'drawStaticText'
        self.args = [x, y, thetext]
        self.shape.addText(x, y, font, text)

    def setPen(self, pen):
        self.pen = pen

    def setBrush(self, brush):
        self.brush = brush

    def setRect(self, rect):
        self.rect = rect

    def setTooltip(self, tooltip):
        self.tooltip = tooltip
