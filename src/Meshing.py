
import os
import copy
from datetime import date
import locale
import numpy as np
from scipy import interpolate

from PySide6 import QtGui, QtCore, QtWidgets

import PyAero
import GraphicsItemsCollection as gic
import GraphicsItem
import Elliptic
import Connect
from Smooth_angle_based import SmoothAngleBased
from Utils import Utils
from Settings import OUTPUTDATA
import logging
logger = logging.getLogger(__name__)


class Windtunnel:
    """
    The Windtunnel class is responsible for generating a computational fluid dynamics (CFD) mesh 
    around an airfoil within a wind tunnel. It includes methods for creating different parts of 
    the mesh, such as the airfoil mesh, trailing edge mesh, tunnel mesh, and tunnel wake mesh. 
    Additionally, it provides functionality for mesh quality assessment, drawing the mesh, and 
    exporting the mesh in various formats.
    """

    def __init__(self):

        # contains list of BlockMesh objects
        self.blocks = []

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

    def AirfoilMesh(self, name='', contour=None, divisions=15, ratio=3.0,
                    thickness=0.04):

        # get airfoil contour coordinates
        x, y = contour

        # make a list of point tuples
        # [(x1, y1), (x2, y2), (x3, y3), ... , (xn, yn)]
        line = list(zip(x, y))

        # block mesh around airfoil contour
        self.block_airfoil = BlockMesh(name=name)
        self.block_airfoil.addLine(line)

        # self.block_airfoil.extrudeLine(line, length=thickness, direction=3,
        #                                divisions=divisions, ratio=ratio)
        self.block_airfoil.extrudeLine_cell_thickness(line,
                                                      cell_thickness=thickness,
                                                      growth=ratio,
                                                      divisions=divisions,
                                                      direction=3)

        self.blocks.append(self.block_airfoil)

    def TrailingEdgeMesh(self, name='', te_divisions=3,
                         thickness=0.04, divisions=10, ratio=1.05):

        # compile first line of trailing edge block
        first = self.block_airfoil.getLine(number=0, direction='v')
        last = self.block_airfoil.getLine(number=-1, direction='v')
        last_reversed = copy.deepcopy(last)
        last_reversed.reverse()

        vec = np.array(first[0]) - np.array(last[0])
        line = copy.deepcopy(last_reversed)

        # in case of TE add the points from the TE
        if self.mainwindow.airfoil.has_TE:
            for i in range(1, te_divisions):
                p = last_reversed[-1] + float(i) / te_divisions * vec
                # p is type numpy.float, so convert it to float
                line.append((float(p[0]), float(p[1])))
            line += first
        # handle case with sharp trailing edge
        else:
            line += first[1:]

        # trailing edge block mesh
        block_te = BlockMesh(name=name)
        block_te.addLine(line)

        # block_te.extrudeLine(line, length=length, direction=4,
        #                      divisions=divisions, ratio=ratio)
        block_te.extrudeLine_cell_thickness(line,
                                            cell_thickness=thickness,
                                            growth=ratio,
                                            divisions=divisions,
                                            direction=4)

        # equidistant point distribution
        block_te.distribute(direction='u', number=-1)

        # make a transfinite interpolation
        # i.e. recreate points inside the block
        block_te.transfinite()

        self.block_te = block_te
        self.blocks.append(block_te)

    def TunnelMesh(self, name='', tunnel_height=2.0, divisions_height=100,
                   ratio_height=10.0, dist='symmetric',
                   smoothing_algorithm='simple',
                   smoothing_iterations=10,
                   smoothing_tolerance=1e-3):
        block_tunnel = BlockMesh(name=name)

        self.tunnel_height = tunnel_height

        # line composed of trailing edge and airfoil meshes
        line = self.block_te.getVLines()[-1]
        line.reverse()
        del line[-1]
        line += self.block_airfoil.getULines()[-1]
        del line[-1]
        line += self.block_te.getVLines()[0]
        block_tunnel.addLine(line)

        # line composed of upper, lower and front line segments
        p1 = np.array((block_tunnel.getULines()[0][0][0], tunnel_height))
        p2 = np.array((0.0, tunnel_height))
        p3 = np.array((0.0, -tunnel_height))
        p4 = np.array((block_tunnel.getULines()[0][-1][0], -tunnel_height))

        # upper line of wind tunnel
        line = list()
        vec = p2 - p1
        for t in np.linspace(0.0, 1.0, 10):
            p = p1 + t * vec
            line.append(p.tolist())
        del line[-1]

        # front half circle of wind tunnel
        for phi in np.linspace(90.0, 270.0, 200):
            phir = np.radians(phi)
            x = tunnel_height * np.cos(phir)
            y = tunnel_height * np.sin(phir)
            line.append((x, y))
        del line[-1]

        # lower line of wind tunnel
        vec = p4 - p3
        for t in np.linspace(0.0, 1.0, 10):
            p = p3 + t * vec
            line.append(p.tolist())

        # make numpy array
        line = np.array(line)

        # interpolate a spline through line
        # at this point "line" is the big "C" of the windtunnel until TE
        tck, _ = interpolate.splprep(line.T, s=0, k=1)

        # point distribution on upper, front and lower part
        if dist == 'symmetric':
            ld = -1.3
            ud = 1.3
        if dist == 'lower':
            ld = -1.2
            ud = 1.5
        if dist == 'upper':
            ld = -1.5
            ud = 1.2
        xx = np.linspace(ld, ud, len(block_tunnel.getULines()[0]))
        t = (np.tanh(xx) + 1.0) / 2.0

        # calculate new points on the big "C" according to t distribution
        xs, ys = interpolate.splev(t, tck, der=0)
        line = list(zip(xs.tolist(), ys.tolist()))

        block_tunnel.addLine(line)

        p5 = np.array(block_tunnel.getULines()[0][0])
        p6 = np.array(block_tunnel.getULines()[0][-1])

        # first vline
        vline1 = BlockMesh.makeLine(p5, p1, divisions=divisions_height,
                                    ratio=ratio_height)

        # last vline
        vline2 = BlockMesh.makeLine(p6, p4, divisions=divisions_height,
                                    ratio=ratio_height)

        boundary = [block_tunnel.getULines()[0],
                    block_tunnel.getULines()[-1],
                    vline1,
                    vline2]
        block_tunnel.transfinite(boundary=boundary)

        # blending between normals (inner lines) and transfinite (outer lines)
        ulines = list()
        old_ulines = block_tunnel.getULines()

        for j, uline in enumerate(block_tunnel.getULines()):

            # skip first and last line
            if j == 0 or j == len(block_tunnel.getULines()) - 1:
                ulines.append(uline)
                continue

            line = list()
            xo, yo = list(zip(*old_ulines[0]))
            xo = np.array(xo)
            yo = np.array(yo)
            normals = BlockMesh.curveNormals(xo, yo)

            for i, point in enumerate(uline):

                # skip first and last point
                if i == 0 or i == len(uline) - 1:
                    line.append(point)
                    continue

                pt = np.array(old_ulines[j][i])
                pto = np.array(old_ulines[0][i])
                vec = pt - pto
                # projection of vec into normal
                dist = np.dot(vec, normals[i]) / np.linalg.norm(normals[i])
                pn = pto + dist * normals[i]
                v = float(j) / float(len(block_tunnel.getULines()))
                exp = 0.6
                pnew = (1.0 - v**exp) * pn + v**exp * pt
                line.append((pnew.tolist()[0], pnew.tolist()[1]))

            ulines.append(line)

        block_tunnel = BlockMesh(name=name)
        for uline in ulines:
            block_tunnel.addLine(uline)

        # make transfinite interpolation from boundary lines
        ij = [0, 30, 0, len(block_tunnel.getULines()) - 1]
        block_tunnel.transfinite(ij=ij)
        ij = [len(block_tunnel.getVLines()) - 31,
              len(block_tunnel.getVLines()) - 1,
              0,
              len(block_tunnel.getULines()) - 1]
        block_tunnel.transfinite(ij=ij)

        # FIXME:
        # FIXME: refactoring needed here (put smoother in blockmesh class)
        # FIXME: and refactor complete meshing functions
        # FIXME:

        if smoothing_algorithm == 'simple':
            # FIXME:
            # FIXME: this can be improved
            # FIXME: and at least documented
            # FIXME:
            smooth = Smooth(block_tunnel)

            nodes = smooth.selectNodes(domain='interior')
            block_tunnel = smooth.smooth(nodes, iterations=1,
                                         algorithm='laplace')
            ij = [1, 30, 1, len(block_tunnel.getULines()) - 2]
            nodes = smooth.selectNodes(domain='ij', ij=ij)
            block_tunnel = smooth.smooth(nodes, iterations=2,
                                         algorithm='laplace')
            ij = [len(block_tunnel.getVLines()) - 31,
                  len(block_tunnel.getVLines()) - 2,
                  1,
                  len(block_tunnel.getULines()) - 2]
            nodes = smooth.selectNodes(domain='ij', ij=ij)
            block_tunnel = smooth.smooth(nodes, iterations=3,
                                         algorithm='laplace')

        elif smoothing_algorithm == 'elliptic':
            # elliptic grid generation
            smoother = Elliptic.Elliptic(block_tunnel.getULines())
            new_ulines = smoother.smooth(iterations=smoothing_iterations,
                                         tolerance=smoothing_tolerance,
                                         bnd_type=None, # can be 'Neumann'
                                         verbose=True)
            block_tunnel.setUlines(new_ulines)

        elif smoothing_algorithm == 'angle_based':
            smoother = SmoothAngleBased(block_tunnel, data_source='block')
            smoothed_vertices = smoother.smooth(iterations=smoothing_iterations,
                                                tolerance=smoothing_tolerance,
                                                verbose=True)
            new_ulines = smoother.mapToUlines(smoothed_vertices)
            block_tunnel.setUlines(new_ulines)

        self.block_tunnel = block_tunnel
        self.blocks.append(block_tunnel)

    def TunnelMeshWake(self, name='', tunnel_wake=2.0,
                       divisions=100, ratio=0.1, spread=0.4):

        chord = 1.0

        block_tunnel_wake = BlockMesh(name=name)

        # line composed of trailing edge and block_tunnel meshes
        line = self.block_tunnel.getVLines()[-1]
        line.reverse()
        del line[-1]
        line += self.block_te.getULines()[-1]
        del line[-1]
        line += self.block_tunnel.getVLines()[0]
        block_tunnel_wake.addLine(line)

        #
        p1 = np.array((self.block_te.getULines()[-1][0][0],
                       self.tunnel_height))
        p4 = np.array((self.block_te.getULines()[-1][-1][0],
                       - self.tunnel_height))
        p7 = np.array((tunnel_wake + chord, self.tunnel_height))
        p8 = np.array((tunnel_wake + chord, -self.tunnel_height))

        upper = BlockMesh.makeLine(p7, p1, divisions=divisions,
                                   ratio=1.0 / ratio)
        lower = BlockMesh.makeLine(p8, p4, divisions=divisions,
                                   ratio=1.0 / ratio)
        left = line
        right = BlockMesh.makeLine(p8, p7, divisions=len(left) - 1, ratio=1.0)

        boundary = [upper, lower, right, left]
        block_tunnel_wake.transfinite(boundary=boundary)

        # equalize division line in wake
        for i, u in enumerate(block_tunnel_wake.getULines()[0]):
            if u[0] < chord + tunnel_wake * spread:
                ll = len(block_tunnel_wake.getULines()[0])
                line_no = -ll + i
                break
        block_tunnel_wake.distribute(direction='v', number=line_no)

        # transfinite left of division line
        ij = [len(block_tunnel_wake.getVLines()) + line_no,
              len(block_tunnel_wake.getVLines()) - 1,
              0,
              len(block_tunnel_wake.getULines()) - 1]
        block_tunnel_wake.transfinite(ij=ij)

        # transfinite right of division line
        ij = [0,
              len(block_tunnel_wake.getVLines()) + line_no,
              0,
              len(block_tunnel_wake.getULines()) - 1]
        block_tunnel_wake.transfinite(ij=ij)

        self.block_tunnel_wake = block_tunnel_wake
        self.blocks.append(block_tunnel_wake)

    def makeMesh(self):

        toolbox = self.mainwindow.centralwidget.toolbox

        if self.mainwindow.airfoil:
            if not hasattr(self.mainwindow.airfoil, 'spline_data'):
                message = 'Splining needs to be done first.'
                self.mainwindow.slots.messageBox(message)
                return

            contour = self.mainwindow.airfoil.spline_data[0]

        else:
            self.mainwindow.slots.messageBox('No airfoil loaded.')
            return

        # delete blocks outline if existing
        # because a new one will be generated
        if hasattr(self.mainwindow.airfoil, 'mesh_blocks'):
            self.mainwindow.scene.removeItem(
                self.mainwindow.airfoil.mesh_blocks)
            del self.mainwindow.airfoil.mesh_blocks

        progdialog = QtWidgets.QProgressDialog(
            "Meshing in progress", "Cancel", 0, 100, self.mainwindow)
        progdialog.setFixedWidth(300)
        progdialog.setMinimumDuration(0)
        progdialog.setWindowTitle('Generating the CFD mesh')
        progdialog.setWindowModality(QtCore.Qt.WindowModal)
        progdialog.setCancelButtonText('Abort meshing ...')
        progdialog.show()

        progdialog.setValue(10)
        # progdialog.setLabelText('making blocks')

        self.AirfoilMesh(name='block_airfoil',
                         contour=contour,
                         divisions=toolbox.points_n.value(),
                         ratio=toolbox.ratio.value(),
                         thickness=toolbox.normal_thickness.value())
        progdialog.setValue(20)

        if progdialog.wasCanceled():
            return

        self.TrailingEdgeMesh(name='block_TE',
                              te_divisions=toolbox.te_div.value(),
                              thickness=toolbox.length_te.value(),
                              divisions=toolbox.points_te.value(),
                              ratio=toolbox.ratio_te.value())
        progdialog.setValue(30)

        if progdialog.wasCanceled():
            return

        self.TunnelMesh(name='block_tunnel',
                        tunnel_height=toolbox.tunnel_height.value(),
                        divisions_height=toolbox.divisions_height.value(),
                        ratio_height=toolbox.ratio_height.value(),
                        dist=toolbox.dist.currentText(),
                        smoothing_algorithm=toolbox.smoothing_algorithm,
                        smoothing_iterations=toolbox.smoother_iterations.value(),
                        smoothing_tolerance=float(toolbox.smoother_tolerance.text()))
        progdialog.setValue(50)

        if progdialog.wasCanceled():
            return

        self.TunnelMeshWake(name='block_tunnel_wake',
                            tunnel_wake=toolbox.tunnel_wake.value(),
                            divisions=toolbox.divisions_wake.value(),
                            ratio=toolbox.ratio_wake.value(),
                            spread=toolbox.spread.value() / 100.0)
        progdialog.setValue(70)

        if progdialog.wasCanceled():
            return

        # connect mesh blocks
        connect = Connect.Connect(progdialog)
        vertices, connectivity, progdialog = \
            connect.connectAllBlocks(self.blocks)

        # add mesh to Wind-tunnel instance
        self.mesh = vertices, connectivity

        # generate cell to vertex connectivity from mesh
        self.makeLCV()

        # generate cell to edge connectivity from mesh
        self.makeLCE()

        # generate boundaries from mesh connectivity
        self.makeBoundaries()

        logger.info('Mesh around {} created'.
                    format(self.mainwindow.airfoil.name))
        logger.info('Mesh has {} vertices and {} elements'.
                    format(len(vertices), len(connectivity)))

        self.drawMesh(self.mainwindow.airfoil)
        self.drawBlockOutline(self.mainwindow.airfoil)

        # mesh quality
        # quality = self.MeshQuality(crit='k2inf')
        # self.drawMeshQuality(quality)

        progdialog.setValue(100)

        # enable mesh export and set filename and boundary definitions
        toolbox.box_meshexport.setEnabled(True)
    
    def makeLCV(self):
        """Make cell to vertex connectivity for the mesh
           LCV is identical to connectivity
        """
        _, connectivity = self.mesh
        self.LCV = connectivity

    def makeLVC(self):
        _, connectivity = self.mesh
        nodes = list(set([node for cell in connectivity for node in cell]))
        self.lvc = dict()
        for node in nodes:
            for cell in connectivity:
                if node in cell:
                    self.lvc.setdefault(node, []).append(cell.tolist())

    def makeLCE(self):
        """Make cell to edge connectivity for the mesh"""
        _, connectivity = self.mesh
        self.LCE = dict()
        self.edges = list()

        for i, cell in enumerate(connectivity):
            # example for quadrilateral:
            # cell: [0, 1, 5, 4]
            # edges: [(0,1), (1,5), (5,4), (4,0)]
            edges = [(cell[j], cell[(j + 1) % len(cell)])
                           for j in range(len(cell))]

            # all edges for cell i
            self.LCE[i] = edges

            # all edges in one list
            self.edges += [tuple(sorted(edge)) for edge in edges]

    def makeLCC(self):
        """Make cell to cell connectivity for the mesh"""
        pass

    def makeBoundaries(self):
        """A boundary edge is an edge that belongs only to one cell"""

        vertices, _ = self.mesh
        vertices = np.array(vertices)

        edges = self.edges

        seen = set()
        unique = list()
        doubles = set()
        for edge in edges:
            if edge not in seen:
                seen.add(edge)
                unique.append(edge)
            else:
                doubles.add(edge)

        self.boundary_edges = [edge for edge in unique if edge not in doubles]

        # tag edges for boundary definitions
        # FIXME
        # FIXME here it's done the dirty way
        # FIXME at least try to make it faster later
        # FIXME
        self.boundary_tags = {'airfoil': [],
                              'inlet': [],
                              'outlet': [],
                              'top': [],
                              'bottom': []}
        
        ### FIXME
        ### FIXME too dirty below (do not work with toplerances!!!)
        ### FIXME

        xmax = np.max(vertices[:,0])
        ymax = np.max(vertices[:,1])
        ymin = np.min(vertices[:,1])

        for edge in self.boundary_edges:
            x1 = vertices[edge[0]][0]
            y1 = vertices[edge[0]][1]
            x2 = vertices[edge[1]][0]
            y2 = vertices[edge[1]][1]
            tol = 1e-6  # tolerance for coordinate comparison
            if x1 > -0.1 and x1 < 1.1 and y1 < 0.5 and y1 > -0.5:
                self.boundary_tags['airfoil'].append(edge)
            elif abs(x1 - xmax) < tol and abs(x2 - xmax) < tol:
                self.boundary_tags['outlet'].append(edge)
            elif abs(y1 - ymax) < tol and abs(y2 - ymax) < tol:
                self.boundary_tags['top'].append(edge)
            elif abs(y1 - ymin) < tol and abs(y2 - ymin) < tol:
                self.boundary_tags['bottom'].append(edge)
            else:
                self.boundary_tags['inlet'].append(edge)

        return

    def drawMesh(self, airfoil):
        """Add the mesh as ItemGroup to the scene

        Args:
            airfoil (TYPE): object containing all airfoil properties and data
        """

        # toggle spline points
        self.mainwindow.centralwidget.airfoil_spline_points_checkbox.click()

        # delete old mesh if existing
        if hasattr(airfoil, 'mesh'):
            logger.debug('MESH item type: {}'.format(type(airfoil.mesh)))
            self.mainwindow.scene.removeItem(airfoil.mesh)

        mesh = list()

        for block in self.blocks:
            for lines in [block.getULines(),
                          block.getVLines()]:
                for line in lines:

                    # instantiate a graphics item
                    contour = gic.GraphicsCollection()
                    # make it polygon type and populate its points
                    points = [QtCore.QPointF(x, y) for x, y in line]
                    contour.Polyline(QtGui.QPolygonF(points), '')
                    # set its properties
                    contour.pen.setColor(QtGui.QColor(0, 0, 0, 255))
                    contour.pen.setWidthF(0.8)
                    contour.pen.setCosmetic(True)
                    contour.brush.setStyle(QtCore.Qt.NoBrush)

                    # add contour as a GraphicsItem to the scene
                    # these are the objects which are drawn in the GraphicsView
                    meshline = GraphicsItem.GraphicsItem(contour)
                    mesh.append(meshline)

        airfoil.mesh = self.mainwindow.scene.createItemGroup(mesh)

        # activate viewing options if mesh is created and displayed
        self.mainwindow.centralwidget.mesh_checkbox.setChecked(True)
        self.mainwindow.centralwidget.mesh_checkbox.setEnabled(True)

    def drawMeshQuality(self, quality):

        vertices, connectivity = self.mesh
        quads = list()
        colors = [Utils.scalar_to_rgb(q, range='256') for q in quality]

        for i, cell in enumerate(connectivity):
            quad = gic.GraphicsCollection()
            points = [QtCore.QPointF(*vertices[vertex]) for vertex in cell]
            quad.Polygon(QtGui.QPolygonF(points), '')
            quad.pen.setColor(QtGui.QColor(0, 0, 0, 255))
            quad.brush.setColor(QtGui.QColor(*colors[i]))
            quad.pen.setWidthF(0.8)
            quad.pen.setCosmetic(True)
            quaditem = GraphicsItem.GraphicsItem(quad)
            quads.append(quaditem)
        
        self.mainwindow.scene.createItemGroup(quads)

    def drawBlockOutline(self, airfoil):
        """Add the mesh block outlines to the scene

        Args:
            airfoil (TYPE): object containing all airfoil properties and data
        """

        # FIXME
        # FIXME Refactoring of code duplication here and in drawMesh
        # FIXME

        mesh_blocks = list()

        for block in self.blocks:
            for lines in [block.getULines()]:
                for line in [lines[0], lines[-1]]:

                    # instantiate a graphics item
                    contour = gic.GraphicsCollection()
                    # make it polygon type and populate its points
                    points = [QtCore.QPointF(x, y) for x, y in line]
                    contour.Polyline(QtGui.QPolygonF(points), '')
                    # set its properties
                    contour.pen.setColor(QtGui.QColor(202, 31, 123, 255))
                    contour.pen.setWidthF(3.0)
                    contour.pen.setCosmetic(True)
                    contour.brush.setStyle(QtCore.Qt.NoBrush)

                    # add contour as a GraphicsItem to the scene
                    # these are the objects which are drawn in the GraphicsView
                    meshline = GraphicsItem.GraphicsItem(contour)
                    mesh_blocks.append(meshline)

            for lines in [block.getVLines()]:
                for line in [lines[0], lines[-1]]:

                    # instantiate a graphics item
                    contour = gic.GraphicsCollection()
                    # make it polygon type and populate its points
                    points = [QtCore.QPointF(x, y) for x, y in line]
                    contour.Polyline(QtGui.QPolygonF(points), '')
                    # set its properties
                    contour.pen.setColor(QtGui.QColor(202, 31, 123, 255))
                    contour.pen.setWidthF(3.0)
                    contour.pen.setCosmetic(True)
                    contour.brush.setStyle(QtCore.Qt.NoBrush)

                    # add contour as a GraphicsItem to the scene
                    # these are the objects which are drawn in the GraphicsView
                    meshline = GraphicsItem.GraphicsItem(contour)
                    mesh_blocks.append(meshline)

        airfoil.mesh_blocks = self.mainwindow.scene \
            .createItemGroup(mesh_blocks)

        # initial visibility of mesh blocks is False, but enabled
        airfoil.mesh_blocks.setVisible(False)
        self.mainwindow.centralwidget.mesh_blocks_checkbox.setEnabled(True)

    def MeshQuality(self, crit='k2inf'):
        vertices, connectivity = self.mesh

        if crit == 'k2inf':
            v12 = vertices[connectivity[:, 1]] - vertices[connectivity[:, 0]]
            v23 = vertices[connectivity[:, 2]] - vertices[connectivity[:, 1]]
            v34 = vertices[connectivity[:, 3]] - vertices[connectivity[:, 2]]
            v41 = vertices[connectivity[:, 0]] - vertices[connectivity[:, 3]]
            a = np.linalg.norm(v12)
            b = np.linalg.norm(v23)
            c = np.linalg.norm(v34)
            d = np.linalg.norm(v41)
            p = 0.5 * (a + b + c + d)
            q2 = np.sqrt(a**2 + b**2 + c**2 + d**2)

            alpha = Utils.angle_between(v12, -v41)
            beta =  Utils.angle_between(v23, -v12)
            gamma = Utils.angle_between(v34, -v23)
            delta = Utils.angle_between(v41, -v12)
            theta = 0.5 * (alpha + gamma)

            # quad area using Bretschneider’s formula
            A = np.sqrt((p -a)*(p-b)*(p-c)*(p-d) - a*b*c*d*np.cos(theta))

            ka = (a**2 + d**2) / (a*d*np.sin(alpha))
            kb = (a**2 + b**2) / (a*b*np.sin(beta))
            kc = (b**2 + c**2) / (b*c*np.sin(gamma))
            kd = (c**2 + d**2) / (c*d*np.sin(delta))
            k = np.stack((ka, kb, kc, kd))

            quality = np.max(k, axis=0) / 2.

        self.mesh.quality = quality

        return self.mesh.quality


class BlockMesh:

    def __init__(self, name='block'):
        self.name = name
        self.ULines = list()

    def addLine(self, line):
        # line is a list of (x, y) tuples
        self.ULines.append(line)

    def getULines(self):
        return self.ULines

    def setUlines(self, ulines):
        self.ULines = ulines

    def getVLines(self):
        vlines = list()
        U, V = self.getDivUV()

        # loop over all u-lines
        for i in range(U + 1):
            # prepare new v-line
            vline = list()
            # collect i-th point on each u-line
            for uline in self.getULines():
                vline.append(uline[i])
            vlines.append(vline)

        return vlines

    def getLine(self, number=0, direction='u'):
        if direction.lower() == 'u':
            lines = self.getULines()
        if direction.lower() == 'v':
            lines = self.getVLines()
        return lines[number]

    def getDivUV(self):
        u = len(self.getULines()[0]) - 1
        v = len(self.getULines()) - 1
        return u, v

    def getNodeCoo(self, node):
        I, J = node[0], node[1]
        uline = self.getULines()[J]
        point = uline[I]
        return np.array(point)

    def setNodeCoo(self, node, new_pos):
        I, J = node[0], node[1]
        uline = self.getULines()[J]
        uline[I] = new_pos
        return

    @staticmethod
    def makeLine(p1, p2, divisions=1, ratio=1.0):
        vec = p2 - p1
        dist = np.linalg.norm(vec)
        spacing = BlockMesh.spacing(divisions=divisions,
                                    ratio=ratio, length=dist)
        line = list()
        line.append((p1.tolist()[0], p1.tolist()[1]))
        for i in range(1, len(spacing)):
            p = p1 + spacing[i] * Utils.unit_vector(vec)
            line.append((p.tolist()[0], p.tolist()[1]))
        del line[-1]
        line.append((p2.tolist()[0], p2.tolist()[1]))
        return line

    def extrudeLine_cell_thickness(self, line, cell_thickness=0.04,
                                   growth=1.05,
                                   divisions=1,
                                   direction=3):
        x, y = list(zip(*line))
        x = np.array(x)
        y = np.array(y)
        if direction == 3:
            spacing, _ = self.spacing_cell_thickness(
                cell_thickness=cell_thickness,
                growth=growth,
                divisions=divisions)
            normals = self.curveNormals(x, y)
            for i in range(1, len(spacing)):
                xo = x + spacing[i] * normals[:, 0]
                yo = y + spacing[i] * normals[:, 1]
                line = list(zip(xo.tolist(), yo.tolist()))
                self.addLine(line)
        elif direction == 4:
            spacing, _ = self.spacing_cell_thickness(
                cell_thickness=cell_thickness,
                growth=growth,
                divisions=divisions)
            normals = self.curveNormals(x, y)
            normalx = normals[:, 0].mean()
            normaly = normals[:, 1].mean()
            for i in range(1, len(spacing)):
                xo = x + spacing[i] * normalx
                yo = y + spacing[i] * normaly
                line = list(zip(xo.tolist(), yo.tolist()))
                self.addLine(line)

    def extrudeLine(self, line, direction=0, length=0.1, divisions=1,
                    ratio=1.00001, constant=False):
        x, y = list(zip(*line))
        x = np.array(x)
        y = np.array(y)
        if constant and direction == 0:
            x.fill(length)
            line = list(zip(x.tolist(), y.tolist()))
            self.addLine(line)
        elif constant and direction == 1:
            y.fill(length)
            line = list(zip(x.tolist(), y.tolist()))
            self.addLine(line)
        elif direction == 3:
            spacing = self.spacing(divisions=divisions,
                                   ratio=ratio,
                                   length=length)
            normals = self.curveNormals(x, y)
            for i in range(1, len(spacing)):
                xo = x + spacing[i] * normals[:, 0]
                yo = y + spacing[i] * normals[:, 1]
                line = list(zip(xo.tolist(), yo.tolist()))
                self.addLine(line)
        elif direction == 4:
            spacing = self.spacing(divisions=divisions,
                                   ratio=ratio,
                                   length=length)
            normals = self.curveNormals(x, y)
            normalx = normals[:, 0].mean()
            normaly = normals[:, 1].mean()
            for i in range(1, len(spacing)):
                xo = x + spacing[i] * normalx
                yo = y + spacing[i] * normaly
                line = list(zip(xo.tolist(), yo.tolist()))
                self.addLine(line)

    def distribute(self, direction='u', number=0, type='constant'):

        if direction == 'u':
            line = np.array(self.getULines()[number])
        elif direction == 'v':
            line = np.array(self.getVLines()[number])

        # interpolate B-spline through data points
        # here, a linear interpolant is derived "k=1"
        # splprep returns:
        # tck ... tuple (t,c,k) containing the vector of knots,
        #         the B-spline coefficients, and the degree of the spline.
        #   u ... array of the parameters for each given point (knot)
        tck, u = interpolate.splprep(line.T, s=0, k=1)

        if type == 'constant':
            t = np.linspace(0.0, 1.0, num=len(line))
        if type == 'transition':
            first = np.array(self.getULines()[0])
            last = np.array(self.getULines()[-1])
            tck_first, u_first = interpolate.splprep(first.T, s=0, k=1)
            tck_last, u_last = interpolate.splprep(last.T, s=0, k=1)
            if number < 0.0:
                number = len(self.getVLines())
            v = float(number) / float(len(self.getVLines()))
            t = (1.0 - v) * u_first + v * u_last

        # evaluate function at any parameter "0<=t<=1"
        line = interpolate.splev(t, tck, der=0)
        line = list(zip(line[0].tolist(), line[1].tolist()))

        if direction == 'u':
            self.getULines()[number] = line
        elif direction == 'v':
            for i, uline in enumerate(self.getULines()):
                self.getULines()[i][number] = line[i]

    @staticmethod
    def spacing_cell_thickness(cell_thickness=0.04, growth=1.1, divisions=10):

        # add cell thickness of first layer
        spacing = [cell_thickness]

        for i in range(divisions - 1):
            spacing.append(spacing[0] + spacing[-1] * growth)

        spacing.insert(0, 0.0)

        length = np.sum(spacing)

        return spacing, length

    @staticmethod
    def spacing(divisions=10, ratio=1.0, length=1.0):
        """Calculate point distribution on a line

        Args:
            divisions (int, optional): Number of subdivisions
            ratio (float, optional): Ratio of last to first subdivision size
            length (float, optional): length of line

        Returns:
            array: individual line segment lengths
        """

        if divisions == 1:
            sp = [0.0, 1.0]
            return np.array(sp)

        growth = ratio**(1.0 / (float(divisions) - 1.0))

        if growth == 1.0:
            growth = 1.0 + 1.0e-10

        s = [1.0]
        for i in range(1, divisions + 1):
            s.append(growth**i)

        spacing = np.array(s)
        spacing -= spacing[0]
        spacing /= spacing[-1]
        spacing *= length

        return spacing

    def mapLines(self, line_1, line_2):
        """Map the distribution of points from one line to another line

        Args:
            line_1 (LIST): Source line (will be mapped)
            line_2 (LIST): Destination line (upon this line_1 is mapped)
        """
        pass

    @staticmethod
    def curveNormals(x, y, closed=False):
        istart = 0
        iend = 0
        n = list()

        for i, _ in enumerate(x):

            if closed:
                if i == len(x) - 1:
                    iend = -i - 1
            else:
                if i == 0:
                    istart = 1
                if i == len(x) - 1:
                    iend = -1

            a = np.array([x[i + 1 + iend] - x[i - 1 + istart],
                          y[i + 1 + iend] - y[i - 1 + istart]])
            e = Utils.unit_vector(a)
            n.append([e[1], -e[0]])
            istart = 0
            iend = 0
        return np.array(n)

    def transfinite(self, boundary=[], ij=[]):
        """Make a transfinite interpolation.

        http://en.wikipedia.org/wiki/Transfinite_interpolation

                       upper
                --------------------
                |                  |
                |                  |
           left |                  | right
                |                  |
                |                  |
                --------------------
                       lower

        Example input for the lower boundary:
            lower = [(0.0, 0.0), (0.1, 0.3),  (0.5, 0.4)]
        """

        if boundary:
            lower = boundary[0]
            upper = boundary[1]
            left = boundary[2]
            right = boundary[3]
        elif ij:
            lower = self.getULines()[ij[2]][ij[0]:ij[1] + 1]
            upper = self.getULines()[ij[3]][ij[0]:ij[1] + 1]
            left = self.getVLines()[ij[0]][ij[2]:ij[3] + 1]
            right = self.getVLines()[ij[1]][ij[2]:ij[3] + 1]
        else:
            lower = self.getULines()[0]
            upper = self.getULines()[-1]
            left = self.getVLines()[0]
            right = self.getVLines()[-1]

        # FIXME
        # FIXME left and right need to swapped from input
        # FIXME
        # FIXME like: left, right = right, left
        # FIXME

        lower = np.array(lower)
        upper = np.array(upper)
        left = np.array(left)
        right = np.array(right)

        # convert the block boundary curves into parametric form
        # as curves need to be between 0 and 1
        # interpolate B-spline through data points
        # here, a linear interpolant is derived "k=1"
        # splprep returns:
        # tck ... tuple (t,c,k) containing the vector of knots,
        #         the B-spline coefficients, and the degree of the spline.
        #   u ... array of the parameters for each given point (knot)
        tck_lower, u_lower = interpolate.splprep(lower.T, s=0, k=1)
        tck_upper, u_upper = interpolate.splprep(upper.T, s=0, k=1)
        tck_left, u_left = interpolate.splprep(left.T, s=0, k=1)
        tck_right, u_right = interpolate.splprep(right.T, s=0, k=1)

        nodes = np.zeros((len(left) * len(lower), 2))

        # corner points
        c1 = lower[0]
        c2 = upper[0]
        c3 = lower[-1]
        c4 = upper[-1]

        for i, xi in enumerate(u_lower):
            for j, eta in enumerate(u_left):

                node = i * len(u_left) + j

                point = (1.0 - xi) * left[j] + xi * right[j] + \
                    (1.0 - eta) * lower[i] + eta * upper[i] - \
                    ((1.0 - xi) * (1.0 - eta) * c1 + (1.0 - xi) * eta * c2 +
                     xi * (1.0 - eta) * c3 + xi * eta * c4)

                nodes[node, 0] = point[0]
                nodes[node, 1] = point[1]

        vlines = list()
        vline = list()
        i = 0
        for node in nodes:
            i += 1
            vline.append(node)
            if i % len(left) == 0:
                vlines.append(vline)
                vline = list()

        vlines.reverse()

        if ij:
            ulines = self.makeUfromV(vlines)
            n = -1
            for k in range(ij[2], ij[3] + 1):
                n += 1
                self.ULines[k][ij[0]:ij[1] + 1] = ulines[n]
        else:
            self.ULines = self.makeUfromV(vlines)

        return

    @staticmethod
    def makeUfromV(vlines):
        ulines = list()
        uline = list()
        for i in range(len(vlines[0])):
            for vline in vlines:
                x, y = vline[i][0], vline[i][1]
                uline.append((x, y))
            ulines.append(uline[::-1])
            uline = list()
        return ulines

    @staticmethod
    def writeFLMA(wind_tunnel, name='', depth=0.3):
        '''Write mesh to AVL-FIRE *.flma format'''

        basename = os.path.basename(name)
        nameroot, extension = os.path.splitext(basename)

        mesh = wind_tunnel.mesh

        vertices, connectivity = mesh

        with open(name, 'w') as f:

            number_of_vertices_2D = len(vertices)

            numvertex = '8'

            # write number of points to FLMA file (*2 for z-direction)
            f.write(str(2 * number_of_vertices_2D) + '\n')

            signum = -1.

            # write x-, y- and z-coordinates to FLMA file
            # loop 1D direction (symmetry)
            for _ in range(2):
                for vertex in vertices:
                    f.write(str(vertex[0]) + ' ' + str(vertex[1]) +
                            ' ' + str(signum * depth / 2.0) + ' ')
                signum = 1.

            # write number of cells to FLMA file
            cells = len(connectivity)
            f.write('\n' + str(cells) + '\n')

            # write cell connectivity to FLMA file
            for cell in connectivity:
                cell_connect = str(cell[0]) + ' ' + \
                    str(cell[1]) + ' ' + \
                    str(cell[2]) + ' ' + \
                    str(cell[3]) + ' ' + \
                    str(cell[0] + number_of_vertices_2D) + ' ' + \
                    str(cell[1] + number_of_vertices_2D) + ' ' + \
                    str(cell[2] + number_of_vertices_2D) + ' ' + \
                    str(cell[3] + number_of_vertices_2D) + '\n'

                f.write(numvertex + '\n')
                f.write(cell_connect)

            # FIRE element type (FET) for HEX element
            fetHEX = '5'
            f.write('\n' + str(cells) + '\n')
            for i in range(cells):
                f.write(fetHEX + ' ')
            f.write('\n\n')

            # FIRE element type (FET) for Quad element
            fetQuad = '3\n'

            # write FIRE selections to FLMA file
            # number of selections
            f.write('6\n')
            # selection name
            f.write('symmetry\n')
            # FIRE element type
            f.write(fetQuad)
            # 2x number of faces in the selection
            # her we take 4x because we put both symmetry selections together
            f.write(str(4 * len(connectivity)) + '\n')
            # cells of the face-selection and face direction (0-5)
            for i in range(len(connectivity)):
                f.write(f' {i} 0')
            for i in range(len(connectivity)):
                f.write(f' {i} 1')
            f.write('\n')
            f.write('\n')
            #
            # FIXME
            # FIXME find all cell around the airfoil, at the outlet and at the inlet
            # FIXME
            #
            # selection name
            f.write('bottom\n')
            f.write(fetQuad)
            f.write('2\n')
            f.write('0 2\n')
            f.write('\n')
            f.write('top\n')
            f.write(fetQuad)
            f.write('2\n')
            f.write('0 3\n')
            f.write('\n')
            f.write('back\n')
            f.write(fetQuad)
            f.write('2\n')
            f.write('0 4\n')
            f.write('\n')
            f.write('front\n')
            f.write(fetQuad)
            f.write('2\n')
            f.write('0 5\n')

            logger.info('FIRE type mesh saved as {}'.
                        format(os.path.join(OUTPUTDATA, basename)))

    @staticmethod
    def writeSU2_nolib(wind_tunnel, name=''):
        '''Write mesh to SU2 format without using meshio'''

        mesh = wind_tunnel.mesh
        vertices, connectivity = mesh
        tags = wind_tunnel.boundary_tags

        num_airfoil_edges = len(tags['airfoil'])
        num_inlet_edges = len(tags['inlet'])
        num_outlet_edges = len(tags['outlet'])
        num_top_edges = len(tags['top'])
        num_bottom_edges = len(tags['bottom'])

        with open(name, 'w') as f:
            # write header
            f.write('%\n')
            f.write('% Problem dimension\n')
            f.write('%\n')
            f.write('NDIME= 2\n')

            f.write('%\n')
            f.write('% Node coordinates\n')
            f.write('%\n')
            f.write('NPOIN= ' + str(len(vertices)) + '\n')
            # write vertices
            for i, vertex in enumerate(vertices):
                f.write(f'{vertex[0]: .8e} {vertex[1]: .8e} {i:<}\n')

            f.write('%\n')
            f.write('% Element connectivity\n')
            f.write('%\n')
            f.write('NELEM= ' + str(len(connectivity)) + '\n')
            # write elements
            for i, cell in enumerate(connectivity):
                f.write(f'9 {cell[0]:10d} {cell[1]:10d} {cell[2]:10d} {cell[3]:10d} {i:>10d}\n')

            f.write('%\n')
            f.write('% Boundary tags\n')
            f.write('%\n')
            # write boundary tags
            f.write('NMARK= 5\n')

            f.write('MARKER_TAG= airfoil\n')
            f.write('MARKER_ELEMS= ' + str(num_airfoil_edges) + '\n')
            for edge in tags['airfoil']:
                f.write(f'3 {edge[0]} {edge[1]}\n')

            f.write('MARKER_TAG= inlet\n')
            f.write('MARKER_ELEMS= ' + str(num_inlet_edges) + '\n')
            for edge in tags['inlet']:
                f.write(f'3 {edge[0]} {edge[1]}\n')

            f.write('MARKER_TAG= outlet\n')
            f.write('MARKER_ELEMS= ' + str(num_outlet_edges) + '\n')
            for edge in tags['outlet']:
                f.write(f'3 {edge[0]} {edge[1]}\n')

            f.write('MARKER_TAG= top\n')
            f.write('MARKER_ELEMS= ' + str(num_top_edges) + '\n')
            for edge in tags['top']:
                f.write(f'3 {edge[0]} {edge[1]}\n')

            f.write('MARKER_TAG= bottom\n')
            f.write('MARKER_ELEMS= ' + str(num_bottom_edges) + '\n')
            for edge in tags['bottom']:
                f.write(f'3 {edge[0]} {edge[1]}\n')
            
        basename = os.path.basename(name)
        logger.info('SU2 type mesh saved as {}'.
                    format(os.path.join(OUTPUTDATA, basename)))

    @staticmethod
    def writeVTK_nolib(wind_tunnel, name=''):
        """
        Write a VTU file (UnstructuredGrid)."""

        mesh = wind_tunnel.mesh
        vertices, connectivity = mesh
        tags = wind_tunnel.boundary_tags

        vertices = [v + (0.0,) for v in vertices]
        # Determine number of points
        num_vertices = len(vertices)

        # Convert connectivity (list of lists) to a consistent format internally
        # without changing the external data model.
        polygon_cells = [np.array(cell, dtype=int) for cell in connectivity]


        # Function to determine VTK cell type based on number of vertices in a cell
        # Add more mappings if you have other cell types.
        def cell_type_from_length(n):
            if n == 2:
                return 3  # VTK_LINE
            elif n == 3:
                return 5  # VTK_TRIANGLE
            elif n == 4:
                return 9  # VTK_QUAD
            else:
                raise ValueError(f"No VTK cell type defined for {n}-node cells.")

        # Process main polygonal cells
        # For these cells, we assign boundary_id=0 as a default.
        # Flatten their connectivity

        # Process main polygonal cells
        polygon_cell_lengths = [len(cell) for cell in polygon_cells]
        polygon_connectivity_flat = np.concatenate([cell for cell in polygon_cells]) if polygon_cells else np.array([], dtype=int)
        polygon_cell_types = np.array([cell_type_from_length(l) for l in polygon_cell_lengths], dtype=np.uint8)
        polygon_boundary_ids = np.zeros(len(polygon_cells), dtype=np.int32)  # default boundary_id=0

        # Process boundary edges (line cells)
        # Assign each boundary name a unique ID starting from 1
        boundary_names = list(tags.keys())
        boundary_id_map = {name: i+1 for i, name in enumerate(boundary_names)}

        # Flatten boundary edges into a single connectivity array
        # Each edge is a 2-vertex line cell
        boundary_edges = []
        boundary_edge_lengths = []
        boundary_edge_types = []
        boundary_edge_ids = []

        for bname, edges in tags.items():
            for edge in edges:
                edge = np.array(edge, dtype=int)  # ensure numpy array
                if len(edge) != 2:
                    raise ValueError("Boundary edges must have exactly 2 vertices.")
                boundary_edges.append(edge)
                boundary_edge_lengths.append(2)
                boundary_edge_types.append(cell_type_from_length(2))
                boundary_edge_ids.append(boundary_id_map[bname])

        if len(boundary_edges) > 0:
            boundary_connectivity_flat = np.concatenate(boundary_edges)
            boundary_cell_types = np.array(boundary_edge_types, dtype=np.uint8)
            boundary_ids_array = np.array(boundary_edge_ids, dtype=np.int32)
        else:
            boundary_connectivity_flat = np.array([], dtype=int)
            boundary_cell_types = np.array([], dtype=np.uint8)
            boundary_ids_array = np.array([], dtype=np.int32)

        # Combine polygonal cells and boundary line cells
        all_connectivity_flat = np.concatenate([polygon_connectivity_flat, boundary_connectivity_flat])
        all_cell_types = np.concatenate([polygon_cell_types, boundary_cell_types])
        all_boundary_ids = np.concatenate([polygon_boundary_ids, boundary_ids_array])
        all_cell_lengths = polygon_cell_lengths + boundary_edge_lengths

        num_cells = len(all_cell_lengths)
        offsets = np.cumsum(all_cell_lengths)

        # Write VTU file in ASCII format
        with open(name, "w") as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">\n')
            f.write('  <UnstructuredGrid>\n')
            f.write(f'    <Piece NumberOfPoints="{num_vertices}" NumberOfCells="{num_cells}">\n')

            # Cell Data: boundary_ids
            f.write('      <CellData Scalars="BoundaryID">\n')
            f.write('        <DataArray type="Int32" Name="BoundaryID" format="ascii">\n')
            f.write('          ' + ' '.join(map(str, all_boundary_ids)) + '\n')
            f.write('        </DataArray>\n')
            f.write('      </CellData>\n')

            # vertices
            f.write('      <Points>\n')
            f.write('        <DataArray type="Float32" NumberOfComponents="3" format="ascii">\n')
            for p in vertices:
                f.write(f'          {p[0]} {p[1]} {p[2]}\n')
            f.write('        </DataArray>\n')
            f.write('      </Points>\n')

            # Cells
            f.write('      <Cells>\n')
            # connectivity
            f.write('        <DataArray type="Int32" Name="connectivity" format="ascii">\n')
            f.write('          ' + ' '.join(map(str, all_connectivity_flat)) + '\n')
            f.write('        </DataArray>\n')

            # offsets
            f.write('        <DataArray type="Int32" Name="offsets" format="ascii">\n')
            f.write('          ' + ' '.join(map(str, offsets)) + '\n')
            f.write('        </DataArray>\n')

            # types
            f.write('        <DataArray type="UInt8" Name="types" format="ascii">\n')
            f.write('          ' + ' '.join(map(str, all_cell_types)) + '\n')
            f.write('        </DataArray>\n')

            f.write('      </Cells>\n')

            f.write('    </Piece>\n')
            f.write('  </UnstructuredGrid>\n')
            f.write('</VTKFile>\n')

        basename = os.path.basename(name)
        logger.info('VTK type mesh saved as {}'.
                    format(os.path.join(OUTPUTDATA, basename)))

    @staticmethod
    def writeGMSH_nolib(wind_tunnel, name=''):
        """Writes a GMSH 2.2 format mesh file."""

        mesh = wind_tunnel.mesh
        vertices, connectivity = mesh
        boundaries = wind_tunnel.boundary_tags

        # Assign unique physical tags to boundaries
        boundary_tags = {name: idx + 1 for idx, name in enumerate(boundaries.keys())}
        num_physical_names = len(boundaries) + 1  # +1 for the domain (elements)

        # Assign a physical tag for the domain elements
        domain_physical_tag = num_physical_names

        # Write the mesh file
        with open(name, 'w') as f:
            # Write MeshFormat section
            f.write('$MeshFormat\n')
            f.write('2.2 0 8\n')  # Version 2.2, ASCII mode, size of double precision
            f.write('$EndMeshFormat\n')

            # Write PhysicalNames section
            f.write('$PhysicalNames\n')
            f.write(f'{num_physical_names}\n')
            # Write boundary physical names
            for name1, tag in boundary_tags.items():
                f.write(f'1 {tag} "{name1}"\n')  # Dimension 1 for lines
            # Write domain physical name
            f.write(f'2 {domain_physical_tag} "Domain"\n')  # Dimension 2 for surface elements
            f.write('$EndPhysicalNames\n')

            # Write Nodes section
            f.write('$Nodes\n')
            f.write(f'{len(vertices)}\n')
            z = 0.0  # 2D mesh
            for idx, (x, y) in enumerate(vertices, start=1):
                f.write(f'{idx} {x: .8e} {y: .8e} {z: .8e}\n')
            f.write('$EndNodes\n')

            # Prepare elements
            elements_data = []
            elem_id = 1

            # Write boundary edge elements
            for name1, edges in boundaries.items():
                physical_tag = boundary_tags[name1]
                geometrical_tag = physical_tag  # For simplicity, set geometrical tag equal to physical tag
                element_type = 1  # Line elements
                num_tags = 2
                for edge in edges:
                    node1, node2 = edge
                    elements_data.append((elem_id,
                                          element_type,
                                          num_tags,
                                          physical_tag,
                                          geometrical_tag,
                                          [node1+1, node2+1])) # +1 to match GMSH 1-based indexing
                    elem_id += 1

            # Write domain elements
            for elem_nodes in connectivity:
                num_nodes = len(elem_nodes)
                if num_nodes == 3:
                    element_type = 2  # Triangle
                elif num_nodes == 4:
                    element_type = 3  # Quadrangle
                elif num_nodes == 6:
                    element_type = 9  # 6-node second order triangle
                elif num_nodes == 8:
                    element_type = 16  # 8-node second order quadrangle
                else:
                    raise ValueError(f"Unsupported element with {num_nodes} nodes.")

                num_tags = 2
                physical_tag = domain_physical_tag
                geometrical_tag = physical_tag
                elements_data.append((elem_id,
                                      element_type,
                                      num_tags,
                                      physical_tag,
                                      geometrical_tag,
                                      [node+1 for node in elem_nodes])) # +1 to match GMSH 1-based indexing
                elem_id += 1

            # Write Elements section
            f.write('$Elements\n')
            f.write(f'{len(elements_data)}\n')
            for elem in elements_data:
                elem_id, elem_type, num_tags, physical_tag, geometrical_tag, node_ids = elem
                node_ids_str = ' '.join(map(str, node_ids))
                f.write(f'{elem_id} {elem_type} {num_tags} {physical_tag} {geometrical_tag} {node_ids_str}\n')
            f.write('$EndElements\n')
                    
        logger.info(f'GMSH type mesh saved as {name}')


class Smooth:

    def __init__(self, block):
        self.block = block

    def getNeighbours(self, node):
        """Get a list of neighbours around a node """

        i, j = node[0], node[1]
        neighbours = {1: (i - 1, j - 1), 2: (i, j - 1), 3: (i + 1, j - 1),
                      4: (i + 1, j), 5: (i + 1, j + 1), 6: (i, j + 1),
                      7: (i - 1, j + 1), 8: (i - 1, j)}
        return neighbours

    def smooth(self, nodes, iterations=1, algorithm='laplace'):
        """Smoothing of a square lattice mesh

        Algorithms:
           - Angle based
             Tian Zhou:
             AN ANGLE-BASED APPROACH TO TWO-DIMENSIONAL MESH SMOOTHING
           - Laplace
             Mean of surrounding node coordinates
           - Parallelogram smoothing
             Sanjay Kumar Khattri:
             A NEW SMOOTHING ALGORITHM FOR QUADRILATERAL AND HEXAHEDRAL MESHES

        Args:
            nodes (TYPE): List of (i, j) tuples for the nodes to be smoothed
            iterations (int, optional): Number of smoothing iterations
            algorithm (str, optional): Smoothing algorithm
        """

        # loop number of smoothing iterations
        for i in range(iterations):

            new_pos = list()

            # smooth a node (i, j)
            for node in nodes:
                nb = self.getNeighbours(node)

                if algorithm == 'laplace':
                    new_pos = (self.block.getNodeCoo(nb[2]) +
                               self.block.getNodeCoo(nb[4]) +
                               self.block.getNodeCoo(nb[6]) +
                               self.block.getNodeCoo(nb[8])) / 4.0

                if algorithm == 'parallelogram':

                    new_pos = (self.block.getNodeCoo(nb[1]) +
                               self.block.getNodeCoo(nb[3]) +
                               self.block.getNodeCoo(nb[5]) +
                               self.block.getNodeCoo(nb[7])) / 4.0 - \
                              (self.block.getNodeCoo(nb[2]) +
                               self.block.getNodeCoo(nb[4]) +
                               self.block.getNodeCoo(nb[6]) +
                               self.block.getNodeCoo(nb[8])) / 2.0

                if algorithm == 'angle_based':
                    pass

                self.block.setNodeCoo(node, new_pos.tolist())

        return self.block

    def selectNodes(self, domain='interior', ij=[]):
        """Generate a node index list

        Args:
            domain (str, optional): Defines the part of the domain where
                                    nodes shall be selected

        Returns:
            List: Indices as (i, j) tuples
        """
        U, V = self.block.getDivUV()
        nodes = list()

        # select all nodes except boundary nodes
        if domain == 'interior':
            istart = 1
            iend = U
            jstart = 1
            jend = V

        if domain == 'ij':
            istart = ij[0]
            iend = ij[1]
            jstart = ij[2]
            jend = ij[3]

        for i in range(istart, iend):
            for j in range(jstart, jend):
                nodes.append((i, j))

        return nodes
