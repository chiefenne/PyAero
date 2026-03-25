from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, TYPE_CHECKING

from Shape import Polygon, Shape

if TYPE_CHECKING:
    from Mesh import Mesh


def _points_match(a, b, tolerance: float = 1.0e-9) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


@dataclass(slots=True)
class BoundaryLoop:
    name: str
    segments: list[Shape] = field(default_factory=list)
    closed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_segment(self, shape: Shape):
        self.segments.append(shape)

    def to_polygon(self, resolution: int | None = None):
        points = []
        for segment in self.segments:
            segment_points = segment.to_polygon(resolution=resolution)
            if not segment_points:
                continue

            current = list(segment_points)
            if points:
                if _points_match(points[-1], current[0]):
                    points.extend(current[1:])
                elif _points_match(points[-1], current[-1]):
                    current.reverse()
                    points.extend(current[1:])
                else:
                    points.extend(current)
            else:
                points.extend(current)

        if self.closed and points and not _points_match(points[0], points[-1]):
            points.append(points[0])
        return points

    def bounds(self, resolution: int | None = None):
        polygon = self.to_polygon(resolution=resolution)
        if not polygon:
            raise ValueError(f'Boundary loop {self.name} is empty.')
        return Polygon(polygon[:-1] if self.closed else polygon).bounds()

    @property
    def is_closed(self) -> bool:
        return self.closed


@dataclass(slots=True)
class DomainPart:
    name: str
    boundary: BoundaryLoop | Shape | None = None
    holes: list[BoundaryLoop | Shape] = field(default_factory=list)
    role: str = 'part'
    mesh: 'Mesh | None' = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Domain:
    """Computational domain described by boundary loops and attached meshes."""

    def __init__(self, name: str, outer_boundary: BoundaryLoop | Shape,
                 inner_shapes: Iterable[BoundaryLoop | Shape] | None = None,
                 mesh: 'Mesh | None' = None,
                 metadata: dict[str, Any] | None = None):
        self.name = name
        self.outer_boundary = self._coerce_loop(
            outer_boundary,
            default_name=f'{name}_outer_boundary',
        )
        self.inner_shapes = [
            self._coerce_loop(shape, default_name=f'{name}_inner_{index}')
            for index, shape in enumerate(inner_shapes or [])
        ]
        self.mesh = mesh
        self.meshes = [mesh] if mesh is not None else []
        self.meshable_parts: list[DomainPart] = []
        self.metadata = dict(metadata or {})

    @staticmethod
    def _coerce_loop(shape_or_loop: BoundaryLoop | Shape,
                     default_name: str) -> BoundaryLoop:
        if isinstance(shape_or_loop, BoundaryLoop):
            return shape_or_loop
        return BoundaryLoop(
            name=default_name,
            segments=[shape_or_loop],
            closed=shape_or_loop.is_closed,
        )

    def iter_boundaries(self):
        yield self.outer_boundary
        yield from self.inner_shapes

    def add_inner_shape(self, shape: BoundaryLoop | Shape, name: str | None = None):
        loop = self._coerce_loop(shape, default_name=name or f'{self.name}_inner')
        self.inner_shapes.append(loop)
        return loop

    def add_part(self, part: DomainPart):
        self.meshable_parts.append(part)
        if part.mesh is not None and part.mesh not in self.meshes:
            self.meshes.append(part.mesh)

    def split_into_meshable_parts(self):
        if not self.meshable_parts:
            self.meshable_parts.append(
                DomainPart(
                    name='fluid',
                    boundary=self.outer_boundary,
                    holes=list(self.inner_shapes),
                    role='fluid',
                    mesh=self.mesh,
                )
            )
        return self.meshable_parts

    def add_mesh(self, mesh: 'Mesh', part_name: str | None = None):
        if mesh not in self.meshes:
            self.meshes.append(mesh)

        if part_name is None:
            self.mesh = mesh
            return mesh

        for part in self.meshable_parts:
            if part.name == part_name:
                part.mesh = mesh
                return mesh

        raise ValueError(f'Unknown domain part: {part_name}')

    def generate_domain(self):
        self.validate()
        return self.split_into_meshable_parts()

    def connect_meshes(self):
        return [part.mesh for part in self.meshable_parts if part.mesh is not None]

    def bounds(self):
        return self.outer_boundary.bounds()

    def validate(self):
        if not self.outer_boundary.segments:
            raise ValueError('The domain outer boundary must contain segments.')

        if not self.outer_boundary.is_closed:
            raise ValueError('The domain outer boundary must be closed.')

        for inner_shape in self.inner_shapes:
            if not inner_shape.is_closed:
                raise ValueError(
                    f'Inner boundary {inner_shape.name} must be closed.'
                )

    def display_domain(self):
        return {
            'outer_boundary': self.outer_boundary.to_polygon(),
            'inner_boundaries': [
                shape.to_polygon() for shape in self.inner_shapes
            ],
        }


class DomainBuilder:
    outer_boundary_order = ('top', 'outlet', 'bottom', 'inlet')

    @classmethod
    def from_mesh(cls, mesh: 'Mesh', airfoil=None, name: str | None = None,
                  metadata: dict[str, Any] | None = None) -> Domain:
        mesh_data = getattr(mesh, 'data', None)
        if mesh_data is None:
            raise ValueError('Mesh model with mesh data is required.')

        outer_boundary = cls.build_outer_boundary(mesh)
        inner_shapes = cls.build_inner_boundaries(airfoil)
        airfoil_name = getattr(airfoil, 'name', None) or getattr(mesh, 'name', 'domain')
        domain = Domain(
            name=name or f'{airfoil_name}_domain',
            outer_boundary=outer_boundary,
            inner_shapes=inner_shapes,
            mesh=mesh,
            metadata=metadata,
        )
        domain.generate_domain()
        return domain

    @classmethod
    def build_outer_boundary(cls, mesh: 'Mesh',
                             name: str = 'wind_tunnel_outer_boundary') -> BoundaryLoop:
        segments = []
        for boundary_name in cls.outer_boundary_order:
            shape = mesh.data.boundary_shape(
                boundary_name,
                closed=False,
                name=f'{boundary_name}_boundary',
            )
            if shape is not None:
                segments.append(shape)

        return BoundaryLoop(
            name=name,
            segments=segments,
            closed=True,
            metadata={'source': 'mesh_boundaries'},
        )

    @staticmethod
    def build_inner_boundaries(airfoil) -> list[BoundaryLoop]:
        if airfoil is None:
            return []

        if isinstance(airfoil, BoundaryLoop):
            return [airfoil]

        if isinstance(airfoil, Shape):
            return [
                BoundaryLoop(
                    name=getattr(airfoil, 'name', 'airfoil'),
                    segments=[airfoil],
                    closed=airfoil.is_closed,
                    metadata={'role': 'airfoil'},
                )
            ]

        to_shape = getattr(airfoil, 'to_shape', None)
        if callable(to_shape):
            airfoil_shape = airfoil.to_shape(prefer_spline=True, closed=True)
            if airfoil_shape is not None:
                return [
                    BoundaryLoop(
                        name=getattr(airfoil, 'name', 'airfoil'),
                        segments=[airfoil_shape],
                        closed=True,
                        metadata={'role': 'airfoil'},
                    )
                ]

        return []
