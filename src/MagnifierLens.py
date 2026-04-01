from __future__ import annotations

import math

from PySide6 import QtCore, QtGui, QtWidgets


class _MagnifierRingOverlay(QtWidgets.QWidget):
    def __init__(self, parent, outline_color):
        super().__init__(parent)
        self._outline_color = QtGui.QColor(outline_color)
        self._outline_width = 2.0

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    def setOutlineWidth(self, width):
        self._outline_width = max(1.0, min(8.0, float(width)))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setBrush(QtCore.Qt.NoBrush)

        margin = self._outline_width / 2.0 + 1.5
        ring_rect = QtCore.QRectF(self.rect()).adjusted(
            margin,
            margin,
            -margin,
            -margin,
        )

        pen = QtGui.QPen(self._outline_color, self._outline_width)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawEllipse(ring_rect)


class MagnifierLensWidget(QtWidgets.QWidget):
    OUTLINE_COLOR = QtGui.QColor(38, 58, 90, 230)

    def __init__(self, main_view):
        super().__init__(main_view.viewport())
        self._main_view = main_view
        self._magnification = 2.0
        self._outline_width = 2.0

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self._lens_view = QtWidgets.QGraphicsView(main_view.scene(), self)
        self._lens_view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._lens_view.setLineWidth(0)
        self._lens_view.setInteractive(False)
        self._lens_view.setFocusPolicy(QtCore.Qt.NoFocus)
        self._lens_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._lens_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._lens_view.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self._lens_view.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self._lens_view.setViewportUpdateMode(main_view.viewportUpdateMode())
        self._lens_view.setRenderHints(main_view.renderHints())
        self._lens_view.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._lens_view.viewport().setAttribute(
            QtCore.Qt.WA_TransparentForMouseEvents,
            True,
        )
        self._ring_overlay = _MagnifierRingOverlay(self, self.OUTLINE_COLOR)

        self.syncFromMainView()
        self.hide()

    def setLensSize(self, diameter):
        diameter = max(64, int(round(diameter)))
        self.resize(diameter, diameter)
        self._updateLensGeometry()
        self.update()

    def setMagnification(self, magnification):
        self._magnification = max(1.0, float(magnification))

    def setOutlineWidth(self, width):
        self._outline_width = max(1.0, min(8.0, float(width)))
        self._ring_overlay.setOutlineWidth(self._outline_width)
        self._updateLensGeometry()
        self.update()

    def syncFromMainView(self):
        if self._lens_view.scene() is not self._main_view.scene():
            self._lens_view.setScene(self._main_view.scene())

        self._lens_view.setRenderHints(self._main_view.renderHints())
        self._lens_view.setViewportUpdateMode(self._main_view.viewportUpdateMode())
        self._lens_view.setStyleSheet(self._main_view.styleSheet())

    def updateLens(self, view_pos):
        self.syncFromMainView()

        scene_pos = self._main_view.mapToScene(view_pos)
        transform = QtGui.QTransform(self._main_view.transform())
        transform.scale(self._magnification, self._magnification)

        self._lens_view.setTransform(transform)
        self._lens_view.centerOn(scene_pos)
        self._moveLens(view_pos)
        self.show()
        self.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._updateLensGeometry()

    def paintEvent(self, event):
        super().paintEvent(event)

    def _updateLensGeometry(self):
        self._ring_overlay.setGeometry(self.rect())
        self._ring_overlay.raise_()

        margin = max(6, int(math.ceil(self._outline_width)) + 4)
        inner_rect = self.rect().adjusted(
            margin,
            margin,
            -margin,
            -margin,
        )
        self._lens_view.setGeometry(inner_rect)
        self._lens_view.setMask(QtGui.QRegion(inner_rect, QtGui.QRegion.Ellipse))

    def _moveLens(self, view_pos):
        diameter = self.width()
        radius = diameter // 2
        parent_rect = self.parentWidget().rect()

        x_pos = view_pos.x() - radius
        y_pos = view_pos.y() - radius

        x_pos = max(0, min(x_pos, max(0, parent_rect.width() - diameter)))
        y_pos = max(0, min(y_pos, max(0, parent_rect.height() - diameter)))

        self.move(x_pos, y_pos)
