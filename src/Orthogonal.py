
import numpy as np
from scipy import interpolate
import matplotlib.pylab as plt


class Orthogonal:
    """Generate an orthogonal curvilinear grid by solving the inverse form of
    two laplace equations.
    Source: Basic Structured Grid Generation, M. Farrashkhalvat and J.P. Miles
    """

    def __init__(self, boundary):
        """Summary

        Args:
            boundary (dictionary): contains x,y-coordinates of all 4 boundaries
        """
        self.xw = boundary['west'][0]
        self.yw = boundary['west'][1]
        self.xe = boundary['east'][0]
        self.ye = boundary['east'][1]
        self.xn = boundary['north'][0]
        self.yn = boundary['north'][1]
        self.xs = boundary['south'][0]
        self.ys = boundary['south'][1]

    def _set(self):
        """set grid size, maximum number of iterations, convergence criterion,
        initial x-y field, etc.
        """

        # grid streched or compressed (lstr=.true.)
        self.lstr = True

        # grid size
        self.ni = 20
        self.nj = 30

        # program control and monitor location
        self.imon = 2
        self.jmon = 2

        # maximum number of iterations
        self.maxit = 1250
        self.niter = 0

        # underrelaxation
        self.urfx = 1.0
        self.urfy = 1.0

        # number of sweeps for tdma solution
        self.nswpx = 1
        self.nswpy = 1

        # geometry indicator
        # plane(indcos=1)
        # axisymmetric(indcos=2)
        self.indcos = 1
        self.ratx = 1.0
        self.raty = 1.0

        # convergence criterion
        self.resmax = 1.0e-4

    def grid(self):
        # set coordinates in the transformed plane
        self.tox = 0.0
        self.h[0] = 0.0
        for i in range(2, self.ni + 1):
            self.tox += self.ratx**(i-2)

        self.ddh = 1.0 / self.tox
        for i in range(2, self.ni + 1):
            self.h[i-1] = self.h[i-2] + self.ddh * self.ratx**(i-2)

        self.toy = 0.0
        self.s[0] = 0.0
        for i in range(2, self.nj + 1):
            self.toy += self.raty**(i-2)

        self.dds = 1.0 / self.toy
        for i in range(2, self.nj + 1):
            self.s[i-1] = self.s[i-2] + self.dds * self.raty**(i-2)

        # streching and compressing terms
        # initialise sources arrays
        self.su = np.zeros((self.ni, self.nj))

        if self.lstr:
            pass

        self.ffun = np.zeros((self.ni))
        self.gfun = np.zeros((self.nj))

    def init(self):
        # calculate increments in the transformed plane
        self.dh = list()
        self.dhe = list()
        self.dhw = list()
        self.ds = list()
        self.dsn = list()
        self.dss = list()
        for i in range(2, self.ni):
            self.dh.append(0.5 * (self.h[i] - self.h[i-2]))
            self.dhe.append(self.h[i] - self.h[i-1])
            self.dhw.append(self.h[i-1] - self.h[i-2])
        for i in range(2, self.nj):
            self.ds.append(0.5 * (self.s[i] - self.s[i-2]))
            self.dsn.append(self.s[i] - self.s[i-1])
            self.dss.append(self.s[i-1] - self.s[i-2])

    def modbc(self):
        self.resorx = 0.0
        self.resory = 0.0

        for i in range(2, self.ni):
            xp = self.x(i, nj - 1)
            yp = self.y(i, nj - 1)
            xb = self.x(i, nj)
            yb = self.y(i, nj)
            ifail = 0
            call e02bcf(nicap7, xkn, cn, xb, 1, sn, ifail)
            interpolate.CubicSpline(x, y, axis=0, bc_type='not-a-knot', extrapolate=None)
            dydxb = min(sn(2), 1.d10)
            dydxb = max(sn(2), 1.d-10)
            if(sn(2).lt.0.0) dydxb = max(sn(2), -1.d10)
            if(sn(2).lt.0.0) dydxb = min(sn(2), -1.d-10)
            x(i, nj) = (yb-yp-xb*dydxb-xp/dydxb)/(-dydxb-1.0/dydxb)
            ifail = 0.0
            call e02bcf(nicap7, xkn, cn, x(i, nj), 1, sn, ifail)
            y(i, nj) = sn(1)
            resxb = abs(xb-x(i, nj))/xl
            resorx = resorx+resxb
            resyb = abs(yb-y(i, nj))/yl
            resory = resory+resyb

    def calcx(self):
        # calculate coefficients
        for i in range(2, self.ni):
            for j in range(2, self.nj):
                self.wfew = self.dhw(i) / self.dhe(i)
                self.wfns = self.dss(j) / self.dsn(j)
                self.dxdh = ((self.x(i + 1, j)-self.x(i, j)) * self.wfew + (self.x(i, j)-self.x(i-1, j))
                             / self.wfew) / (dhe(i) + dhw(i))
                self.dxds = ((self.x(i, j + 1)-self.x(i, j)) * self.wfns + (self.x(i, j)-self.x(i, j-1))
                             / self.wfns) / (dsn(j) + dss(j))
                self.dydh = ((self.y(i + 1, j)-self.y(i, j)) * self.wfew + (self.y(i, j)-self.y(i-1, j))
                             / self.wfew) / (dhe(i) + dhw(i))
                self.dyds = ((self.y(i, j + 1)-self.y(i, j)) * self.wfns + (self.y(i, j)-self.y(i, j-1))
                             / self.wfns) / (dsn(j) + dss(j))

              ans = dxdh*dxdh+dydh*dydh
              aew = dxds*dxds+dyds*dyds
              an(i, j) = dh(i) / dsn(j)*ans
              as(i, j) = dh(i) / dss(j)*ans
              ae(i, j) = ds(j) / dhe(i)*aew
              aw(i, j) = ds(j) / dhw(i)*aew

              # stretching terms

              sf1=aew*ds(j)*dh(i)*dxdh*ffun(i)
              sf2=ans*ds(j)*dh(i)*dxds*gfun(j)
              su(i,j)=sf1+sf2


              do 103 i=2,nim1
              do 104 j=2,njm1
              ap(i,j)=an(i,j)+as(i,j)+ae(i,j)+aw(i,j)
        c-----implicit underrelaxation
              ap(i,j)=ap(i,j)/urfx
              su(i,j)=ap(i,j)*(1.0-urfx)*x(i,j)+su(i,j)
          104 continue
          103 continue
        c
              call lisolv(2,2,nim1,njm1,x,nswpx)


    def calcy(self):
        pass

    def lisolv(self):
        pass

    def checks(self):
        pass

    def _print(self):
        pass

    def outpt(self):
        pass

    def metric(self):
        pass


class TransfiniteInterpolation:

    """Make a transfinite interpolation.
    http://en.wikipedia.org/wiki/Transfinite_interpolation

    Attributes:
        boundary (TYPE): Description
        ULines (TYPE): Description
    """

    def __init__(self):
        """Summary

        Args:
            boundary (TYPE): Description
        """
        pass

    @staticmethod
    def transfinite(north, south, west, east):
        """Make a transfinite interpolation.
        http://en.wikipedia.org/wiki/Transfinite_interpolation
        """

        south = np.array(south)
        north = np.array(north)
        west = np.array(west)
        east = np.array(east)

        # convert the block boundary curves into parametric form
        # as curves need to be between 0 and 1
        # interpolate B-spline through data points
        # here, a linear interpolant is derived "k=1"
        # splprep returns:
        # tck ... tuple (t,c,k) containing the vector of knots,
        #         the B-spline coefficients, and the degree of the spline.
        #   u ... array of the parameters for each given point (knot)
        tck_lower, u_lower = interpolate.splprep(south.T, s=0, k=1)
        tck_upper, u_upper = interpolate.splprep(north.T, s=0, k=1)
        tck_left, u_left = interpolate.splprep(west.T, s=0, k=1)
        tck_right, u_right = interpolate.splprep(east.T, s=0, k=1)

        # evaluate function at any parameter "0<=t<=1"
        def eta_left(t):
            return np.array(interpolate.splev(t, tck_left, der=0))

        def eta_right(t):
            return np.array(interpolate.splev(t, tck_right, der=0))

        def xi_bottom(t):
            return np.array(interpolate.splev(t, tck_lower, der=0))

        def xi_top(t):
            return np.array(interpolate.splev(t, tck_upper, der=0))

        nodes = np.zeros((len(west) * len(south), 2))

        # corner points
        c1 = xi_bottom(0.0)
        c2 = xi_top(0.0)
        c3 = xi_bottom(1.0)
        c4 = xi_top(1.0)

        for i, xi in enumerate(u_lower):
            xi_t = u_upper[i]
            for j, eta in enumerate(u_left):
                eta_r = u_right[j]

                node = i * len(u_left) + j

                # formula for the transinite interpolation
                point = (1.0 - xi) * eta_left(eta) + xi * eta_right(eta_r) + \
                    (1.0 - eta) * xi_bottom(xi) + eta * xi_top(xi_t) - \
                    ((1.0 - xi) * (1.0 - eta) * c1 + (1.0 - xi) * eta * c2 +
                     xi * (1.0 - eta) * c3 + xi * eta * c4)

                nodes[node, 0] = point[0]
                nodes[node, 1] = point[1]

        return nodes


def main(boundary):

    block = Orthogonal(boundary)
    block._set()
    block.grid()
    block.init()

    # solve
    solve = True
    while solve:
        block.niter += 1
        block.calcx()
        block.calcy()
        block.modbc()

        # check convergence
        block.sormax = max(block.resorx, block.resory)
        if (block.niter > block.maxit) or (block.sormax < block.resmax):
            solve = False

    block.outpt()
    block.checks()
    block.metric()


if __name__ == '__main__':

    # boundary curves in xi direction
    south = [(0.0, 0.0), (0.1, 0.0),  (0.2, 0.0), (0.3, 0.0), (0.4, 0.0), (0.45, 0.0), (0.5, 0.0)]
    north = [(0.2, 0.5), (0.3, 0.5),  (0.4, 0.5), (0.5, 0.5), (0.6, 0.5), (0.64, 0.5), (0.7, 0.5)]

    # boundary curves in eta direction
    west = [(0.0, 0.0), (0.1, 0.2),  (0.18, 0.25), (0.18, 0.38), (0.19, 0.45), (0.2, 0.5)]
    east = [(0.5, 0.0), (0.5, 0.1),  (0.55, 0.18), (0.6, 0.3), (0.65, 0.4), (0.7, 0.5)]

    nodes = TransfiniteInterpolation.transfinite(north, south, west, east)

    north = np.array(north)
    south = np.array(south)
    west = np.array(west)
    east = np.array(east)

    vlines = list()
    vline = list()
    i = 0
    for node in nodes:
        i += 1
        vline.append(node)
        if i % len(west) == 0:
            vlines.append(vline)
            vline = list()

    ulines = list()
    uline = list()
    for i in range(len(vlines[0])):
        for vline in vlines:
            uline.append(vline[i])
        ulines.append(uline)
        uline = list()

    for vline in vlines:
        plt.plot(np.array(vline)[:, 0], np.array(vline)[:, 1], 'm')

    for uline in ulines:
        plt.plot(np.array(uline)[:, 0], np.array(uline)[:, 1], 'm')

    plt.plot(nodes[:, 0], nodes[:, 1], 'mo', zorder=10, clip_on=False)
    plt.title('Points created by TFI')
    plt.axis('equal')
    plt.show()
