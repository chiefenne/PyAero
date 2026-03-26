from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from Shape import Polygon, Polyline, Point2D

logger = logging.getLogger(__name__)


Edge = tuple[int, int]


def _as_vertices(vertices: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(vertices, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError('Vertices must be a 2D array with shape (n, 2).')
    return array


def _as_connectivity(connectivity: Sequence[Sequence[int]]) -> np.ndarray:
    array = np.asarray(connectivity, dtype=int)
    if array.ndim != 2:
        raise ValueError('Connectivity must be a 2D integer array.')
    return array


def _normalized_edge(edge: Sequence[int]) -> Edge:
    if len(edge) != 2:
        raise ValueError('Edges must contain exactly two vertex ids.')
    a, b = int(edge[0]), int(edge[1])
    return a, b


def _sorted_edge(edge: Sequence[int]) -> Edge:
    a, b = _normalized_edge(edge)
    return (a, b) if a <= b else (b, a)


def _trace_edge_path(edges: Sequence[Sequence[int]]) -> tuple[list[int], bool]:
    if not edges:
        return [], False

    adjacency: dict[int, list[tuple[int, int]]] = defaultdict(list)
    normalized_edges = [_normalized_edge(edge) for edge in edges]

    for index, (start, end) in enumerate(normalized_edges):
        adjacency[start].append((index, end))
        adjacency[end].append((index, start))

    endpoints = [node for node, neighbours in adjacency.items()
                 if len(neighbours) == 1]
    is_closed = not endpoints
    start = min(endpoints) if endpoints else min(adjacency)

    ordered_nodes = [start]
    used_edges: set[int] = set()
    previous = None
    current = start

    while len(used_edges) < len(normalized_edges):
        candidates = [
            (edge_index, neighbour)
            for edge_index, neighbour in adjacency[current]
            if edge_index not in used_edges
        ]

        if not candidates:
            break

        if previous is None:
            edge_index, next_node = candidates[0]
        else:
            edge_index, next_node = next(
                (
                    candidate for candidate in candidates
                    if candidate[1] != previous
                ),
                candidates[0],
            )

        used_edges.add(edge_index)
        ordered_nodes.append(next_node)
        previous, current = current, next_node

    if len(used_edges) != len(normalized_edges):
        raise ValueError('Boundary edges do not form a single connected path.')

    if is_closed and ordered_nodes[0] != ordered_nodes[-1]:
        ordered_nodes.append(ordered_nodes[0])

    return ordered_nodes, is_closed


@dataclass(slots=True)
class MeshStatistics:
    vertex_count: int
    cell_count: int
    edge_count: int
    block_count: int = 0


@dataclass(slots=True)
class MeshBlock:
    name: str
    u_lines: list[list[Point2D]]

    @classmethod
    def from_legacy(cls, block) -> 'MeshBlock':
        lines = [
            [(float(x), float(y)) for x, y in line]
            for line in block.getULines()
        ]
        return cls(name=getattr(block, 'name', 'block'), u_lines=lines)

    @property
    def is_empty(self) -> bool:
        return not self.u_lines

    @property
    def v_lines(self) -> list[list[Point2D]]:
        if not self.u_lines:
            return []
        line_length = len(self.u_lines[0])
        return [
            [u_line[index] for u_line in self.u_lines]
            for index in range(line_length)
        ]

    @property
    def divisions(self) -> tuple[int, int]:
        if self.is_empty:
            return 0, 0
        return len(self.u_lines[0]) - 1, len(self.u_lines) - 1

    def iter_boundary_lines(self) -> Iterable[list[Point2D]]:
        if self.is_empty:
            return
        yield self.u_lines[0]
        yield self.u_lines[-1]
        v_lines = self.v_lines
        yield v_lines[0]
        yield v_lines[-1]


@dataclass(slots=True)
class MeshData:
    vertices: np.ndarray | Sequence[Sequence[float]]
    connectivity: np.ndarray | Sequence[Sequence[int]]
    boundary_tags: dict[str, list[Edge]] = field(default_factory=dict)
    cell_to_vertices: np.ndarray | Sequence[Sequence[int]] | None = None
    cell_to_edges: Mapping[int, Sequence[Sequence[int]]] | None = None
    quality: np.ndarray | Sequence[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.vertices = _as_vertices(self.vertices)
        self.connectivity = _as_connectivity(self.connectivity)

        if self.cell_to_vertices is None:
            self.cell_to_vertices = self.connectivity.copy()
        else:
            self.cell_to_vertices = _as_connectivity(self.cell_to_vertices)

        normalized_tags: dict[str, list[Edge]] = {}
        for tag, edges in self.boundary_tags.items():
            normalized_tags[tag] = [_normalized_edge(edge) for edge in edges]
        self.boundary_tags = normalized_tags

        if self.cell_to_edges is None:
            self.cell_to_edges = self._build_cell_to_edges()
        else:
            self.cell_to_edges = {
                int(cell_id): [_normalized_edge(edge) for edge in edges]
                for cell_id, edges in self.cell_to_edges.items()
            }

        if self.quality is not None:
            self.quality = np.asarray(self.quality, dtype=float)

    @property
    def vertex_count(self) -> int:
        return int(len(self.vertices))

    @property
    def cell_count(self) -> int:
        return int(len(self.connectivity))

    def _build_cell_to_edges(self) -> dict[int, list[Edge]]:
        mapping: dict[int, list[Edge]] = {}
        for cell_id, cell in enumerate(self.connectivity):
            edges = []
            for index in range(len(cell)):
                edge = (int(cell[index]), int(cell[(index + 1) % len(cell)]))
                edges.append(edge)
            mapping[cell_id] = edges
        return mapping

    def unique_edges(self) -> list[Edge]:
        unique = {_sorted_edge(edge)
                  for edges in self.cell_to_edges.values()
                  for edge in edges}
        return sorted(unique)

    def statistics(self, block_count: int = 0) -> MeshStatistics:
        return MeshStatistics(
            vertex_count=self.vertex_count,
            cell_count=self.cell_count,
            edge_count=len(self.unique_edges()),
            block_count=block_count,
        )

    def boundary_vertices(self, tag: str) -> list[Point2D]:
        edges = self.boundary_tags.get(tag, [])
        if not edges:
            return []
        ordered_ids, _ = _trace_edge_path(edges)
        return [
            (
                float(self.vertices[vertex_id][0]),
                float(self.vertices[vertex_id][1]),
            )
            for vertex_id in ordered_ids
        ]

    def boundary_shape(self, tag: str, closed: bool | None = None,
                       name: str | None = None):
        edges = self.boundary_tags.get(tag, [])
        if not edges:
            return None

        points = self.boundary_vertices(tag)
        _, inferred_closed = _trace_edge_path(edges)
        is_closed = inferred_closed if closed is None else bool(closed)

        if is_closed and points and points[0] == points[-1]:
            points = points[:-1]

        label = name or tag
        if is_closed:
            return Polygon(points, name=label)
        return Polyline(points, closed=False, name=label)

    @classmethod
    def from_file(cls, filename: str, mesh_format: str | None = None,
                  **kwargs) -> 'MeshData':
        """Read mesh data from disk via the mesh import registry."""
        return MeshImportRegistry.import_file(
            filename,
            mesh_format=mesh_format,
            **kwargs,
        )


class Mesh(ABC):
    """Abstract mesh model used by the new domain layer."""

    def __init__(self, name: str = '', data: MeshData | None = None,
                 metadata: Mapping[str, Any] | None = None):
        self.name = name or self.__class__.__name__
        self.data = data
        self.metadata = dict(metadata or {})

    @abstractmethod
    def generate_mesh(self) -> MeshData | None:
        """Generate or return the mesh data."""

    def mesh_quality(self):
        if self.data is None:
            return None
        return self.data.quality

    def mesh_statistics(self) -> MeshStatistics:
        if self.data is None:
            return MeshStatistics(0, 0, 0, 0)
        return self.data.statistics()

    def display_mesh(self):
        return self.data


class BlockStructuredMesh(Mesh):
    """Model wrapper around a block-structured mesh and its topology."""

    def __init__(self, name: str = '', blocks: Iterable[MeshBlock] | None = None,
                 data: MeshData | None = None,
                 boundary_conditions: Mapping[str, str] | None = None,
                 metadata: Mapping[str, Any] | None = None):
        super().__init__(name=name, data=data, metadata=metadata)
        self.blocks = list(blocks or [])
        self.boundary_conditions = dict(boundary_conditions or {})

    def add_block(self, block: MeshBlock):
        self.blocks.append(block)

    def generate_mesh(self) -> MeshData | None:
        return self.data

    def mesh_statistics(self) -> MeshStatistics:
        if self.data is None:
            return MeshStatistics(0, 0, 0, len(self.blocks))
        return self.data.statistics(block_count=len(self.blocks))

    @classmethod
    def from_windtunnel(cls, wind_tunnel, name: str = '',
                        boundary_conditions: Mapping[str, str] | None = None):
        blocks = [MeshBlock.from_legacy(block) for block in wind_tunnel.blocks]

        vertices, connectivity = wind_tunnel.mesh
        topology = getattr(wind_tunnel, 'topology', None)
        if topology is None:
            topology = MeshTopology.from_mesh(vertices, connectivity)
        mesh_data = MeshData(
            vertices=vertices,
            connectivity=connectivity,
            boundary_tags=topology.boundary_tags,
            cell_to_vertices=topology.cell_to_vertices,
            cell_to_edges=topology.cell_to_edges,
            quality=getattr(wind_tunnel, 'quality', None),
            metadata={
                'source': wind_tunnel.__class__.__name__,
                'block_names': [block.name for block in blocks],
                'boundary_edges': list(topology.boundary_edges),
            },
        )

        return cls(
            name=name or getattr(wind_tunnel, 'name', 'BlockStructuredMesh'),
            blocks=blocks,
            data=mesh_data,
            boundary_conditions=boundary_conditions,
            metadata={'legacy_engine': wind_tunnel.__class__.__name__},
        )


class BlockMesh(BlockStructuredMesh):
    """Backward-compatible block mesh name for the new model layer."""


class UnstructuredMesh(Mesh):
    def __init__(self, name: str = '', data: MeshData | None = None,
                 element_type: str = 'mixed',
                 metadata: Mapping[str, Any] | None = None):
        super().__init__(name=name, data=data, metadata=metadata)
        self.element_type = element_type

    def generate_mesh(self) -> MeshData | None:
        return self.data


class TriangularMesh(UnstructuredMesh):
    def __init__(self, name: str = '', data: MeshData | None = None,
                 use_quads_near_airfoil: bool = True,
                 metadata: Mapping[str, Any] | None = None):
        super().__init__(
            name=name or 'TriangularMesh',
            data=data,
            element_type='triangle',
            metadata=metadata,
        )
        self.use_quads_near_airfoil = use_quads_near_airfoil


@dataclass(slots=True)
class BoundaryDefinitions:
    airfoil: str = 'airfoil'
    inlet: str = 'inlet'
    outlet: str = 'outlet'
    top: str = 'top'
    bottom: str = 'bottom'

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str] | None = None):
        defaults = cls()
        if not mapping:
            return defaults
        return cls(
            airfoil=mapping.get('airfoil', defaults.airfoil),
            inlet=mapping.get('inlet', defaults.inlet),
            outlet=mapping.get('outlet', defaults.outlet),
            top=mapping.get('top', defaults.top),
            bottom=mapping.get('bottom', defaults.bottom),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            'airfoil': self.airfoil,
            'inlet': self.inlet,
            'outlet': self.outlet,
            'top': self.top,
            'bottom': self.bottom,
        }

    def items(self):
        return self.as_dict().items()


class BoundaryClassifier:
    default_tags = ('airfoil', 'inlet', 'outlet', 'top', 'bottom')

    @staticmethod
    def find_boundary_edges(edges: Sequence[Sequence[int]]) -> list[Edge]:
        normalized = [_sorted_edge(edge) for edge in edges]
        counts: dict[Edge, int] = defaultdict(int)
        for edge in normalized:
            counts[edge] += 1
        return [edge for edge, count in counts.items() if count == 1]

    @classmethod
    def classify(cls, vertices: Sequence[Sequence[float]],
                 edges: Sequence[Sequence[int]],
                 tolerance: float = 1.0e-6) -> tuple[list[Edge], dict[str, list[Edge]]]:
        vertices_array = _as_vertices(vertices)
        boundary_edges = cls.find_boundary_edges(edges)
        boundary_tags = {tag: [] for tag in cls.default_tags}

        xmax = float(np.max(vertices_array[:, 0]))
        ymax = float(np.max(vertices_array[:, 1]))
        ymin = float(np.min(vertices_array[:, 1]))

        for edge in boundary_edges:
            x1 = vertices_array[edge[0]][0]
            y1 = vertices_array[edge[0]][1]
            x2 = vertices_array[edge[1]][0]
            y2 = vertices_array[edge[1]][1]
            x_mid = 0.5 * (x1 + x2)
            y_mid = 0.5 * (y1 + y2)

            if -0.1 < x_mid < 1.1 and -0.5 < y_mid < 0.5:
                boundary_tags['airfoil'].append(edge)
            elif abs(x1 - xmax) < tolerance and abs(x2 - xmax) < tolerance:
                boundary_tags['outlet'].append(edge)
            elif abs(y1 - ymax) < tolerance and abs(y2 - ymax) < tolerance:
                boundary_tags['top'].append(edge)
            elif abs(y1 - ymin) < tolerance and abs(y2 - ymin) < tolerance:
                boundary_tags['bottom'].append(edge)
            else:
                boundary_tags['inlet'].append(edge)

        return boundary_edges, boundary_tags


@dataclass(slots=True)
class MeshTopology:
    cell_to_vertices: np.ndarray
    cell_to_edges: dict[int, list[Edge]]
    edges: list[Edge]
    boundary_edges: list[Edge]
    boundary_tags: dict[str, list[Edge]]

    @classmethod
    def from_mesh(cls, vertices: Sequence[Sequence[float]],
                  connectivity: Sequence[Sequence[int]],
                  tolerance: float = 1.0e-6) -> 'MeshTopology':
        vertices_array = _as_vertices(vertices)
        connectivity_array = _as_connectivity(connectivity)
        cell_to_vertices = connectivity_array.copy()
        cell_to_edges: dict[int, list[Edge]] = {}
        edges: list[Edge] = []

        for cell_id, cell in enumerate(connectivity_array):
            cell_edges = []
            for index in range(len(cell)):
                edge = _normalized_edge(
                    (int(cell[index]), int(cell[(index + 1) % len(cell)]))
                )
                cell_edges.append(edge)
                edges.append(_sorted_edge(edge))
            cell_to_edges[cell_id] = cell_edges

        boundary_edges, boundary_tags = BoundaryClassifier.classify(
            vertices_array,
            edges,
            tolerance=tolerance,
        )
        return cls(
            cell_to_vertices=cell_to_vertices,
            cell_to_edges=cell_to_edges,
            edges=edges,
            boundary_edges=boundary_edges,
            boundary_tags=boundary_tags,
        )


def _coerce_mesh_data(mesh_or_data) -> MeshData:
    if isinstance(mesh_or_data, MeshData):
        return mesh_or_data

    if isinstance(mesh_or_data, Mesh):
        if mesh_or_data.data is None:
            raise ValueError('Mesh model does not carry mesh data yet.')
        return mesh_or_data.data

    raise TypeError('Expected a Mesh model or MeshData instance.')


def _coerce_boundary_definitions(mesh_or_data, boundary_definitions=None):
    if isinstance(boundary_definitions, BoundaryDefinitions):
        return boundary_definitions

    if boundary_definitions is not None:
        return BoundaryDefinitions.from_mapping(boundary_definitions)

    boundary_mapping = getattr(mesh_or_data, 'boundary_conditions', None)
    return BoundaryDefinitions.from_mapping(boundary_mapping)


class MeshImporter(ABC):
    """Base class for 2D mesh importers.

    The current import/export layer only operates on 2D mesh data.
    FIRE/FLMA is a special case on disk because it stores the 2D mesh as a
    single-cell extrusion in the third dimension.
    """

    format_name = 'mesh'

    @abstractmethod
    def read(self, filename: str, **kwargs) -> MeshData:
        """Read mesh data from disk."""


class PlannedMeshImporter(MeshImporter):
    """Placeholder importer used to mark future mesh-import entry points."""

    detail = 'Only 2D mesh import/export is in scope at the moment.'

    def read(self, filename: str, **kwargs) -> MeshData:
        format_label = self.format_name.upper()
        basename = os.path.basename(filename)
        raise NotImplementedError(
            f'{format_label} mesh import is reserved for future work '
            f'({basename}). {self.detail}'
        )


class FlmaImporter(PlannedMeshImporter):
    format_name = 'flma'
    detail = (
        'Only 2D mesh import/export is in scope at the moment. '
        'FIRE/FLMA currently represents the 2D mesh as a one-cell extrusion '
        'in the third dimension.'
    )


class Su2Importer(PlannedMeshImporter):
    format_name = 'su2'


class GmshImporter(PlannedMeshImporter):
    format_name = 'msh'


class AbaqusInpImporter(PlannedMeshImporter):
    format_name = 'inp'


class CgnsImporter(PlannedMeshImporter):
    format_name = 'cgns'


class VtuImporter(PlannedMeshImporter):
    format_name = 'vtu'


class VtkImporter(PlannedMeshImporter):
    format_name = 'vtk'


class MeshExporter(ABC):
    format_name = 'mesh'

    @abstractmethod
    def write(self, mesh_or_data, name: str,
              boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
              **kwargs):
        """Write mesh data to disk."""


class FlmaExporter(MeshExporter):
    format_name = 'flma'

    def write(self, mesh_or_data, name: str,
              boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
              **kwargs):
        mesh_data = _coerce_mesh_data(mesh_or_data)
        vertices = mesh_data.vertices.tolist()
        connectivity = mesh_data.connectivity.tolist()
        depth = float(kwargs.get('depth', 0.3))

        with open(name, 'w') as handle:
            number_of_vertices_2d = len(vertices)
            handle.write(str(2 * number_of_vertices_2d) + '\n')

            # FIRE expects a thin 3D volume. For now the 2D mesh is exported
            # as a single-cell extrusion in the third dimension.
            signum = -1.0
            for _ in range(2):
                for vertex in vertices:
                    handle.write(
                        f'{vertex[0]} {vertex[1]} {signum * depth / 2.0} '
                    )
                signum = 1.0

            cells = len(connectivity)
            handle.write('\n' + str(cells) + '\n')

            for cell in connectivity:
                cell_connect = (
                    f'{cell[0]} {cell[1]} {cell[2]} {cell[3]} '
                    f'{cell[0] + number_of_vertices_2d} '
                    f'{cell[1] + number_of_vertices_2d} '
                    f'{cell[2] + number_of_vertices_2d} '
                    f'{cell[3] + number_of_vertices_2d}\n'
                )
                handle.write('8\n')
                handle.write(cell_connect)

            handle.write('\n' + str(cells) + '\n')
            handle.write(' '.join(['5'] * cells))
            handle.write('\n\n')

            handle.write('6\n')
            handle.write('symmetry\n')
            handle.write('3\n')
            handle.write(str(4 * len(connectivity)) + '\n')
            for index in range(len(connectivity)):
                handle.write(f' {index} 0')
            for index in range(len(connectivity)):
                handle.write(f' {index} 1')
            handle.write('\n\n')

            for selection in ('bottom', 'top', 'back', 'front'):
                handle.write(selection + '\n')
                handle.write('3\n')
                handle.write('2\n')
                direction = {'bottom': 2, 'top': 3, 'back': 4, 'front': 5}[selection]
                handle.write(f'0 {direction}\n')
                handle.write('\n')

        logger.info('FIRE type mesh saved as %s', os.path.basename(name))


class Su2Exporter(MeshExporter):
    format_name = 'su2'

    def write(self, mesh_or_data, name: str,
              boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
              **kwargs):
        mesh_data = _coerce_mesh_data(mesh_or_data)
        definitions = _coerce_boundary_definitions(
            mesh_or_data, boundary_definitions
        )
        vertices = mesh_data.vertices.tolist()
        connectivity = mesh_data.connectivity.tolist()
        tags = mesh_data.boundary_tags

        with open(name, 'w') as handle:
            handle.write('%\n% Problem dimension\n%\nNDIME= 2\n')
            handle.write('%\n% Node coordinates\n%\n')
            handle.write(f'NPOIN= {len(vertices)}\n')
            for index, vertex in enumerate(vertices):
                handle.write(f'{vertex[0]: .8e} {vertex[1]: .8e} {index}\n')

            handle.write('%\n% Element connectivity\n%\n')
            handle.write(f'NELEM= {len(connectivity)}\n')
            for index, cell in enumerate(connectivity):
                handle.write(
                    f'9 {cell[0]:10d} {cell[1]:10d} {cell[2]:10d} '
                    f'{cell[3]:10d} {index:>10d}\n'
                )

            handle.write('%\n% Boundary tags\n%\n')
            active_boundaries = [
                (tag, label) for tag, label in definitions.items()
                if tag in tags
            ]
            handle.write(f'NMARK= {len(active_boundaries)}\n')
            for tag, label in active_boundaries:
                handle.write(f'MARKER_TAG= {label}\n')
                handle.write(f'MARKER_ELEMS= {len(tags[tag])}\n')
                for edge in tags[tag]:
                    handle.write(f'3 {edge[0]} {edge[1]}\n')

        logger.info('SU2 type mesh saved as %s', os.path.basename(name))


class VtuExporter(MeshExporter):
    format_name = 'vtu'

    def write(self, mesh_or_data, name: str,
              boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
              **kwargs):
        mesh_data = _coerce_mesh_data(mesh_or_data)
        definitions = _coerce_boundary_definitions(
            mesh_or_data, boundary_definitions
        )

        vertices = [tuple(vertex) + (0.0,) for vertex in mesh_data.vertices.tolist()]
        connectivity = [np.array(cell, dtype=int)
                        for cell in mesh_data.connectivity.tolist()]
        tags = mesh_data.boundary_tags

        def cell_type_from_length(length):
            if length == 2:
                return 3
            if length == 3:
                return 5
            if length == 4:
                return 9
            raise ValueError(f'No VTK cell type defined for {length}-node cells.')

        polygon_lengths = [len(cell) for cell in connectivity]
        polygon_connectivity = (
            np.concatenate([cell for cell in connectivity])
            if connectivity else np.array([], dtype=int)
        )
        polygon_types = np.array(
            [cell_type_from_length(length) for length in polygon_lengths],
            dtype=np.uint8,
        )
        polygon_boundary_ids = np.zeros(len(connectivity), dtype=np.int32)

        boundary_names = [
            label for tag, label in definitions.items() if tag in tags
        ]
        boundary_id_map = {name: index + 1 for index, name in enumerate(boundary_names)}
        boundary_edges = []
        boundary_lengths = []
        boundary_types = []
        boundary_ids = []

        for tag, label in definitions.items():
            for edge in tags.get(tag, []):
                boundary_edges.append(np.array(edge, dtype=int))
                boundary_lengths.append(2)
                boundary_types.append(cell_type_from_length(2))
                boundary_ids.append(boundary_id_map[label])

        if boundary_edges:
            boundary_connectivity = np.concatenate(boundary_edges)
            boundary_cell_types = np.array(boundary_types, dtype=np.uint8)
            boundary_ids_array = np.array(boundary_ids, dtype=np.int32)
        else:
            boundary_connectivity = np.array([], dtype=int)
            boundary_cell_types = np.array([], dtype=np.uint8)
            boundary_ids_array = np.array([], dtype=np.int32)

        all_connectivity = np.concatenate(
            [polygon_connectivity, boundary_connectivity]
        )
        all_cell_types = np.concatenate([polygon_types, boundary_cell_types])
        all_boundary_ids = np.concatenate(
            [polygon_boundary_ids, boundary_ids_array]
        )
        all_lengths = polygon_lengths + boundary_lengths
        offsets = np.cumsum(all_lengths)

        with open(name, 'w') as handle:
            handle.write('<?xml version="1.0"?>\n')
            handle.write(
                '<VTKFile type="UnstructuredGrid" version="0.1" '
                'byte_order="LittleEndian">\n'
            )
            handle.write('  <UnstructuredGrid>\n')
            handle.write(
                f'    <Piece NumberOfPoints="{len(vertices)}" '
                f'NumberOfCells="{len(all_lengths)}">\n'
            )
            handle.write('      <CellData Scalars="BoundaryID">\n')
            handle.write(
                '        <DataArray type="Int32" Name="BoundaryID" format="ascii">\n'
            )
            handle.write('          ' + ' '.join(map(str, all_boundary_ids)) + '\n')
            handle.write('        </DataArray>\n')
            handle.write('      </CellData>\n')
            handle.write('      <Points>\n')
            handle.write(
                '        <DataArray type="Float32" NumberOfComponents="3" format="ascii">\n'
            )
            for point in vertices:
                handle.write(f'          {point[0]} {point[1]} {point[2]}\n')
            handle.write('        </DataArray>\n')
            handle.write('      </Points>\n')
            handle.write('      <Cells>\n')
            handle.write(
                '        <DataArray type="Int32" Name="connectivity" format="ascii">\n'
            )
            handle.write('          ' + ' '.join(map(str, all_connectivity)) + '\n')
            handle.write('        </DataArray>\n')
            handle.write(
                '        <DataArray type="Int32" Name="offsets" format="ascii">\n'
            )
            handle.write('          ' + ' '.join(map(str, offsets)) + '\n')
            handle.write('        </DataArray>\n')
            handle.write(
                '        <DataArray type="UInt8" Name="types" format="ascii">\n'
            )
            handle.write('          ' + ' '.join(map(str, all_cell_types)) + '\n')
            handle.write('        </DataArray>\n')
            handle.write('      </Cells>\n')
            handle.write('    </Piece>\n')
            handle.write('  </UnstructuredGrid>\n')
            handle.write('</VTKFile>\n')

        logger.info('VTK type mesh saved as %s', os.path.basename(name))


class GmshExporter(MeshExporter):
    format_name = 'gmsh'

    def write(self, mesh_or_data, name: str,
              boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
              **kwargs):
        mesh_data = _coerce_mesh_data(mesh_or_data)
        definitions = _coerce_boundary_definitions(
            mesh_or_data, boundary_definitions
        )
        vertices = mesh_data.vertices.tolist()
        connectivity = mesh_data.connectivity.tolist()
        boundaries = mesh_data.boundary_tags

        active_boundaries = [
            (tag, label) for tag, label in definitions.items()
            if tag in boundaries
        ]
        boundary_tags = {
            tag: index + 1 for index, (tag, _label) in enumerate(active_boundaries)
        }
        domain_physical_tag = len(active_boundaries) + 1

        with open(name, 'w') as handle:
            handle.write('$MeshFormat\n2.2 0 8\n$EndMeshFormat\n')
            handle.write('$PhysicalNames\n')
            handle.write(f'{len(active_boundaries) + 1}\n')
            for tag, label in active_boundaries:
                handle.write(f'1 {boundary_tags[tag]} "{label}"\n')
            handle.write(f'2 {domain_physical_tag} "Domain"\n')
            handle.write('$EndPhysicalNames\n')

            handle.write('$Nodes\n')
            handle.write(f'{len(vertices)}\n')
            for index, (x, y) in enumerate(vertices, start=1):
                handle.write(f'{index} {x: .8e} {y: .8e} 0.00000000e+00\n')
            handle.write('$EndNodes\n')

            elements = []
            element_id = 1
            for tag, _label in active_boundaries:
                physical_tag = boundary_tags[tag]
                for edge in boundaries[tag]:
                    elements.append(
                        (
                            element_id,
                            1,
                            2,
                            physical_tag,
                            physical_tag,
                            [edge[0] + 1, edge[1] + 1],
                        )
                    )
                    element_id += 1

            for cell in connectivity:
                node_count = len(cell)
                element_type = {3: 2, 4: 3, 6: 9, 8: 16}.get(node_count)
                if element_type is None:
                    raise ValueError(
                        f'Unsupported element with {node_count} nodes.'
                    )
                elements.append(
                    (
                        element_id,
                        element_type,
                        2,
                        domain_physical_tag,
                        domain_physical_tag,
                        [node + 1 for node in cell],
                    )
                )
                element_id += 1

            handle.write('$Elements\n')
            handle.write(f'{len(elements)}\n')
            for elem_id, elem_type, num_tags, physical_tag, geometrical_tag, node_ids in elements:
                node_ids_str = ' '.join(map(str, node_ids))
                handle.write(
                    f'{elem_id} {elem_type} {num_tags} {physical_tag} '
                    f'{geometrical_tag} {node_ids_str}\n'
                )
            handle.write('$EndElements\n')

        logger.info('GMSH type mesh saved as %s', os.path.basename(name))


class MeshImportRegistry:
    _registry = {
        'flma': FlmaImporter(),
        'su2': Su2Importer(),
        'msh': GmshImporter(),
        'gmsh': GmshImporter(),
        'inp': AbaqusInpImporter(),
        'cgns': CgnsImporter(),
        'vtu': VtuImporter(),
        'vtk': VtkImporter(),
    }

    @classmethod
    def _normalize_format(cls, mesh_format: str) -> str:
        return mesh_format.strip().lower().lstrip('.')

    @classmethod
    def format_from_filename(cls, filename: str) -> str:
        _, extension = os.path.splitext(filename)
        if not extension:
            raise ValueError(
                f'Unable to determine mesh format from filename: {filename}'
            )
        return cls._normalize_format(extension)

    @classmethod
    def can_import(cls, filename: str) -> bool:
        try:
            mesh_format = cls.format_from_filename(filename)
        except ValueError:
            return False
        return mesh_format in cls._registry

    @classmethod
    def supported_extensions(cls) -> tuple[str, ...]:
        extensions = [
            'flma',
            'su2',
            'msh',
            'inp',
            'cgns',
            'vtu',
            'vtk',
        ]
        return tuple(extension for extension in extensions if extension in cls._registry)

    @classmethod
    def qt_file_dialog_filter(cls) -> str:
        patterns = ' '.join(
            f'*.{extension}' for extension in cls.supported_extensions()
        )
        return f'Mesh files ({patterns})'

    @classmethod
    def import_file(cls, filename: str, mesh_format: str | None = None,
                    **kwargs) -> MeshData:
        key = cls._normalize_format(mesh_format) if mesh_format else (
            cls.format_from_filename(filename)
        )
        try:
            importer = cls._registry[key]
        except KeyError as error:
            raise ValueError(f'Unknown mesh import format: {key}') from error
        return importer.read(filename, **kwargs)


class MeshExportRegistry:
    _registry = {
        'flma': FlmaExporter(),
        'su2': Su2Exporter(),
        'vtk': VtuExporter(),
        'vtu': VtuExporter(),
        'gmsh': GmshExporter(),
        'msh': GmshExporter(),
    }

    @classmethod
    def export(cls, mesh_or_data, mesh_format: str, name: str,
               boundary_definitions: BoundaryDefinitions | Mapping[str, str] | None = None,
               **kwargs):
        key = mesh_format.strip().lower()
        try:
            exporter = cls._registry[key]
        except KeyError as error:
            raise ValueError(f'Unknown mesh export format: {mesh_format}') from error
        exporter.write(
            mesh_or_data,
            name=name,
            boundary_definitions=boundary_definitions,
            **kwargs,
        )


class MeshFactory:
    """Factory class to create mesh model objects."""

    _registry = {
        'block': BlockMesh,
        'block_structured': BlockStructuredMesh,
        'triangular': TriangularMesh,
        'unstructured': UnstructuredMesh,
    }

    @classmethod
    def create_mesh(cls, mesh_type: str, **kwargs):
        key = mesh_type.strip().lower()
        try:
            mesh_class = cls._registry[key]
        except KeyError as error:
            raise ValueError(f'Unknown mesh type: {mesh_type}') from error
        return mesh_class(**kwargs)
