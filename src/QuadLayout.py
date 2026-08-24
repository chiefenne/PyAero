from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

from ExperimentalCGrid import ExperimentalCGridGenerator
from ExperimentalOGrid import ExperimentalOGridGenerator


MINIMUM_LOOP_POINTS = 13
MINIMUM_SPACING = 1.0e-9
SPLIT_LE_FRACTION = 0.10
SPLIT_TE_FRACTION = 0.90


def _as_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(points, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError('Layout points must be an N x 2 array.')
    return array


def _as_loop_points(loop) -> np.ndarray:
    if isinstance(loop, np.ndarray):
        return _as_points(loop)

    if (
            isinstance(loop, (tuple, list)) and
            len(loop) == 2 and
            np.asarray(loop[0]).ndim == 1 and
            np.asarray(loop[1]).ndim == 1):
        return _as_points(np.column_stack(loop))

    return _as_points(loop)


def _close_loop(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = _as_points(points)
    if len(array) == 0:
        return np.empty((0, 2), dtype=float)
    if np.allclose(array[0], array[-1], atol=1.0e-10):
        closed = np.array(array, copy=True, dtype=float)
        closed[-1] = closed[0]
        return closed
    return np.vstack((array, array[0]))


def _open_loop(points: Sequence[Sequence[float]]) -> np.ndarray:
    closed = _close_loop(points)
    if len(closed) <= 1:
        return np.empty((0, 2), dtype=float)
    return np.asarray(closed[:-1], dtype=float)


def _signed_area(points: Sequence[Sequence[float]]) -> float:
    closed = _close_loop(points)
    if len(closed) < 4:
        return 0.0
    x_values = closed[:, 0]
    y_values = closed[:, 1]
    return 0.5 * float(
        np.dot(x_values[:-1], y_values[1:]) -
        np.dot(y_values[:-1], x_values[1:])
    )


def _ensure_counter_clockwise(points: Sequence[Sequence[float]]) -> np.ndarray:
    closed = _close_loop(points)
    if _signed_area(closed) < 0.0:
        closed = closed[::-1]
        closed[-1] = closed[0]
    return closed


def _polyline_cumulative(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = _as_points(points)
    if len(array) == 0:
        return np.zeros(0, dtype=float)
    deltas = np.diff(array, axis=0)
    segment_lengths = np.linalg.norm(deltas, axis=1)
    return np.concatenate(([0.0], np.cumsum(segment_lengths)))


def _polyline_length(points: Sequence[Sequence[float]]) -> float:
    cumulative = _polyline_cumulative(points)
    return float(cumulative[-1]) if len(cumulative) else 0.0


def _sample_polyline_distances(points: Sequence[Sequence[float]],
                               distances) -> np.ndarray:
    array = _as_points(points)
    cumulative = _polyline_cumulative(array)
    if len(cumulative) == 0 or np.isclose(cumulative[-1], 0.0):
        if len(array) == 0:
            return np.empty((0, 2), dtype=float)
        return np.repeat(array[:1], len(distances), axis=0)

    distances = np.asarray(distances, dtype=float)
    distances = np.clip(distances, 0.0, cumulative[-1])
    x_values = np.interp(distances, cumulative, array[:, 0])
    y_values = np.interp(distances, cumulative, array[:, 1])
    return np.column_stack((x_values, y_values))


def _resample_polyline_count(points: Sequence[Sequence[float]], count: int
                             ) -> np.ndarray:
    count = max(1, int(count))
    array = _as_points(points)
    cumulative = _polyline_cumulative(array)
    if len(cumulative) == 0 or np.isclose(cumulative[-1], 0.0):
        if len(array) == 0:
            return np.zeros((count, 2), dtype=float)
        return np.repeat(array[:1], count, axis=0)
    targets = np.linspace(0.0, cumulative[-1], count)
    return _sample_polyline_distances(array, targets)


def _sample_segment_count(start: Sequence[float], end: Sequence[float], count: int
                          ) -> np.ndarray:
    start = np.asarray(start, dtype=float)
    end = np.asarray(end, dtype=float)
    count = max(1, int(count))
    if count == 1:
        return start[np.newaxis, :]
    distances = np.linspace(0.0, 1.0, count)
    return start[np.newaxis, :] + distances[:, None] * (end - start)[None, :]


def _sample_quadratic_bezier(start: Sequence[float], control: Sequence[float],
                             end: Sequence[float], count: int) -> np.ndarray:
    start = np.asarray(start, dtype=float)
    control = np.asarray(control, dtype=float)
    end = np.asarray(end, dtype=float)
    count = max(2, int(count))
    parameters = np.linspace(0.0, 1.0, count)
    one_minus = 1.0 - parameters
    return (
        (one_minus ** 2)[:, None] * start[None, :] +
        (2.0 * one_minus * parameters)[:, None] * control[None, :] +
        (parameters ** 2)[:, None] * end[None, :]
    )


def _compose_segments(*segments: Iterable[Sequence[float]]) -> np.ndarray:
    combined = []
    for segment in segments:
        points = _as_points(segment)
        if len(points) == 0:
            continue
        if not combined:
            combined.append(points)
            continue
        if np.allclose(combined[-1][-1], points[0], atol=1.0e-10):
            combined.append(points[1:])
        else:
            combined.append(points)

    if not combined:
        return np.empty((0, 2), dtype=float)
    return np.vstack(combined)


def _point_count_from_length(length: float, target_spacing: float, *,
                             minimum: int = 2, maximum: int | None = None) -> int:
    spacing = max(float(target_spacing), MINIMUM_SPACING)
    count = max(int(minimum), int(np.ceil(max(0.0, float(length)) / spacing)) + 1)
    if maximum is not None:
        count = min(count, int(maximum))
    return count


def _leading_edge_index(points: np.ndarray) -> int:
    return int(np.argmin(points[:, 0]))


def _te_upper_index(points: np.ndarray) -> int:
    x_values = points[:, 0]
    xmax = float(np.max(x_values))
    candidates = np.flatnonzero(np.abs(x_values - xmax) <= 1.0e-8)
    if not candidates.size:
        return int(np.argmax(x_values))
    y_values = points[candidates, 1]
    return int(candidates[int(np.argmax(y_values))])


def _rotate_open_loop(points: Sequence[Sequence[float]]) -> np.ndarray:
    open_points = _open_loop(points)
    if len(open_points) < 3:
        raise ValueError('An element loop requires at least three unique points.')
    start_index = _te_upper_index(open_points)
    return np.vstack((open_points[start_index:], open_points[:start_index]))


def _centered_normals(points: Sequence[Sequence[float]]) -> np.ndarray:
    open_points = _open_loop(points)
    if len(open_points) < 3:
        raise ValueError('Loop normals require at least three unique points.')

    previous_points = np.roll(open_points, 1, axis=0)
    next_points = np.roll(open_points, -1, axis=0)
    tangents = next_points - previous_points
    lengths = np.linalg.norm(tangents, axis=1)
    lengths = np.maximum(lengths, MINIMUM_SPACING)
    unit_tangents = tangents / lengths[:, None]
    normals = np.column_stack((unit_tangents[:, 1], -unit_tangents[:, 0]))
    return normals


def _offset_loop(points: Sequence[Sequence[float]], distance: float) -> np.ndarray:
    if distance <= 0.0:
        return _close_loop(points)
    open_points = _open_loop(points)
    normals = _centered_normals(points)
    offset = open_points + float(distance) * normals
    return _close_loop(offset)


def _layer_offsets(first_layer: float, growth: float, divisions: int) -> np.ndarray:
    divisions = max(1, int(divisions))
    thickness = max(float(first_layer), MINIMUM_SPACING)
    growth = max(float(growth), 1.0)

    offsets = np.zeros(divisions + 1, dtype=float)
    spacing = thickness
    for index in range(1, divisions + 1):
        offsets[index] = offsets[index - 1] + spacing
        spacing *= growth
    return offsets


def _minimum_loop_gap(boundary_loops: Sequence[np.ndarray]) -> float:
    if len(boundary_loops) < 2:
        return float('inf')

    sampled_loops = [
        _resample_polyline_count(_close_loop(loop), min(200, max(40, len(loop))))[:-1]
        for loop in boundary_loops
    ]

    minimum_gap = float('inf')
    for index, left in enumerate(sampled_loops[:-1]):
        for right in sampled_loops[index + 1:]:
            deltas = left[:, None, :] - right[None, :, :]
            distances = np.linalg.norm(deltas, axis=2)
            minimum_gap = min(minimum_gap, float(np.min(distances)))
    return minimum_gap


def _sort_loops_by_streamwise_position(boundary_loops: Sequence[np.ndarray]
                                       ) -> list[np.ndarray]:
    return sorted(
        [_close_loop(loop) for loop in boundary_loops],
        key=lambda loop: (
            float(np.mean(loop[:-1, 0])),
            float(np.mean(loop[:-1, 1])),
        ),
    )


def _prepare_boundary_loop(loop, *, surface_points: int | None, minimum_points: int,
                           trailing_edge_divisions: int) -> np.ndarray:
    points = _as_loop_points(loop)
    if len(points) < 3:
        raise ValueError('Each boundary loop requires at least three points.')

    if np.allclose(points[0], points[-1], atol=1.0e-10):
        closed = np.array(points, copy=True, dtype=float)
        closed[-1] = closed[0]
    else:
        closure = _sample_segment_count(
            points[-1],
            points[0],
            max(2, int(trailing_edge_divisions) + 1),
        )
        closed = _compose_segments(points, closure)

    target_points = len(closed)
    if surface_points is not None and int(surface_points) > 0:
        target_points = int(surface_points)
    target_points = max(int(minimum_points), target_points)
    if target_points != len(closed):
        closed = _resample_polyline_count(closed, target_points)
        closed[-1] = closed[0]

    if len(closed) < minimum_points:
        closed = _resample_polyline_count(closed, minimum_points)
        closed[-1] = closed[0]

    return _ensure_counter_clockwise(closed)


def _first_index_leq(values: np.ndarray, target: float) -> int:
    matches = np.flatnonzero(values <= target)
    if matches.size:
        return int(matches[0])
    return len(values) - 1


def _first_index_geq(values: np.ndarray, target: float) -> int:
    matches = np.flatnonzero(values >= target)
    if matches.size:
        return int(matches[0])
    return len(values) - 1


def _segment_split_indices(open_loop: np.ndarray) -> dict[str, int]:
    leading_index = _leading_edge_index(open_loop)
    upper = open_loop[:leading_index + 1]
    lower = open_loop[leading_index:]

    if len(upper) < 2 or len(lower) < 2:
        raise ValueError('Element loop could not be split into upper and lower surfaces.')

    x_min = float(np.min(open_loop[:, 0]))
    x_max = float(np.max(open_loop[:, 0]))
    chord = max(x_max - x_min, MINIMUM_SPACING)
    x_le_limit = x_min + SPLIT_LE_FRACTION * chord
    x_te_limit = x_min + SPLIT_TE_FRACTION * chord

    upper_te = _first_index_leq(upper[:, 0], x_te_limit)
    upper_le = _first_index_leq(upper[:, 0], x_le_limit)
    if upper_le <= upper_te:
        upper_te = max(0, min(upper_te, len(upper) - 3))
        upper_le = min(len(upper) - 2, upper_te + 1)

    lower_le = _first_index_geq(lower[:, 0], x_le_limit)
    lower_te = _first_index_geq(lower[:, 0], x_te_limit)
    if lower_te <= lower_le:
        lower_le = max(0, min(lower_le, len(lower) - 3))
        lower_te = min(len(lower) - 2, lower_le + 1)

    return {
        'leading_index': leading_index,
        'upper_te': upper_te,
        'upper_le': upper_le,
        'lower_le': lower_le,
        'lower_te': lower_te,
    }


def _segment_split_indices_for_stations(open_loop: np.ndarray, *,
                                        leading_station: float,
                                        trailing_station: float
                                        ) -> dict[str, int]:
    leading_station = float(np.clip(leading_station, 0.01, 0.45))
    trailing_station = float(
        np.clip(trailing_station, leading_station + 0.05, 0.99)
    )

    leading_index = _leading_edge_index(open_loop)
    upper = open_loop[:leading_index + 1]
    lower = open_loop[leading_index:]

    if len(upper) < 2 or len(lower) < 2:
        raise ValueError('Element loop could not be split into upper and lower surfaces.')

    x_min = float(np.min(open_loop[:, 0]))
    x_max = float(np.max(open_loop[:, 0]))
    chord = max(x_max - x_min, MINIMUM_SPACING)
    x_le_limit = x_min + leading_station * chord
    x_te_limit = x_min + trailing_station * chord

    upper_te = _first_index_leq(upper[:, 0], x_te_limit)
    upper_le = _first_index_leq(upper[:, 0], x_le_limit)
    if upper_le <= upper_te:
        upper_te = max(0, min(upper_te, len(upper) - 3))
        upper_le = min(len(upper) - 2, upper_te + 1)

    lower_le = _first_index_geq(lower[:, 0], x_le_limit)
    lower_te = _first_index_geq(lower[:, 0], x_te_limit)
    if lower_te <= lower_le:
        lower_le = max(0, min(lower_le, len(lower) - 3))
        lower_te = min(len(lower) - 2, lower_le + 1)

    return {
        'leading_index': leading_index,
        'upper_te': upper_te,
        'upper_le': upper_le,
        'lower_le': lower_le,
        'lower_te': lower_te,
    }


def _raw_segments_from_indices(open_loop: np.ndarray, indices: dict[str, int], *,
                               trailing_edge_divisions: int) -> dict[str, np.ndarray]:
    leading_index = indices['leading_index']
    upper = open_loop[:leading_index + 1]
    lower = open_loop[leading_index:]

    closure = _sample_segment_count(
        lower[-1],
        upper[0],
        max(2, int(trailing_edge_divisions) + 1),
    )

    top = upper[indices['upper_te']:indices['upper_le'] + 1]
    left = _compose_segments(
        upper[indices['upper_le']:],
        lower[:indices['lower_le'] + 1],
    )
    bottom = lower[indices['lower_le']:indices['lower_te'] + 1]
    right = _compose_segments(
        lower[indices['lower_te']:],
        closure,
        upper[:indices['upper_te'] + 1],
    )

    return {
        'top': top,
        'left': left,
        'bottom': bottom,
        'right': right,
    }


@dataclass(slots=True)
class QuadSingularity:
    position: np.ndarray | Sequence[float]
    charge: int = 0
    kind: str = 'regular'
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        position = np.asarray(self.position, dtype=float)
        if position.shape != (2,):
            raise ValueError('Singularity position must be a 2D point.')
        self.position = position
        self.charge = int(self.charge)
        self.kind = str(self.kind).strip() or 'regular'


@dataclass(slots=True)
class QuadBlockSpec:
    name: str
    lower_boundary: np.ndarray | Sequence[Sequence[float]]
    upper_boundary: np.ndarray | Sequence[Sequence[float]]
    left_boundary: np.ndarray | Sequence[Sequence[float]]
    right_boundary: np.ndarray | Sequence[Sequence[float]]
    role: str = 'connector'
    element_index: int | None = None
    protected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.lower_boundary = _as_points(self.lower_boundary)
        self.upper_boundary = _as_points(self.upper_boundary)
        self.left_boundary = _as_points(self.left_boundary)
        self.right_boundary = _as_points(self.right_boundary)
        self.name = str(self.name).strip() or 'block'
        self.role = str(self.role).strip() or 'connector'
        self.protected = bool(self.protected)


@dataclass(slots=True)
class QuadLayoutPlan:
    boundary_points: np.ndarray | Sequence[Sequence[float]]
    boundary_loops: list[np.ndarray | Sequence[Sequence[float]]] = field(default_factory=list)
    near_wall_loops: list[np.ndarray | Sequence[Sequence[float]]] = field(default_factory=list)
    outer_boundary: np.ndarray | Sequence[Sequence[float]] | None = None
    block_specs: list[QuadBlockSpec] = field(default_factory=list)
    singularities: list[QuadSingularity] = field(default_factory=list)
    separatrices: list[np.ndarray] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.boundary_points = _as_points(self.boundary_points)
        self.boundary_loops = [
            _close_loop(loop) for loop in (self.boundary_loops or [self.boundary_points])
        ]
        self.near_wall_loops = [_close_loop(loop) for loop in self.near_wall_loops]
        self.outer_boundary = (
            _close_loop(self.outer_boundary)
            if self.outer_boundary is not None and len(np.asarray(self.outer_boundary)) != 0
            else _close_loop(self.boundary_points)
        )
        self.block_specs = [
            spec if isinstance(spec, QuadBlockSpec) else QuadBlockSpec(**dict(spec))
            for spec in self.block_specs
        ]
        self.separatrices = [_as_points(separatrix) for separatrix in self.separatrices]


class QuadLayoutGenerator:
    """Stage 4 layout scaffold for multi-element structured quad meshes."""

    name = 'multi_element_oc'

    @staticmethod
    def create_plan(boundary_points: Sequence[Sequence[float]], *,
                    boundary_loops=None, near_wall_loops=None,
                    outer_boundary=None, block_specs=None,
                    singularities=None, separatrices=None, metadata=None):
        return QuadLayoutPlan(
            boundary_points=boundary_points,
            boundary_loops=list(boundary_loops or [boundary_points]),
            near_wall_loops=list(near_wall_loops or []),
            outer_boundary=outer_boundary if outer_boundary is not None else boundary_points,
            block_specs=list(block_specs or []),
            singularities=list(singularities or []),
            separatrices=list(separatrices or []),
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _loop_surface_point_targets(loop_inputs, surface_points):
        if surface_points is None:
            return [None] * len(loop_inputs)

        if isinstance(surface_points, Sequence) and not isinstance(surface_points, (str, bytes)):
            values = list(surface_points)
            if len(values) != len(loop_inputs):
                raise ValueError(
                    'Per-loop surface point targets must match the number of boundary loops.'
                )
            return [
                None if value is None else int(value)
                for value in values
            ]

        target = int(surface_points)
        if target <= 0:
            return [None] * len(loop_inputs)
        return [target] * len(loop_inputs)

    @classmethod
    def _boundary_loops_from_input(cls, boundary_points=None, *, boundary_loops=None,
                                   metadata=None, surface_points: int | Sequence[int] | None,
                                   trailing_edge_divisions: int) -> list[np.ndarray]:
        metadata = dict(metadata or {})
        loop_inputs = boundary_loops
        if loop_inputs is None:
            loop_inputs = (
                metadata.get('hybrid_boundary_loops') or
                metadata.get('boundary_loops') or
                metadata.get('element_loops')
            )
        if loop_inputs is None:
            if boundary_points is None:
                raise ValueError('A hybrid layout requires at least one boundary loop.')
            loop_inputs = [boundary_points]

        surface_targets = cls._loop_surface_point_targets(
            loop_inputs,
            surface_points,
        )
        prepared = [
            _prepare_boundary_loop(
                loop,
                surface_points=target_points,
                minimum_points=MINIMUM_LOOP_POINTS,
                trailing_edge_divisions=trailing_edge_divisions,
            )
            for loop, target_points in zip(loop_inputs, surface_targets)
        ]
        return _sort_loops_by_streamwise_position(prepared)

    @classmethod
    def generate(cls, boundary_points=None, *, boundary_loops=None,
                 metadata=None, tunnel_height: float,
                 wake_length: float, surface_points: int | Sequence[int] | None = 0,
                 normal_divisions: int = 20,
                 first_layer_thickness: float = 0.004,
                 layer_growth: float = 1.05,
                 connector_layers: int = 80,
                 trailing_edge_divisions: int = 3):
        boundary_loops = cls._boundary_loops_from_input(
            boundary_points,
            boundary_loops=boundary_loops,
            metadata=metadata,
            surface_points=surface_points,
            trailing_edge_divisions=trailing_edge_divisions,
        )

        layer_offsets = _layer_offsets(
            first_layer=first_layer_thickness,
            growth=layer_growth,
            divisions=normal_divisions,
        )
        nominal_ring_thickness = float(layer_offsets[-1])
        minimum_gap = _minimum_loop_gap(boundary_loops)
        clearance_limit = float('inf')
        if np.isfinite(minimum_gap):
            clearance_limit = 0.35 * minimum_gap

        ring_thickness = min(
            nominal_ring_thickness,
            clearance_limit if np.isfinite(clearance_limit) else nominal_ring_thickness,
            0.45 * max(float(tunnel_height), MINIMUM_SPACING),
        )
        ring_thickness = max(float(first_layer_thickness), ring_thickness)

        all_points = np.vstack([loop[:-1] for loop in boundary_loops])
        x_min = float(np.min(all_points[:, 0]))
        x_max = float(np.max(all_points[:, 0]))
        y_min = float(np.min(all_points[:, 1]))
        y_max = float(np.max(all_points[:, 1]))
        y_center = 0.5 * (y_min + y_max)

        farfield_left = x_min - float(tunnel_height)
        farfield_right = x_max + float(wake_length)
        farfield_top = y_center + float(tunnel_height)
        farfield_bottom = y_center - float(tunnel_height)
        outer_boundary = np.array(
            [
                (farfield_left, farfield_bottom),
                (farfield_right, farfield_bottom),
                (farfield_right, farfield_top),
                (farfield_left, farfield_top),
                (farfield_left, farfield_bottom),
            ],
            dtype=float,
        )

        perimeter_spacings = []
        for loop in boundary_loops:
            open_loop = _rotate_open_loop(loop)
            perimeter_spacings.append(
                _polyline_length(_close_loop(open_loop)) / max(1, len(open_loop))
            )
        target_spacing = max(float(np.mean(perimeter_spacings)), MINIMUM_SPACING)

        connector_layers = max(4, int(connector_layers))
        connector_point_count = connector_layers + 1

        raw_elements = []
        side_lengths = []
        for element_index, loop in enumerate(boundary_loops):
            inner_open = _rotate_open_loop(loop)
            outer_open = _rotate_open_loop(_offset_loop(loop, ring_thickness))
            indices = _segment_split_indices(inner_open)
            inner_raw = _raw_segments_from_indices(
                inner_open,
                indices,
                trailing_edge_divisions=trailing_edge_divisions,
            )
            outer_raw = _raw_segments_from_indices(
                outer_open,
                indices,
                trailing_edge_divisions=trailing_edge_divisions,
            )
            side_lengths.extend((
                _polyline_length(inner_raw['left']),
                _polyline_length(inner_raw['right']),
            ))
            raw_elements.append({
                'index': element_index,
                'inner_loop': _close_loop(inner_open),
                'outer_loop': _close_loop(outer_open),
                'inner_raw': inner_raw,
                'outer_raw': outer_raw,
            })

        average_side_length = float(np.mean(side_lengths)) if side_lengths else target_spacing
        side_point_count = _point_count_from_length(
            average_side_length,
            target_spacing,
            minimum=6,
            maximum=160,
        )

        block_specs = []
        top_chain_segments = []
        bottom_chain_segments = []
        element_segments = []

        for element in raw_elements:
            inner_raw = element['inner_raw']
            outer_raw = element['outer_raw']
            element_index = element['index']

            top_count = _point_count_from_length(
                _polyline_length(inner_raw['top']),
                target_spacing,
                minimum=3,
                maximum=240,
            )
            bottom_count = _point_count_from_length(
                _polyline_length(inner_raw['bottom']),
                target_spacing,
                minimum=3,
                maximum=240,
            )

            segments = {
                'top': _resample_polyline_count(inner_raw['top'], top_count),
                'left': _resample_polyline_count(inner_raw['left'], side_point_count),
                'bottom': _resample_polyline_count(inner_raw['bottom'], bottom_count),
                'right': _resample_polyline_count(inner_raw['right'], side_point_count),
            }
            outer_segments = {
                'top': _resample_polyline_count(outer_raw['top'], top_count),
                'left': _resample_polyline_count(outer_raw['left'], side_point_count),
                'bottom': _resample_polyline_count(outer_raw['bottom'], bottom_count),
                'right': _resample_polyline_count(outer_raw['right'], side_point_count),
            }

            element_segments.append({
                'inner': segments,
                'outer': outer_segments,
                'inner_loop': element['inner_loop'],
                'outer_loop': element['outer_loop'],
            })

            for side in ('top', 'left', 'bottom', 'right'):
                block_specs.append(
                    QuadBlockSpec(
                        name=f'block_hybrid_element_{element_index}_{side}',
                        lower_boundary=segments[side],
                        upper_boundary=outer_segments[side],
                        left_boundary=_sample_segment_count(
                            segments[side][0],
                            outer_segments[side][0],
                            connector_point_count,
                        ),
                        right_boundary=_sample_segment_count(
                            segments[side][-1],
                            outer_segments[side][-1],
                            connector_point_count,
                        ),
                        role='element_ring',
                        element_index=element_index,
                        protected=True,
                        metadata={'side': side},
                    )
                )

            top_chain_segments.append(outer_segments['top'][::-1])
            bottom_chain_segments.append(outer_segments['bottom'])

        bridge_specs = []
        bridge_top_segments = []
        bridge_bottom_segments = []
        for element_index in range(len(element_segments) - 1):
            left_element = element_segments[element_index]
            right_element = element_segments[element_index + 1]

            left_boundary = left_element['outer']['right']
            right_boundary = right_element['outer']['left'][::-1]

            bridge_point_count = max(
                _point_count_from_length(
                    np.linalg.norm(right_boundary[0] - left_boundary[0]),
                    target_spacing,
                    minimum=2,
                    maximum=200,
                ),
                _point_count_from_length(
                    np.linalg.norm(right_boundary[-1] - left_boundary[-1]),
                    target_spacing,
                    minimum=2,
                    maximum=200,
                ),
            )
            bottom_bridge = _sample_segment_count(
                left_boundary[0],
                right_boundary[0],
                bridge_point_count,
            )
            top_bridge = _sample_segment_count(
                left_boundary[-1],
                right_boundary[-1],
                bridge_point_count,
            )

            bridge_bottom_segments.append(bottom_bridge)
            bridge_top_segments.append(top_bridge)
            bridge_specs.append(
                QuadBlockSpec(
                    name=f'block_hybrid_bridge_{element_index}_{element_index + 1}',
                    lower_boundary=bottom_bridge,
                    upper_boundary=top_bridge,
                    left_boundary=left_boundary,
                    right_boundary=right_boundary,
                    role='bridge',
                    metadata={
                        'left_element': element_index,
                        'right_element': element_index + 1,
                    },
                )
            )

        composed_top = []
        composed_bottom = []
        for index, segment in enumerate(top_chain_segments):
            composed_top.append(segment)
            if index < len(bridge_top_segments):
                composed_top.append(bridge_top_segments[index])
        for index, segment in enumerate(bottom_chain_segments):
            composed_bottom.append(segment)
            if index < len(bridge_bottom_segments):
                composed_bottom.append(bridge_bottom_segments[index])

        top_chain = _compose_segments(*composed_top)
        bottom_chain = _compose_segments(*composed_bottom)

        first_element = element_segments[0]
        last_element = element_segments[-1]

        inlet_right = first_element['outer']['left'][::-1]
        outlet_left = last_element['outer']['right']

        inlet_point_count = max(
            _point_count_from_length(
                np.linalg.norm(inlet_right[0] - np.array((farfield_left, farfield_bottom))),
                target_spacing,
                minimum=2,
                maximum=200,
            ),
            _point_count_from_length(
                np.linalg.norm(inlet_right[-1] - np.array((farfield_left, farfield_top))),
                target_spacing,
                minimum=2,
                maximum=200,
            ),
        )
        inlet_lower = _sample_segment_count(
            np.array((farfield_left, farfield_bottom), dtype=float),
            inlet_right[0],
            inlet_point_count,
        )
        inlet_upper = _sample_segment_count(
            np.array((farfield_left, farfield_top), dtype=float),
            inlet_right[-1],
            inlet_point_count,
        )
        outlet_point_count = max(
            _point_count_from_length(
                np.linalg.norm(outlet_left[0] - np.array((farfield_right, farfield_bottom))),
                target_spacing,
                minimum=2,
                maximum=240,
            ),
            _point_count_from_length(
                np.linalg.norm(outlet_left[-1] - np.array((farfield_right, farfield_top))),
                target_spacing,
                minimum=2,
                maximum=240,
            ),
        )
        outlet_lower = _sample_segment_count(
            outlet_left[0],
            np.array((farfield_right, farfield_bottom), dtype=float),
            outlet_point_count,
        )
        outlet_upper = _sample_segment_count(
            outlet_left[-1],
            np.array((farfield_right, farfield_top), dtype=float),
            outlet_point_count,
        )

        connector_vertical_count = max(inlet_point_count, outlet_point_count)
        inlet_lower = _resample_polyline_count(
            inlet_lower,
            connector_vertical_count,
        )
        inlet_upper = _resample_polyline_count(
            inlet_upper,
            connector_vertical_count,
        )
        outlet_lower = _resample_polyline_count(
            outlet_lower,
            connector_vertical_count,
        )
        outlet_upper = _resample_polyline_count(
            outlet_upper,
            connector_vertical_count,
        )

        top_upper = _sample_segment_count(
            np.array((farfield_left, farfield_top), dtype=float),
            np.array((farfield_right, farfield_top), dtype=float),
            len(top_chain),
        )
        bottom_upper = _sample_segment_count(
            np.array((farfield_left, farfield_bottom), dtype=float),
            np.array((farfield_right, farfield_bottom), dtype=float),
            len(bottom_chain),
        )

        block_specs.extend(bridge_specs)
        block_specs.extend((
            QuadBlockSpec(
                name='block_hybrid_inlet',
                lower_boundary=inlet_lower,
                upper_boundary=inlet_upper,
                left_boundary=_sample_segment_count(
                    (farfield_left, farfield_bottom),
                    (farfield_left, farfield_top),
                    side_point_count,
                ),
                right_boundary=inlet_right,
                role='inlet_connector',
            ),
            QuadBlockSpec(
                name='block_hybrid_outlet',
                lower_boundary=outlet_lower,
                upper_boundary=outlet_upper,
                left_boundary=outlet_left,
                right_boundary=_sample_segment_count(
                    (farfield_right, farfield_bottom),
                    (farfield_right, farfield_top),
                    side_point_count,
                ),
                role='outlet_connector',
            ),
            QuadBlockSpec(
                name='block_hybrid_top',
                lower_boundary=top_chain,
                upper_boundary=top_upper,
                left_boundary=inlet_upper[::-1],
                right_boundary=outlet_upper,
                role='top_connector',
            ),
            QuadBlockSpec(
                name='block_hybrid_bottom',
                lower_boundary=bottom_chain,
                upper_boundary=bottom_upper,
                left_boundary=inlet_lower[::-1],
                right_boundary=outlet_lower,
                role='bottom_connector',
            ),
        ))

        return QuadLayoutPlan(
            boundary_points=outer_boundary,
            boundary_loops=boundary_loops,
            near_wall_loops=[element['outer_loop'] for element in element_segments],
            outer_boundary=outer_boundary,
            block_specs=block_specs,
            metadata={
                'strategy': cls.name,
                'implemented': True,
                'element_count': len(boundary_loops),
                'block_count': len(block_specs),
                'ring_thickness': float(ring_thickness),
                'connector_layers': int(connector_layers),
                'normal_divisions': int(normal_divisions),
                'first_layer_thickness': float(first_layer_thickness),
                'target_spacing': float(target_spacing),
                'minimum_inter_element_gap': float(minimum_gap)
                if np.isfinite(minimum_gap) else None,
            },
        )

    @classmethod
    def generate_metric_c_grid(
            cls,
            boundary_points=None, *,
            boundary_loops=None,
            metadata=None,
            tunnel_height: float,
            wake_length: float,
            surface_points: int | Sequence[int] | None = 0,
            normal_divisions: int = 20,
            first_layer_thickness: float = 0.004,
            connector_layers: int = 80,
            trailing_edge_divisions: int = 3,
            singularity_template: str = 'auto_boundary_c',
    ):
        boundary_loops = cls._boundary_loops_from_input(
            boundary_points,
            boundary_loops=boundary_loops,
            metadata=metadata,
            surface_points=surface_points,
            trailing_edge_divisions=trailing_edge_divisions,
        )
        if len(boundary_loops) != 1:
            raise ValueError(
                'The metric C-grid layout currently supports one closed contour.'
            )

        loop = boundary_loops[0]
        contour_points = np.asarray(loop, dtype=float)
        wake_point_count = max(6, int(connector_layers))
        singularity_template = (
            str(singularity_template).strip().lower() or 'auto_boundary_c'
        )
        if singularity_template not in ('auto_boundary_c',):
            singularity_template = 'auto_boundary_c'

        target_spacing = (
            _polyline_length(_close_loop(contour_points)) /
            max(1, len(contour_points) - 1)
        )

        reference_te_x = ExperimentalCGridGenerator._reference_trailing_edge_x(
            contour_points
        )
        te_spacing = ExperimentalCGridGenerator._trailing_edge_spacing(
            contour_points
        )
        upper_wake, lower_wake = ExperimentalCGridGenerator._build_wake_branches(
            start_point=contour_points[0],
            end_point=contour_points[-1],
            reference_te_x=reference_te_x,
            wake_length=float(wake_length),
            point_count=wake_point_count,
            first_spacing=te_spacing,
        )
        outer_boundary = _close_loop(
            ExperimentalCGridGenerator._build_outer_boundary(
                reference_te_x=reference_te_x,
                radius=float(tunnel_height),
                wake_length=float(wake_length),
                upper_points=len(upper_wake),
                middle_points=len(contour_points),
                lower_points=len(lower_wake),
                te_spacing=te_spacing,
                wake_length_ratio=1.0,
                wake_start_ratio=10.0,
            )
        )

        te_position = np.array(contour_points[0], copy=True, dtype=float)
        wake_upper = np.array(upper_wake[-1], copy=True, dtype=float)
        wake_lower = np.array(lower_wake[-1], copy=True, dtype=float)
        marker_offset = max(0.008, 0.008 * float(tunnel_height))

        block_specs = [
            QuadBlockSpec(
                name='block_metric_c_grid',
                lower_boundary=contour_points,
                upper_boundary=outer_boundary,
                left_boundary=upper_wake,
                right_boundary=lower_wake,
                role='metric_c_grid',
                protected=True,
                metadata={
                    'contour_points': contour_points,
                    'tunnel_height': float(tunnel_height),
                    'wake_length': float(wake_length),
                    'normal_divisions': int(normal_divisions),
                    'first_layer_thickness': float(first_layer_thickness),
                    'wake_point_count': int(wake_point_count),
                    'mesh_family': 'c_grid',
                    'te_geometry': 'sharp',
                },
            ),
        ]

        singularities = [
            QuadSingularity(
                position=te_position,
                charge=0,
                kind='boundary',
                metadata={
                    'label': 'TE upper',
                    'role': 'te_upper',
                    'mode': 'auto',
                    'valence_hint': 1,
                    'display_offset': (0.0, marker_offset),
                },
            ),
            QuadSingularity(
                position=te_position,
                charge=0,
                kind='boundary',
                metadata={
                    'label': 'TE lower',
                    'role': 'te_lower',
                    'mode': 'auto',
                    'valence_hint': 1,
                    'display_offset': (0.0, -marker_offset),
                },
            ),
            QuadSingularity(
                position=wake_upper,
                charge=0,
                kind='boundary',
                metadata={
                    'label': 'Wake upper',
                    'role': 'wake_upper',
                    'mode': 'auto',
                    'valence_hint': 1,
                    'display_offset': (0.0, marker_offset),
                },
            ),
            QuadSingularity(
                position=wake_lower,
                charge=0,
                kind='boundary',
                metadata={
                    'label': 'Wake lower',
                    'role': 'wake_lower',
                    'mode': 'auto',
                    'valence_hint': 1,
                    'display_offset': (0.0, -marker_offset),
                },
            )
        ]

        return QuadLayoutPlan(
            boundary_points=outer_boundary,
            boundary_loops=boundary_loops,
            near_wall_loops=[],
            outer_boundary=outer_boundary,
            block_specs=block_specs,
            singularities=singularities,
            separatrices=[
                upper_wake,
                lower_wake,
            ],
            metadata={
                'strategy': 'metric_c_grid',
                'implemented': True,
                'element_count': 1,
                'block_count': len(block_specs),
                'farfield_shape': 'legacy_wind_tunnel',
                'mesh_family': 'c_grid',
                'te_geometry': 'sharp',
                'singularity_template': singularity_template,
                'wake_point_count': int(wake_point_count),
                'separatrix_count': 2,
                'normal_divisions': int(normal_divisions),
                'first_layer_thickness': float(first_layer_thickness),
                'target_spacing': float(target_spacing),
            },
        )

    @classmethod
    def generate_metric_wind_tunnel(
            cls,
            boundary_points=None, *,
            boundary_loops=None,
            metadata=None,
            tunnel_height: float,
            wake_length: float,
            surface_points: int | Sequence[int] | None = 0,
            normal_divisions: int = 20,
            first_layer_thickness: float = 0.004,
            layer_growth: float = 1.05,
            connector_layers: int = 80,
            trailing_edge_divisions: int = 3,
            leading_edge_station: float = 0.10,
            trailing_edge_station: float = 0.90,
            nose_singularity_blend: float = 0.45,
            wake_singularity_blend: float = 0.55,
            vertical_singularity_blend: float = 0.55,
    ):
        del layer_growth
        del leading_edge_station
        del trailing_edge_station
        del nose_singularity_blend
        del wake_singularity_blend
        del vertical_singularity_blend

        return cls.generate_metric_c_grid(
            boundary_points,
            boundary_loops=boundary_loops,
            metadata=metadata,
            tunnel_height=tunnel_height,
            wake_length=wake_length,
            surface_points=surface_points,
            normal_divisions=normal_divisions,
            first_layer_thickness=first_layer_thickness,
            connector_layers=connector_layers,
            trailing_edge_divisions=trailing_edge_divisions,
        )
