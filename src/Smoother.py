from __future__ import annotations

from abc import ABC, abstractmethod


class Smoother(ABC):
    """Abstract base class for smoothing algorithms."""

    name = 'base'

    @abstractmethod
    def smooth(self, mesh, domain=None, **kwargs):
        """Apply smoothing to a mesh or block-like object."""


class NoOpSmoother(Smoother):
    name = 'none'

    def smooth(self, mesh, domain=None, **kwargs):
        return mesh


class SimpleBlockSmoother(Smoother):
    name = 'simple'

    def smooth(self, mesh, domain=None, **kwargs):
        from BlockMesh import Smooth

        smooth = Smooth(mesh)

        nodes = smooth.selectNodes(domain='interior')
        mesh = smooth.smooth(nodes, iterations=1, algorithm='laplace')

        ij = [1, 30, 1, len(mesh.getULines()) - 2]
        nodes = smooth.selectNodes(domain='ij', ij=ij)
        mesh = smooth.smooth(nodes, iterations=2, algorithm='laplace')

        ij = [len(mesh.getVLines()) - 31,
              len(mesh.getVLines()) - 2,
              1,
              len(mesh.getULines()) - 2]
        nodes = smooth.selectNodes(domain='ij', ij=ij)
        mesh = smooth.smooth(nodes, iterations=3, algorithm='laplace')
        return mesh


class EllipticBlockSmoother(Smoother):
    name = 'elliptic'

    def smooth(self, mesh, domain=None, **kwargs):
        import Elliptic

        iterations = int(kwargs.get('iterations', 10))
        tolerance = float(kwargs.get('tolerance', 1.0e-3))

        smoother = Elliptic.Elliptic(mesh.getULines())
        new_ulines = smoother.smooth(
            iterations=iterations,
            tolerance=tolerance,
            bnd_type=None,
            verbose=True,
        )
        mesh.setUlines(new_ulines)
        return mesh


class AngleBasedBlockSmoother(Smoother):
    name = 'angle_based'

    def smooth(self, mesh, domain=None, **kwargs):
        from Smooth_angle_based import SmoothAngleBased

        iterations = int(kwargs.get('iterations', 20))
        tolerance = float(kwargs.get('tolerance', 1.0e-4))

        smoother = SmoothAngleBased(mesh, data_source='block')
        smoothed_vertices = smoother.smooth(
            iterations=iterations,
            tolerance=tolerance,
            verbose=True,
        )
        mesh.setUlines(smoother.mapToUlines(smoothed_vertices))
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
