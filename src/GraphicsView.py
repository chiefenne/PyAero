import os
import math

from PySide2 import QtGui, QtCore, QtWidgets

from Settings import ZOOMANCHOR, SCROLLBARS, SCALEINC, MINZOOM, MAXZOOM, \
                      MARKERSIZE, MARKERPENWIDTH, RUBBERBANDSIZE, VIEWSTYLE

# put constraints on rubberband zoom (relative rectangle wdith)
RUBBERBANDSIZE = min(RUBBERBANDSIZE, 1.0)
RUBBERBANDSIZE = max(RUBBERBANDSIZE, 0.05)


class GraphicsView(QtWidgets.QGraphicsView):
    """The graphics view is the canvas where airfoils are drawn upon
    Its coordinates are in pixels or "physical" coordinates.

    Attributes:
        ctrl (bool): carries status of CTRL key; used aslo in rubberband
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
        self.ctrl = False

        self._rightMousePressed = False
        self._was_dragging = False

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
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        else:
            # view center stays fixed during zoom
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)

        if SCROLLBARS:
            self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
            self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        else:
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
            style = ("""
            QtWidgets.QGraphicsView {border-style:solid; border-color: lightgrey; \
            border-width: 1px; background-color: QLinearGradient( \
            x1: 0.0, y1: 0.0, x2: 0.0, y2: 1.0, \
            stop: 0.3 white, stop: 1.0 #263a5a); } """)

            # if more stops are needed
            # stop: 0.3 white, stop: 0.6 #4b73b4, stop: 1.0 #263a5a); } """)
        else:
            style = ("""
            QtWidgets.QGraphicsView { border-style:solid; border-color: lightgrey; \
            border-width: 1px; background-color: white } """)

        self.setStyleSheet(style)

    def resizeEvent(self, event):
        """Re-implement QGraphicsView's resizeEvent handler"""

        # call original implementation of QGraphicsView resizeEvent handler
        super(GraphicsView, self).resizeEvent(event)

        # scrollbars need to be switched off when calling fitinview from
        # within resize event otherwise strange recursion can occur
        self.fitInView(self.sceneview, mode=QtCore.Qt.KeepAspectRatio)

    def mousePressEvent(self, event):
        """Re-implement QGraphicsView's mousePressEvent handler"""

        if event.button() == QtCore.Qt.LeftButton:
            # do the standard operation only for left button click
            # e.g. for selection
            # on right button click this is not called
            # therefore no deselection happens then
            super(GraphicsView, self).mousePressEvent(event)

        # if a mouse event happens in the graphics view
        # put the keyboard focus to the view as well
        self.setFocus()

        self.origin = event.pos()

        # do rubberband zoom only with left mouse button
        if event.button() == QtCore.Qt.LeftButton:
            # initiate rubberband origin and size (zero at first)
            self.rubberband.setGeometry(QtCore.QRect(self.origin,
                                        QtCore.QSize()))
            # show, even at zero size, allows to check later using isVisible()
            self.rubberband.show()

        if event.button() == QtCore.Qt.RightButton:
            self._rightMousePressed = True
            self.setCursor(QtCore.Qt.OpenHandCursor)
            self._dragPos = event.pos()

        # call original implementation of QGraphicsView mousePressEvent handler
        # super(GraphicsView, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Re-implement QGraphicsView's mouseMoveEvent handler"""

        # if a mouse event happens in the graphics view
        # put the keyboard focus to the view as well
        self.setFocus()

        # pan the view with the right mouse button
        if self._rightMousePressed:
            self._was_dragging = True
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            newPos = event.pos()
            diff = newPos - self._dragPos
            self._dragPos = newPos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - diff.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - diff.y())

        if self.rubberband.isVisible():

            # returns the current state of the modifier keys on the keyboard
            modifiers = QtWidgets.QApplication.keyboardModifiers()

            if modifiers == QtCore.Qt.ControlModifier:
                self.ctrl = True
                # allow to select via rubberband
                # no zooming done
                self.setInteractive(True)

                rect = self.rubberband.geometry()
                for item in self.items():
                    bnd = self.mapFromScene(item.boundingRect()).boundingRect()
                    if rect.intersects(bnd):
                        item.setSelected(True)
                    else:
                        item.setSelected(False)
            else:
                # do not allow to select with the rubberband
                # instead do zooming
                self.setInteractive(False)

            self.rubberband.setGeometry(
                QtCore.QRect(self.origin, event.pos()).normalized())

        # call original implementation of QGraphicsView mouseMoveEvent handler
        super(GraphicsView, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Re-implement QGraphicsView's mouseReleaseEvent handler"""

        self._rightMousePressed = False
        self.setCursor(QtCore.Qt.ArrowCursor)

        # call original implementation of QGraphicsView
        # mouseReleaseEvent handler
        super(GraphicsView, self).mouseReleaseEvent(event)

        if self.rubberband.isVisible():

            # returns the current state of the modifier keys on the keyboard
            modifiers = QtWidgets.QApplication.keyboardModifiers()

            if (modifiers == QtCore.Qt.ControlModifier) or self.ctrl:
                self.ctrl = False
                self.rubberband.hide()
            else:
                self.rubberband.hide()
                rect = self.rubberband.geometry()
                rectf = self.mapToScene(rect).boundingRect()

                # zoom the selected rectangle (works on scene coordinates)
                # zoom rect must be at least 5% of view width to allow zoom
                if rect.width() > RUBBERBANDSIZE * self.width():
                    self.fitInView(rectf, mode=QtCore.Qt.KeepAspectRatio)

                # rescale markers during zoom
                # i.e. keep them constant size
                self.adjustMarkerSize()

            # reset to True, so that mouse wheel zoom anchor works
            self.setInteractive(True)

        # reset ScrollHandDrag if it was active
        if self.dragMode() == QtWidgets.QGraphicsView.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

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
        # call original implementation of QGraphicsView wheelEvent handler
        # super(GraphicsView, self).wheelEvent(event)

    def keyPressEvent(self, event):
        """Re-implement QGraphicsView's keyPressEvent handler"""

        key = event.key()

        # returns the current state of the modifier keys on the keyboard
        modifiers = QtWidgets.QApplication.keyboardModifiers()

        # check if CTRL+SHIFT is pressed simultaneously
        if (modifiers & QtCore.Qt.ControlModifier) and \
                (modifiers & QtCore.Qt.ShiftModifier):
            pass

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

        # call original implementation of QGraphicsView keyPressEvent handler
        # the call here needs to be at the end of the method so that we can
        # optionally return without calling it; see above
        super(GraphicsView, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Re-implement QGraphicsView's keyReleaseEvent handler"""

        # call original implementation of QGraphicsView keyReleaseEvent handler
        super(GraphicsView, self).keyReleaseEvent(event)

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
            path = url.toLocalFile().toLocal8Bit().data()
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
        which are otherwise affected by zoom.
        """
        # markers are drawn in PGraphicsItem using scene coordinates
        # in order to keep them constant size, also when zooming
        # a fixed pixel size is mapped to scene coordinates
        # depending on the zoom, this leads to always different scene
        # coordinates
        # map a square with side length of MARKERSIZE to the scene coords
        poly = self.mapToScene(QtCore.QRect(0, 0, MARKERSIZE, MARKERSIZE))
        pw = self.mapToScene(QtCore.QRect(0, 0, MARKERPENWIDTH,
                             MARKERPENWIDTH))
        rect = poly.boundingRect()
        r = rect.width()
        pwr = pw.boundingRect()
        pw_mapped = pwr.width()

        for airfoil in self.parent.airfoils:
            if hasattr(airfoil, 'markers'):
                markers = airfoil.markers.childItems()
                x, y = airfoil.raw_coordinates
                for i, marker in enumerate(markers):
                    # in case of circle, args is a QRectF
                    marker.args = [QtCore.QRectF(x[i]-r, y[i]-r, 2.*r, 2.*r)]
                    marker.penwidth = pw_mapped
            if hasattr(airfoil, 'markersSpline'):
                markers = airfoil.markersSpline.childItems()
                x, y = airfoil.spline_data[0]
                for i, marker in enumerate(markers):
                    # in case of circle, args is a QRectF
                    marker.args = [QtCore.QRectF(x[i]-r, y[i]-r, 2.*r, 2.*r)]
                    marker.penwidth = pw_mapped

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

        if self._was_dragging:
            self._was_dragging = False
            return

        menu = QtWidgets.QMenu(self)

        fitairfoil = menu.addAction('Fit airfoil in view')
        fitairfoil.setShortcut('CTRL+f')

        fitall = menu.addAction('Fit all items in view')
        fitall.setShortcut('HOME, CTRL+SHIFT+f')

        menu.addSeparator()

        delitems = menu.addAction('Delete selected')
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

        # continue handling events
        super(GraphicsView, self).contextMenuEvent(event)


class RubberBand(QtWidgets.QRubberBand):
    """Custom rubberband
    from: http://stackoverflow.com/questions/25642618
    """

    def __init__(self, *args, **kwargs):

        super(RubberBand, self).__init__(*args, **kwargs)

        self.view = args[1]

        # set pen
        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.SolidLine)
        self.pen.setColor(QtGui.QColor(80, 80, 100))

        # set brush
        color = QtGui.QColor(30, 30, 50, 30)
        self.brush = QtGui.QBrush(color)

        # set style selectively for the rubberband like that
        # see: http://stackoverflow.com/questions/25642618
        # required as opacity might not work
        # NOTE: opacity removed here
        self.setStyle(QtWidgets.QStyleFactory.create('windowsvista'))

    def paintEvent(self, QPaintEvent):

        painter = QtGui.QPainter(self)

        # check if zooming or selecting
        if self.view.ctrl:
            # selecting is activated
            self.pen.setWidth(4)
            self.pen.setStyle(QtCore.Qt.SolidLine)
            self.pen.setColor(QtGui.QColor(200, 200, 0))
            color = QtGui.QColor(200, 200, 0, 30)
            self.brush = QtGui.QBrush(color)
        else:
            # zoom rect must be at least RUBBERBANDSIZE % of view to allow zoom
            if QPaintEvent.rect().width() < RUBBERBANDSIZE * self.view.width():
                self.pen.setWidth(2)
                self.pen.setStyle(QtCore.Qt.DotLine)
            else:
                self.pen.setWidth(4)
                self.pen.setStyle(QtCore.Qt.SolidLine)

            self.pen.setColor(QtGui.QColor(80, 80, 100))
            color = QtGui.QColor(30, 30, 50, 30)
            self.brush = QtGui.QBrush(color)

        painter.setPen(self.pen)

        # set brush
        painter.setBrush(self.brush)

        # draw rectangle
        painter.drawRect(QPaintEvent.rect())
