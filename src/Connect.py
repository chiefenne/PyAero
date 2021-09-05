import copy

import numpy as np
from scipy import spatial

from PySide6 import QtCore

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

        connectivity_shifted = list()
        for cell in connectivity:
            new_cell = [vertex + shift for vertex in cell]
            connectivity_shifted.append(new_cell)

        return connectivity_shifted

    def connectAllBlocks(self, blocks):

        # compile global vertex list and cell connectivity from all blocks
        vertices = list()
        connectivity = list()

        for i, block in enumerate(blocks):

            # accumulated number of vertices
            # for i = 0 shift is automatically 0
            # so the connectivity of the first block doesn't get shifted
            # thus, this variable must be set before 'vertices += ...'
            shift = len(vertices)
            print('Shift in block {}: {}'.format(i, shift))

            # concatenate vertices of all blocks
            # vertices += [vertex for vertex in self.getVertices(block)]
            vertices += self.getVertices(block)

            # shift the block connectivity by accumulated number of vertices
            # from all blocks before this one
            connectivity_block = \
                self.shiftConnectivity(self.getConnectivity(block), shift)
            connectivity += [tuple(cell) for cell in connectivity_block]

        self.progdialog.setValue(80)

        # FIXME
        # FIXME for some reason tuples need to be redefined
        # FIXME
        vertices = [(vertex[0], vertex[1]) for vertex in vertices]

        # search vertices of all blocks against themselves
        # finds itself AND multiple connections very fast
        # uses Scipy kd-tree for quick nearest-neighbor lookup
        # the distance tolerance is specified via the radius variable
        vertex_and_neighbours = self.getNearestNeighbours(vertices,
                                                          vertices,
                                                          radius=1.e-6)

        # substitute vertex ids in connectivity at block connections
        connectivity_connected = list()
        for cell in connectivity:
            cell_new = list()
            for node in cell:
                # if there is only one cell in vertex_and_neighbours,
                # then it is taken as it is
                # if there is more than one cell,
                # then the minimum vertex index is used
                # so a few vertices remain unused and need to be removed later
                node_new = min(vertex_and_neighbours[node])
                cell_new.append(node_new)
            connectivity_connected.append(cell_new)

        # DEBUG
        with open('vertices.dat', 'w') as f:
            for i, vertex in enumerate(vertices):
                f.write('{:8d} {:10.6f} {:10.6f}\n'.format(i, vertex[0], vertex[1]))
        with open('connectivity.dat', 'w') as f:
            for i, cell in enumerate(connectivity):
                f.write('{:8d}'.format(i) + ' '.join(['{:8d}'.format(c) for c in cell]) + '\n')
        with open('connectivity_connected.dat', 'w') as f:
            for i, cell in enumerate(connectivity_connected):
                f.write('{:8d}'.format(i) + ' '.join(['{:8d}'.format(c) for c in cell]) + '\n')

        connectivity_array = np.array(connectivity)
        cconnectivity_connected_array = np.array(connectivity_connected)

        self.progdialog.setValue(90)

        connectivity_clean = copy.deepcopy(connectivity_connected)

        return (vertices, connectivity, self.progdialog)
