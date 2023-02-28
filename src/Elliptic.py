
import copy

import numpy as np

from Utils import Utils

import logging
logger = logging.getLogger(__name__)


class Elliptic:
    def __init__(self, ulines):

        self.ulines = ulines
        
        self.nx = np.array(self.ulines).shape[1]
        self.ny = np.array(self.ulines).shape[0]

        # initialize coordinate array
        self.x = np.empty((self.nx, self.ny))
        self.y = np.empty_like(self.x)

        
        # map coordinates from ulines to i,j index
        self.mapUlines()
 
    def mapUlines(self):
        for j, uline in enumerate(self.ulines):
           for i, u in enumerate(uline):
               self.x[i, j] = u[0]
               self.y[i, j] = u[1]
    
    def mapToUlines(self):
        self.new_ulines = list()
        for j, uline in enumerate(self.ulines):
            new_uline = list()
            for i, u in enumerate(uline):
                new_uline.append((self.xn[i, j], self.yn[i, j]))
            self.new_ulines.append(new_uline)

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

    def smooth(self, iterations=10, tolerance=1e-3, bnd_type=None, verbose=False):

        self.mapUlines()

        self.xn = copy.deepcopy(self.x)
        self.yn = copy.deepcopy(self.y)

        # calculate normals at boundaries
        # used for Neumann boundary conditions
        normals_left = self.curveNormals(self.xn[0, :], self.yn[0, :])
        normals_right = self.curveNormals(self.xn[-1, :], self.yn[-1, :])
        normals_top = self.curveNormals(self.xn[:, -1], self.yn[:, -1])
        normals_bottom = self.curveNormals(self.xn[:, 0], self.yn[:, 0])

        for iteration in range(iterations):

            # loop internal nodes, index a[0, 0] refers to the first internal node
            for i in range(1, self.nx - 1):
                for j in range(1, self.ny - 1):

                    # g22
                    alpha = 1./4. * ( (self.x[i, j+1] - self.x[i, j-1])**2 \
                                  + (self.y[i, j+1] - self.y[i, j-1])**2 )
                    # g11
                    gamma = 1./4. * ( (self.x[i+1, j] - self.x[i-1, j])**2 \
                                  + (self.y[i+1, j] - self.y[i-1, j])**2 )
                    # g12
                    beta = 1./16. * ( ( self.x[i+1, j] - self.x[i-1, j] ) \
                                    * ( self.x[i, j+1] - self.x[i, j-1] ) \
                                    + ( self.y[i+1, j] - self.y[i-1, j] ) \
                                    * ( self.y[i, j+1] - self.y[i, j-1] ) )
                    # calculate new x-coordinate
                    self.xn[i,j] = -0.5 / (alpha + gamma + 1.e-9) \
                        * (2. * beta * ( self.x[i+1, j+1] - self.x[i-1, j+1] \
                        - self.x[i+1, j-1] + self.x[i-1, j-1] ) \
                        - alpha * ( self.x[i+1, j] + self.x[i-1, j] ) \
                        - gamma * ( self.x[i, j+1] + self.x[i, j-1] ) )
                    # calculate new y-coordinate
                    self.yn[i,j] = -0.5 / (alpha + gamma + 1.e-9) \
                        * (2. * beta * ( self.y[i+1, j+1] - self.y[i-1, j+1] \
                        - self.y[i+1, j-1] + self.y[i-1, j-1] ) \
                        - alpha * ( self.y[i+1, j] + self.y[i-1, j] ) \
                        - gamma * ( self.y[i, j+1] + self.y[i, j-1] ) )

                    # Neumann boundary conditions (normal to boundary here)
                    # project vector a (boundary node to internal node)
                    # onto vector b (normal vector at boundary) and move 
                    # internal node to this position
                    if bnd_type == 'Neumann':
                        if j == 1:
                            a = [self.xn[i,1] - self.xn[i,0],
                                 self.yn[i,1] - self.yn[i,0]]
                            b = normals_bottom[i]
                            projected = np.dot(a, b) / np.dot(b, b) * b
                            self.xn[i,1] = self.xn[i,0] + projected[0]
                            self.yn[i,1] = self.yn[i,0] + projected[1]
                        elif i == self.nx - 1:
                            pass
                        elif j == 1:
                            pass
                        elif j == self.ny - 1:
                            pass

            tol = np.max(np.abs(self.xn - self.x)) + np.max(np.abs(self.yn - self.y))

            if verbose:
                logger.info(f'Iteration={iteration+1:3d}, residual={tol:.3e}')

            if tol < tolerance:
                break

            # update coordinates for next iteration
            self.x = copy.deepcopy(self.xn)
            self.y = copy.deepcopy(self.yn)
                    
        # map coordinates back to uline data structure
        self.mapToUlines()

        return self.new_ulines