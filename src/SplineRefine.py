import copy

import numpy as np
from scipy import interpolate

from PySide6 import QtGui, QtCore

from Utils import Utils
import GraphicsItemsCollection as gic
import GraphicsItem

import logging
logger = logging.getLogger(__name__)


class SplineRefine:

    def __init__(self):

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

    def doSplineRefine(self, tolerance=172.0, points=150, ref_te=3,
                       ref_te_n=6, ref_te_ratio=3.0):

        logger.debug('Arrived in doSplineRefine')

        # get raw coordinates
        x, y = self.mainwindow.airfoil.raw_coordinates

        # interpolate a spline through the raw contour points
        # constant point distribution used here
        # typically nose radius poorly resolved by that
        self.spline_data = self.spline(x, y, points=points, degree=3)

        # refine the contour in order to meet the tolerance
        # this keeps the constant distribution but refines around the nose
        spline_data = copy.deepcopy(self.spline_data)
        self.refine(spline_data, tolerance=tolerance)

        # redo spline on refined contour
        # spline only evaluated at refined contour points (evaluate=True)
        coo, u, t, der1, der2, tck = self.spline_data
        x, y = coo
        self.spline_data = self.spline(x, y, points=points, degree=3,
                                       evaluate=True)

        # refine the trailing edge of the spline
        self.refine_te(ref_te, ref_te_n, ref_te_ratio)

        # add spline data to airfoil object
        self.mainwindow.airfoil.spline_data = self.spline_data

    def getCamberThickness(self, spline_data, le_id):

        # split airfoil spline at leading edge
        # FIXME
        # FIXME why do I need to substract -3 here to be at LE ????
        # FIXME
        u_le = spline_data[1][le_id - 3]
        upper = np.linspace(u_le, 0.0, 300)
        lower = np.linspace(u_le, 1.0, 300)
        tck = spline_data[5]
        coo_upper = interpolate.splev(upper, tck, der=0)
        coo_lower = interpolate.splev(lower, tck, der=0)

        camber = 0.5 * (np.array(coo_upper) + np.array(coo_lower))
        thickness = np.array(coo_upper) - np.array(coo_lower)

        # maximum distance of y-coordinated to chord
        max_camber = np.max(camber[1])
        pos_camber = np.where(camber[1] == max_camber)
        max_camber_pos = camber[0][pos_camber][0]

        # maximum thickness
        max_thickness = np.max(thickness)
        pos_thickness = np.where(thickness == max_thickness)[1]
        # print('coo_upper[0]', coo_upper[0])
        max_thickness_pos = coo_upper[0][pos_thickness][0]

        # since we work with unit chord, multiply with 100 for percent
        logger.info('Maximum thickness: {:5.2f} % at {:5.2f} % chord'
            .format(max_thickness*100.0, max_thickness_pos*100.0))

        # since we work with unit chord, multiply with 100 for percent
        logger.info('Maximum camber: {:5.2f} % at {:5.2f} % chord'
            .format(max_camber*100.0, max_camber_pos*100.0))

        return camber

    def makeLeCircle(self, rc, xc, yc, xle, yle):

        # delete exitsing LE circle ItemGroup from scene
        if hasattr(self.mainwindow.airfoil, 'le_circle') and \
                self.mainwindow.airfoil.le_circle in self.mainwindow.scene.items():
            self.mainwindow.scene.removeItem(self.mainwindow.airfoil.le_circle)

        # put LE circle, center and tangent point in a list
        circles = list()

        circle = gic.GraphicsCollection()
        circle.pen.setColor(QtGui.QColor(0, 150, 0, 255))
        circle.pen.setWidthF(0.3)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(QtGui.QColor(10, 200, 10, 150))
        circle.Circle(xc, yc, rc)

        circle = GraphicsItem.GraphicsItem(circle)
        circles.append(circle)

        circle = gic.GraphicsCollection()
        circle.pen.setColor(QtGui.QColor(255, 0, 0, 255))
        circle.pen.setWidthF(0.3)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(QtGui.QColor(255, 0, 0, 255))
        circle.Circle(xc, yc, 0.0002)

        circle = GraphicsItem.GraphicsItem(circle)
        circles.append(circle)

        circle = gic.GraphicsCollection()
        circle.pen.setColor(QtGui.QColor(255, 0, 0, 255))
        circle.pen.setWidthF(1.6)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(QtGui.QColor(255, 0, 0, 255))
        circle.Circle(xle, yle, 0.0002)

        circle = GraphicsItem.GraphicsItem(circle)
        circles.append(circle)

        self.mainwindow.airfoil.le_circle = \
            self.mainwindow.scene.createItemGroup(circles)
        self.mainwindow.airfoil.le_circle.setZValue(110)

        self.mainwindow.centralwidget.leading_edge_circle_checkbox.setChecked(True)
        self.mainwindow.centralwidget.leading_edge_circle_checkbox.setEnabled(True)

    def spline(self, x, y, points=200, degree=2, evaluate=False):
        """Interpolate spline through given points

        Args:
            spline (int, optional): Number of points on the spline
            degree (int, optional): Degree of the spline
            evaluate (bool, optional): If True, evaluate spline just at
                                       the coordinates of the knots
        """

        # interpolate B-spline through data points
        # returns knots of control polygon
        # tck ... tuple (t,c,k) containing the vector of knots,
        # the B-spline coefficients, and the degree of the spline.
        # u ... array of the parameters for each knot
        # NOTE: s=0.0 is important as no smoothing should be done on the spline
        # after interpolating it
        tck, u = interpolate.splprep([x, y], s=0.0, k=degree)

        # number of points on interpolated B-spline (parameter t)
        t = np.linspace(0.0, 1.0, points)

        # if True, evaluate spline just at the coordinates of the knots
        if evaluate:
            t = u

        # evaluate B-spline at given parameters
        # der=0: returns point coordinates
        coo = interpolate.splev(t, tck, der=0)

        # evaluate 1st derivative at given parameters
        der1 = interpolate.splev(t, tck, der=1)

        # evaluate 2nd derivative at given parameters
        der2 = interpolate.splev(t, tck, der=2)

        spline_data = [coo, u, t, der1, der2, tck]

        return spline_data

    def refine(self, spline_data, tolerance=170.0, recursions=0):
        """Recursive refinement with respect to angle criterion (tol).
        If angle between two adjacent line segments is less than tol,
        a recursive refinement of the contour is performed until
        tol is met.

        Args:
            tol (float, optional): Angle between two adjacent contour segments
            recursions (int, optional): NO USER INPUT HERE
                                        Needed just for level information
                                        during recursions
        """

        # self.spline_data = [coo, u, t, der1, der2, tck]
        xx, yy = spline_data[0]
        t = spline_data[2]
        tck = spline_data[5]

        logger.debug('\nPoints before refining: {} \n'.format(len(xx)))

        xn = copy.deepcopy(xx)
        yn = copy.deepcopy(yy)
        tn = copy.deepcopy(t)

        j = 0
        refinements = 0
        first = True
        refined = dict()

        for i in range(len(xx) - 2):
            refined[i] = False

            # angle between two contour line segments
            a = np.array([xx[i], yy[i]])
            b = np.array([xx[i + 1], yy[i + 1]])
            c = np.array([xx[i + 2], yy[i + 2]])
            angle = Utils.angle_between(a - b, c - b, degree=True)

            if angle < tolerance:

                logger.debug('Refining between segments {} {},'
                             .format(i, i + 1))
                logger.debug('Tol={0:5.1f}, Angle={1:05.1f}\n'
                             .format(tolerance, angle))

                refined[i] = True
                refinements += 1

                # parameters for new points
                t1 = (t[i] + t[i + 1]) / 2.
                t2 = (t[i + 1] + t[i + 2]) / 2.

                # coordinates of new points
                p1 = interpolate.splev(t1, tck, der=0)
                p2 = interpolate.splev(t2, tck, der=0)

                # insert points and their parameters into arrays
                if i > 0 and not refined[i - 1]:
                    xn = np.insert(xn, i + 1 + j, p1[0])
                    yn = np.insert(yn, i + 1 + j, p1[1])
                    tn = np.insert(tn, i + 1 + j, t1)
                    j += 1
                xn = np.insert(xn, i + 2 + j, p2[0])
                yn = np.insert(yn, i + 2 + j, p2[1])
                tn = np.insert(tn, i + 2 + j, t2)
                j += 1

                if first and recursions > 0:
                    logger.debug('Recursion level: {} \n'.format(recursions))
                    first = False

        logger.debug('Points after refining: {}'.format(len(xn)))

        # update coordinate array, including inserted points
        spline_data[0] = (xn, yn)
        # update parameter array, including parameters of inserted points
        spline_data[2] = tn

        # this is the recursion :)
        if refinements > 0:
            self.refine(spline_data, tolerance, recursions + 1)

        # stopping from recursion if no refinements done in this recursion
        else:
            # update derivatives, including inserted points
            spline_data[3] = interpolate.splev(tn, tck, der=1)
            spline_data[4] = interpolate.splev(tn, tck, der=2)

            logger.debug('No more refinements.')
            logger.debug('\nTotal number of recursions: {}'
                         .format(recursions - 1))

            # due to recursive call to refine, here no object can be returned
            # instead use self to transfer data to the outer world :)
            self.spline_data = copy.deepcopy(spline_data)
            return

    def refine_te(self, ref_te, ref_te_n, ref_te_ratio):
        """Refine the airfoil contour at the trailing edge

        Args:
            ref_te (TYPE): Description
            ref_te_n (TYPE): Description
            ref_te_ratio (TYPE): Description

        Returns:
            TYPE: Description
        """
        # get parameter of point to which refinement reaches
        tref = self.spline_data[2][ref_te]

        # calculate the new spacing at the trailing edge points
        spacing = self.spacing(divisions=ref_te_n, ratio=ref_te_ratio,
                               thickness=tref)

        # insert new points with the spacing into the airfoil contour data

        x, y = self.spline_data[0]
        t = self.spline_data[2]
        tck = self.spline_data[5]

        # remove points which will be refined
        index = range(ref_te + 1)
        x = np.delete(x, index)
        y = np.delete(y, index)
        t = np.delete(t, index)

        index = range(len(x))[-(ref_te + 1):]
        x = np.delete(x, index)
        y = np.delete(y, index)
        t = np.delete(t, index)

        # add refined points
        for s in spacing[::-1]:
            # upper side
            p = interpolate.splev(s, tck, der=0)
            x = np.insert(x, 0, p[0])
            y = np.insert(y, 0, p[1])
            t = np.insert(t, 0, s)
            # lower side
            p = interpolate.splev(1. - s, tck, der=0)
            x = np.append(x, p[0])
            y = np.append(y, p[1])
            t = np.append(t, 1. - s)

        # update coordinate array, including inserted points
        self.spline_data[0] = (x, y)
        # update parameter array, including parameters of inserted points
        self.spline_data[2] = t
        # update derivatives, including inserted points
        self.spline_data[3] = interpolate.splev(t, tck, der=1)
        self.spline_data[4] = interpolate.splev(t, tck, der=2)

    def spacing(self, divisions=10, ratio=1.0, thickness=1.0):
        """Calculate point distribution on a line

        Args:
            divisions (int, optional): Number of subdivisions
            ratio (float, optional): Ratio of last to first subdivision size
            thickness (float, optional): length of line

        Returns:
            TYPE: Description
        """
        if divisions == 1:
            sp = [0.0, 1.0]
            return np.array(sp)

        growth = ratio**(1.0 / (float(divisions) - 1.0))

        if growth == 1.0:
            growth = 1.0 + 1.0e-10

        s0 = 1.0
        s = [s0]
        for i in range(1, divisions + 1):
            app = s0 * growth**i
            s.append(app)
        sp = np.array(s)
        sp -= sp[0]
        sp /= sp[-1]
        sp *= thickness
        return sp

    def writeContour(self):

        xr = self.raw_coordinates[0]
        xc = self.coordinates[0]
        yc = self.coordinates[1]
        s = '# Spline with {0} points based on initial contour'.format(len(xc))
        s1 = '({0} points)\n'.format(len(xr))
        info = s + s1

        with open(self.name + '_spline_' + str(len(xc)) + '.dat', 'w') as f:
            f.write('#\n')
            f.write('# Airfoil: ' + self.name + '\n')
            f.write('# Created from ' + self.filename + '\n')
            f.write(info)
            f.write('#\n')
            for i in range(len(xc)):
                data = '{:10.8f} {:10.8f} \n'.format(xc[i], yc[i])
                f.write(data)
