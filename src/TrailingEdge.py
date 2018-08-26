import copy

import numpy as np

from PySide2 import QtGui, QtCore
from Utils import Utils
import ContourAnalysis as pca


class TrailingEdge:

    def __init__(self, id):

        self.id = id

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow

        # get spline data from airfoil object
        self.spline_data = self.mainwindow.airfoils[self.id].spline_data

        # contour analysis instance (no canvas/drawing needed)
        self.contour = pca.ContourAnalysis(None, canvas=False)
        self.contour.spline_data = self.spline_data
        self.contour.getCurvature()

    def getUpperLower(self):
        """Split contour in upper and lower parts

        Returns:
            TYPE: Coordinates of upper and lower contours
        """
        # leading edge radius
        rc, xc, yc, xle, yle, le_id = self.contour.getLeRadius()

        x, y = self.spline_data[0]
        upper = (x[:le_id + 1], y[:le_id + 1])
        lower = (x[le_id:], y[le_id:])

        return upper, lower

    def trailingEdge(self, blend=0.3, ex=3.0, thickness=0.6, side='both'):
        """Implement a finite trailing edge thicknes into the original
        contour

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
        self.mainwindow.airfoils[self.id].spline_data[0] = (xt, yt)

        # add splined and refined contour to the airfoil contourGroup
        for airfoil in self.mainwindow.airfoils:
            if airfoil.contourPolygon.isSelected():
                airfoil.makeContourSpline()
                airfoil.makeSplineMarkers()
                airfoil.addSplineMarkers()
                airfoil.contourSpline.brush.setStyle(
                    QtCore.Qt.SolidPattern)
                color = QtGui.QColor()
                color.setNamedColor('#7c8696')
                airfoil.contourSpline.brush.setColor(color)
                airfoil.polygonMarkersGroup.setZValue(100)
                airfoil.chord.setZValue(99)
                airfoil.polygonMarkersGroup.setVisible(False)
                airfoil.contourPolygon.brush.setStyle(QtCore.Qt.NoBrush)
                airfoil.contourPolygon.pen.setStyle(QtCore.Qt.NoPen)
                # self.mainwindow.view.adjustMarkerSize()

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

    def writeContour(self):

        xr = self.raw_coordinates[0]
        xc = self.coordinates[0]
        yc = self.coordinates[1]
        s = '# Trailing edge added to initial contour'.format(len(xc))
        s1 = '({0} points)\n'.format(len(xr))
        info = s + s1

        with open(self.name + '_TE' + '.dat', 'w') as f:
            f.write('#\n')
            f.write('# Airfoil: ' + self.name + '\n')
            f.write('# Created from ' + self.filename + '\n')
            f.write(info)
            f.write('#\n')
            for i in range(len(xc)):
                data = '{:10.8f} {:10.8f} \n'.format(xc[i], yc[i])
                f.write(data)
