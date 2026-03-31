import numpy as np

from MathUtils import VectorUtils
from Utils import get_main_window

class TrailingEdge:

    def __init__(self):

        # get MainWindow instance (overcomes handling parents)
        self.mw = get_main_window()

    def getUpperLower(self):
        """Split contour in upper and lower parts

        Returns:
            TYPE: Coordinates of upper and lower contours
        """
        spline_data = self.mw.airfoil.spline_data
        x, y = spline_data.coordinates
        le_id = int(np.argmin(x))
        upper = (x[:le_id + 1], y[:le_id + 1])
        lower = (x[le_id:], y[le_id:])

        return upper, lower

    def trailingEdge(self, blend=0.3, ex=3.0, thickness=0.6, side='both',
                     lower_blend=None, lower_exponent=None):
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
        xu = np.array(upper[0], copy=True)
        yu = np.array(upper[1], copy=True)
        xl = np.array(lower[0], copy=True)
        yl = np.array(lower[1], copy=True)
        xnu = np.array(xu, copy=True)
        ynu = np.array(yu, copy=True)
        xnl = np.array(xl, copy=True)
        ynl = np.array(yl, copy=True)

        lower_blend = blend if lower_blend is None else lower_blend
        lower_exponent = ex if lower_exponent is None else lower_exponent

        if side == 'upper' or side == 'both':
            xnu, ynu = self.trailing(xu, yu, blend, ex, thickness,
                                     side='upper')
        if side == 'lower' or side == 'both':
            xnl, ynl = self.trailing(xl, yl, lower_blend, lower_exponent, thickness,
                                     side='lower')
        xt = np.concatenate([xnu, xnl[1:]])
        yt = np.concatenate([ynu, ynl[1:]])
        self.mw.airfoil.spline_data.coordinates = (xt, yt)

    def trailing(self, xx, yy, blend, ex, thickness, side='upper'):
        xmin = np.min(xx)
        xmax = np.max(xx)
        chord = xmax - xmin
        thickness = chord * thickness / 100.0
        x = np.array(xx, copy=True)
        y = np.array(yy, copy=True)
        if blend <= 0.0 or xmax <= 0.0 or thickness == 0.0:
            return x, y

        blend_mask = x > (1.0 - blend) * xmax
        if not np.any(blend_mask):
            return x, y

        if side == 'upper':
            signum = 1.0
            a = np.array([x[1] - x[0], y[1] - y[0]])
        elif side == 'lower':
            signum = -1.0
            a = np.array([x[-2] - x[-1], y[-2] - y[-1]])
        e = VectorUtils.unit_vector(a)
        n = np.array([e[1], -e[0]])
        shift = 0.5 * thickness

        shift_blend = (x[blend_mask] - xmax * (1.0 - blend)) / (xmax * blend)
        delta = signum * np.power(shift_blend, ex) * shift
        x[blend_mask] += n[0] * delta
        y[blend_mask] += n[1] * delta
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
