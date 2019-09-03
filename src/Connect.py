from collections import Counter

import numpy as np
from scipy import spatial

from PySide2 import QtCore


class Connect:
    """docstring"""

    def __init__(self, progdialog):

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

        self.progdialog = progdialog

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

    def getNearestNeighboursPairs(self, vertices, radius=1.e-6):
        tree = spatial.cKDTree(vertices)
        pairs = tree.query_pairs(radius, p=2., eps=0)
        return pairs

    def getNearestNeighboursBiDirectional(d1, d2, radius=1.e-6):
        """Get all indices ofts in d1 which are within distance r to d2"""
        tree_1 = spatial.cKDTree(d1)
        tree_2 = spatial.cKDTree(d2)
        idx1 = tree_2.query_ball_tree(tree_1, radius, p=2., eps=0)
        idx2 = tree_1.query_ball_tree(tree_2, radius, p=2., eps=0)
        matching = [e[0] for e in idx1 if e]
        opposite = [e[0] for e in idx2 if e]
        return matching, opposite

    def getNearestNeighbours(self, vertices, neighbours, radius=1.e-6):
        """Get the nearest neighbours to each vertex in a list of vertices

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

        connectivity_shifted = list()
        for cell in connectivity:
            new_cell = [vertex + shift for vertex in cell]
            connectivity_shifted.append(new_cell)

        return connectivity_shifted

    def connectAllBlocks(self, blocks):

        # compile global vertex list and cell connectivity from all blocks
        vertices = list()
        connectivity = list()

        for block in blocks:
            # needs to be set here (vertices up to block - 1)
            shift = len(vertices)
            vertices += [vertex for vertex in self.getVertices(block)]
            # shift the block connectivity by accumulated number of vertices
            # from all blocks before this one
            connectivity_block = \
                self.shiftConnectivity(self.getConnectivity(block), shift)
            connectivity += [tuple(cell) for cell in connectivity_block]

        self.progdialog.setValue(80)

        vertices = [(vertex[0], vertex[1]) for vertex in vertices]

        # search all vertices against themselves
        # finds itself AND multiple connections
        vertex_and_neighbours = self.getNearestNeighbours(vertices,
                                                          vertices,
                                                          radius=1.e-6)

        # substitute vertex ids in connectivity at block connections
        modified = list()
        connectivity_connected = list()
        for cell in connectivity:
            cell_new = list()
            for node in cell:
                node_new = min(vertex_and_neighbours[node])
                cell_new.append(node_new)
            connectivity_connected.append(cell_new)
            if tuple(cell) != tuple(cell_new):
                modified.append((tuple(cell), tuple(cell_new)))

        with open('vertex_and_neighbours.txt', 'w') as f:
            for vn in vertex_and_neighbours:
                f.write(str(vn) + ' ' + str(vertex_and_neighbours[vn]) + '\n')
        with open('vertex_and_neighbours_2.txt', 'w') as f:
            for vn in vertex_and_neighbours:
                if len(vertex_and_neighbours[vn]) == 2:
                    f.write(str(vn) + ' ' + str(vertex_and_neighbours[vn]) +
                            '\n')
        with open('vertex_and_neighbours_3.txt', 'w') as f:
            for vn in vertex_and_neighbours:
                if len(vertex_and_neighbours[vn]) > 2:
                    f.write(str(vn) + ' ' + str(vertex_and_neighbours[vn]) +
                            '\n')
        with open('block_connections.txt', 'w') as f:
            for m in modified:
                f.write(str(m) + '\n')

        self.progdialog.setValue(90)

        return (vertices, connectivity_connected, self.progdialog)
