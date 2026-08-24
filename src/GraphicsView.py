import os

from PySide6 import QtGui, QtCore, QtWidgets
import shiboken6

import MagnifierLens
from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)



class GraphicsView(QtWidgets.QGraphicsView):
    """The graphics view is the canvas where airfoils are drawn upon
    Its coordinates are in pixels or "physical" coordinates.

    Attributes:
        origin (QPoint): stores location of mouse press
        rubberband (QRubberBand): an instance of the custom rubberband class
                           used for zooming and selecting
        sceneview (QRectF): stores current view in scene coordinates
    """
    MAGNIFIER_SIZE_STEP = 24
    MAGNIFIER_MIN_SIZE = 96
    MAGNIFIER_MAX_SIZE = 700
    MAGNIFIER_MIN_OUTLINE_WIDTH = 1.0
    MAGNIFIER_MAX_OUTLINE_WIDTH = 8.0
    MAGNIFIER_MAGNIFICATION_STEP = 0.25
    MAGNIFIER_MIN_MAGNIFICATION = 1.25
    MAGNIFIER_MAX_MAGNIFICATION = 6.0

    def __init__(self, scene=None):
        """Default settings for graphicsview instance"""

        super().__init__(scene)

        self.mw = get_main_window()

        self._leftMousePressed = False
        self._magnifier_active = False
        self._magnifier_size = 180
        self._magnifier_outline_width = 2.0
        self._magnifier_magnification = 2.0
        self._magnifier_last_pos = None
        self._magnifier_wheel_accumulator = 0.0
        self._magnifier_action_states = {}

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
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setLineWidth(0)

        self.applyViewSettings()

        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # normally (0, 0) is upperleft corner of view
        # swap y-axis in order to make (0, 0) lower left
        # and y-axis pointing upwards
        self.scale(1, -1)

        # cache view to be able to keep it during resize
        self.getSceneFromView()

        self._magnifier_lens = MagnifierLens.MagnifierLensWidget(self)
        self.applyMagnifierSettings()
        self.setMouseTracking(False)
        self.viewport().setMouseTracking(False)

    def applyViewSettings(self):
        # view behaviour when zooming
        if self.mw.ZOOM_ANCHOR == 'mouse':
            # point under mouse pointer stays fixed during zoom
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.AnchorUnderMouse)
        else:
            # view center stays fixed during zoom
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.AnchorViewCenter)

        # set background style and color for view
        self.viewstyle = self.mw.VIEW_STYLE
        self.setBackground(self.mw.VIEW_STYLE)

        # put constraints on rubberband zoom (relative rectangle width)
        self.mw.RUBBERBAND_MIN = min(self.mw.RUBBERBAND_MIN, 1.0)
        self.mw.RUBBERBAND_MIN = max(self.mw.RUBBERBAND_MIN, 0.05)

        self.applyMagnifierSettings()

    def applyMagnifierSettings(self):
        size = getattr(self.mw, 'MAGNIFIER_SIZE', self._magnifier_size)
        outline_width = getattr(
            self.mw,
            'MAGNIFIER_OUTLINE_WIDTH',
            self._magnifier_outline_width,
        )
        magnification = getattr(
            self.mw,
            'MAGNIFIER_MAGNIFICATION',
            self._magnifier_magnification,
        )

        self._magnifier_size = self._clampMagnifierSize(size)
        self._magnifier_outline_width = self._clampMagnifierOutlineWidth(
            outline_width
        )
        self._magnifier_magnification = self._clampMagnification(magnification)

        if not hasattr(self, '_magnifier_lens'):
            return

        self._magnifier_lens.setLensSize(self._magnifier_size)
        self._magnifier_lens.setOutlineWidth(self._magnifier_outline_width)
        self._magnifier_lens.setMagnification(self._magnifier_magnification)
        self._magnifier_lens.syncFromMainView()

        if self._magnifier_active and self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def setBackground(self, styletype):
        """Switches between gradient and simple background using style sheets.
        border-color (in HTML) works only if border-style is set.
        """

        if styletype == 'gradient':
            style = """
            background-color: QLinearGradient(x1: 0.0, y1: 0.0,
            x2: 0.0, y2: 1.0, stop: 0.3 white, stop: 1.0 #263a5a);
            """

            # if more stops are needed
            # stop: 0.3 white, stop: 0.6 #4b73b4, stop: 1.0 #263a5a); } """)
        else:
            style = ("""
            background-color: white;""")

        self.setStyleSheet(style)
        if hasattr(self, '_magnifier_lens'):
            self._magnifier_lens.syncFromMainView()

    def fitInView(self, *args, **kwargs):
        result = super().fitInView(*args, **kwargs)
        self.refreshCustomItemGeometry()
        if self._magnifier_active and self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)
        return result

    def refreshCustomItemGeometry(self):
        scene = self.scene()
        if scene is None:
            return

        for item in scene.items():
            refresh_geometry = getattr(item, 'refreshGeometry', None)
            if callable(refresh_geometry):
                refresh_geometry()

    def resizeEvent(self, event):
        """Re-implement QGraphicsView's resizeEvent handler"""

        # call corresponding base class method
        super().resizeEvent(event)

        # scrollbars need to be switched off when calling fitinview from
        # within resize event otherwise strange recursion can occur
        self.fitInView(self.sceneview,
                       aspectRadioMode=QtCore.Qt.KeepAspectRatio)
        self.adjustMarkerSize()

        if self._magnifier_active and self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def mousePressEvent(self, event):
        """Re-implement QGraphicsView's mousePressEvent handler"""

        if self._magnifier_active:
            self.setFocus()
            if event.button() == QtCore.Qt.RightButton:
                event.ignore()
            else:
                event.accept()
            return

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

        if self._magnifier_active:
            self.setFocus()
            self._updateMagnifier(event.pos())
            event.accept()
            return

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

        if self._magnifier_active:
            if event.button() == QtCore.Qt.RightButton:
                event.ignore()
            else:
                event.accept()
            return

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

        if self._magnifier_active:
            steps = self._magnifierWheelSteps(event)
            if steps:
                self._adjustMagnifierMagnification(
                    steps * self.MAGNIFIER_MAGNIFICATION_STEP
                )
                if self._magnifier_last_pos is not None:
                    self._updateMagnifier(self._magnifier_last_pos)
            event.accept()
            return

        # detect if event comes from a touchpad or similar (e.g., Apple magic mouse)
        # then zoom based on pixel delta
        device = event.device().type().name

        if device == 'TouchPad':
            delta = event.pixelDelta().y()
            damping = 0.0
        else:
            delta = event.angleDelta().y()
            damping = 0.0

        # Determine the scale factor based on the wheel direction
        factor = self.mw.SCALE_INCREMENT - damping
        scale_factor = 1.0 / factor if delta * self.mw.ZOOM_DIRECTION > 0 else factor

        # Apply the scaling
        self.scaleView(scale_factor)

        # DO NOT CONTINUE HANDLING EVENTS HERE!!!
        # this would destroy the mouse anchor
        # call corresponding base class method
        # super().wheelEvent(event)

    def _scaleFromKeyboard(self, factor):
        anchor = self.transformationAnchor()
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.scaleView(factor)
        self.setTransformationAnchor(anchor)

    def zoomIn(self):
        self._scaleFromKeyboard(self.mw.SCALE_INCREMENT)

    def zoomOut(self):
        self._scaleFromKeyboard(1.0 / self.mw.SCALE_INCREMENT)

    def toggleMagnifier(self):
        self.setMagnifierEnabled(not self._magnifier_active)

    def setMagnifierEnabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self._magnifier_active:
            return

        self._magnifier_active = enabled
        self._magnifier_wheel_accumulator = 0.0
        self._leftMousePressed = False
        self.rubberband.hide()
        self._setMagnifierActionStates(enabled)

        self.setMouseTracking(enabled)
        self.viewport().setMouseTracking(enabled)

        if not enabled:
            self._magnifier_lens.hide()
            self._magnifier_last_pos = None
            return

        view_pos = self.viewport().mapFromGlobal(QtGui.QCursor.pos())
        if self.viewport().rect().contains(view_pos):
            self._updateMagnifier(view_pos)
        else:
            self._magnifier_lens.hide()

    def magnifierZoomIn(self):
        if not self._magnifier_active:
            return
        self._adjustMagnifierMagnification(self.MAGNIFIER_MAGNIFICATION_STEP)
        if self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def magnifierZoomOut(self):
        if not self._magnifier_active:
            return
        self._adjustMagnifierMagnification(-self.MAGNIFIER_MAGNIFICATION_STEP)
        if self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def magnifierIncreaseSize(self):
        if not self._magnifier_active:
            return
        self._adjustMagnifierSize(self.MAGNIFIER_SIZE_STEP)
        if self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def magnifierDecreaseSize(self):
        if not self._magnifier_active:
            return
        self._adjustMagnifierSize(-self.MAGNIFIER_SIZE_STEP)
        if self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def keyPressEvent(self, event):
        """Forward keypress events to Qt's action system."""
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
                self.mw.slots.openFile(path)

    def scaleView(self, factor):

        # check if zoom limits are exceeded
        # m11 = x-scaling
        sx = self.transform().m11()

        too_big = sx > self.mw.MAX_ZOOM and factor > 1.0
        too_small = sx < self.mw.MIN_ZOOM and factor < 1.0

        if too_big or too_small:
            return

        # do the actual zooming
        self.scale(factor, factor)

        # rescale markers during zoom, i.e., keep them constant size
        self.adjustMarkerSize()

        self.refreshCustomItemGeometry()

        # cache view to be able to keep it during resize
        self.getSceneFromView()

        if self._magnifier_active and self._magnifier_last_pos is not None:
            self._updateMagnifier(self._magnifier_last_pos)

    def adjustMarkerSize(self):
        """Adjust marker size during zoom. Marker items are circles
        which are otherwise affected by zoom. Using MARKER_SIZE from
        Settings a fixed markersize (e.g. 3 pixels) can be kept.
        This method imitates the behaviour of pen.setCosmetic().
        """

        if getattr(self.mw, '_viewer_subject', 'airfoil') != 'airfoil':
            return

        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            return

        marker_radius = self._markerRadiusInScene()
        for coordinates, markers, scale in airfoil.markerCollections():
            self._resizeMarkers(markers, coordinates, marker_radius * scale)

    def _markerRadiusInScene(self):
        current_zoom = self.transform().m11()
        zoom_span = self.mw.MAX_ZOOM - self.mw.MIN_ZOOM
        if zoom_span == 0.0:
            scale_marker = 1.0
        else:
            scale_marker = 1.0 + 3.0 * (current_zoom - self.mw.MIN_ZOOM) / zoom_span

        # Markers are drawn in scene coordinates. Map the configured marker size
        # from view pixels back to the scene so the apparent size stays stable.
        mapped_marker = self.mapToScene(
            QtCore.QRect(
                0,
                0,
                self.mw.MARKER_SIZE * scale_marker,
                self.mw.MARKER_SIZE * scale_marker,
            )
        )
        return mapped_marker.boundingRect().width()

    def _resizeMarkers(self, markers, coordinates, marker_radius):
        x_values, y_values = coordinates
        for marker, x_value, y_value in zip(markers, x_values, y_values):
            if not shiboken6.isValid(marker):
                continue
            marker.args = [
                QtCore.QRectF(
                    x_value - marker_radius,
                    y_value - marker_radius,
                    2.0 * marker_radius,
                    2.0 * marker_radius,
                )
            ]
            sync_geometry = getattr(marker, 'syncGeometryFromArgs', None)
            if callable(sync_geometry):
                sync_geometry()

    def getSceneFromView(self):
        """Cache view to be able to keep it during resize"""

        # map view rectangle to scene coordinates
        polygon = self.mapToScene(self.rect())

        # sceneview describes the rectangle which is currently
        # being viewed in scene coordinates
        # this is needed during resizing to be able to keep the view
        self.sceneview = QtCore.QRectF(polygon[0], polygon[2])

    def enterEvent(self, event):
        super().enterEvent(event)
        if not self._magnifier_active:
            return

        view_pos = self.viewport().mapFromGlobal(QtGui.QCursor.pos())
        if self.viewport().rect().contains(view_pos):
            self._updateMagnifier(view_pos)

    def leaveEvent(self, event):
        if self._magnifier_active:
            self._magnifier_lens.hide()
            self._magnifier_last_pos = None
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        """Creates context menu (popup menu) for the graphicsview.

        This has to be done by reimplementing the contextMenuEvent handler
        from The QWidget class.
        """

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet(
            """
            QMenu{
                background-color: #EFEFFF;
            }
            QMenu::hover{
                background-color: #B0B0FF;
            }
            """
            )

        if self._magnifier_active:
            toggle_magnifier = self.mw.action_registry.action('view.toggle_magnifier')
            magnifier_zoom_in = self.mw.action_registry.action('view.magnifier_zoom_in')
            magnifier_zoom_out = self.mw.action_registry.action('view.magnifier_zoom_out')
            magnifier_size_up = self.mw.action_registry.action('view.magnifier_size_up')
            magnifier_size_down = self.mw.action_registry.action('view.magnifier_size_down')
            settings_action = self.mw.action_registry.action('tools.settings')

            if toggle_magnifier is not None:
                menu.addAction(toggle_magnifier)
            menu.addSeparator()
            if magnifier_zoom_in is not None:
                menu.addAction(magnifier_zoom_in)
            if magnifier_zoom_out is not None:
                menu.addAction(magnifier_zoom_out)
            menu.addSeparator()
            if magnifier_size_up is not None:
                menu.addAction(magnifier_size_up)
            if magnifier_size_down is not None:
                menu.addAction(magnifier_size_down)
            if settings_action is not None:
                menu.addSeparator()
                menu.addAction(settings_action)

            menu.exec_(self.mapToGlobal(event.pos()))
            event.accept()
            return

        fit_airfoil = self.mw.action_registry.action('view.fit_airfoil')
        fit_all = self.mw.action_registry.action('view.fit_all')
        delete_airfoil = self.mw.action_registry.action('airfoil.delete_active')
        toggle_background = self.mw.action_registry.action('view.toggle_background')
        toggle_magnifier = self.mw.action_registry.action('view.toggle_magnifier')

        if fit_airfoil is not None:
            menu.addAction(fit_airfoil)
        if fit_all is not None:
            menu.addAction(fit_all)
        menu.addSeparator()
        if toggle_magnifier is not None:
            menu.addAction(toggle_magnifier)
        menu.addSeparator()
        if delete_airfoil is not None:
            menu.addAction(delete_airfoil)
        menu.addSeparator()
        if toggle_background is not None:
            menu.addAction(toggle_background)

        menu.exec_(self.mapToGlobal(event.pos()))
        event.accept()

    def _updateMagnifier(self, view_pos):
        if not self._magnifier_active:
            return

        viewport_rect = self.viewport().rect()
        if not viewport_rect.contains(view_pos):
            self._magnifier_lens.hide()
            self._magnifier_last_pos = None
            return

        self._magnifier_last_pos = QtCore.QPoint(view_pos)
        self._magnifier_lens.setMagnification(self._magnifier_magnification)
        self._magnifier_lens.setLensSize(self._magnifier_size)
        self._magnifier_lens.updateLens(view_pos)

    def _adjustMagnifierSize(self, delta):
        self._magnifier_size = self._clampMagnifierSize(self._magnifier_size + delta)
        self._magnifier_lens.setLensSize(self._magnifier_size)

    def _adjustMagnifierMagnification(self, delta):
        self._magnifier_magnification = self._clampMagnification(
            self._magnifier_magnification + delta
        )
        self._magnifier_lens.setMagnification(self._magnifier_magnification)

    def _setMagnifierActionStates(self, magnifier_active):
        action_registry = getattr(self.mw, 'action_registry', None)
        if action_registry is None:
            return

        managed_action_ids = (
            'view.fit_airfoil',
            'view.fit_all',
            'view.toggle_background',
            'view.zoom_in',
            'view.zoom_out',
            'airfoil.delete_active',
        )

        if magnifier_active:
            self._magnifier_action_states = {}
            for action_id in managed_action_ids:
                action = action_registry.action(action_id)
                if action is None:
                    continue
                self._magnifier_action_states[action_id] = action.isEnabled()
                action.setEnabled(False)
            return

        for action_id, was_enabled in self._magnifier_action_states.items():
            action = action_registry.action(action_id)
            if action is not None:
                action.setEnabled(was_enabled)
        self._magnifier_action_states = {}

    def _magnifierWheelSteps(self, event):
        angle_delta = event.angleDelta().y()
        pixel_delta = event.pixelDelta().y()

        if angle_delta:
            self._magnifier_wheel_accumulator += angle_delta / 120.0
        elif pixel_delta:
            self._magnifier_wheel_accumulator += pixel_delta / 40.0
        else:
            return 0

        steps = int(self._magnifier_wheel_accumulator)
        self._magnifier_wheel_accumulator -= steps
        return steps

    def _clampMagnifierSize(self, size):
        return max(
            self.MAGNIFIER_MIN_SIZE,
            min(self.MAGNIFIER_MAX_SIZE, int(round(size))),
        )

    def _clampMagnifierOutlineWidth(self, width):
        return max(
            self.MAGNIFIER_MIN_OUTLINE_WIDTH,
            min(self.MAGNIFIER_MAX_OUTLINE_WIDTH, float(width)),
        )

    def _clampMagnification(self, magnification):
        return max(
            self.MAGNIFIER_MIN_MAGNIFICATION,
            min(self.MAGNIFIER_MAX_MAGNIFICATION, float(magnification)),
        )


class RubberBand(QtWidgets.QRubberBand):
    """Custom rubberband
    from: http://stackoverflow.com/questions/25642618
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.view = args[1]
        self.mw = getattr(self.view, 'mw', get_main_window())

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
        painter = QtGui.QPainter()
        if not painter.begin(self):
            return

        try:
            self.pen.setColor(QtGui.QColor(80, 80, 100))
            self.pen.setWidthF(1.5)
            self.pen.setStyle(QtCore.Qt.DotLine)

            minimum_width = self.mw.RUBBERBAND_MIN * self.view.width()
            minimum_height = self.mw.RUBBERBAND_MIN * self.view.height()
            rect = QPaintEvent.rect()

            # Zoom rect must be at least RUBBERBAND_MIN % of the view size.
            if rect.width() < minimum_width or rect.height() < minimum_height:
                self.brush.setStyle(QtCore.Qt.NoBrush)
                self.allow_zoom = False
            else:
                color = QtGui.QColor(10, 30, 140, 45)
                self.brush.setColor(color)
                self.brush.setStyle(QtCore.Qt.SolidPattern)
                self.allow_zoom = True

            painter.setBrush(self.brush)
            painter.setPen(self.pen)
            painter.drawRect(rect)
        finally:
            painter.end()
