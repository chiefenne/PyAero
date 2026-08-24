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

    def render_unstructured_mesh(self, target, mesh_data):
        self._remove_scene_item(getattr(target, 'mesh', None))

        edge_items = []
        seen_edges = set()
        vertices = getattr(mesh_data, 'vertices', None)
        connectivity = getattr(mesh_data, 'connectivity', None)
        if vertices is None or connectivity is None:
            return None

        for cell in connectivity:
            count = len(cell)
            for index in range(count):
                a_value = int(cell[index])
                b_value = int(cell[(index + 1) % count])
                edge = self._sorted_edge((a_value, b_value))
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                line = (
                    vertices[edge[0]],
                    vertices[edge[1]],
                )
                edge_items.append(
                    self._make_polyline_item(
                        line,
                        color=QtGui.QColor(0, 0, 0, 255),
                        width=0.7,
                    )
                )

        target.mesh = self.mw.scene.createItemGroup(edge_items)
        target.mesh.setVisible(True)
        self._set_checkbox('mesh_checkbox', checked=True, enabled=True)
        return target.mesh

    def render_block_outline(self, airfoil, blocks, *, layout_plan=None):
        self._remove_scene_item(getattr(airfoil, 'mesh_blocks', None))
        outline_items = []
        blocks = list(blocks)

        if (
                layout_plan is not None and (
                    getattr(layout_plan, 'singularities', None) or
                    getattr(layout_plan, 'separatrices', None)
                )):
            outline_items.extend(self._make_layout_outline_items(layout_plan))

        if not outline_items:
            for block in blocks:
                for lines in (block.getULines(), block.getVLines()):
                    for line in (lines[0], lines[-1]):
                        outline_items.append(
                            self._make_polyline_item(
                                line,
                                color=QtGui.QColor(220, 38, 38, 255),
                                width=3.0,
                            )
                        )

        airfoil.mesh_blocks = self.mw.scene.createItemGroup(outline_items)
        airfoil.mesh_blocks.setVisible(True)
        self._set_checkbox('mesh_blocks_checkbox', checked=True, enabled=True)
        return airfoil.mesh_blocks

    def render_constraint_outline(self, target, loops):
        self._remove_scene_item(getattr(target, 'mesh_blocks', None))
        red = QtGui.QColor(220, 38, 38, 255)
        outline_items = []

        for loop in loops or []:
            points = getattr(loop, 'points', loop)
            outline_items.append(
                self._make_polyline_item(
                    points,
                    color=red,
                    width=2.2,
                )
            )

        target.mesh_blocks = self.mw.scene.createItemGroup(outline_items)
        target.mesh_blocks.setVisible(True)
        self._set_checkbox('mesh_blocks_checkbox', checked=True, enabled=True)
        return target.mesh_blocks

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

    def _make_layout_outline_items(self, layout_plan):
        red = QtGui.QColor(220, 38, 38, 255)
        items = []

        if getattr(layout_plan, 'outer_boundary', None) is not None:
            items.append(
                self._make_polyline_item(
                    layout_plan.outer_boundary,
                    color=red,
                    width=2.6,
                )
            )

        for loop in getattr(layout_plan, 'boundary_loops', []) or []:
            items.append(
                self._make_polyline_item(
                    loop,
                    color=red,
                    width=2.2,
                )
            )

        for separatrix in getattr(layout_plan, 'separatrices', []) or []:
            items.append(
                self._make_polyline_item(
                    separatrix,
                    color=red,
                    width=2.2,
                )
            )

        marker_size = self._marker_size(layout_plan)
        for singularity in getattr(layout_plan, 'singularities', []) or []:
            items.append(
                self._make_singularity_item(
                    singularity,
                    color=red,
                    size=marker_size,
                )
            )

        return items

    def _marker_size(self, layout_plan):
        outer = getattr(layout_plan, 'outer_boundary', None)
        if outer is None or len(outer) == 0:
            return 0.03

        x_values = [float(point[0]) for point in outer]
        y_values = [float(point[1]) for point in outer]
        diagonal = ((max(x_values) - min(x_values)) ** 2 +
                    (max(y_values) - min(y_values)) ** 2) ** 0.5
        return max(0.008, 0.0012 * diagonal)

    def _make_singularity_item(self, singularity, *, color, size):
        metadata = getattr(singularity, 'metadata', {}) or {}
        dx, dy = metadata.get('display_offset', (0.0, 0.0))
        x_value = float(singularity.position[0]) + float(dx)
        y_value = float(singularity.position[1]) + float(dy)
        kind = str(getattr(singularity, 'kind', 'boundary')).strip().lower()
        label = metadata.get('label', kind.title())

        if kind == 'boundary':
            marker = gic.GraphicsCollection()
            points = QtGui.QPolygonF([
                QtCore.QPointF(x_value, y_value + size),
                QtCore.QPointF(x_value + size, y_value),
                QtCore.QPointF(x_value, y_value - size),
                QtCore.QPointF(x_value - size, y_value),
            ])
            marker.Polygon(points, label)
        else:
            marker = gic.GraphicsCollection()
            marker.Circle(x_value, y_value, size)
            marker.setTooltip(label)

        marker.pen.setColor(color)
        marker.pen.setWidthF(1.5)
        marker.pen.setCosmetic(True)
        marker.brush.setColor(QtGui.QColor(color.red(), color.green(), color.blue(), 80))
        marker.brush.setStyle(QtCore.Qt.SolidPattern)
        return GraphicsItem.GraphicsItem(marker)

    @staticmethod
    def _sorted_edge(edge):
        a_value = int(edge[0])
        b_value = int(edge[1])
        return (a_value, b_value) if a_value <= b_value else (b_value, a_value)

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
