# -*- coding: utf-8 -*-

import numpy as np


class Transformations:
    """Collection of static methods for geometric transformations

    Dependencies: numpy (np)

    NOTE: Homogenous coordinates are used,
          i.e. 4-th dimension is 1: P(x/y/z/1)
          This is necessary so that also translation
          can be handled using matrix operations

    Several geometric operations can be combined into one transformation matrix
    by multiplying all individual transformations.
    Multiplication via numpy.dot() --> A*B: A.dot(B)
    Order is from right (1st transformation) to left (last transformation)

    Example: Rotate (R) then translate (T1) then scale (S) then mirror (M)
             then translate (T2)
        Setup individual transformation matrices
        >>> R = rotate3D(...)
        >>> T1 = translate3D(...)
        >>> S = scale3D(...)
        >>> M = mirror3D(...)
        >>> T2 = translate3D(...)
        Compile combined transformation matrix
        >>> MATRIX = T2.dot(M.dot(S.dot(T1.dot(R))))
        Apply combined transformation to points(s)
        >>> P = (1., 2., 6., 1.)
        >>> P_new = MATRIX.dot(P)
    """

    @staticmethod
    def rotate3D(axis='x', phi=0.0, degree=True):
        """Calculate 3D transformation matrix for rotation
        around one of the coordinate system axis

        Args:
            axis (str, optional): Rotation axis
            phi (float, optional): Rotation angle
            degree (bool, optional): Specifies if input is in degree or radians

        EXAMPLE: Rotate point P around x-axis by 90° to get P_rot
            >>> P = (1., 2., 6., 1.)
            >>> rotmat = rotate3D(axis='x', phi=90.0)
            >>> P_rot = rotmat.dot(P)
        """

        if degree:
            phi = phi / 180.0 * np.pi

        if axis == 'x':
            # 3D rotation x-axis
            ROT = np.array([[1.0, 0.0, 0.0, 0.0],
                            [0.0, np.cos(phi), -np.sin(phi), 0.0],
                            [0.0, np.sin(phi), np.cos(phi), 0.0],
                            [0.0, 0.0, 0.0, 1.0]])
        elif axis == 'y':
            # 3D rotation y-axis
            ROT = np.array([[np.cos(phi), 0.0, np.sin(phi), 0.0],
                            [0.0, 1.0, 0.0, 0.0],
                            [-np.sin(phi), 0.0, np.cos(phi), 0.0],
                            [0.0, 0.0, 0.0, 1.0]])
        elif axis == 'z':
            # 3D rotation z-axis
            ROT = np.array([[np.cos(phi), -np.sin(phi), 0.0, 0.0],
                            [np.sin(phi), np.cos(phi), 0.0, 0.0],
                            [0.0, 0.0, 1.0, 0.0],
                            [0.0, 0.0, 0.0, 1.0]])

        return ROT

    @staticmethod
    def translate3D(vector):
        """Calculate 3D transformation matrix for translation
        along a given vector

        Args:
            vector (tuple): x, y, z coordinates of translation vector

        EXAMPLE: Translate point P along vector to get P_trans
            >>> P = (1., 2., 6., 1.)
            >>> vector = (10., 0., 0., 1.)
            >>> transmat = translate3D(vector)
            >>> P_trans = transmat.dot(P)
        """
        TRANS = np.array([[1.0, 0.0, 0.0, vector[0]],
                          [0.0, 1.0, 0.0, vector[1]],
                          [0.0, 0.0, 1.0, vector[2]],
                          [0.0, 0.0, 0.0, 1.0]])
        return TRANS

    @staticmethod
    def scale3D(scale):
        """Calculate 3D transformation matrix for scaling

        Args:
            scale (tuple): Scaling factors for each axis

        EXAMPLE: Scale point P by sx, sy, sz to get P_scale
            >>> P = (1., 2., 6., 1.)
            >>> scale = (2., 2., 2.)
            >>> scalemat = scale3D(scale)
            >>> P_scale = scalemat.dot(P)
        """
        SCALE = np.array([[scale[0], 0.0, 0.0, 0.0],
                          [0.0, scale[1], 0.0, 0.0],
                          [0.0, 0.0, scale[2], 0.0],
                          [0.0, 0.0, 0.0, 1.0]])
        return SCALE

    @staticmethod
    def mirror3D(plane='xy'):
        """Calculate 3D transformation matrix for mirroring wrt to xy, xz, yz planes

        EXAMPLE: Mirror point P wrt xy-plane to get P_mirror
            >>> P = (1., 2., 6., 1.)
            >>> mirmat = mirror3D(plane='xy')
            >>> P_rot = mirmat.dot(P)
        """
        if plane == 'xy':
            # 3D mirroring wrt xy-plane
            MIRROR = np.array([[1.0, 0.0, 0.0, 0.0],
                               [0.0, 1.0, 0.0, 0.0],
                               [0.0, 0.0, -1.0, 0.0],
                               [0.0, 0.0, 0.0, 1.0]])
        elif plane == 'xz':
            # 3D mirroring wrt xz-plane
            MIRROR = np.array([[1.0, 0.0, 0.0, 0.0],
                               [0.0, -1.0, 0.0, 0.0],
                               [0.0, 0.0, 1.0, 0.0],
                               [0.0, 0.0, 0.0, 1.0]])
        elif plane == 'yz':
            # 3D mirroring wrt yz-plane
            MIRROR = np.array([[-1.0, 0.0, 0.0, 0.0],
                               [0.0, 1.0, 0.0, 0.0],
                               [0.0, 0.0, 1.0, 0.0],
                               [0.0, 0.0, 0.0, 1.0]])
        return MIRROR


class Utils:
    """Collection of utility functions (static methods).
    """
    def __init__(self):
        pass

    @staticmethod
    def vector(p1, p2):
        """Returns a vector made of two points

        Args:
            p1 (tuple, list or np.array): Point, e.g. (1, 2) or [7., 4.3]
            p2 (tuple, list or np.array): Point, e.g. (1, 2) or [7., 4.3]

        Returns:
            np.array: vector in numpy format
        """

        p1 = np.array(p1)
        p2 = np.array(p2)

        return p2 - p1

    @staticmethod
    def vector_length(vector):
        """ Returns the length of the vector.  """
        return np.linalg.norm(vector)

    @staticmethod
    def unit_vector(vector):
        """ Returns the unit vector of the vector.  """
        return vector / np.linalg.norm(vector)

    @staticmethod
    def angle_between(a, b, degree=False):
        """Returns the angle between
        vectors 'a' and 'b'
        """
        a = np.array(a)
        b = np.array(b)

        a_u = Utils.unit_vector(a)
        b_u = Utils.unit_vector(b)
        angle = np.arccos(np.clip(np.dot(a_u, b_u), -1.0, 1.0))
        if degree:
            angle *= 180.0 / np.pi
        return angle

    @staticmethod
    def scalar_to_rgb(value, vmin, vmax, range='1'):
        """Convert scalar value to RGB color
            
            Args:
                value (float): scalar value
                vmin (float): minimum value
                vmax (float): maximum value
                range (str): color range (1 or 256)
    
            Returns:
                tuple: RGB color
        """
        v = np.clip(value, vmin, vmax)
        dv = vmax - vmin
        c = [1., 1., 1.]
        
        if v < (vmin + 0.25 * dv):
            c[0] = 0
            c[1] = 4 * (v - vmin) / dv
        elif v < (vmin + 0.5 * dv):
            c[0] = 0;
            c[2] = 1 + 4 * (vmin + 0.25 * dv - v) / dv;
        elif v < (vmin + 0.75 * dv):
            c[0] = 4 * (v - vmin - 0.5 * dv) / dv;
            c[2] = 0;
        else:
            c[1] = 1 + 4 * (vmin + 0.75 * dv - v) / dv;
            c[2] = 0;
        
        r, g, b = np.clip(c[0], 0., 1.), np.clip(c[1], 0., 1.), np.clip(c[2], 0., 1.)

        if range == '256':
            r *= 255
            g *= 255
            b *= 255

        return r, g, b