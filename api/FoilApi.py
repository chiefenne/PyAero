import numpy as np
import logging
import matplotlib.pyplot as plt
from scipy import interpolate
import copy
from Utils import Utils
logger = logging.getLogger(__name__)


class FoilApi:
    def __init__(self, name='foil'):
        """
        build apis to be called as a package
        """
        # foil_data_shape:(2, pointsnum)
        self.raw_coordinates = None
        self.spline_data = None
        # self.foilxy = None
        self.name = name
        self.has_TE = None
        self.offset = None

        self.refine_parameters = {
            "Airfoil contour refinement": {
            "Refinement tolerance": 172.0,
            "Refine trailing edge old": 3,
            "Refine trailing edge new": 6,
            "Refine trailing edge ratio" : 3,
            "Number of points on spline" : 200
            },
            "Airfoil trailing edge": {
            "Upper side blending length": 30.0,
            "Lower side blending length": 30.0,
            "Upper blending polynomial exponent": 3,
            "Lower blending polynomial exponent" : 3,
            "Trailing edge thickness relative to chord" : 0.4
            }
        }

    def readContour(self, file_path, comment):
        try:
            with open(file_path, mode='r') as f:
                lines = f.readlines()
        except IOError as error:
            # exc_info=True sends traceback to the logger
            logger.error('Failed to open file {} with error {}'. \
                         format(file_path, error), exc_info=True)
            return False

        data = [line for line in lines if comment not in line]

        try:
            x = [float(l.split()[0]) for l in data]
            y = [float(l.split()[1]) for l in data]
        except (ValueError, IndexError) as error:
            logger.error('Unable to parse file file {}'. \
                         format(file_path))
            logger.error('Following error occured: {}'.format(error))
            return False
        except:
            # exc_info=True sends traceback to the logger
            logger.error('Unable to parse file file {}. Unknown error caught'\
                         .format(file_path), exc_info=True)
            return False

        # store airfoil coordinates as list of tuples
        self.raw_coordinates = np.array((x, y))

        # normalize airfoil to unit chord
        self.raw_coordinates[0] -= np.min(x)
        divisor = np.max(self.raw_coordinates[0])
        self.raw_coordinates[0] /= divisor
        self.raw_coordinates[1] /= divisor
        self.offset = [np.min(y), np.max(y)]

        return True

    def doSplineRefine(self):
        refinement = self.refine_parameters['Airfoil contour refinement']
        tolerance=refinement['Refinement tolerance']
        points=refinement['Number of points on spline']
        ref_te=refinement['Refine trailing edge old']
        ref_te_n=refinement['Refine trailing edge new']
        ref_te_ratio=refinement['Refine trailing edge ratio']

        logger.debug('Arrived in doSplineRefine')

        # get raw coordinates
        x, y = self.raw_coordinates[0, :], self.raw_coordinates[1, :]

        # interpolate a spline through the raw contour points
        # constant point distribution used here
        # typically nose radius poorly resolevd by that
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
        self.spline_data = self.spline_data

    def addTrailingEdge(self):
        te = self.refine_parameters['Airfoil trailing edge']

        self.trailingEdge(blend=te['Upper side blending length'] / 100.0,
                            ex=te['Upper blending polynomial exponent'],
                            thickness=te['Trailing edge thickness relative to chord'],
                            side='upper')

        self.trailingEdge(blend=te['Lower side blending length'] / 100.0,
                            ex=te['Lower blending polynomial exponent'],
                            thickness=te['Trailing edge thickness relative to chord'],
                            side='lower')

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
            return None


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

    def getUpperLower(self):
        """Split contour in upper and lower parts

        Returns:
            TYPE: Coordinates of upper and lower contours
        """
        # leading edge radius
        # get LE radius, etc.
        spline_data = self.spline_data
        curvature_data = self.getCurvature(spline_data)
        rc, xc, yc, xle, yle, le_id = self.getLeRadius(spline_data,
                                                               curvature_data)

        x, y = spline_data[0]
        upper = (x[:le_id + 1], y[:le_id + 1])
        lower = (x[le_id:], y[le_id:])

        return upper, lower

    def trailingEdge(self, blend=0.3, ex=3.0, thickness=0.6, side='both'):
        """Implement a finite trailing edge thickness into the original
        contour (i.e. a blunt trailing edge)

        Args:
            blend (float, optional): Length to blend the TE
            ex (float, optional): Exponent that modifies the blending
                                  curve
            thickness (float, optional): TE thickness
            side (str, optional): Defines if blending is done on upper,
                                  lower or both sides

        Returns:
            tuple: Updated spline coordinates
        """
        upper, lower = self.getUpperLower()
        xu = copy.copy(upper[0])
        yu = copy.copy(upper[1])
        xl = copy.copy(lower[0])
        yl = copy.copy(lower[1])
        xnu = copy.copy(xu)
        ynu = copy.copy(yu)
        xnl = copy.copy(xl)
        ynl = copy.copy(yl)
        if side == 'upper' or side == 'both':
            xnu, ynu = self.trailing(xu, yu, blend, ex, thickness,
                                     side='upper')
        if side == 'lower' or side == 'both':
            xnl, ynl = self.trailing(xl, yl, blend, ex, thickness,
                                     side='lower')
        xt = np.concatenate([xnu, xnl[1:]])
        yt = np.concatenate([ynu, ynl[1:]])
        self.spline_data[0] = (xt, yt)

    def trailing(self, xx, yy, blend, ex, thickness, side='upper'):
        xmin = np.min(xx)
        xmax = np.max(xx)
        chord = xmax - xmin
        thickness = chord * thickness / 100.0
        blend_points = np.where(xx > (1.0 - blend) * xmax)
        x = copy.copy(xx)
        y = copy.copy(yy)
        if side == 'upper':
            signum = 1.0
            a = np.array([x[1] - x[0], y[1] - y[0]])
        elif side == 'lower':
            signum = -1.0
            a = np.array([x[-2] - x[-1], y[-2] - y[-1]])
        e = Utils.unit_vector(a)
        n = np.array([e[1], -e[0]])
        shift = 0.5 * thickness
        for i in blend_points:
            shift_blend = (x[i] - xmax * (1.0 - blend)) / \
                          (xmax * blend)
            x[i] = x[i] + signum * n[0] * shift_blend**ex * shift
            y[i] = y[i] + signum * n[1] * shift_blend**ex * shift
        return x, y

    @staticmethod
    def getCurvature(spline_data):
        """Curvature and radius of curvature of a parametric curve

        der1 is dx/dt and dy/dt at each point
        der2 is d2x/dt2 and d2y/dt2 at each point

        Returns:
            float: Tuple of numpy arrays carrying gradient of the curve,
                   the curvature, radiusses of curvature circles and
                   curvature circle centers for each point of the curve
        """

        coo = spline_data[0]
        der1 = spline_data[3]
        der2 = spline_data[4]

        xd = der1[0]
        yd = der1[1]
        x2d = der2[0]
        y2d = der2[1]
        n = xd**2 + yd**2
        d = xd*y2d - yd*x2d

        # gradient dy/dx = dy/du / dx/du
        gradient = der1[1] / der1[0]

        # radius of curvature
        R = n**(3./2.) / abs(d)

        # curvature
        C = d / n**(3./2.)

        # coordinates of curvature-circle center points
        xc = coo[0] - R * yd / np.sqrt(n)
        yc = coo[1] + R * xd / np.sqrt(n)

        return [gradient, C, R, xc, yc]

    @staticmethod
    def getLeRadius(spline_data, curvature_data):
        """Identify leading edge radius, i.e. smallest radius of
        parametric curve

        Returns:
            FLOAT: leading edge radius, its center and related contour
            point and id
        """

        radius = curvature_data[2]
        rc = np.min(radius)
        # numpy where returns a tuple
        # we take the first element, which is type array
        le_id = np.where(radius == rc)[0]
        # convert the numpy array to a list and take the first element
        le_id = le_id.tolist()[0]
        # leading edge curvature circle center
        xc = curvature_data[3][le_id]
        yc = curvature_data[4][le_id]
        xr, yr = spline_data[0]
        xle = xr[le_id]
        yle = yr[le_id]

        return rc, xc, yc, xle, yle, le_id

# class TrailingEdge:

#     def __init__(self, airfoil):

#         # get MainWindow instance (overcomes handling parents)
#         # self.mainwindow = QtCore.QCoreApplication.instance().mainwindow
#         self.airfoil = airfoil



# x = FoilApi()
# x.readContour('../data/Airfoils/F3B-F3F/hs179.dat', '#')
# x.doSplineRefine()
# xy = x.spline_data[0]

# plt.plot(xy[0], xy[1])
# plt.show()
