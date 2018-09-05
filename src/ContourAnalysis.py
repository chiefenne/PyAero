
import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

import logging
logger = logging.getLogger(__name__)


class ContourAnalysis(QtWidgets.QFrame):
    """Summary

    Attributes:
        canvas (TYPE): Description
        figure (TYPE): Description
        raw_coordinates (list): contour points as tuples
        toolbar (TYPE): Description
    """
    def __init__(self, canvas=False):
        super().__init__()

        # get MainWindow instance (overcomes handling parents)
        self.mainwindow = QtCore.QCoreApplication.instance().mainwindow
        
        # run the gui part only when canvas set to true
        if canvas:
            self.initUI()

    def initUI(self):
        pass

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

    def analyze(self):

        # get specific curve properties
        spline_data = self.mainwindow.airfoil.spline_data
        curvature_data = ContourAnalysis.getCurvature(spline_data)

        # add new attributes to airfoil instance
        self.mainwindow.airfoil.curvature_data = curvature_data

        self.drawContour()

    def drawContour(self, quantity='gradient'):
        """quantity is one of 'gradient', 'curvature', 'radius' """
        pass
