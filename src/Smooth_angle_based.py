
import copy
from distutils.debug import DEBUG
from types import prepare_class

import numpy as np

from PySide6 import QtGui, QtCore

import GraphicsItemsCollection as gic
import GraphicsItem
import Connect
import logging
logger = logging.getLogger(__name__)

class SmoothAngleBased:
    """Mesh smoothing based on the paper:

    An Angular Method with Position Control for Block Mesh Squareness Improvement
    by Jin Yao, Douglas Stillman

    There are several errors in the paper.
    Nevertheless, the idea and algorithm description are formulated very clear.

    The errors are in the summation over all 12 angles, which in fact needs
    to be split into four for the alphas and eight for the betas.
    Therefore also the depicted derivatives are wrong as well as
    the inverse Hessian for the Newton optimization iterations.

    This class contains the corrected equations. 
    """

    def __init__(self, data, data_source='block'):
        
        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

        # data_source is one of 'block' or 'mesh'
        if data_source == 'block':
            self.block = data
            connect = Connect.Connect(None)
            vertices = connect.getVertices(self.block)
            connectivity = connect.getConnectivity(self.block)
            self.mesh = vertices, connectivity
        if data_source == 'mesh':
            self.mesh = data

        lvc = self.makeLVC()
        self.stencils = self.make_stencil(lvc)

        self.drawlines = None

    def makeLVC(self):
        _, connectivity = self.mesh
        nodes = set([node for cell in connectivity for node in cell])

        self.lvc = dict()
        conn = np.array(connectivity)

        for node in nodes:
            cells, _ = np.where(conn == node)
            self.lvc.setdefault(node, []).append([conn[cell] for cell in cells])

        return self.lvc

    def make_stencil(self, lvc, verbose=False):     
        # lvc is a dictionary
        self.stencils = dict()
        for idx in range(len(lvc)):
            v, c = np.unique(lvc[idx], return_counts=True)
            vertices_quad = v[np.argwhere(c==1)]
            vertices_star = v[np.argwhere(c==2)]
    
            cells_with_common_edges = list()
            if len(vertices_star) != 4:
                continue
            
            for vertex in vertices_star:
                mask = np.isin(lvc[idx], [vertex[0], idx])
                mask1 = np.count_nonzero(mask, axis=1) == 2
                cells_with_common_edges.append(np.array(lvc[idx])[mask1])

            if idx == 6 and verbose:
            
                for cells in cells_with_common_edges:
                    mask2 = np.isin(cells, np.append(vertices_star.flatten(), idx))
    
            corresponding_corners = list()
            for cells in cells_with_common_edges:
                mask2 = np.isin(cells, np.append(vertices_star.flatten(), idx))
                corresponding_corners.append(cells[~mask2])
    
            self.stencils[idx] = corresponding_corners
    
        return self.stencils

    def make_cardinals(self, vertices):

        cardinals = dict()
        
        for stencil in self.stencils:
            s = self.stencils[stencil]

            D = [vertices[s[2][0]][0], vertices[s[2][0]][1]]
            EE = [vertices[s[0][0]][0], vertices[s[0][0]][1]]
            F = [vertices[s[1][1]][0], vertices[s[1][1]][1]]
            G = [vertices[s[0][1]][0], vertices[s[0][1]][1]]

            S = (0.5 * (D[0] + EE[0]), 0.5 * (D[1] + EE[1]))
            W = (0.5 * (D[0] + G[0]), 0.5 * (D[1] + G[1]))
            E = (0.5 * (EE[0] + F[0]), 0.5 * (EE[1] + F[1]))
            N = (0.5 * (G[0] + F[0]), 0.5 * (G[1] + F[1]))
            cardinals[stencil] = (S, W, E, N, D, EE, F, G)
        return cardinals

    def draw_cardinal(self, S, W, E, N, D, EE, F, G):

        self.drawlines = list()

        gc = gic.GraphicsCollection()

        points = [QtCore.QPointF(x, y) for x, y in [S, N]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(255, 0, 0, 255))
        gc.pen.setWidthF(3.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)

        gc = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in [E, W]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(0, 255, 0, 255))
        gc.pen.setWidthF(3.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)

        gc = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in [D, EE, F, G, D]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(0, 0, 255, 255))
        gc.pen.setWidthF(5.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)

        '''
        gc = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in [EE, G]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(0, 255, 255, 255))
        gc.pen.setWidthF(9.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)

        gc = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in [D, G]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(255, 0, 255, 255))
        gc.pen.setWidthF(9.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)

        gc = gic.GraphicsCollection()
        points = [QtCore.QPointF(x, y) for x, y in [D, F]]
        gc.Polyline(QtGui.QPolygonF(points), '')
        gc.pen.setColor(QtGui.QColor(0, 0, 0, 255))
        gc.pen.setWidthF(9.0)
        gc.pen.setCosmetic(True)
        gc.brush.setStyle(QtCore.Qt.NoBrush)
        meshline = GraphicsItem.GraphicsItem(gc)
        self.drawlines.append(meshline)
        '''

        # self.mainwindow.scene.createItemGroup(self.drawlines)

    def smooth(self, iterations=20, tolerance=1.e-4, verbose=False):

        # iterations=1

        vertices, _ = self.mesh
    
        cardinals = self.make_cardinals(vertices)

        smoothed_vertices = copy.deepcopy(vertices)
        smoothed_vertices_old = copy.deepcopy(vertices)
    
        corner = False
        omega = 1
        if corner:
            omega = 0

        # loop until convergence
        iteration = 0
        while iteration < iterations:
            iteration += 1

            # loop over all stencils (for vertices to be smoothed)
            for ic, cardinal in enumerate(cardinals):

                (x, y) = smoothed_vertices[cardinal]
                (xold, yold) = smoothed_vertices_old[cardinal]

                S, W, E, N, D, EE, F, G = cardinals[cardinal]

                DEBUG = False
                if DEBUG and ic == 143:
                    self.draw_cardinal(S, W, E, N, D, EE, F, G)
                    # print('ic, cardinal', ic, cardinal)
                    # print('Stencil', self.stencils[cardinal])

                # calculate position control
                NS = np.linalg.norm( (S[0] - N[0], S[1] - N[1]) )
                WE = np.linalg.norm( (E[0] - W[0], E[1] - W[1]) )
                sigma = np.max((NS/WE, WE/NS))

                # angles alpha
                a1 = np.array([S[0], E[0], N[0], W[0]])
                a2 = np.array([E[0], N[0], W[0], S[0]])
                b1 = np.array([S[1], E[1], N[1], W[1]])
                b2 = np.array([E[1], N[1], W[1], S[1]])

                # angles beta
                c1 = np.array([S[0], S[0], E[0], E[0], N[0], N[0], W[0], W[0]])
                c2 = np.array([D[0], EE[0], EE[0], F[0], F[0], G[0], G[0], D[0]])
                d1 = np.array([S[1], S[1], E[1], E[1], N[1], N[1], W[1], W[1]])
                d2 = np.array([D[1], EE[1], EE[1], F[1], F[1], G[1], G[1], D[1]])

                # derivatives of alpha contributions (including position control)
                ca = np.sum(omega / ( (a1**2 + b1**2 - 2*a1*xold + xold**2 - 2*b1*yold + yold**2) * \
                                      (a2**2 + b2**2 - 2*a2*xold + xold**2 - 2*b2*yold + yold**2) + 1.e-9))                
                dTdx_alpha = np.sum(-(a1*a2 + b1*b2 - a1*x - a2*x + x**2 - b1*y - b2*y + y**2) * \
                                (a1 + a2 - 2.*x) - (a1 + a1 + a1 + a1 - 4.*x) * sigma)
                dTdy_alpha = np.sum(-(a1*a2 + b1*b2 - a1*x - a2*x + x**2 - b1*y - b2*y + y**2) * \
                                (b1 + b2 - 2*y) - (b1 + b1 + b1 + b1 - 4*y)*sigma)
                d2Tdx2_alpha = np.sum((a1 + a2 - 2*x)**2 + 2*a1*a2 + 2*b1*b2 - 2*a1*x - 2*a2*x + 2*x**2 - \
                                2*b1*y - 2*b2*y + 2*y**2 + 4*sigma)
                d2Tdy2_alpha = np.sum(2*a1*a2 + (b1 + b2 - 2*y)**2 + 2*b1*b2 - 2*a1*x - 2*a2*x + 2*x**2 - \
                                2*b1*y - 2*b2*y + 2*y**2 + 4*sigma)
                d2Tdxdy_alpha = np.sum((a1 + a2 - 2*x)*(b1 + b2 - 2*y))

                # derivatives of beta contributions (including position control)
                cb = np.sum(omega / ((c1**2 - 2*c1*c2 + c2**2 + d1**2 - 2*d1*d2 + d2**2) * \
                                        (c1**2 + d1**2 - 2*c1*xold + xold**2 - 2*d1*yold + yold**2) + 1.e-9))
                dTdx_beta = np.sum(-(c1**2 - c1*c2 + d1**2 - d1*d2 - c1*x + c2*x - d1*y + d2*y) * (c1 - c2) -\
                                        (a1[0] + a1[1] + a1[2] + a1[3] - 4.*x)*sigma)
                dTdy_beta = np.sum(-(c1**2 - c1*c2 + d1**2 - d1*d2 - c1*x + c2*x - d1*y + d2*y) * (d1 - d2) -\
                                        (b1[0] + b1[1] + b1[2] + b1[3] - 4*y)*sigma)
                d2Tdx2_beta = np.sum((c1 - c2)**2 + 4*sigma)
                d2Tdy2_beta = np.sum((d1 - d2)**2 + 4*sigma)
                d2Tdxdy_beta = np.sum((c1 - c2)*(d1 - d2))

                # compile derivatives of all contributions
                dTdx = ca * dTdx_alpha + cb * dTdx_beta
                dTdy = ca * dTdy_alpha + cb * dTdy_beta
                d2Tdx2 = ca * d2Tdx2_alpha + cb * d2Tdx2_beta
                d2Tdy2 = ca * d2Tdy2_alpha + cb * d2Tdy2_beta
                d2Tdxdy = ca * d2Tdxdy_alpha + cb * d2Tdxdy_beta

                # Newton iteration for optimization
                xnew = x - [d2Tdy2 * dTdx - d2Tdxdy * dTdy] / (d2Tdx2 * d2Tdy2 - (d2Tdxdy)**2)
                ynew = y - [d2Tdx2 * dTdy - d2Tdxdy * dTdx] / (d2Tdx2 * d2Tdy2 - (d2Tdxdy)**2)

                smoothed_vertices[cardinal] = (xnew[0], ynew[0])
                smoothed_vertices_old[cardinal] = (x, y)

                tol = np.linalg.norm((xnew[0] - x, ynew[0] - y))

            if verbose:
                logger.info(f'Iteration={iteration:3d}, residual={tol:.3e}')

            if tol < tolerance:
                break

            # update current cardinals for next iteration
            cardinals = self.make_cardinals(smoothed_vertices)

        if self.drawlines:
            self.mainwindow.scene.createItemGroup(self.drawlines)

        return smoothed_vertices
    
    def mapToUlines(self, smoothed_vertices):

        self.new_ulines = list()

        j = -1
        for uline in self.block.getULines():
            new_uline = list()
            for i in range(len(uline)):
                j += 1
                new_uline.append(smoothed_vertices[j])

            self.new_ulines.append(new_uline)

        return self.new_ulines
