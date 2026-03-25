from __future__ import annotations

from PySide6 import QtGui, QtCore

import GraphicsItemsCollection as gic
import GraphicsItem
from Utils import get_main_window, scalar_to_rgb


class MeshSceneRenderer:
    """Qt scene renderer for mesh-related graphics items."""

    def __init__(self, mainwindow=None):
        self.mw = mainwindow or get_main_window()

    def render_mesh(self, airfoil, blocks):
        self._set_item_visibility(getattr(airfoil, 'splineMarkersGroup', None),
                                  visible=False)
        self._set_checkbox(
            'airfoil_spline_points_checkbox',
            checked=False,
        )

        self._remove_scene_item(getattr(airfoil, 'mesh', None))
        mesh_items = []
        for block in blocks:
            for lines in (block.getULines(), block.getVLines()):
                for line in lines:
                    mesh_items.append(
                        self._make_polyline_item(
                            line,
                            color=QtGui.QColor(0, 0, 0, 255),
                            width=0.8,
                        )
                    )

        airfoil.mesh = self.mw.scene.createItemGroup(mesh_items)
        self._set_checkbox('mesh_checkbox', checked=True, enabled=True)
        return airfoil.mesh

    def render_block_outline(self, airfoil, blocks):
        self._remove_scene_item(getattr(airfoil, 'mesh_blocks', None))
        outline_items = []
        for block in blocks:
            for lines in (block.getULines(), block.getVLines()):
                for line in (lines[0], lines[-1]):
                    outline_items.append(
                        self._make_polyline_item(
                            line,
                            color=QtGui.QColor(202, 31, 123, 255),
                            width=3.0,
                        )
                    )

        airfoil.mesh_blocks = self.mw.scene.createItemGroup(outline_items)
        airfoil.mesh_blocks.setVisible(False)
        self._set_checkbox('mesh_blocks_checkbox', checked=False, enabled=True)
        return airfoil.mesh_blocks

    def render_mesh_quality(self, vertices, connectivity, quality, airfoil=None):
        if airfoil is not None:
            self._remove_scene_item(getattr(airfoil, 'mesh_quality', None))

        quads = []
        colors = [scalar_to_rgb(q, range='256') for q in quality]
        for index, cell in enumerate(connectivity):
            quad = gic.GraphicsCollection()
            points = [QtCore.QPointF(*vertices[vertex]) for vertex in cell]
            quad.Polygon(QtGui.QPolygonF(points), '')
            quad.pen.setColor(QtGui.QColor(0, 0, 0, 255))
            quad.brush.setColor(QtGui.QColor(*colors[index]))
            quad.pen.setWidthF(0.8)
            quad.pen.setCosmetic(True)
            quads.append(GraphicsItem.GraphicsItem(quad))

        group = self.mw.scene.createItemGroup(quads)
        if airfoil is not None:
            airfoil.mesh_quality = group
        return group

    def _make_polyline_item(self, line, color, width):
        contour = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in line]
        contour.Polyline(QtGui.QPolygonF(points), '')
        contour.pen.setColor(color)
        contour.pen.setWidthF(width)
        contour.pen.setCosmetic(True)
        contour.brush.setStyle(QtCore.Qt.NoBrush)
        return GraphicsItem.GraphicsItem(contour)

    def _remove_scene_item(self, item):
        if item is None:
            return
        if item.scene() is not None:
            item.scene().removeItem(item)

    def _set_item_visibility(self, item, visible: bool):
        if item is not None:
            item.setVisible(visible)

    def _set_checkbox(self, name, checked=None, enabled=None):
        checkbox = getattr(self.mw.mainArea, name, None)
        if checkbox is None:
            return
        if checked is not None:
            checkbox.setChecked(checked)
        if enabled is not None:
            checkbox.setEnabled(enabled)
