import copy

import numpy as np
from scipy import interpolate

from PySide6 import QtGui, QtCore

from ContourData import SplineData
from CSTAirfoil import (
    METHOD_BSPLINE,
    METHOD_CST_MODIFIED,
    build_modified_cst_spline_data,
)
from MathUtils import VectorUtils
import GraphicsItemsCollection as gic
import GraphicsItem

import logging
logger = logging.getLogger(__name__)


class SplineRefine:
    MAX_REFINEMENT_RECURSIONS = 50
    MIN_REFINEMENT_PARAMETER_DELTA = 1.0e-10

    def __init__(self):

        # MainWindow instance
        self.mw = QtCore.QCoreApplication.instance().mainwindow
        self.spline_data = None

    def doSplineRefine(self, tolerance=172.0, points=150, ref_te=3,
                       ref_te_n=6, ref_te_ratio=3.0,
                       method=METHOD_BSPLINE, cst_order=8):

        logger.debug('Arrived in doSplineRefine')

        # get raw coordinates
        x, y = self.mw.airfoil.raw_coordinates

        if method == METHOD_CST_MODIFIED:
            self.spline_data = build_modified_cst_spline_data(
                (x, y),
                point_count=points,
                order=cst_order,
            )
            spline_data = copy.deepcopy(self.spline_data)
            self.spline_data = self.refine(spline_data, tolerance=tolerance)
        else:
            # interpolate a spline through the raw contour points
            # constant point distribution used here
            # typically nose radius poorly resolved by that
            self.spline_data = self.spline(x, y, points=points, degree=3)

            # refine the contour in order to meet the tolerance
            # this keeps the constant distribution but refines around the nose
            spline_data = copy.deepcopy(self.spline_data)
            self.spline_data = self.refine(spline_data, tolerance=tolerance)

            # redo spline on refined contour
            # spline only evaluated at refined contour points (evaluate=True)
            x, y = self.spline_data.coordinates
            self.spline_data = self.spline(x, y, points=points, degree=3,
                                           evaluate=True)

        # refine the trailing edge of the spline
        self.refine_te(ref_te, ref_te_n, ref_te_ratio)

        # add spline data to airfoil object
        self.mw.airfoil.spline_data = self.spline_data

    def getCamberThickness(self, spline_data, le_id):

        del le_id
        stations = np.linspace(0.0, 1.0, 300)
        upper = spline_data.upper_surface_parameters(stations)
        lower = spline_data.lower_surface_parameters(stations)
        coo_upper = spline_data.evaluate(upper, der=0)
        coo_lower = spline_data.evaluate(lower, der=0)

        camber = 0.5 * (np.array(coo_upper) + np.array(coo_lower))
        thickness_vectors = np.array(coo_upper) - np.array(coo_lower)
        paired_thickness = np.linalg.norm(thickness_vectors, axis=0)

        # maximum distance of y-coordinated to chord
        max_camber_id = int(np.argmax(camber[1]))
        max_camber = camber[1][max_camber_id]
        max_camber_pos = camber[0][max_camber_id]

        # Thickness is defined here by the distance between paired upper/lower
        # spline samples, preserving the deliberate parameter-based pairing.
        max_thickness_id = int(np.argmax(paired_thickness))
        max_thickness = paired_thickness[max_thickness_id]
        max_thickness_pos = camber[0][max_thickness_id]

        # since we work with unit chord, multiply with 100 for percent
        logger.info('Maximum thickness: {:5.2f} % at {:5.2f} % chord'
            .format(max_thickness*100.0, max_thickness_pos*100.0))

        # since we work with unit chord, multiply with 100 for percent
        logger.info('Maximum camber: {:5.2f} % at {:5.2f} % chord'
            .format(max_camber*100.0, max_camber_pos*100.0))

        return camber

    def makeLeCircle(self, rc, xc, yc, xle, yle):
        palette = self.mw.airfoil._display_palette()

        # delete exitsing LE circle ItemGroup from scene
        if hasattr(self.mw.airfoil, 'le_circle') and \
                self.mw.airfoil.le_circle in self.mw.scene.items():
            self.mw.scene.removeItem(self.mw.airfoil.le_circle)

        # put LE circle, center and tangent point in a list
        circles = list()

        circle = gic.GraphicsCollection()
        circle.pen.setColor(palette['le_circle_pen'])
        circle.pen.setWidthF(0.9)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(palette['le_circle_fill'])
        circle.Circle(xc, yc, rc)

        circle = GraphicsItem.GraphicsItem(circle)
        circle.setAcceptHoverEvents(False)
        circles.append(circle)

        circle = gic.GraphicsCollection()
        circle.pen.setColor(palette['le_center_pen'])
        circle.pen.setWidthF(0.95)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(palette['le_center_fill'])
        circle.Circle(xc, yc, 0.0002)

        circle = GraphicsItem.GraphicsItem(circle)
        circle.setAcceptHoverEvents(False)
        circles.append(circle)

        circle = gic.GraphicsCollection()
        circle.pen.setColor(palette['le_tangent_pen'])
        circle.pen.setWidthF(1.2)
        # no pen thickness change when zoomed
        circle.pen.setCosmetic(True)
        circle.brush.setColor(palette['le_tangent_fill'])
        circle.Circle(xle, yle, 0.0002)

        circle = GraphicsItem.GraphicsItem(circle)
        circle.setAcceptHoverEvents(False)
        circles.append(circle)

        self.mw.airfoil.le_circle = \
            self.mw.scene.createItemGroup(circles)
        self.mw.airfoil.le_circle.setZValue(110)

        self.mw.mainArea.leading_edge_circle_checkbox.setChecked(True)
        self.mw.mainArea.leading_edge_circle_checkbox.setEnabled(True)

    def spline(self, x, y, points=200, degree=2, evaluate=False):
        """Interpolate spline through given points

        Args:
            points (int, optional): Number of points used to sample the spline
            degree (int, optional): Degree of the spline
            evaluate (bool, optional): If True, evaluate the spline at the
                                       input-point parameters returned by
                                       splprep so the output matches the
                                       current contour points.
        """

        # Interpolate a parametric B-spline through the input contour points.
        # tck ... tuple (knots, coefficients, degree) describing the spline.
        # u   ... parameter value assigned by splprep to each input point.
        # NOTE: s=0.0 is important as no smoothing should be done on the spline
        # after interpolating it
        tck, u = interpolate.splprep([x, y], s=0.0, k=degree)

        # t is the parameter array used to sample the spline for coo/derivatives.
        t = np.linspace(0.0, 1.0, points)

        # When evaluate=True we keep the refined contour point distribution
        # instead of resampling it on a uniform parameter grid.
        if evaluate:
            t = u

        # evaluate B-spline at given parameters
        # der=0: returns point coordinates
        coo = interpolate.splev(t, tck, der=0)

        # evaluate 1st derivative at given parameters
        der1 = interpolate.splev(t, tck, der=1)

        # evaluate 2nd derivative at given parameters
        der2 = interpolate.splev(t, tck, der=2)

        return SplineData(
            coordinates=coo,
            fit_parameters=u,
            sample_parameters=t,
            first_derivative=der1,
            second_derivative=der2,
            spline=tck,
            method=METHOD_BSPLINE,
            metadata={
                'degree': degree,
                'label': 'B-spline',
            },
            leading_edge_parameter=float(t[int(np.argmin(coo[0]))]),
        )

    def _refreshSampledData(self, spline_data, parameters=None):
        if parameters is not None:
            spline_data.sample_parameters = np.asarray(parameters, dtype=float)

        t = np.asarray(spline_data.sample_parameters, dtype=float)
        spline_data.coordinates = tuple(
            np.asarray(values, dtype=float)
            for values in spline_data.evaluate(t, der=0)
        )
        spline_data.first_derivative = tuple(
            np.asarray(values, dtype=float)
            for values in spline_data.evaluate(t, der=1)
        )
        spline_data.second_derivative = tuple(
            np.asarray(values, dtype=float)
            for values in spline_data.evaluate(t, der=2)
        )
        spline_data.leading_edge_parameter = float(
            t[int(np.argmin(spline_data.coordinates[0]))]
        )
        return spline_data

    def rebuildSplineData(self, coordinates=None, degree=3, method=None,
                          cst_order=None):
        coordinates = coordinates or (
            self.spline_data.coordinates if self.spline_data is not None else None
        )
        if coordinates is None:
            return None

        x, y = coordinates
        point_count = len(x)
        if point_count < 2:
            return None

        template = self.spline_data
        if template is None:
            template = getattr(getattr(self.mw, 'airfoil', None), 'spline_data', None)

        active_method = method or getattr(template, 'method', METHOD_BSPLINE)
        if active_method == METHOD_CST_MODIFIED:
            order = cst_order
            if order is None and template is not None:
                order = getattr(template, 'metadata', {}).get('order')
            order = 8 if order is None else int(order)

            sample_parameters = None
            if template is not None and \
                    getattr(template, 'sample_parameters', None) is not None and \
                    len(template.sample_parameters) == point_count:
                sample_parameters = np.asarray(template.sample_parameters, dtype=float)

            self.spline_data = build_modified_cst_spline_data(
                (x, y),
                order=order,
                sample_parameters=sample_parameters,
            )
            return self.spline_data

        degree = max(1, min(degree, point_count - 1))
        self.spline_data = self.spline(
            x,
            y,
            points=point_count,
            degree=degree,
            evaluate=True,
        )
        return self.spline_data

    def _finalizeRefinement(self, spline_data, recursions, reason):
        self._refreshSampledData(spline_data)

        logger.debug(reason)
        logger.debug(
            '\nTotal number of recursive refinement passes: {}'
            .format(recursions)
        )

        self.spline_data = copy.deepcopy(spline_data)
        return self.spline_data

    def _canInsertRefinementParameters(self, *parameters, min_parameter_delta):
        parameters = np.asarray(parameters, dtype=float)
        differences = np.abs(parameters[:, None] - parameters[None, :])
        differences = differences[np.triu_indices(len(parameters), k=1)]
        return bool(np.all(differences > min_parameter_delta))

    def refine(self, spline_data, tolerance=170.0, recursions=0,
               max_recursions=None, min_parameter_delta=None):
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
        max_recursions = (
            self.MAX_REFINEMENT_RECURSIONS
            if max_recursions is None else
            int(max_recursions)
        )
        min_parameter_delta = (
            self.MIN_REFINEMENT_PARAMETER_DELTA
            if min_parameter_delta is None else
            float(min_parameter_delta)
        )

        xx, yy = spline_data.coordinates
        t = spline_data.sample_parameters

        logger.debug('\nPoints before refining: {} \n'.format(len(xx)))
        if recursions > 0:
            logger.debug('Refinement recursion level: {}'.format(recursions))

        if recursions >= max_recursions:
            return self._finalizeRefinement(
                spline_data,
                recursions,
                'Reached maximum recursive refinement depth ({}).'
                .format(max_recursions),
            )

        if len(xx) < 3:
            return self._finalizeRefinement(
                spline_data,
                recursions,
                'Refinement stopped because fewer than three contour points remain.',
            )

        refinements = 0
        refined = [False] * (len(xx) - 2)
        spacing_limited = 0

        for i in range(len(xx) - 2):
            # angle between two contour line segments
            a = np.array([xx[i], yy[i]])
            b = np.array([xx[i + 1], yy[i + 1]])
            c = np.array([xx[i + 2], yy[i + 2]])
            angle = VectorUtils.angle_between(a - b, c - b, degree=True)

            if angle < tolerance:
                # parameters for new points
                t1 = (t[i] + t[i + 1]) / 2.
                t2 = (t[i + 1] + t[i + 2]) / 2.
                can_insert = self._canInsertRefinementParameters(
                    t[i], t1, t[i + 1], t2, t[i + 2],
                    min_parameter_delta=min_parameter_delta,
                )
                if not can_insert:
                    spacing_limited += 1
                    continue

                logger.debug('Refining between segments {} {},'
                             .format(i, i + 1))
                logger.debug('Tol={0:5.1f}, Angle={1:05.1f}\n'
                             .format(tolerance, angle))

                refined[i] = True
                refinements += 1

        xn = [float(xx[0])]
        yn = [float(yy[0])]
        tn = [float(t[0])]

        for segment_index in range(len(xx) - 1):
            # Preserve the existing midpoint insertion rule from the recursive
            # implementation: interior segments receive one midpoint if either
            # adjacent refinement triplet requested it.
            if segment_index > 0:
                insert_midpoint = refined[segment_index - 1]
                if segment_index < len(refined):
                    insert_midpoint = insert_midpoint or refined[segment_index]
                if insert_midpoint:
                    t_mid = 0.5 * (t[segment_index] + t[segment_index + 1])
                    p_mid = spline_data.evaluate(t_mid, der=0)
                    xn.append(float(p_mid[0]))
                    yn.append(float(p_mid[1]))
                    tn.append(float(t_mid))

            xn.append(float(xx[segment_index + 1]))
            yn.append(float(yy[segment_index + 1]))
            tn.append(float(t[segment_index + 1]))

        logger.debug('Points after refining: {}'.format(len(xn)))

        # update coordinate array, including inserted points
        spline_data.coordinates = (
            np.asarray(xn, dtype=float),
            np.asarray(yn, dtype=float),
        )
        # update parameter array, including parameters of inserted points
        spline_data.sample_parameters = np.asarray(tn, dtype=float)

        # this is the recursion :)
        if refinements > 0:
            return self.refine(
                spline_data,
                tolerance=tolerance,
                recursions=recursions + 1,
                max_recursions=max_recursions,
                min_parameter_delta=min_parameter_delta,
            )

        # stopping from recursion if no refinements done in this recursion
        reason = 'No more refinements.'
        if spacing_limited > 0:
            reason = (
                'No more refinements. Minimum parameter spacing blocked {} '
                'candidate insertions.'
            ).format(spacing_limited)
        return self._finalizeRefinement(spline_data, recursions, reason)

    def refine_te(self, ref_te, ref_te_n, ref_te_ratio):
        """Refine the airfoil contour at the trailing edge

        Args:
            ref_te (int): Number of original points removed per side near the
                trailing edge before reinserting the refined distribution.
            ref_te_n (int): Number of refined subdivisions used per side.
            ref_te_ratio (float): Growth ratio used for the refined spacing.
        """
        # get parameter of point to which refinement reaches
        tref = self.spline_data.sample_parameters[ref_te]

        # calculate the new spacing at the trailing edge points
        spacing = self.spacing(divisions=ref_te_n, ratio=ref_te_ratio,
                               thickness=tref)

        # insert new points with the spacing into the airfoil contour data

        x, y = self.spline_data.coordinates
        t = self.spline_data.sample_parameters

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
            p = self.spline_data.evaluate(s, der=0)
            x = np.insert(x, 0, p[0])
            y = np.insert(y, 0, p[1])
            t = np.insert(t, 0, s)
            # lower side
            p = self.spline_data.evaluate(1. - s, der=0)
            x = np.append(x, p[0])
            y = np.append(y, p[1])
            t = np.append(t, 1. - s)

        self.spline_data.coordinates = (x, y)
        self._refreshSampledData(self.spline_data, parameters=t)

    def spacing(self, divisions=10, ratio=1.0, thickness=1.0):
        """Calculate point distribution on a line

        Args:
            divisions (int, optional): Number of subdivisions
            ratio (float, optional): Ratio of last to first subdivision size
            thickness (float, optional): length of line

        Returns:
            np.ndarray: Normalized spacing scaled to ``thickness``.
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
