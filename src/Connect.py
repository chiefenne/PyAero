from __future__ import annotations

import os

import numpy as np
from scipy import spatial

class Connect:
    """Merge structured mesh blocks into a single vertex/connectivity set."""

    MERGE_RADIUS = 1.0e-6

    def __init__(self, progdialog=None, progress_callback=None):
        self.progdialog = progdialog
        self.progress_callback = progress_callback
        if self.progress_callback is None and progdialog is not None:
            callback = getattr(progdialog, 'setValue', None)
            if callable(callback):
                self.progress_callback = callback

    def _setProgress(self, value):
        if self.progress_callback is not None:
            self.progress_callback(value)

    def getVertices(self, block):
        """Make a list of point tuples from a BlockMesh object

        Args:
            block (BlockMesh): BlockMesh object

        Returns:
            list: list of point tuples
                  # [(x1, y1), (x2, y2), (x3, y3), ... , (xn, yn)]
        """
        vertices = list()
        for uline in block.getULines():
            vertices += uline
        return vertices

    def getConnectivity(self, block):

        connectivity = list()

        U, V = block.getDivUV()
        up = U + 1
        for u in range(U):
            for v in range(V):
                p1 = v * up + u
                p2 = p1 + up
                p3 = p2 + 1
                p4 = p1 + 1
                connectivity.append((p1, p2, p3, p4))

        return connectivity

    def getMinMaxConnectivityIDs(self, connectivity):
        id_min = 1e10
        id_max = -1
        for cell in connectivity:
            for id in cell:
                id_min = min(id_min, id)
                id_max = max(id_max, id)
        return id_min, id_max

    def getNearestNeighboursPairs(self, vertices, radius=1.e-6):
        tree = spatial.cKDTree(vertices)
        pairs = tree.query_pairs(radius, p=2., eps=0)
        return pairs

    @staticmethod
    def getNearestNeighboursBiDirectional(d1, d2, radius=1.e-6):
        """Get matching point indices between two point sets within ``radius``."""
        tree_1 = spatial.cKDTree(d1)
        tree_2 = spatial.cKDTree(d2)
        idx1 = tree_2.query_ball_tree(tree_1, radius, p=2., eps=0)
        idx2 = tree_1.query_ball_tree(tree_2, radius, p=2., eps=0)
        matching = [e[0] for e in idx1 if e]
        opposite = [e[0] for e in idx2 if e]
        return matching, opposite

    def getNearestNeighbours(self, vertices, neighbours, radius=1.e-6):
        """Get the nearest neighbours to each vertex in a list of vertices
        uses Scipy kd-tree for quick nearest-neighbor lookup

        Args:
            vertices (list of tuples): Vertices for which nearest neighbours
                                       should be searched
            neighbours (list of tuples): These are the neighbours which
                                         are being searched
            radius (float, optional): Search neighbours within this radius

        Returns:
            vertex_and_neighbours(dictionary): Contains vertices searched
                                               as key and a list of nearest
                                               neighbours as values
        """

        # setup k-dimensional tree
        tree = spatial.cKDTree(neighbours)

        vertex_and_neighbours = dict()
        for vertex_id, vertex in enumerate(vertices):
            vertex_and_neighbours[vertex_id] = \
                tree.query_ball_point(vertex, radius)

        return vertex_and_neighbours

    def shiftConnectivity(self, connectivity, shift):

        if shift == 0:
            return connectivity

        return [
            tuple(vertex + shift for vertex in cell)
            for cell in connectivity
        ]

    def _collectBlocks(self, blocks):
        vertices = []
        connectivity = []

        for block in blocks:
            shift = len(vertices)
            vertices.extend(self.getVertices(block))
            connectivity.extend(
                self.shiftConnectivity(self.getConnectivity(block), shift)
            )

        return vertices, connectivity

    def _mergeConnectivity(self, vertices, connectivity):
        vertex_and_neighbours = self.getNearestNeighbours(
            vertices,
            vertices,
            radius=self.MERGE_RADIUS,
        )
        connectivity_connected = [
            [min(vertex_and_neighbours[node]) for node in cell]
            for cell in connectivity
        ]

        return np.asarray(connectivity), np.asarray(connectivity_connected)

    def _compactConnectivity(self, vertices, unconnected, connected):
        deleted_nodes = np.unique(unconnected[np.where(connected != unconnected)])

        if deleted_nodes.size:
            keep_mask = np.ones(len(vertices), dtype=bool)
            keep_mask[deleted_nodes] = False
            vertices_clean = [
                vertex for vertex, keep in zip(vertices, keep_mask) if keep
            ]
        else:
            vertices_clean = list(vertices)

        remaining_nodes = np.setdiff1d(np.unique(connected), deleted_nodes)
        mapping = {node: index for index, node in enumerate(remaining_nodes)}
        mapping_keys = np.array(list(mapping.keys()))
        mapping_values = np.array(list(mapping.values()))
        mapping_array = np.zeros(mapping_keys.max() + 1, dtype=mapping_values.dtype)
        mapping_array[mapping_keys] = mapping_values
        connectivity_clean = mapping_array[connected]

        return vertices_clean, connectivity_clean, deleted_nodes

    def connectAllBlocks(self, blocks):

        if not blocks:
            return [], np.empty((0, 4), dtype=int)

        # compile global vertex list and cell connectivity from all blocks
        vertices, connectivity = self._collectBlocks(blocks)

        self._setProgress(80)

        # BlockMesh stores vertices as plain 2D float tuples, so connectivity
        # merging can work directly on the collected point data.
        unconnected, connected = self._mergeConnectivity(vertices, connectivity)
        vertices_clean, connectivity_clean, deleted_nodes = self._compactConnectivity(
            vertices,
            unconnected,
            connected,
        )

        self._setProgress(90)

        # DEBUGGING
        # self.write_debug(unconnected, connected, deleted_nodes, vertices, vertices_clean, connectivity_clean)
        # self.draw_connectivity(vertices, deleted_nodes)

        return vertices_clean, connectivity_clean

    def draw_connectivity(self, vertices, deleted_nodes, scene):
        from PySide6 import QtGui

        import GraphicsItemsCollection as gic
        import GraphicsItem

        self.connections = list()

        # instantiate a graphics item
        marker = gic.GraphicsCollection()
         # set its properties
        marker.pen.setColor(QtGui.QColor(60, 60, 255, 255))
        marker.brush.setColor(QtGui.QColor(255, 50, 50, 230))
        marker.pen.setWidthF(1.6)
        # no pen thickness change when zoomed
        marker.pen.setCosmetic(True)

        for node in deleted_nodes:
            marker.Circle(vertices[node][0], vertices[node][1], 0.003)
            marker_item = GraphicsItem.GraphicsItem(marker)
            self.connections.append(marker_item)
            
        # add to the scene
        self.connections = scene.createItemGroup(self.connections)

    def write_debug(self, unconnected, connected, deleted_nodes, vertices,
                    vertices_clean, connectivity_clean):
        debug_data = {
            'unconnected': unconnected,
            'connected': connected,
            'deleted_nodes': deleted_nodes,
            'vertices': vertices,
            'vertices_clean': vertices_clean,
            'connectivity_clean': connectivity_clean
        }

        folder = 'debug'
        os.makedirs(folder, exist_ok=True)

        for name, data in debug_data.items():
            with open(os.path.join(folder, f'{name}.txt'), 'w',
                      encoding='utf-8') as f:
                f.writelines(f'{item}\n' for item in data)
