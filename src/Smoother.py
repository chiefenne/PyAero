from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

import Connect


@dataclass(frozen=True)
class StructuredBlockGrid:
    """Structured block coordinates stored as x/y index arrays."""

    x: np.ndarray
    y: np.ndarray

    def __post_init__(self):
        if self.x.shape != self.y.shape:
            raise ValueError('Structured grid x/y arrays must have the same shape.')
        if self.x.ndim != 2:
            raise ValueError('Structured grid coordinates must be 2D arrays.')

    @property
    def nx(self):
        return self.x.shape[0]

    @property
    def ny(self):
        return self.x.shape[1]

    def copy(self):
        return StructuredBlockGrid(
            x=np.array(self.x, copy=True, dtype=float),
            y=np.array(self.y, copy=True, dtype=float),
        )

    @classmethod
    def from_ulines(cls, ulines):
        if not ulines:
            empty = np.empty((0, 0), dtype=float)
            return cls(x=empty, y=empty)

        ny = len(ulines)
        nx = len(ulines[0])
        x = np.empty((nx, ny), dtype=float)
        y = np.empty_like(x)

        for j_index, uline in enumerate(ulines):
            if len(uline) != nx:
                raise ValueError('All structured block lines must have the same length.')

            coordinates = np.asarray(uline, dtype=float)
            if coordinates.ndim != 2 or coordinates.shape[1] != 2:
                raise ValueError('Structured block lines must contain 2D coordinates.')

            x[:, j_index] = coordinates[:, 0]
            y[:, j_index] = coordinates[:, 1]

        return cls(x=x, y=y)

    def to_ulines(self):
        ulines = []
        for j_index in range(self.ny):
            ulines.append(
                [
                    (float(self.x[i_index, j_index]), float(self.y[i_index, j_index]))
                    for i_index in range(self.nx)
                ]
            )
        return ulines


class Smoother(ABC):
    """Abstract base class for smoothing algorithms."""

    name = 'base'

    @abstractmethod
    def smooth(self, mesh, domain=None, **kwargs):
        """Apply smoothing to a mesh or block-like object."""


class BlockMeshSmoother(Smoother):
    """Common utilities for smoothers operating on BlockMesh-like objects."""

    default_iterations = 0
    default_tolerance = 0.0
    default_verbose = False
    default_log_interval = 10

    def smooth(self, mesh, domain=None, **kwargs):
        self._require_block_mesh(mesh)
        return self._smooth_block(mesh, domain=domain, **kwargs)

    @abstractmethod
    def _smooth_block(self, mesh, domain=None, **kwargs):
        """Smooth a BlockMesh-like object and return it."""

    @staticmethod
    def _require_block_mesh(mesh):
        if not hasattr(mesh, 'getULines') or not callable(mesh.getULines):
            raise TypeError('Expected a block mesh with a getULines() method.')
        if not hasattr(mesh, 'setUlines') or not callable(mesh.setUlines):
            raise TypeError('Expected a block mesh with a setUlines() method.')

    @staticmethod
    def _grid_from_mesh(mesh):
        return StructuredBlockGrid.from_ulines(mesh.getULines())

    @staticmethod
    def _apply_grid(mesh, grid):
        mesh.setUlines(grid.to_ulines())
        return mesh

    @staticmethod
    def _block_topology(mesh):
        connector = Connect.Connect()
        return connector.getVertices(mesh), connector.getConnectivity(mesh)

    @staticmethod
    def _map_vertices_to_ulines(mesh, vertices):
        ulines = []
        vertex_index = 0

        for uline in mesh.getULines():
            point_count = len(uline)
            new_uline = []
            for offset in range(point_count):
                x_value, y_value = vertices[vertex_index + offset]
                new_uline.append((float(x_value), float(y_value)))
            ulines.append(new_uline)
            vertex_index += point_count

        if vertex_index != len(vertices):
            raise ValueError(
                'Vertex count does not match the structured block line layout.'
            )

        return ulines

    @classmethod
    def _coerce_iterations(cls, kwargs):
        return int(kwargs.get('iterations', cls.default_iterations))

    @classmethod
    def _coerce_tolerance(cls, kwargs):
        return float(kwargs.get('tolerance', cls.default_tolerance))

    @classmethod
    def _coerce_verbose(cls, kwargs):
        return bool(kwargs.get('verbose', cls.default_verbose))

    @classmethod
    def _coerce_log_interval(cls, kwargs):
        interval = int(kwargs.get('log_interval', cls.default_log_interval))
        return max(1, interval)


class StructuredGridSmoother(BlockMeshSmoother):
    """Base class for smoothers that work on structured x/y arrays."""

    def _smooth_block(self, mesh, domain=None, **kwargs):
        grid = self._grid_from_mesh(mesh)
        smoothed_grid = self.smooth_grid(grid, domain=domain, **kwargs)
        return self._apply_grid(mesh, smoothed_grid)

    @abstractmethod
    def smooth_grid(self, grid, domain=None, **kwargs):
        """Return a smoothed StructuredBlockGrid."""


class NoOpSmoother(BlockMeshSmoother):
    name = 'none'

    def _smooth_block(self, mesh, domain=None, **kwargs):
        return mesh


class SimpleBlockSmoother(StructuredGridSmoother):
    name = 'simple'

    @staticmethod
    def _normalize_region(grid, domain='interior', ij=None):
        if domain == 'interior':
            i_start, i_end = 1, grid.nx - 1
            j_start, j_end = 1, grid.ny - 1
        elif domain == 'ij' and ij is not None:
            i_start, i_end = ij[0], ij[1]
            j_start, j_end = ij[2], ij[3]
        else:
            raise ValueError(f'Unknown node selection domain: {domain}')

        i_start = max(1, min(i_start, grid.nx - 1))
        i_end = max(i_start, min(i_end, grid.nx - 1))
        j_start = max(1, min(j_start, grid.ny - 1))
        j_end = max(j_start, min(j_end, grid.ny - 1))

        return i_start, i_end, j_start, j_end

    @staticmethod
    def _smooth_region(x, y, region, iterations=1, algorithm='laplace'):
        i_start, i_end, j_start, j_end = region

        for _ in range(iterations):
            for i_index in range(i_start, i_end):
                for j_index in range(j_start, j_end):
                    if algorithm == 'laplace':
                        x[i_index, j_index] = (
                            x[i_index, j_index - 1] +
                            x[i_index + 1, j_index] +
                            x[i_index, j_index + 1] +
                            x[i_index - 1, j_index]
                        ) / 4.0
                        y[i_index, j_index] = (
                            y[i_index, j_index - 1] +
                            y[i_index + 1, j_index] +
                            y[i_index, j_index + 1] +
                            y[i_index - 1, j_index]
                        ) / 4.0
                    elif algorithm == 'parallelogram':
                        x[i_index, j_index] = (
                            x[i_index - 1, j_index - 1] +
                            x[i_index + 1, j_index - 1] +
                            x[i_index + 1, j_index + 1] +
                            x[i_index - 1, j_index + 1]
                        ) / 4.0 - (
                            x[i_index, j_index - 1] +
                            x[i_index + 1, j_index] +
                            x[i_index, j_index + 1] +
                            x[i_index - 1, j_index]
                        ) / 2.0
                        y[i_index, j_index] = (
                            y[i_index - 1, j_index - 1] +
                            y[i_index + 1, j_index - 1] +
                            y[i_index + 1, j_index + 1] +
                            y[i_index - 1, j_index + 1]
                        ) / 4.0 - (
                            y[i_index, j_index - 1] +
                            y[i_index + 1, j_index] +
                            y[i_index, j_index + 1] +
                            y[i_index - 1, j_index]
                        ) / 2.0
                    else:
                        raise ValueError(
                            f'Unknown simple smoothing algorithm: {algorithm}'
                        )

    def smooth_grid(self, grid, domain=None, **kwargs):
        smoothed = grid.copy()

        self._smooth_region(
            smoothed.x,
            smoothed.y,
            self._normalize_region(smoothed, domain='interior'),
            iterations=1,
            algorithm='laplace',
        )

        self._smooth_region(
            smoothed.x,
            smoothed.y,
            self._normalize_region(
                smoothed,
                domain='ij',
                ij=[1, 30, 1, smoothed.ny - 2],
            ),
            iterations=2,
            algorithm='laplace',
        )

        self._smooth_region(
            smoothed.x,
            smoothed.y,
            self._normalize_region(
                smoothed,
                domain='ij',
                ij=[smoothed.nx - 31, smoothed.nx - 2, 1, smoothed.ny - 2],
            ),
            iterations=3,
            algorithm='laplace',
        )

        return smoothed


class EllipticBlockSmoother(StructuredGridSmoother):
    name = 'elliptic'
    default_iterations = 10
    default_tolerance = 1.0e-3

    def smooth_grid(self, grid, domain=None, **kwargs):
        from Elliptic import EllipticSolver

        iterations = self._coerce_iterations(kwargs)
        tolerance = self._coerce_tolerance(kwargs)
        verbose = self._coerce_verbose(kwargs)
        log_interval = self._coerce_log_interval(kwargs)
        boundary_condition = kwargs.get('boundary_condition', kwargs.get('bnd_type'))
        boundary_guides = kwargs.get('boundary_guides')
        sliding_boundaries = kwargs.get('sliding_boundaries')
        relaxation = kwargs.get('relaxation')

        solver = EllipticSolver(grid.x, grid.y)
        x_smooth, y_smooth = solver.smooth(
            iterations=iterations,
            tolerance=tolerance,
            boundary_condition=boundary_condition,
            boundary_guides=boundary_guides,
            sliding_boundaries=sliding_boundaries,
            relaxation=relaxation,
            verbose=verbose,
            log_interval=log_interval,
        )
        return StructuredBlockGrid(x=x_smooth, y=y_smooth)


class AngleBasedBlockSmoother(BlockMeshSmoother):
    name = 'angle_based'
    default_iterations = 20
    default_tolerance = 1.0e-4

    def _smooth_block(self, mesh, domain=None, **kwargs):
        from Smooth_angle_based import SmoothAngleBased

        iterations = self._coerce_iterations(kwargs)
        tolerance = self._coerce_tolerance(kwargs)
        verbose = self._coerce_verbose(kwargs)
        log_interval = self._coerce_log_interval(kwargs)

        vertices, connectivity = self._block_topology(mesh)
        smoother = SmoothAngleBased(vertices, connectivity)
        smoothed_vertices = smoother.smooth(
            iterations=iterations,
            tolerance=tolerance,
            verbose=verbose,
            log_interval=log_interval,
        )
        mesh.setUlines(self._map_vertices_to_ulines(mesh, smoothed_vertices))
        return mesh


class SmootherFactory:
    """Factory class to create smoother instances."""

    _registry = {
        'none': NoOpSmoother,
        'simple': SimpleBlockSmoother,
        'laplace': SimpleBlockSmoother,
        'elliptic': EllipticBlockSmoother,
        'angle_based': AngleBasedBlockSmoother,
    }

    @classmethod
    def create_smoother(cls, algorithm: str):
        key = algorithm.strip().lower()
        try:
            smoother_class = cls._registry[key]
        except KeyError as error:
            raise ValueError(
                f'Unknown smoothing algorithm: {algorithm}'
            ) from error
        return smoother_class()
