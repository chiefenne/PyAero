from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import Domain
import Mesh
from Shape import Arc, Circle, Line, Polygon, Polyline, Rectangle
import Settings

try:
    from scipy.spatial import Delaunay, QhullError
except ImportError:  # pragma: no cover - guarded at runtime in the UI.
    Delaunay = None
    QhullError = RuntimeError


PointArray = np.ndarray
BOUNDARY_RECOVERY_SWEEP_LIMIT = 3


@dataclass(slots=True)
class MetricTriangulationSettings:
    example: str = 'rectangle'
    width: float = 4.0
    height: float = 2.0
    hole_radius: float = 0.35
    hole_spacing: float = 1.40
    outer_resolution: int = 72
    hole_resolution: int = 44
    interior_x: int = 32
    interior_y: int = 16
    qhull_options: str = 'Qbb Qc Q12 QJ'
    airfoil_path: str | None = None

    def __post_init__(self):
        self.example = str(self.example).strip().lower() or 'rectangle'
        if self.example not in MetricExampleFactory.available_examples():
            raise ValueError(f'Unknown metric test example: {self.example}')

        self.width = float(self.width)
        self.height = float(self.height)
        self.hole_radius = float(self.hole_radius)
        self.hole_spacing = float(self.hole_spacing)
        self.outer_resolution = max(8, int(self.outer_resolution))
        self.hole_resolution = max(12, int(self.hole_resolution))
        self.interior_x = max(0, int(self.interior_x))
        self.interior_y = max(0, int(self.interior_y))

        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError('Rectangle width and height must be positive.')
        if self.hole_radius < 0.0:
            raise ValueError('Hole radius must be non-negative.')
        if self.hole_spacing < 0.0:
            raise ValueError('Hole spacing must be non-negative.')


@dataclass(slots=True)
class ConstraintLoop:
    tag: str
    points: PointArray
    is_hole: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> 'ConstraintLoop':
        return ConstraintLoop(
            tag=self.tag,
            points=np.array(self.points, dtype=float, copy=True),
            is_hole=self.is_hole,
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class MetricTriangulationResult:
    name: str
    domain: Domain.Domain
    loops: list[ConstraintLoop]
    mesh: Mesh.TriangularMesh
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def mesh_data(self) -> Mesh.MeshData:
        return self.mesh.data


class _ConstrainedTriangulation:
    def __init__(self, vertices: PointArray, triangles: np.ndarray):
        self.vertices = np.asarray(vertices, dtype=float)
        self.triangles = [
            self._normalize_triangle(np.asarray(triangle, dtype=int))
            for triangle in np.asarray(triangles, dtype=int)
        ]
        self.edge_to_triangles: dict[tuple[int, int], list[int]] = {}
        self._rebuild_topology()

    def _rebuild_topology(self):
        edge_to_triangles: dict[tuple[int, int], list[int]] = {}
        for triangle_index, triangle in enumerate(self.triangles):
            for index in range(3):
                edge = MetricTriangulator._sorted_edge((
                    int(triangle[index]),
                    int(triangle[(index + 1) % 3]),
                ))
                edge_to_triangles.setdefault(edge, []).append(triangle_index)
        self.edge_to_triangles = edge_to_triangles

    def has_edge(self, edge: tuple[int, int]) -> bool:
        return MetricTriangulator._sorted_edge(edge) in self.edge_to_triangles

    def recover_edge(self, edge: tuple[int, int],
                     constrained_edges: set[tuple[int, int]],
                     max_iterations: int | None = None) -> bool:
        target = MetricTriangulator._sorted_edge(edge)
        if self.has_edge(target):
            constrained_edges.add(target)
            return True

        if max_iterations is None:
            max_iterations = max(20, 8 * len(self.triangles))

        for _ in range(max_iterations):
            if self.has_edge(target):
                constrained_edges.add(target)
                return True

            candidates = self._intersecting_edges(target, constrained_edges)
            if not candidates:
                return False

            flipped = False
            for candidate in candidates:
                if self._flip_edge(candidate, constrained_edges):
                    flipped = True
                    break
            if not flipped:
                return False

        return self.has_edge(target)

    def filtered_triangles(self, mask: np.ndarray) -> np.ndarray:
        kept = [
            np.asarray(triangle, dtype=int)
            for triangle, keep in zip(self.triangles, mask)
            if bool(keep)
        ]
        if not kept:
            raise ValueError('No triangles remain after applying the domain filters.')
        return np.asarray(kept, dtype=int)

    def _intersecting_edges(self, edge: tuple[int, int],
                            constrained_edges: set[tuple[int, int]]
                            ) -> list[tuple[int, int]]:
        start = self.vertices[edge[0]]
        end = self.vertices[edge[1]]
        xmin = min(float(start[0]), float(end[0]))
        xmax = max(float(start[0]), float(end[0]))
        ymin = min(float(start[1]), float(end[1]))
        ymax = max(float(start[1]), float(end[1]))
        candidates = []

        for existing_edge in self.edge_to_triangles:
            if existing_edge == edge:
                continue
            if edge[0] in existing_edge or edge[1] in existing_edge:
                continue

            boundary_start = self.vertices[existing_edge[0]]
            boundary_end = self.vertices[existing_edge[1]]
            if (
                    max(float(boundary_start[0]), float(boundary_end[0])) < xmin or
                    min(float(boundary_start[0]), float(boundary_end[0])) > xmax or
                    max(float(boundary_start[1]), float(boundary_end[1])) < ymin or
                    min(float(boundary_start[1]), float(boundary_end[1])) > ymax):
                continue

            if not MetricTriangulator._segments_cross_proper(
                    start, end, boundary_start, boundary_end):
                continue

            if existing_edge in constrained_edges:
                return []
            candidates.append(existing_edge)

        return candidates

    def _flip_edge(self, edge: tuple[int, int],
                   constrained_edges: set[tuple[int, int]]) -> bool:
        edge = MetricTriangulator._sorted_edge(edge)
        if edge in constrained_edges:
            return False

        adjacent = self.edge_to_triangles.get(edge, [])
        if len(adjacent) != 2:
            return False

        triangle_a = self.triangles[adjacent[0]]
        triangle_b = self.triangles[adjacent[1]]
        opposite_a = self._opposite_vertex(triangle_a, edge)
        opposite_b = self._opposite_vertex(triangle_b, edge)
        if opposite_a is None or opposite_b is None or opposite_a == opposite_b:
            return False

        new_edge = MetricTriangulator._sorted_edge((opposite_a, opposite_b))
        if new_edge in constrained_edges:
            return False

        a_point = self.vertices[edge[0]]
        b_point = self.vertices[edge[1]]
        c_point = self.vertices[opposite_a]
        d_point = self.vertices[opposite_b]
        if not MetricTriangulator._segments_cross_proper(
                a_point, b_point, c_point, d_point):
            return False

        new_triangle_a = self._normalize_triangle(
            np.asarray((opposite_a, opposite_b, edge[0]), dtype=int)
        )
        new_triangle_b = self._normalize_triangle(
            np.asarray((opposite_b, opposite_a, edge[1]), dtype=int)
        )

        if (
                abs(MetricTriangulator._triangle_area(
                    self.vertices[new_triangle_a])) <= 1.0e-12 or
                abs(MetricTriangulator._triangle_area(
                    self.vertices[new_triangle_b])) <= 1.0e-12):
            return False

        self.triangles[adjacent[0]] = new_triangle_a
        self.triangles[adjacent[1]] = new_triangle_b
        self._rebuild_topology()
        return True

    def _normalize_triangle(self, triangle: np.ndarray) -> np.ndarray:
        if MetricTriangulator._triangle_area(self.vertices[triangle]) < 0.0:
            return np.asarray((triangle[0], triangle[2], triangle[1]), dtype=int)
        return np.asarray(triangle, dtype=int)

    @staticmethod
    def _opposite_vertex(triangle: np.ndarray, edge: tuple[int, int]) -> int | None:
        for vertex in triangle:
            if int(vertex) not in edge:
                return int(vertex)
        return None


class MetricExampleFactory:
    _AVAILABLE = (
        'rectangle',
        'rectangle_circle',
        'rectangle_two_circles',
        'default_airfoil_tunnel',
    )

    @classmethod
    def available_examples(cls) -> tuple[str, ...]:
        return cls._AVAILABLE

    @classmethod
    def build_domain(cls, settings: MetricTriangulationSettings) -> Domain.Domain:
        if settings.example == 'default_airfoil_tunnel':
            outer = cls._build_wind_tunnel_outer_boundary(settings)
        else:
            outer = Rectangle(
                width=settings.width,
                height=settings.height,
                center=(0.0, 0.0),
                name='outer_box',
            )

        holes = []
        if settings.example == 'rectangle_circle':
            holes.append(
                Circle(center=(0.0, 0.0), radius=settings.hole_radius, name='hole_1')
            )
        elif settings.example == 'rectangle_two_circles':
            half_spacing = 0.5 * settings.hole_spacing
            holes.extend([
                Circle(
                    center=(-half_spacing, 0.0),
                    radius=settings.hole_radius,
                    name='hole_1',
                ),
                Circle(
                    center=(half_spacing, 0.0),
                    radius=settings.hole_radius,
                    name='hole_2',
                ),
            ])
        elif settings.example == 'default_airfoil_tunnel':
            holes.append(
                cls._load_default_airfoil_shape(settings)
            )

        cls._validate_holes(settings, outer, holes)
        return Domain.Domain(
            name=f'metric_test_{settings.example}',
            outer_boundary=outer,
            inner_shapes=holes,
            metadata={
                'source': 'metric_tests',
                'example': settings.example,
            },
        )

    @staticmethod
    def _validate_holes(settings: MetricTriangulationSettings,
                        outer,
                        holes: Iterable):
        xmin_outer, xmax_outer, ymin_outer, ymax_outer = outer.bounds()
        radius = settings.hole_radius
        tolerance = 1.0e-9

        for hole in holes:
            if isinstance(hole, Circle):
                center_x, center_y = hole.center
                if center_x - radius <= xmin_outer + tolerance or center_x + radius >= xmax_outer - tolerance:
                    raise ValueError(
                        'Hole radius / spacing places a circle outside the outer boundary width.'
                    )
                if center_y - radius <= ymin_outer + tolerance or center_y + radius >= ymax_outer - tolerance:
                    raise ValueError(
                        'Hole radius places a circle outside the outer boundary height.'
                    )
                continue

            xmin, xmax, ymin, ymax = hole.bounds()
            if xmin <= xmin_outer + tolerance or xmax >= xmax_outer - tolerance:
                raise ValueError('Airfoil hole exceeds the outer boundary width.')
            if ymin <= ymin_outer + tolerance or ymax >= ymax_outer - tolerance:
                raise ValueError('Airfoil hole exceeds the outer boundary height.')

    @classmethod
    def _load_default_airfoil_shape(cls,
                                    settings: MetricTriangulationSettings
                                    ) -> Domain.BoundaryLoop:
        airfoil_path = cls._resolve_airfoil_path(settings.airfoil_path)
        coordinates = cls._read_airfoil_coordinates(airfoil_path)
        return Domain.BoundaryLoop(
            name='default_airfoil',
            segments=[Polygon(coordinates, name='default_airfoil_contour')],
            closed=True,
            metadata={
                'role': 'airfoil',
                'use_source_vertices': True,
            },
        )

    @staticmethod
    def _build_wind_tunnel_outer_boundary(
            settings: MetricTriangulationSettings) -> Domain.BoundaryLoop:
        radius = 0.5 * float(settings.height)
        inlet_center_x = 0.5
        outlet_x = inlet_center_x + float(settings.width) - radius
        if outlet_x <= inlet_center_x + 1.0e-9:
            raise ValueError(
                'Wind-tunnel width must be larger than half the tunnel height.'
            )

        return Domain.BoundaryLoop(
            name='outer_wind_tunnel',
            segments=[
                Line(
                    p1=(outlet_x, radius),
                    p2=(inlet_center_x, radius),
                    name='top',
                ),
                Arc(
                    center=(inlet_center_x, 0.0),
                    radius=radius,
                    start_angle=0.5 * np.pi,
                    end_angle=1.5 * np.pi,
                    name='inlet',
                ),
                Line(
                    p1=(inlet_center_x, -radius),
                    p2=(outlet_x, -radius),
                    name='bottom',
                ),
                Line(
                    p1=(outlet_x, -radius),
                    p2=(outlet_x, radius),
                    name='outlet',
                ),
            ],
            closed=True,
            metadata={
                'shape': 'wind_tunnel',
                'role': 'outer',
            },
        )

    @staticmethod
    def _resolve_airfoil_path(configured_path: str | None) -> Path:
        if configured_path:
            path = Path(configured_path)
            if not path.is_absolute():
                path = Settings.ROOT / path
            return path.resolve()

        parser = configparser.ConfigParser(
            interpolation=configparser.ExtendedInterpolation()
        )
        parser.optionxform = str
        parser.read(Settings.CONFIG_FILE, encoding='utf-8')
        default_path = parser.get('Application', 'DEFAULT_AIRFOIL')
        return (Settings.ROOT / default_path).resolve()

    @staticmethod
    def _read_airfoil_coordinates(path: Path) -> list[tuple[float, float]]:
        if not path.exists():
            raise ValueError(f'Default airfoil file does not exist: {path}')

        points = []
        with path.open('r', encoding='utf-8') as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                try:
                    x_value = float(parts[0])
                    y_value = float(parts[1])
                except ValueError:
                    continue
                points.append((x_value, y_value))

        if len(points) < 3:
            raise ValueError(f'Airfoil file does not contain enough coordinates: {path}')

        coordinates = np.asarray(points, dtype=float)
        coordinates[:, 0] -= np.min(coordinates[:, 0])
        scale = np.max(coordinates[:, 0])
        if scale <= 1.0e-12:
            raise ValueError(f'Airfoil file has invalid chord length: {path}')
        coordinates[:, 0] /= scale
        coordinates[:, 1] /= scale

        if np.linalg.norm(coordinates[0] - coordinates[-1]) > 1.0e-12:
            coordinates = np.vstack([coordinates, coordinates[0]])
        return [
            (float(point[0]), float(point[1]))
            for point in coordinates[:-1]
        ]


class MetricTriangulator:
    @classmethod
    def generate(cls, settings: MetricTriangulationSettings) -> MetricTriangulationResult:
        if Delaunay is None:
            raise ValueError(
                'SciPy is required for the metric triangulation playground.'
            )

        domain = MetricExampleFactory.build_domain(settings)
        loops = cls._sample_loops(domain, settings)
        warnings: list[str] = []
        vertices, boundary_tags, loop_vertex_ids = cls._assemble_vertices(
            loops,
            settings,
        )
        simplices = cls._delaunay(vertices, settings.qhull_options)
        triangulation = _ConstrainedTriangulation(vertices, simplices)

        constrained_edges: set[tuple[int, int]] = set()
        pending_edges = [
            cls._sorted_edge(edge)
            for edges in boundary_tags.values()
            for edge in edges
        ]
        recovery_sweeps_used = 0

        for sweep in range(BOUNDARY_RECOVERY_SWEEP_LIMIT):
            failed_edges = []
            for edge in pending_edges:
                if triangulation.recover_edge(edge, constrained_edges):
                    continue
                failed_edges.append(edge)
            recovery_sweeps_used = sweep + 1
            pending_edges = failed_edges
            if not pending_edges:
                break

        if pending_edges:
            warnings.append(
                f'{len(pending_edges)} constraint segments could not be recovered directly.'
            )

        triangles = cls._filter_triangles(
            vertices,
            triangulation,
            loop_vertex_ids,
        )

        mesh_edge_set = cls._edge_set(triangles)
        boundary_tags, missing_boundary_edges = cls._existing_boundary_tags(
            boundary_tags,
            mesh_edge_set,
        )
        if missing_boundary_edges:
            warnings.append(
                f'{missing_boundary_edges} constraint edges are not present in '
                'the filtered triangulation.'
            )

        mesh_data = Mesh.MeshData(
            vertices=vertices,
            connectivity=triangles,
            boundary_tags=boundary_tags,
            metadata={
                'source': 'MetricTriangulator',
                'example': settings.example,
                'recovery_sweeps_used': recovery_sweeps_used,
                'warnings': list(warnings),
            },
        )
        mesh = Mesh.TriangularMesh(
            name=f'{settings.example}_triangulation',
            data=mesh_data,
            metadata={
                'engine': 'metric_test_cdt',
                'example': settings.example,
            },
        )

        return MetricTriangulationResult(
            name=mesh.name,
            domain=domain,
            loops=loops,
            mesh=mesh,
            warnings=warnings,
            metadata={
                'example': settings.example,
                'loop_count': len(loops),
                'recovery_sweeps_used': recovery_sweeps_used,
                'warning_count': len(warnings),
            },
        )

    @classmethod
    def _sample_loops(cls, domain: Domain.Domain,
                      settings: MetricTriangulationSettings) -> list[ConstraintLoop]:
        loops = [
            ConstraintLoop(
                tag='outer',
                points=cls._sample_boundary_loop(
                    domain.outer_boundary,
                    resolution=settings.outer_resolution,
                ),
                is_hole=False,
                metadata={'role': 'outer'},
            )
        ]

        for index, hole in enumerate(domain.inner_shapes, start=1):
            loops.append(
                ConstraintLoop(
                    tag=f'hole_{index}',
                    points=cls._sample_boundary_loop(
                        hole,
                        resolution=settings.hole_resolution,
                    ),
                    is_hole=True,
                    metadata={'role': 'hole', 'index': index},
                )
            )

        return loops

    @classmethod
    def _sample_boundary_loop(cls, loop: Domain.BoundaryLoop,
                              resolution: int) -> PointArray:
        if loop.metadata.get('use_source_vertices'):
            return cls._normalize_loop_points(loop.to_polygon(resolution=None))

        if len(loop.segments) == 1:
            segment = loop.segments[0]
            if isinstance(segment, Circle):
                return cls._normalize_loop_points(
                    segment.sample_points(resolution=resolution)
                )
            if isinstance(segment, (Rectangle, Polygon, Polyline)):
                return cls._sample_polyline_preserving_vertices(
                    segment.sample_points(resolution=None),
                    resolution=resolution,
                    closed=segment.is_closed,
                )

        return cls._sample_composite_loop(loop, resolution)

    @classmethod
    def _sample_composite_loop(cls, loop: Domain.BoundaryLoop,
                               resolution: int) -> PointArray:
        segments = list(loop.segments)
        if not segments:
            raise ValueError(f'Boundary loop {loop.name} is empty.')

        base_counts = np.asarray(
            [
                3 if isinstance(segment, (Arc, Circle)) else 2
                for segment in segments
            ],
            dtype=int,
        )
        minimum_resolution = int(np.sum(base_counts - 1))
        target_resolution = max(int(resolution), minimum_resolution)

        lengths = np.asarray(
            [cls._shape_length(segment) for segment in segments],
            dtype=float,
        )
        counts = np.array(base_counts, copy=True)
        extra_points = target_resolution - minimum_resolution
        total_length = float(np.sum(lengths))
        if extra_points > 0 and total_length > 1.0e-14:
            raw = extra_points * lengths / total_length
            increments = np.floor(raw).astype(int)
            remainder = extra_points - int(np.sum(increments))
            if remainder > 0:
                order = np.argsort(-(raw - increments))
                increments[order[:remainder]] += 1
            counts += increments

        points: list[tuple[float, float]] = []
        for segment, count in zip(segments, counts):
            segment_points = segment.sample_points(resolution=int(count))
            if not segment_points:
                continue
            current = list(segment_points)
            if points:
                if np.allclose(points[-1], current[0], atol=1.0e-9):
                    points.extend(current[1:])
                elif np.allclose(points[-1], current[-1], atol=1.0e-9):
                    current.reverse()
                    points.extend(current[1:])
                else:
                    points.extend(current)
            else:
                points.extend(current)

        if loop.is_closed and not np.allclose(points[0], points[-1], atol=1.0e-9):
            points.append(points[0])
        return cls._normalize_loop_points(points)

    @staticmethod
    def _shape_length(shape) -> float:
        if isinstance(shape, Line):
            start = np.asarray(shape.start, dtype=float)
            end = np.asarray(shape.end, dtype=float)
            return float(np.linalg.norm(end - start))

        if isinstance(shape, Arc):
            points = np.asarray(shape.sample_points(resolution=128), dtype=float)
        else:
            points = np.asarray(shape.sample_points(resolution=None), dtype=float)

        if len(points) < 2:
            return 0.0
        return float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))

    @classmethod
    def _sample_polyline_preserving_vertices(cls,
                                             points: Iterable[tuple[float, float]],
                                             resolution: int,
                                             closed: bool) -> PointArray:
        loop = cls._normalize_loop_points(points)
        base = loop[:-1]
        if resolution <= len(base):
            return np.vstack([base, base[0]])

        deltas = np.diff(loop, axis=0)
        segment_lengths = np.linalg.norm(deltas, axis=1)
        total_length = float(np.sum(segment_lengths))
        if total_length <= 1.0e-14:
            return loop

        extra_points = resolution - len(base)
        raw = extra_points * segment_lengths / total_length
        counts = np.floor(raw).astype(int)
        remainder = extra_points - int(np.sum(counts))
        if remainder > 0:
            order = np.argsort(-(raw - counts))
            counts[order[:remainder]] += 1

        sampled = [loop[0]]
        for index, count in enumerate(counts):
            start = loop[index]
            end = loop[index + 1]
            if count > 0:
                weights = np.arange(1, count + 1, dtype=float) / (count + 1.0)
                interpolated = start + weights[:, None] * (end - start)
                sampled.extend(interpolated)
            sampled.append(end)

        return cls._normalize_loop_points(sampled)

    @staticmethod
    def _normalize_loop_points(points: Iterable[tuple[float, float]]) -> PointArray:
        array = np.asarray(list(points), dtype=float)
        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError('Loop points must form an array with shape (n, 2).')

        cleaned = [array[0]]
        for point in array[1:]:
            if np.linalg.norm(point - cleaned[-1]) > 1.0e-12:
                cleaned.append(point)
        loop = np.asarray(cleaned, dtype=float)
        if np.linalg.norm(loop[0] - loop[-1]) > 1.0e-12:
            loop = np.vstack([loop, loop[0]])
        if len(loop) < 4:
            raise ValueError('Each loop needs at least three unique vertices.')
        return loop

    @classmethod
    def _assemble_vertices(cls, loops: list[ConstraintLoop],
                           settings: MetricTriangulationSettings):
        builder = _VertexBuilder()
        boundary_tags: dict[str, list[tuple[int, int]]] = {}
        loop_vertex_ids: list[np.ndarray] = []

        for loop in loops:
            ids = [builder.add(point) for point in loop.points[:-1]]
            ids.append(ids[0])
            loop_ids = np.asarray(ids, dtype=int)
            loop_vertex_ids.append(loop_ids)
            boundary_tags[loop.tag] = [
                (int(loop_ids[index]), int(loop_ids[index + 1]))
                for index in range(len(loop_ids) - 1)
            ]

        for point in cls._interior_grid_points(loops, settings):
            builder.add(point)

        return builder.as_array(), boundary_tags, loop_vertex_ids

    @classmethod
    def _interior_grid_points(cls, loops: list[ConstraintLoop],
                              settings: MetricTriangulationSettings) -> list[tuple[float, float]]:
        if settings.interior_x <= 0 or settings.interior_y <= 0:
            return []

        outer = loops[0].points
        xmin = float(np.min(outer[:, 0]))
        xmax = float(np.max(outer[:, 0]))
        ymin = float(np.min(outer[:, 1]))
        ymax = float(np.max(outer[:, 1]))
        x_values = np.linspace(xmin, xmax, settings.interior_x + 2)[1:-1]
        y_values = np.linspace(ymin, ymax, settings.interior_y + 2)[1:-1]
        grid_x, grid_y = np.meshgrid(x_values, y_values, indexing='xy')
        points = np.column_stack((grid_x.ravel(), grid_y.ravel()))
        inside = cls._points_in_domain(points, loops)
        return [
            (float(point[0]), float(point[1]))
            for point in points[inside]
        ]

    @classmethod
    def _delaunay(cls, vertices: PointArray, qhull_options: str) -> np.ndarray:
        try:
            simplices = Delaunay(vertices, qhull_options=qhull_options).simplices
        except QhullError as error:
            raise ValueError(f'Delaunay triangulation failed: {error}') from error
        return np.asarray(simplices, dtype=int)

    @staticmethod
    def _edge_set(connectivity: np.ndarray) -> set[tuple[int, int]]:
        edges: set[tuple[int, int]] = set()
        for cell in np.asarray(connectivity, dtype=int):
            count = len(cell)
            for index in range(count):
                a_value = int(cell[index])
                b_value = int(cell[(index + 1) % count])
                if a_value <= b_value:
                    edges.add((a_value, b_value))
                else:
                    edges.add((b_value, a_value))
        return edges

    @classmethod
    def _filter_triangles(cls, vertices: PointArray,
                          triangulation: _ConstrainedTriangulation,
                          loop_vertex_ids: list[np.ndarray]) -> np.ndarray:
        loops = [
            vertices[vertex_ids]
            for vertex_ids in loop_vertex_ids
        ]
        simplices = np.asarray(triangulation.triangles, dtype=int)
        triangles = vertices[simplices]
        areas = np.abs(cls._triangle_area_array(triangles))
        centroids = np.mean(triangles, axis=1)
        loop_specs = [
            ConstraintLoop('outer', loops[0], is_hole=False),
            *[
                ConstraintLoop(f'hole_{index}', loop, is_hole=True)
                for index, loop in enumerate(loops[1:], start=1)
            ],
        ]
        inside_domain = cls._points_in_domain(centroids, loop_specs)
        keep_mask = (areas > 1.0e-12) & inside_domain
        return triangulation.filtered_triangles(keep_mask)

    @classmethod
    def _existing_boundary_tags(cls, boundary_tags: dict[str, list[tuple[int, int]]],
                                mesh_edge_set: set[tuple[int, int]]):
        existing: dict[str, list[tuple[int, int]]] = {}
        missing_count = 0
        for tag, edges in boundary_tags.items():
            present = []
            for edge in edges:
                if cls._sorted_edge(edge) in mesh_edge_set:
                    present.append(edge)
                else:
                    missing_count += 1
            existing[tag] = present
        return existing, missing_count

    @classmethod
    def _point_in_domain(cls, point: tuple[float, float],
                         loops: list[ConstraintLoop]) -> bool:
        points = np.asarray([[float(point[0]), float(point[1])]], dtype=float)
        return bool(cls._points_in_domain(points, loops)[0])

    @classmethod
    def _points_in_domain(cls, points: np.ndarray,
                          loops: list[ConstraintLoop]) -> np.ndarray:
        if not loops:
            return np.zeros(len(points), dtype=bool)

        inside = cls._points_in_polygon(points, loops[0].points)
        for hole in loops[1:]:
            inside &= ~cls._points_in_polygon(points, hole.points)
        return inside

    @classmethod
    def _point_in_polygon(cls, point: tuple[float, float],
                          polygon: PointArray) -> bool:
        points = np.asarray([[float(point[0]), float(point[1])]], dtype=float)
        return bool(cls._points_in_polygon(points, polygon)[0])

    @staticmethod
    def _points_in_polygon(points: np.ndarray, polygon: PointArray,
                           tolerance: float = 1.0e-12) -> np.ndarray:
        if len(points) == 0:
            return np.zeros(0, dtype=bool)

        points = np.asarray(points, dtype=float)
        x_values = points[:, 0][:, None]
        y_values = points[:, 1][:, None]
        x1 = polygon[:-1, 0][None, :]
        y1 = polygon[:-1, 1][None, :]
        x2 = polygon[1:, 0][None, :]
        y2 = polygon[1:, 1][None, :]

        cross = (x_values - x1) * (y2 - y1) - (y_values - y1) * (x2 - x1)
        min_x = np.minimum(x1, x2) - tolerance
        max_x = np.maximum(x1, x2) + tolerance
        min_y = np.minimum(y1, y2) - tolerance
        max_y = np.maximum(y1, y2) + tolerance
        on_segment = (
            np.abs(cross) <= tolerance
        ) & (
            x_values >= min_x
        ) & (
            x_values <= max_x
        ) & (
            y_values >= min_y
        ) & (
            y_values <= max_y
        )

        denominator = y2 - y1
        safe_denominator = np.where(
            np.abs(denominator) <= tolerance,
            1.0,
            denominator,
        )
        intersects = ((y1 > y_values) != (y2 > y_values))
        x_intersections = x1 + (y_values - y1) * (x2 - x1) / safe_denominator
        toggles = intersects & (x_intersections >= x_values - tolerance)
        inside = np.count_nonzero(toggles, axis=1) % 2 == 1
        return inside | np.any(on_segment, axis=1)

    @staticmethod
    def _point_on_segment(point: tuple[float, float],
                          start: np.ndarray,
                          end: np.ndarray,
                          tolerance: float = 1.0e-9) -> bool:
        px, py = float(point[0]), float(point[1])
        x1, y1 = float(start[0]), float(start[1])
        x2, y2 = float(end[0]), float(end[1])
        cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
        if abs(cross) > tolerance:
            return False
        dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
        return dot <= tolerance

    @staticmethod
    def _triangle_area(triangle: PointArray) -> float:
        ax_value = float(triangle[1][0] - triangle[0][0])
        ay_value = float(triangle[1][1] - triangle[0][1])
        bx_value = float(triangle[2][0] - triangle[0][0])
        by_value = float(triangle[2][1] - triangle[0][1])
        return 0.5 * (ax_value * by_value - ay_value * bx_value)

    @staticmethod
    def _triangle_area_array(triangles: np.ndarray) -> np.ndarray:
        ax_values = triangles[:, 1, 0] - triangles[:, 0, 0]
        ay_values = triangles[:, 1, 1] - triangles[:, 0, 1]
        bx_values = triangles[:, 2, 0] - triangles[:, 0, 0]
        by_values = triangles[:, 2, 1] - triangles[:, 0, 1]
        return 0.5 * (ax_values * by_values - ay_values * bx_values)

    @classmethod
    def _segments_intersect(cls, a_start: np.ndarray, a_end: np.ndarray,
                            b_start: np.ndarray, b_end: np.ndarray,
                            tolerance: float = 1.0e-9) -> bool:
        o1 = cls._orientation(a_start, a_end, b_start)
        o2 = cls._orientation(a_start, a_end, b_end)
        o3 = cls._orientation(b_start, b_end, a_start)
        o4 = cls._orientation(b_start, b_end, a_end)

        if (
                (o1 > tolerance and o2 < -tolerance) or
                (o1 < -tolerance and o2 > tolerance)
        ) and (
                (o3 > tolerance and o4 < -tolerance) or
                (o3 < -tolerance and o4 > tolerance)
        ):
            return True

        if abs(o1) <= tolerance and cls._point_on_segment(tuple(b_start), a_start, a_end):
            return True
        if abs(o2) <= tolerance and cls._point_on_segment(tuple(b_end), a_start, a_end):
            return True
        if abs(o3) <= tolerance and cls._point_on_segment(tuple(a_start), b_start, b_end):
            return True
        if abs(o4) <= tolerance and cls._point_on_segment(tuple(a_end), b_start, b_end):
            return True
        return False

    @classmethod
    def _segments_cross_proper(cls, a_start: np.ndarray, a_end: np.ndarray,
                               b_start: np.ndarray, b_end: np.ndarray,
                               tolerance: float = 1.0e-9) -> bool:
        o1 = cls._orientation(a_start, a_end, b_start)
        o2 = cls._orientation(a_start, a_end, b_end)
        o3 = cls._orientation(b_start, b_end, a_start)
        o4 = cls._orientation(b_start, b_end, a_end)

        return (
            ((o1 > tolerance and o2 < -tolerance) or
             (o1 < -tolerance and o2 > tolerance)) and
            ((o3 > tolerance and o4 < -tolerance) or
             (o3 < -tolerance and o4 > tolerance))
        )

    @staticmethod
    def _orientation(start: np.ndarray, end: np.ndarray, point: np.ndarray) -> float:
        return float(
            (end[0] - start[0]) * (point[1] - start[1]) -
            (end[1] - start[1]) * (point[0] - start[0])
        )

    @staticmethod
    def _sorted_edge(edge: tuple[int, int]) -> tuple[int, int]:
        a_value, b_value = int(edge[0]), int(edge[1])
        return (a_value, b_value) if a_value <= b_value else (b_value, a_value)


class _VertexBuilder:
    def __init__(self, tolerance: float = 1.0e-10):
        self._tolerance = float(tolerance)
        self._points: list[tuple[float, float]] = []
        self._index_by_key: dict[tuple[int, int], int] = {}

    def add(self, point: Iterable[float]) -> int:
        x_value, y_value = float(point[0]), float(point[1])
        key = self._key((x_value, y_value))
        existing = self._index_by_key.get(key)
        if existing is not None:
            return existing
        index = len(self._points)
        self._points.append((x_value, y_value))
        self._index_by_key[key] = index
        return index

    def as_array(self) -> PointArray:
        return np.asarray(self._points, dtype=float)

    def _key(self, point: tuple[float, float]) -> tuple[int, int]:
        scale = 1.0 / self._tolerance
        return int(round(point[0] * scale)), int(round(point[1] * scale))
