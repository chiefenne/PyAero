
from functools import partial
import copy

import numpy as np
from scipy import optimize

DEBUG = False


class Elliptic:
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

    def solver(self, solver_type, iterations):

        # knowns
        f_o = copy.copy(self.f[:, 0])
        u_o = copy.copy(self.u[:, 0])

        # extra parameters for 'function'
        # are later wrapped with partial
        etamax = copy.copy(self.etamax)

        #
        def F(unknowns, F_args=[etamax]):
            """Summary

            Args:
                unknowns (np.array): x, y

            Returns:
                TYPE: Description
            """

            # unknowns
            if DEBUG:
                print('unknowns', unknowns)

            # (x, y) = unknowns
            x = unknowns[0: etamax]
            y = unknowns[etamax:2 * etamax]

            eq1 = np.zeros_like(x)
            eq2 = np.zeros_like(x)

            # boundary conditions
            x[0] = 0.0
            y[0] = 0.0

            deta = 1.0
            dgsi = 1.0

            # array slicing for index j
            # [1:] means index j
            # [:-1] means index j-1

            dxdgsi = (x[1:, :] - x[:-1, :]) / (2 * dgsi)
            dydgsi = (y[1:, :] - y[:-1, :]) / (2 * dgsi)
            dxdeta = (x[1:, :] - x[:-1, :]) / (2 * deta)
            dydeta = (y[1:, :] - y[:-1, :]) / (2 * deta)

            # components of the covariant metric tensor
            g11 = dxdgsi**2 + dydgsi**2
            g22 = dxdeta**2 + dydeta**2
            g12 = dxdgsi * dxdeta + dydgsi * dydeta

            a = g22 / dgsi**2
            b = 2 * g22 / dgsi**2 + 2 * g11 / deta**2
            c = a
            d = g11 / deta**2 * (x[:, :-1] + x[:, 1:]) - \
                2 * g12 * (x[:-1, :-1] + x[1:, 1:] - x[1:, :-1] - x[:-1, 1:]) \
                / (4 * dgsi * deta)
            e = g11 / deta**2 * (y[:, :-1] + y[:, 1:]) - \
                2 * g12 * (y[:-1, :-1] + y[1:, 1:] - y[1:, :-1] - y[:-1, 1:]) \
                / (4 * dgsi * deta)

            # Winslow x
            eq1[1:] = -a * x[1:, :] + b * x[:, :] - c * x[:-1, :] - d

            # Winslow y
            eq2[1:] = -a * y[1:, :] + b * y[:, :] - c * y[:-1, :] - e

            # boundary conditions make up another 2 equations
            # put them on the 0-th element of all 2 equations
            eq1[0] = x[0]
            eq2[0] = y[0]

            return np.array([eq1, eq2]).ravel()

        # initial guess
        guess = np.array([f_o, u_o]).ravel()

        F_partial = partial(F,
                            F_args=[etamax])

        solution = optimize.fsolve(F_partial, guess,
                                   full_output=True, xtol=1e-06)

        solver_message = solution[3]
        print('  Solver: {}'.format(solver_message))

        return solution, solver_message

    def shift_profiles(self):

        self.x[:, 0] = copy.copy(self.solution[0][0 *
                                 self.etamax:1 * self.etamax])
        self.y[:, 0] = copy.copy(self.solution[0][1 *
                                 self.etamax:2 * self.etamax])

    def main(self, solver_type='fsolve', iterations=10):

        # initial velocity profile
        self.boundary_conditions()

        for self.nx in range(1, self.gsimax):
            self.solution, self.solver_message = \
                self.solver(solver_type, iterations)
            self.shift_profiles()
