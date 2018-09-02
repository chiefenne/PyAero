
# from matplotlib.backends.backend_qt4agg \
#     import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.backends.backend_qt4agg \
#     import NavigationToolbar2QT as NavigationToolbar
# import matplotlib.pyplot as plt
# import matplotlib.patches as patches
import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

import logging
logger = logging.getLogger(__name__)


class ContourAnalysis(QtWidgets.QFrame):
    """Summary

    Attributes:
        canvas (TYPE): Description
        curvature_data (TYPE): Description
        figure (TYPE): Description
        parent (QMainWindow object): MainWindow instance
        raw_coordinates (list): contour points as tuples
        spline_data (TYPE): Description
        toolbar (TYPE): Description
    """
    def __init__(self, parent, canvas=False):
        super().__init__(parent)

        self.parent = parent
        self.spline_data = None
        self.curvature_data = None

        # run the gui part only when canvas set to true
        if canvas:
            self.initUI()

    def initUI(self):

        # a figure instance to plot on
        self.figure_top = plt.figure(figsize=(25, 35), tight_layout=True)
        self.figure_center = plt.figure(figsize=(25, 35), tight_layout=True)
        self.figure_bottom = plt.figure(figsize=(25, 35), tight_layout=True)

        # background of figures
        r, g, b = 170./255., 170./255., 170./255.
        self.figure_top.patch.set_facecolor(color=(r, g, b))
        self.figure_center.patch.set_facecolor(color=(r, g, b))
        self.figure_bottom.patch.set_facecolor(color=(r, g, b))

        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        self.canvas_top = FigureCanvas(self.figure_top)
        self.canvas_center = FigureCanvas(self.figure_center)
        self.canvas_bottom = FigureCanvas(self.figure_bottom)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        self.toolbar_top = NavigationToolbar(self.canvas_top, self)
        self.toolbar_center = NavigationToolbar(self.canvas_center, self)
        self.toolbar_bottom = NavigationToolbar(self.canvas_bottom, self,
                                                coordinates=True)

        vbox1 = QtGui.QVBoxLayout()
        vbox1.addWidget(self.canvas_top)
        vbox1.addWidget(self.toolbar_top)
        widget1 = QtGui.QWidget()
        widget1.setLayout(vbox1)
        vbox2 = QtGui.QVBoxLayout()
        vbox2.addWidget(self.canvas_center)
        vbox2.addWidget(self.toolbar_center)
        widget2 = QtGui.QWidget()
        widget2.setLayout(vbox2)
        vbox3 = QtGui.QVBoxLayout()
        vbox3.addWidget(self.canvas_bottom)
        vbox3.addWidget(self.toolbar_bottom)
        widget3 = QtGui.QWidget()
        widget3.setLayout(vbox3)

        splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(widget1)
        splitter.addWidget(widget2)
        splitter.addWidget(widget3)
        splitter.setSizes([400, 400, 800])
        splitter.setHandleWidth(6)

        # set the layout
        layout = QtGui.QVBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)

        # make handle of splitter visible
        handle = splitter.handle(1)
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        button = QtGui.QToolButton(handle)
        button.setArrowType(QtCore.Qt.NoArrow)
        layout.addWidget(button)
        layout.setAlignment(button, QtCore.Qt.AlignCenter)
        handle.setLayout(layout)
        handle = splitter.handle(2)
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        button = QtGui.QToolButton(handle)
        button.setArrowType(QtCore.Qt.NoArrow)
        layout.addWidget(button)
        layout.setAlignment(button, QtCore.Qt.AlignCenter)
        handle.setLayout(layout)

    def reset(self):
        self.spline_data = None
        self.curvature_data = None

        # clears the current figure
        # necessary so that changing between gradient, radius, etc. works
        plt.clf()

    def getCurvature(self):
        """Curvature and radius of curvature of a parametric curve

        der1 is dx/dt and dy/dt at each point
        der2 is d2x/dt2 and d2y/dt2 at each point

        Returns:
            float: Tuple of numpy arrays carrying gradient of the curve,
                   the curvature, radiusses of curvature circles and
                   curvature circle centers for each point of the curve
        """

        coo = self.spline_data[0]
        der1 = self.spline_data[3]
        der2 = self.spline_data[4]

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

        self.curvature_data = [gradient, C, R, xc, yc]
        return

    def analyze(self, plot, reset=True):

        if reset:
            logger.debug('Printing stack', exc_info=True)
            self.reset()

        # get specific curve properties
        self.getCurvature()

        # add new attributes to airfoil instance
        self.parent.airfoil.spline_data = self.spline_data
        self.parent.airfoil.curvature_data = self.curvature_data

        self.drawContour(plot)

    def getLeRadius(self):
        """Identify leading edge radius, i.e. smallest radius of
        parametric curve

        Returns:
            FLOAT: leading edge radius, its center and related contour
            point and id
        """
        radius = self.curvature_data[2]
        rc = np.min(radius)
        # numpy where returns a tuple
        # we take the first element, which is type array
        le_id = np.where(radius == rc)[0]
        # convert the numpy array to a list and take the first element
        le_id = le_id.tolist()[0]
        # leading edge curvature circle center
        xc = self.curvature_data[3][le_id]
        yc = self.curvature_data[4][le_id]
        xr, yr = self.spline_data[0]
        xle = xr[le_id]
        yle = yr[le_id]
        logger.info('Leading edge radius id: {}'.format(le_id))
        logger.info('Leading edge radius: {}'.format(rc))

        return rc, xc, yc, xle, yle, le_id

    def drawContour(self, plot):

        # curvature_data --> gradient, C, R, xc, yc

        x, y = self.parent.airfoil.raw_coordinates
        xr, yr = self.spline_data[0]
        gradient = self.curvature_data[0]
        curvature = self.curvature_data[1]
        radius = self.curvature_data[2]

        # leading edge radius
        rc, xc, yc, xle, yle, le_id = self.getLeRadius()

        # create axes
        ax1 = self.figure_top.add_subplot(111, frame_on=False)
        ax2 = self.figure_center.add_subplot(111, frame_on=False)
        ax3 = self.figure_bottom.add_subplot(111, frame_on=False)

        # plot original contour
        r, g, b = 30./255., 30./255., 30./255.
        ax1.plot(x, y, marker='o', mfc='r', color=(r, g, b), linewidth=2)
        ax1.set_title('Original Contour', fontsize=14)
        ax1.set_xlim(-0.05, 1.05)
        # ax1.set_ylim(-10.0, 14.0)
        r, g, b = 120./255., 120./255., 120./255.
        ax1.fill(x, y, color=(r, g, b))
        ax1.set_aspect('equal')

        # plot refined contour
        r, g, b = 30./255., 30./255., 30./255.
        ax2.plot(xr, yr, marker='o', mfc='r', color=(r, g, b), linewidth=2)
        # leading edge curvature circle
        circle = patches.Circle((xc, yc), rc, edgecolor='y', facecolor='None',
                                lw=2, ls='solid', zorder=2)
        ax2.plot((xc, xle), (yc, yle), 'r', linewidth=1)
        ax2.plot(xc, yc, marker='o', mfc='b', linewidth=2)
        ax2.plot(xle, yle, marker='o', mfc='b', linewidth=2)
        ax2.add_patch(circle)
        ax2.set_title('Refined Contour', fontsize=14)
        ax2.set_xlim(-0.05, 1.05)
        # ax2.set_ylim(-10.0, 14.0)
        r, g, b = 90./255., 90./255., 90./255.
        ax2.fill(xr, yr, color=(r, g, b))
        ax2.set_aspect('equal')

        # select plotting variable for contour analysis
        plotvar = {1: [gradient, 'Gradient'], 2: [curvature, 'Curvature'],
                   3: [radius, 'Radius of Curvature']}

        ax3.cla()

        # plot either of three possible analysis results
        r, g, b = 30./255., 30./255., 30./255.
        ax3.plot(xr, plotvar[plot][0], marker='o', mfc='r', color=(r, g, b),
                 linewidth=2)
        ax3.set_title(plotvar[plot][1], fontsize=14)
        ax3.set_xlim(-0.05, 1.05)
        if plot == 1:
            ax3.set_ylim(-1.0, 1.0)
        r, g, b = 90./255., 90./255., 90./255.
        ax3.fill(xr, plotvar[plot][0], color=(r, g, b))

        # refresh canvas
        self.canvas_top.draw()
        self.canvas_center.draw()
        self.canvas_bottom.draw()
