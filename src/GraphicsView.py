import os
import math

from PySide6 import QtGui, QtCore, QtWidgets

from Settings import ZOOMANCHOR, SCALEINC, MINZOOM, MAXZOOM, \
                      MARKERSIZE, RUBBERBANDSIZE, VIEWSTYLE
import logging
logger = logging.getLogger(__name__)

# put constraints on rubberband zoom (relative rectangle wdith)
RUBBERBANDSIZE = min(RUBBERBANDSIZE, 1.0)
RUBBERBANDSIZE = max(RUBBERBANDSIZE, 0.05)


class GraphicsView(QtWidgets.QGraphicsView):
    """The graphics view is the canvas where airfoils are drawn upon
    Its coordinates are in pixels or "physical" coordinates.

    Attributes:
        origin (QPoint): stores location of mouse press
        parent (QMainWindow): mainwindow instance
        rubberband (QRubberBand): an instance of the custom rubberband class
                           used for zooming and selecting
        sceneview (QRectF): stores current view in scene coordinates
    """
    def __init__(self, parent=None, scene=None):
        """Default settings for graphicsview instance

        Args:
            parent (QMainWindow, optional): mainwindow instance
        """

        super().__init__(scene)

        self.parent = parent

        self._leftMousePressed = False

        # allow drops from drag and drop
        self.setAcceptDrops(True)

        # use custom rubberband
        self.rubberband = RubberBand(QtWidgets.QRubberBand.Rectangle, self)

        # needed for correct mouse wheel zoom
        # otherwise mouse anchor is wrong; it would use (0, 0)
        self.setInteractive(True)

        # set QGraphicsView attributes
        self.setRenderHints(QtGui.QPainter.Antialiasing |
                            QtGui.QPainter.TextAntialiasing)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)

        # view behaviour when zooming
        if ZOOMANCHOR == 'mouse':
            # point under mouse pointer stays fixed during zoom
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.AnchorUnderMouse)
        else:
            # view center stays fixed during zoom
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.AnchorViewCenter)

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # normally (0, 0) is upperleft corner of view
        # swap y-axis in order to make (0, 0) lower left
        # and y-axis pointing upwards
        self.scale(1, -1)

        # cache view to be able to keep it during resize
        self.getSceneFromView()

        # set background style and color for view
        self.setBackground(VIEWSTYLE)

    def setBackground(self, styletype):
        """Switches between gradient and simple background using style sheets.
        border-color (in HTML) works only if border-style is set.
        """

        if styletype == 'gradient':
            style = """
            border-style:solid; border-color: lightgrey;
            border-width: 1px; background-color: QLinearGradient(x1: 0.0, y1: 0.0,
            x2: 0.0, y2: 1.0, stop: 0.3 white, stop: 1.0 #263a5a);
            """

            # if more stops are needed
            # stop: 0.3 white, stop: 0.6 #4b73b4, stop: 1.0 #263a5a); } """)
        else:
            style = ("""
            border-style:solid; border-color: lightgrey; \
            border-width: 1px; background-color: white;""")

        self.setStyleSheet(style)

    def resizeEvent(self, event):
        """Re-implement QGraphicsView's resizeEvent handler"""

        # call corresponding base class method
        super().resizeEvent(event)

        # scrollbars need to be switched off when calling fitinview from
        # within resize event otherwise strange recursion can occur
        self.fitInView(self.sceneview,
                       aspectRadioMode=QtCore.Qt.KeepAspectRatio)

    def mousePressEvent(self, event):
        """Re-implement QGraphicsView's mousePressEvent handler"""

        # status of CTRL key
        ctrl = event.modifiers() == QtCore.Qt.ControlModifier

        # if a mouse event happens in the graphics view
        # put the keyboard focus to the view as well
        self.setFocus()

        self.origin = event.pos()

        # do rubberband zoom only with left mouse button
        if event.button() == QtCore.Qt.LeftButton:

            self._leftMousePressed = True
            self._dragPos = event.pos()

            if ctrl:
                self.setCursor(QtCore.Qt.ClosedHandCursor)
            else:
                # initiate rubberband origin and size (zero at first)
                self.rubberband.setGeometry(QtCore.QRect(self.origin,
                    QtCore.QSize()))
                # show, even at zero size
                # allows to check later using isVisible()
                self.rubberband.show()

        # call corresponding base class method
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Re-implement QGraphicsView's mouseMoveEvent handler"""

        # if a mouse event happens in the graphics view
        # put the keyboard focus to the view as well
        self.setFocus()

        # status of CTRL key
        ctrl = event.modifiers() == QtCore.Qt.ControlModifier

        # pan the view with the left mouse button and CRTL down
        if self._leftMousePressed and ctrl:
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            newPos = event.pos()
            diff = newPos - self._dragPos
            self._dragPos = newPos

            # this actually does the pan
            # no matter if scroll bars are displayed or not
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - diff.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - diff.y())

        if self.rubberband.isVisible() and not ctrl:
            self.setInteractive(False)
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin, event.pos()).normalized())

        # call corresponding base class method
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Re-implement QGraphicsView's mouseReleaseEvent handler"""

        self._leftMousePressed = False
        self.setCursor(QtCore.Qt.ArrowCursor)

        # do zoom wrt to rect of rubberband
        if self.rubberband.isVisible():

            self.rubberband.hide()
            rect = self.rubberband.geometry()
            rectf = self.mapToScene(rect).boundingRect()

            # zoom the selected rectangle (works on scene coordinates)
            # zoom rect must be at least 5% of view width to allow zoom
            if self.rubberband.allow_zoom:
                self.fitInView(rectf,
                               aspectRadioMode=QtCore.Qt.KeepAspectRatio)

            # rescale markers during zoom
            # i.e. keep them constant size
            self.adjustMarkerSize()

            # reset to True, so that mouse wheel zoom anchor works
            self.setInteractive(True)

        # reset ScrollHandDrag if it was active
        if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

        # call corresponding base class method
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Re-implement QGraphicsView's wheelEvent handler"""

        f = SCALEINC
        # wheelevent.angleDelta() returns a QPoint instance
        # the angle increment of the wheel is stored on the .y() attribute
        angledelta = event.angleDelta().y()
        if math.copysign(1, angledelta) > 0:
            f = 1.0 / SCALEINC

        self.scaleView(f)

        # DO NOT CONTINUE HANDLING EVENTS HERE!!!
        # this would destroy the mouse anchor
        # call corresponding base class method
        # super().wheelEvent(event)

    def keyPressEvent(self, event):
        """Re-implement QGraphicsView's keyPressEvent handler"""

        key = event.key()

        if key == QtCore.Qt.Key_Plus or key == QtCore.Qt.Key_PageDown:
            f = SCALEINC
            # if scaling with the keys, the do not use mouse as zoom anchor
            anchor = self.transformationAnchor()
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
            self.scaleView(f)
            self.setTransformationAnchor(anchor)

            if key == QtCore.Qt.Key_PageDown:
                # return here so that later base class is NOT called
                # because QAbstractScrollArea would otherwise handle
                # the event and do something we do not want
                return

        elif key == QtCore.Qt.Key_Minus or key == QtCore.Qt.Key_PageUp:
            f = 1.0 / SCALEINC
            # if scaling with the keys, the do not use mouse as zoom anchor
            anchor = self.transformationAnchor()
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
            self.scaleView(f)
            self.setTransformationAnchor(anchor)

            if key == QtCore.Qt.Key_PageUp:
                # return here so that later base class is NOT called
                # because QAbstractScrollArea would otherwise handle
                # the event and do something we do not want
                return

        elif key == QtCore.Qt.Key_Home:
            self.parent.slots.onViewAll()
        elif key == QtCore.Qt.Key_Delete:
            # removes all selected airfoils
            self.parent.slots.removeAirfoil()

        # call corresponding base class method
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Re-implement QGraphicsView's keyReleaseEvent handler"""

        # call corresponding base class method
        super().keyReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        pass

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            if event.mimeData().hasText():
                event.setDropAction(QtCore.Qt.CopyAction)
                event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.parent.slots.loadAirfoil(path, comment='#')

    def scaleView(self, factor):

        # check if zoom limits are exceeded
        # m11 = x-scaling
        sx = self.transform().m11()

        too_big = sx > MAXZOOM and factor > 1.0
        too_small = sx < MINZOOM and factor < 1.0

        if too_big or too_small:
            return

        # do the actual zooming
        self.scale(factor, factor)

        # rescale markers during zoom, i.e. keep them constant size
        self.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.getSceneFromView()

    def adjustMarkerSize(self):
        """Adjust marker size during zoom. Marker items are circles
        which are otherwise affected by zoom. Using MARKERSIZE from
        Settings a fixed markersize (e.g. 3 pixels) can be kept.
        This method immitates the behaviour of pen.setCosmetic()
        """

        # FIXME
        # FIXME this fixes an accidential call of this method
        # FIXME should be fixed by checking when called
        # FIXME
        if not self.parent.airfoil:
            return
        
        # 
        current_zoom = self.transform().m11()
        scale_marker = 1. + 3. * (current_zoom - MINZOOM) / (MAXZOOM - MINZOOM)
        # scale_marker = 100.
        # logger.info(f'Current zoom value {current_zoom}')
        # logger.info(f'Scale factor for markers {scale_marker}')

        # markers are drawn in GraphicsItem using scene coordinates
        # in order to keep them constant size, also when zooming
        # a fixed pixel size (MARKERSIZE from settings) is mapped to
        # scene coordinates
        # depending on the zoom, this leads to always different
        # scene coordinates
        # map a square with side length of MARKERSIZE to the scene coords

        mappedMarker = self.mapToScene(
            QtCore.QRect(0, 0, MARKERSIZE*scale_marker, MARKERSIZE*scale_marker))
        mappedMarkerWidth = mappedMarker.boundingRect().width()

        if self.parent.airfoil.contourPolygon:
            markers = self.parent.airfoil.polygonMarkers
            x, y = self.parent.airfoil.raw_coordinates
            for i, marker in enumerate(markers):
                # in case of circle, args is a QRectF
                marker.args = [QtCore.QRectF(x[i] - mappedMarkerWidth,
                                             y[i] - mappedMarkerWidth,
                                             2. * mappedMarkerWidth,
                                             2. * mappedMarkerWidth)]

        # if self.parent.airfoil.contourSpline:
        if hasattr(self.parent.airfoil, 'contourSpline'):
            markers = self.parent.airfoil.splineMarkers
            x, y = self.parent.airfoil.spline_data[0]
            for i, marker in enumerate(markers):
                # in case of circle, args is a QRectF
                marker.args = [QtCore.QRectF(x[i] - mappedMarkerWidth,
                                             y[i] - mappedMarkerWidth,
                                             2. * mappedMarkerWidth,
                                             2. * mappedMarkerWidth)]

    def getSceneFromView(self):
        """Cache view to be able to keep it during resize"""

        # map view rectangle to scene coordinates
        polygon = self.mapToScene(self.rect())

        # sceneview describes the rectangle which is currently
        # being viewed in scene coordinates
        # this is needed during resizing to be able to keep the view
        self.sceneview = QtCore.QRectF(polygon[0], polygon[2])

    def contextMenuEvent(self, event):
        """creates popup menu for the graphicsview"""

        menu = QtWidgets.QMenu(self)

        fitairfoil = menu.addAction('Fit airfoil in view')
        fitairfoil.setShortcut('CTRL+f')

        fitall = menu.addAction('Fit all items in view')
        fitall.setShortcut('HOME, CTRL+SHIFT+f')

        menu.addSeparator()

        delitems = menu.addAction('Delete airfoil')
        delitems.setShortcut('Del')

        menu.addSeparator()

        togglebg = menu.addAction('Toggle background')
        togglebg.setShortcut('CTRL+b')

        action = menu.exec_(self.mapToGlobal(event.pos()))

        if action == togglebg:
            self.parent.slots.onBackground()
        elif action == fitairfoil:
            self.parent.slots.fitAirfoilInView()
        elif action == fitall:
            self.parent.slots.onViewAll()
        # remove all selected items from the scene
        elif action == delitems:
            self.parent.slots.removeAirfoil()

        # call corresponding base class method
        super().contextMenuEvent(event)


class RubberBand(QtWidgets.QRubberBand):
    """Custom rubberband
    from: http://stackoverflow.com/questions/25642618
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.view = args[1]

        # set pen and brush (filling)
        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.DotLine)
        self.pen.setColor(QtGui.QColor(80, 80, 100))
        self.brush = QtGui.QBrush()
        color = QtGui.QColor(20, 20, 80, 30)
        self.brush.setColor(color)
        # self.brush.setStyle(QtCore.Qt.NoBrush)
        self.brush.setStyle(QtCore.Qt.SolidPattern)

        # set style selectively for the rubberband like that
        # see: http://stackoverflow.com/questions/25642618
        # required as opacity might not work
        # NOTE: opacity removed here
        self.setStyle(QtWidgets.QStyleFactory.create('windowsvista'))

        # set boolean for allowing zoom
        self.allow_zoom = False

    def paintEvent(self, QPaintEvent):

        painter = QtGui.QPainter(self)

        self.pen.setColor(QtGui.QColor(80, 80, 100))
        self.pen.setWidthF(1.5)
        self.pen.setStyle(QtCore.Qt.DotLine)

        # zoom rect must be at least RUBBERBANDSIZE % of view to allow zoom
        if (QPaintEvent.rect().width() < RUBBERBANDSIZE * self.view.width()) \
            or \
           (QPaintEvent.rect().height() < RUBBERBANDSIZE * self.view.height()):

            self.brush.setStyle(QtCore.Qt.NoBrush)

            # set boolean for allowing zoom
            self.allow_zoom = False
        else:
            # if rubberband rect is big enough indicate this by fill color
            color = QtGui.QColor(10, 30, 140, 45)
            self.brush.setColor(color)
            self.brush.setStyle(QtCore.Qt.SolidPattern)

            # set boolean for allowing zoom
            self.allow_zoom = True

        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        painter.drawRect(QPaintEvent.rect())
