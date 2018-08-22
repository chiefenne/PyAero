import numpy as np
import scipy.spatial as ssp

from PySide2 import QtGui, QtCore


class Connect(object):
    """docstring for Export"""
    def __init__(self):
        super(Connect, self).__init__()

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

    def getVertices(self, block):
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

    def getNearestNeighbours(self, vertices, radius=0.001):
        V = np.array(vertices)
        tree = ssp.cKDTree(V)
        pairs = tree.query_pairs(radius, p=2., eps=0)
        return pairs

    def connectAllBlocks(self, blocks):

        progdialog = QtGui.QProgressDialog(
            "", "Cancel", 0, 3, self.mainwindow)
        progdialog.setWindowTitle('Connect mesh blocks')
        progdialog.setWindowModality(QtCore.Qt.WindowModal)
        progdialog.show()

        progdialog.setValue(0)
        progdialog.setLabelText('connecting part 1/3')

        connected_1 = self.connectBlocks(blocks[0], blocks[1],
                                         radius=0.0001, type_='block')
        progdialog.setValue(1)

        if progdialog.wasCanceled():
            return
        progdialog.setLabelText('connecting part 2/3')

        connected_2 = self.connectBlocks(blocks[2], blocks[3],
                                         radius=0.0001, type_='block')

        progdialog.setValue(2)

        if progdialog.wasCanceled():
            return
        progdialog.setLabelText('connecting part 3/3')

        connected = self.connectBlocks(connected_1, connected_2,
                                       radius=0.0001, type_='connected')

        progdialog.setValue(3)

        return connected

    def connectBlocks(self, block_1, block_2, radius=0.001, type_='block'):

        if type_ == 'block':
            vertices_1 = self.getVertices(block_1)
            vertices_2 = self.getVertices(block_2)
            connectivity_1 = self.getConnectivity(block_1)
            connectivity_2 = self.getConnectivity(block_2)
        if type_ == 'connected':
            vertices_1, connectivity_1 = block_1
            vertices_2, connectivity_2 = block_2

        vertices = vertices_1 + vertices_2
        lv1 = len(vertices_1)

        connectivity_2mod = list()
        for cell in connectivity_2:
            new_cell = [vertex+lv1 for vertex in cell]
            connectivity_2mod.append(new_cell)

        pairs = self.getNearestNeighbours(vertices, radius=radius)
        pairs = list(pairs)
        I, J = zip(*pairs)

        # this is dirty, but seems to work
        # vertices which are not used need somehow to be
        # "removed" without removing them
        # so that they later can not be found again in nearest neighbour search
        for vertex_id in J:
            vertices[vertex_id] = (15.+np.random.random_sample(),
                                   15.+np.random.random_sample())

        connectivity_2_new = list()
        for cell in connectivity_2mod:
            new_cell = list()
            for vertex in cell:
                new_vertex = vertex
                if vertex in J:
                    new_vertex = I[J.index(vertex)]
                new_cell.append(new_vertex)
            connectivity_2_new.append(new_cell)

        connectivity = connectivity_1 + connectivity_2_new

        return (vertices, connectivity)
