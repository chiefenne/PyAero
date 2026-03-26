from PySide6 import QtGui, QtCore, QtWidgets

from Utils import get_main_window

class GraphicsItem(QtWidgets.QGraphicsItem):
    """
     From the QT docs:
     To write your own graphics item, you first create a subclass
     of QGraphicsItem, and then start by implementing its two pure
     virtual public functions: boundingRect(), which returns an estimate
     of the area painted by the item, and paint(),
     which implements the actual painting.
    """

    def __init__(self, item):
        """
        Args:
            item (object): GraphicsItemsCollection object
        """
        super().__init__()

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

        self.scene = self.mw.scene

        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsFocusable, True)

        # docs: For performance reasons, these notifications
        # are disabled by default.
        # needed for : ItemScaleHasChanged
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)

        self.setAcceptHoverEvents(True)

        # method of QPainter
        self.method = item.method
        self.args = item.args
        self.pen = item.pen
        self.penwidth = item.pen.widthF()
        self.brush = item.brush
        self.rect = QtCore.QRectF(item.rect)
        self.setToolTip(item.tooltip)
        self.scale = item.scale
        self.font = item.font
        self.item_shape = item.shape
        self.hoverstyle = QtCore.Qt.SolidLine
        self.hoverwidth = 2.
        if hasattr(item, 'name'):
            self.name = item.name

        # initialize bounding rectangle (including penwidth)
        self.setBoundingRect()

    def itemChange(self, change, value):
        return QtWidgets.QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, event):

        # set item as topmost in stack
        # zstack = [itm.zValue() for itm in self.scene.items()]
        # zmax = max(zstack)
        # self.setZValue(zmax + 1)

        self.setSelected(True)

        # handle event
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
        # handle event
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):

        # handle event
        super().mouseMoveEvent(event)

    def shape(self):
        # this function may be overwritten when subclassing QGraphicsItem
        # it gives more accurate results for collision detection, etc.
        return self.item_shape

    def boundingRect(self):
        # this function must be overwritten when subclassing QGraphicsItem
        # bounding box rect shall be set to the bounds of the item. Due to the
        # line thickness this rect is bigger than the rect of the ellipse or
        # rect, etc.
        # rect + line thickness is size
        return self.boundingrect

    def _boundingPadding(self, penwidth=None):
        penwidth = self.pen.widthF() if penwidth is None else penwidth
        if penwidth <= 0.0:
            return 0.0, 0.0

        if not self.pen.isCosmetic():
            half_width = penwidth / 2.0
            return half_width, half_width

        view = getattr(self.mw, 'view', None)
        if view is None:
            half_width = penwidth / 2.0
            return half_width, half_width

        transform = view.transform()
        sx = abs(transform.m11())
        sy = abs(transform.m22())
        half_x = penwidth / (2.0 * sx) if sx else penwidth / 2.0
        half_y = penwidth / (2.0 * sy) if sy else penwidth / 2.0
        return half_x, half_y

    def _makeBoundingRect(self, rect):
        pad_x, pad_y = self._boundingPadding()
        return QtCore.QRectF(rect.left() - pad_x,
                             rect.top() - pad_y,
                             rect.width() + 2.0 * pad_x,
                             rect.height() + 2.0 * pad_y)

    def setBoundingRect(self):
        boundingrect = self._makeBoundingRect(self.rect)
        if hasattr(self, 'boundingrect') and self.boundingrect != boundingrect:
            self.prepareGeometryChange()
        self.boundingrect = boundingrect

    def refreshGeometry(self):
        self.setBoundingRect()

    def syncGeometryFromArgs(self):
        if self.method not in ('drawEllipse', 'drawRect') or not self.args:
            return

        rect = self.args[0]
        if not isinstance(rect, QtCore.QRectF):
            return

        rect = QtCore.QRectF(rect)
        path = QtGui.QPainterPath()
        if self.method == 'drawEllipse':
            path.addEllipse(rect)
        else:
            path.addRect(rect)

        boundingrect = self._makeBoundingRect(rect)
        geometry_changed = (
            rect != self.rect or
            not hasattr(self, 'boundingrect') or
            self.boundingrect != boundingrect
        )
        if geometry_changed:
            self.prepareGeometryChange()

        self.rect = rect
        self.item_shape = path
        self.boundingrect = boundingrect

    def paint(self, painter, option, widget):
        # this function must be overwritten when subclassing QGraphicsItem

        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        painter.setFont(self.font)

        # draw the gridline aliased, that makes them looking "sharper"
        if self.method == 'drawPolyline':
            painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        else:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # care for difference between objects and text
        # i.e. normally y-coordinates go top down
        # to make a normal coordinate system the y-axis is swapped in GraphicsView
        # since Qt does this automatically for text in the original setup
        # the text here needs to be swapped back to be printed correctly
        # scale on text items therefore in GraphicsItemsCollection
        # gets scale (1, -1), all other items get scale (1, 1)
        painter.scale(self.scale[0], self.scale[1])

        # call module painter with its method given by string in self.method
        # args are arguments to method
        # painter is a QPainter instance
        # depending on the method a variable number of arguments is needed
        # example:
        # if self.method = 'drawEllipse'
        # and self.args = QRectF(x, y, w, h)
        # the call to painter would render as:
        # painter.drawEllipse(*self.args)
        getattr(painter, self.method)(*self.args)

        if self.isSelected():
            # draw rectangle around selected item
            self.drawFocusRect(painter)

            # make selected item opaque
            color = self.brush.color()
            # color.setAlpha(80)
            brush = QtGui.QBrush(color)
            painter.setBrush(brush)

    def drawFocusRect(self, painter):
        self.focusbrush = QtGui.QBrush()
        self.focuspen = QtGui.QPen(QtCore.Qt.DashLine)
        self.focuspen.setColor(QtCore.Qt.darkGray)
        self.focuspen.setWidthF(1.0)
        # no pen thickness change when zoomed
        self.focuspen.setCosmetic(True)  # no thickness change when zoomed
        painter.setBrush(self.focusbrush)
        painter.setPen(self.focuspen)

        painter.drawRect(self.boundingRect())

    def hoverEnterEvent(self, event):
        if not self.isSelected():
            self.pen.setWidthF(self.penwidth + self.hoverwidth)
            self.setBoundingRect()
        # handle event
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.pen.setWidthF(self.penwidth)
        self.setBoundingRect()
        # handle event
        super().hoverLeaveEvent(event)
