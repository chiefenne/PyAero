from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from MathUtils import VectorUtils

import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundaryGuide:
    """Preferred spacing/direction profile for a structured elliptic boundary."""

    target_vectors: np.ndarray
    relaxation: float = 0.25
    layers: int = 5
    decay: float = 0.8
    layer_scale_factors: np.ndarray | None = None

    def __post_init__(self):
        vectors = np.asarray(self.target_vectors, dtype=float)
        if vectors.ndim != 2 or vectors.shape[1] != 2:
            raise ValueError('Boundary guide vectors must be an N x 2 array.')

        object.__setattr__(self, 'target_vectors', vectors)
        object.__setattr__(
            self,
            'relaxation',
            float(np.clip(self.relaxation, 0.0, 1.0)),
        )
        object.__setattr__(self, 'layers', max(1, int(self.layers)))
        object.__setattr__(self, 'decay', max(0.0, float(self.decay)))

        scale_factors = self.layer_scale_factors
        if scale_factors is None:
            object.__setattr__(self, 'layer_scale_factors', None)
            return

        normalized = np.asarray(scale_factors, dtype=float)
        if normalized.ndim == 1:
            normalized = normalized[np.newaxis, :]
        if normalized.ndim != 2 or normalized.shape[1] != vectors.shape[0]:
            raise ValueError(
                'Boundary guide scale factors must be an L x N array '
                'matching the guide point count.'
            )
        object.__setattr__(self, 'layer_scale_factors', normalized)
        object.__setattr__(self, 'layers', normalized.shape[0])


@dataclass(frozen=True)
class SlidingBoundary:
    """Boundary constrained to exact geometry with redistributed parameter spacing."""

    geometry: np.ndarray
    relaxation: float = 0.35
    control_layers: int = 4
    smoothing_passes: int = 2
    spacing_weight: float = 4.0
    min_spacing_fraction: float = 1.0e-4
    control_origins: np.ndarray | None = None
    control_directions: np.ndarray | None = None
    control_segment: str | None = None

    def __post_init__(self):
        geometry = np.asarray(self.geometry, dtype=float)
        if geometry.ndim != 2 or geometry.shape[1] != 2:
            raise ValueError('Sliding boundary geometry must be an N x 2 array.')

        object.__setattr__(self, 'geometry', geometry)
        object.__setattr__(
            self,
            'relaxation',
            float(np.clip(self.relaxation, 0.0, 1.0)),
        )
        object.__setattr__(
            self,
            'control_layers',
            max(1, int(self.control_layers)),
        )
        object.__setattr__(
            self,
            'smoothing_passes',
            max(0, int(self.smoothing_passes)),
        )
        object.__setattr__(
            self,
            'spacing_weight',
            max(0.0, float(self.spacing_weight)),
        )
        object.__setattr__(
            self,
            'min_spacing_fraction',
            max(0.0, float(self.min_spacing_fraction)),
        )
        segment = self.control_segment
        if segment is None:
            object.__setattr__(self, 'control_segment', None)
        else:
            object.__setattr__(
                self,
                'control_segment',
                str(segment).strip().lower() or None,
            )
        origins = self.control_origins
        directions = self.control_directions
        if origins is None and directions is None:
            object.__setattr__(self, 'control_origins', None)
            object.__setattr__(self, 'control_directions', None)
            return
        if origins is None or directions is None:
            raise ValueError(
                'Sliding boundary control origins and directions must be provided together.'
            )

        normalized_origins = np.asarray(origins, dtype=float)
        normalized_directions = np.asarray(directions, dtype=float)
        if normalized_origins.shape != geometry.shape:
            raise ValueError(
                'Sliding boundary control origins must match the geometry point layout.'
            )
        if normalized_directions.shape != geometry.shape:
            raise ValueError(
                'Sliding boundary control directions must match the geometry point layout.'
            )
        object.__setattr__(self, 'control_origins', normalized_origins)
        object.__setattr__(self, 'control_directions', normalized_directions)


class EllipticSolver:
    """Structured elliptic grid smoother with exact-geometry sliding boundaries."""

    EPSILON = 1.0e-9
    DEFAULT_LOG_INTERVAL = 10
    DEFAULT_RELAXATION = 0.6
    SLIDING_CONTINUATION_FACTOR = 1.0
    MIN_UNIFORM_PARAMETER_FRACTION = 0.60
    RAY_TARGET_BLEND = 0.45
    LOCAL_TARGET_BLEND = 0.30
    CURRENT_TARGET_BLEND = 0.25
    RAY_SPACING_BLEND = 0.20
    LOCAL_SPACING_BLEND = 0.20
    UNIFORM_SPACING_BLEND = 0.60
    PAIR_TARGET_BLEND = 0.45
    ARC_RAY_TARGET_BLEND = 0.25
    PAIR_LOCAL_TARGET_BLEND = 0.20
    PAIR_CURRENT_TARGET_BLEND = 0.10
    PAIR_SPACING_BLEND = 0.50
    PAIR_LOCAL_SPACING_BLEND = 0.20
    PAIR_UNIFORM_SPACING_BLEND = 0.30

    def __init__(self, x, y):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)

        if self.x.shape != self.y.shape:
            raise ValueError('Elliptic smoother requires x/y arrays with equal shape.')
        if self.x.ndim != 2:
            raise ValueError('Elliptic smoother requires 2D structured coordinate arrays.')

    @staticmethod
    def curveNormals(x, y, closed=False):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        point_count = len(x)
        if point_count == 0:
            return np.empty((0, 2), dtype=float)
        if point_count == 1:
            return np.array([[0.0, 1.0]], dtype=float)

        tangents = np.empty((point_count, 2), dtype=float)
        if closed:
            previous = np.column_stack((np.roll(x, 1), np.roll(y, 1)))
            following = np.column_stack((np.roll(x, -1), np.roll(y, -1)))
            tangents[:, 0] = following[:, 0] - previous[:, 0]
            tangents[:, 1] = following[:, 1] - previous[:, 1]
        else:
            tangents[0] = [x[1] - x[0], y[1] - y[0]]
            tangents[-1] = [x[-1] - x[-2], y[-1] - y[-2]]
            if point_count > 2:
                tangents[1:-1, 0] = x[2:] - x[:-2]
                tangents[1:-1, 1] = y[2:] - y[:-2]

        units = VectorUtils.unit_vector(tangents)
        return np.column_stack((units[:, 1], -units[:, 0]))

    @staticmethod
    def _should_log_iteration(iteration, iterations, log_interval):
        return (
            iteration == 1 or
            iteration == iterations or
            iteration % log_interval == 0
        )

    @staticmethod
    def _smooth_profile(values, passes):
        profile = np.asarray(values, dtype=float)
        if profile.ndim != 1 or profile.size < 3 or passes <= 0:
            return np.array(profile, copy=True, dtype=float)

        smoothed = np.array(profile, copy=True, dtype=float)
        for _ in range(int(passes)):
            updated = np.array(smoothed, copy=True, dtype=float)
            updated[1:-1] = (
                0.25 * smoothed[:-2] +
                0.50 * smoothed[1:-1] +
                0.25 * smoothed[2:]
            )
            smoothed = updated

        return smoothed

    @classmethod
    def _normalize_boundary_guides(cls, boundary_guides, shape):
        if not boundary_guides:
            return {}

        normalized = {}
        for side, guide in boundary_guides.items():
            key = str(side).strip().lower()
            if key not in ('bottom', 'top'):
                raise ValueError(f'Unsupported guided elliptic boundary: {side}')

            normalized_guide = guide
            if not isinstance(normalized_guide, BoundaryGuide):
                normalized_guide = BoundaryGuide(**guide)

            expected_points = shape[0]
            if normalized_guide.target_vectors.shape[0] != expected_points:
                raise ValueError(
                    f'Boundary guide for {key} requires {expected_points} '
                    f'points, got {normalized_guide.target_vectors.shape[0]}.'
                )
            normalized[key] = normalized_guide

        return normalized

    @classmethod
    def _normalize_sliding_boundaries(cls, sliding_boundaries, shape):
        if not sliding_boundaries:
            return {}

        normalized = {}
        for side, boundary in sliding_boundaries.items():
            key = str(side).strip().lower()
            if key not in ('bottom', 'top'):
                raise ValueError(f'Unsupported sliding elliptic boundary: {side}')

            normalized_boundary = boundary
            if not isinstance(normalized_boundary, SlidingBoundary):
                normalized_boundary = SlidingBoundary(**boundary)

            expected_points = shape[0]
            if normalized_boundary.geometry.shape[0] != expected_points:
                raise ValueError(
                    f'Sliding boundary for {key} requires {expected_points} '
                    f'points, got {normalized_boundary.geometry.shape[0]}.'
                )
            normalized[key] = normalized_boundary

        return normalized

    @staticmethod
    def _polyline_parameters(points):
        points = np.asarray(points, dtype=float)
        if len(points) <= 1:
            return np.zeros(len(points), dtype=float)

        deltas = np.linalg.norm(np.diff(points, axis=0), axis=1)
        cumulative = np.concatenate(([0.0], np.cumsum(deltas)))
        total_length = cumulative[-1]
        if total_length <= 0.0:
            return np.linspace(0.0, 1.0, len(points))
        return cumulative / total_length

    @classmethod
    def _sample_polyline(cls, geometry, parameters):
        geometry = np.asarray(geometry, dtype=float)
        parameters = np.asarray(parameters, dtype=float)

        if len(geometry) == 0:
            empty = np.empty((0, 2), dtype=float)
            return empty, empty
        if len(geometry) == 1:
            points = np.repeat(geometry, len(parameters), axis=0)
            tangents = np.tile(np.array([[1.0, 0.0]], dtype=float), (len(parameters), 1))
            return points, tangents

        reference_parameters = cls._polyline_parameters(geometry)
        x_values = np.interp(parameters, reference_parameters, geometry[:, 0])
        y_values = np.interp(parameters, reference_parameters, geometry[:, 1])
        sampled_points = np.column_stack((x_values, y_values))

        step = 1.0e-4
        previous = np.clip(parameters - step, 0.0, 1.0)
        following = np.clip(parameters + step, 0.0, 1.0)
        prev_x = np.interp(previous, reference_parameters, geometry[:, 0])
        prev_y = np.interp(previous, reference_parameters, geometry[:, 1])
        next_x = np.interp(following, reference_parameters, geometry[:, 0])
        next_y = np.interp(following, reference_parameters, geometry[:, 1])
        tangents = np.column_stack((next_x - prev_x, next_y - prev_y))
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        tangents = np.divide(
            tangents,
            norms,
            out=np.zeros_like(tangents),
            where=norms > cls.EPSILON,
        )
        return sampled_points, tangents

    @classmethod
    def _project_points_onto_polyline(cls, geometry, points):
        geometry = np.asarray(geometry, dtype=float)
        points = np.asarray(points, dtype=float)

        if len(geometry) == 0:
            empty = np.empty((0, 2), dtype=float)
            return empty, np.empty((0,), dtype=float)
        if len(geometry) == 1:
            projected = np.repeat(geometry, len(points), axis=0)
            return projected, np.zeros(len(points), dtype=float)

        reference_parameters = cls._polyline_parameters(geometry)
        segment_start = geometry[:-1]
        segment_end = geometry[1:]
        segment_vectors = segment_end - segment_start
        segment_length_sq = np.sum(segment_vectors * segment_vectors, axis=1)

        projected = np.empty_like(points, dtype=float)
        projected_parameters = np.empty(len(points), dtype=float)

        for index, point in enumerate(points):
            offsets = point - segment_start
            local = np.divide(
                np.sum(offsets * segment_vectors, axis=1),
                segment_length_sq,
                out=np.zeros_like(segment_length_sq),
                where=segment_length_sq > cls.EPSILON,
            )
            local = np.clip(local, 0.0, 1.0)
            candidates = segment_start + local[:, None] * segment_vectors
            distance_sq = np.sum((candidates - point) ** 2, axis=1)
            best = int(np.argmin(distance_sq))
            projected[index] = candidates[best]
            projected_parameters[index] = (
                reference_parameters[best] +
                local[best] * (reference_parameters[best + 1] - reference_parameters[best])
            )

        return projected, projected_parameters

    @classmethod
    def _control_segment_slice(cls, geometry, segment):
        if segment is None:
            return 0, len(geometry)

        if segment != 'c_arc':
            raise ValueError(f'Unsupported sliding boundary control segment: {segment}')

        if len(geometry) < 3:
            return 0, len(geometry)

        x_values = np.asarray(geometry[:, 0], dtype=float)
        tolerance = max(1.0e-8, 1.0e-8 * np.max(np.abs(x_values)))
        zero_crossings = np.where(np.abs(x_values) <= tolerance)[0]
        if zero_crossings.size < 2:
            return 0, len(geometry)

        start = int(zero_crossings[0])
        stop = int(zero_crossings[-1]) + 1
        if stop - start < 2:
            return 0, len(geometry)
        return start, stop

    @staticmethod
    def _cross_2d(first, second):
        return first[0] * second[1] - first[1] * second[0]

    @classmethod
    def _ray_parameters_on_polyline(cls, geometry, origins, directions):
        geometry = np.asarray(geometry, dtype=float)
        origins = np.asarray(origins, dtype=float)
        directions = np.asarray(directions, dtype=float)

        if len(geometry) <= 1 or len(origins) == 0:
            return np.zeros(len(origins), dtype=float)

        reference_parameters = cls._polyline_parameters(geometry)
        segment_start = geometry[:-1]
        segment_end = geometry[1:]
        segment_vectors = segment_end - segment_start
        parameters = np.empty(len(origins), dtype=float)

        for point_index, (origin, direction) in enumerate(zip(origins, directions)):
            direction_norm = np.linalg.norm(direction)
            if direction_norm <= cls.EPSILON:
                fallback_point = origin[np.newaxis, :]
                _, projected = cls._project_points_onto_polyline(geometry, fallback_point)
                parameters[point_index] = projected[0]
                continue

            best_parameter = None
            best_distance = np.inf

            for segment_index, (start, segment) in enumerate(zip(segment_start, segment_vectors)):
                denominator = cls._cross_2d(direction, segment)
                if abs(denominator) <= cls.EPSILON:
                    continue

                delta = start - origin
                ray_distance = cls._cross_2d(delta, segment) / denominator
                segment_fraction = cls._cross_2d(delta, direction) / denominator

                if ray_distance < 0.0:
                    continue
                if segment_fraction < -1.0e-9 or segment_fraction > 1.0 + 1.0e-9:
                    continue

                clipped_fraction = float(np.clip(segment_fraction, 0.0, 1.0))
                if ray_distance < best_distance:
                    best_distance = ray_distance
                    best_parameter = (
                        reference_parameters[segment_index] +
                        clipped_fraction * (
                            reference_parameters[segment_index + 1] -
                            reference_parameters[segment_index]
                        )
                    )

            if best_parameter is None:
                fallback_point = (origin + direction)[np.newaxis, :]
                _, projected = cls._project_points_onto_polyline(geometry, fallback_point)
                best_parameter = projected[0]

            parameters[point_index] = best_parameter

        return parameters

    @classmethod
    def _ray_parameters_on_control_segment(cls, geometry, origins, directions, segment):
        start, stop = cls._control_segment_slice(geometry, segment)
        if start == 0 and stop == len(geometry):
            return cls._ray_parameters_on_polyline(geometry, origins, directions)

        reference_parameters = cls._polyline_parameters(geometry)
        segment_geometry = geometry[start:stop]
        segment_parameters = cls._ray_parameters_on_polyline(
            segment_geometry,
            origins,
            directions,
        )
        local_reference = cls._polyline_parameters(segment_geometry)
        return np.interp(
            segment_parameters,
            local_reference,
            reference_parameters[start:stop],
        )

    @classmethod
    def _parameter_spacing(cls, geometry, min_spacing_fraction):
        parameters = cls._polyline_parameters(geometry)
        if len(parameters) <= 1:
            return 0.0
        average_spacing = 1.0 / float(len(parameters) - 1)
        return float(
            max(
                max(np.min(np.diff(parameters)), cls.EPSILON) *
                max(0.0, float(min_spacing_fraction)),
                average_spacing * cls.MIN_UNIFORM_PARAMETER_FRACTION,
            )
        )

    @classmethod
    def _guard_parameters(cls, parameters, min_spacing):
        guarded = np.array(parameters, copy=True, dtype=float)
        if len(guarded) <= 2:
            return guarded

        guarded[0] = 0.0
        guarded[-1] = 1.0

        for index in range(1, len(guarded) - 1):
            guarded[index] = max(guarded[index], guarded[index - 1] + min_spacing)

        for index in range(len(guarded) - 2, 0, -1):
            guarded[index] = min(guarded[index], guarded[index + 1] - min_spacing)

        guarded[1:-1] = np.clip(guarded[1:-1], 0.0, 1.0)
        guarded[0] = 0.0
        guarded[-1] = 1.0
        return guarded

    @staticmethod
    def _boundary_row(x, y, column):
        return np.column_stack((x[:, column], y[:, column]))

    @classmethod
    def _control_row_pairs(cls, x, y, side, layer_count):
        pairs = []
        ny = x.shape[1]
        available_pairs = max(0, ny - 3)
        pair_count = min(max(1, int(layer_count)), available_pairs)

        if pair_count <= 0:
            return pairs

        if side == 'top':
            for depth in range(1, pair_count + 1):
                near_column = -1 - depth
                far_column = near_column - 1
                pairs.append(
                    (
                        cls._boundary_row(x, y, near_column),
                        cls._boundary_row(x, y, far_column),
                    )
                )
        elif side == 'bottom':
            for depth in range(1, pair_count + 1):
                near_column = depth
                far_column = near_column + 1
                pairs.append(
                    (
                        cls._boundary_row(x, y, near_column),
                        cls._boundary_row(x, y, far_column),
                    )
                )
        else:
            raise ValueError(f'Unsupported sliding boundary: {side}')

        return pairs

    @classmethod
    def _solve_parameter_distribution(cls, projection_target, edge_fractions, spacing_weight):
        point_count = len(projection_target)
        if point_count <= 2:
            return np.array(projection_target, copy=True, dtype=float)

        spacing_weight = max(0.0, float(spacing_weight))
        if spacing_weight <= 0.0:
            solution = np.array(projection_target, copy=True, dtype=float)
            solution[0] = 0.0
            solution[-1] = 1.0
            return solution

        interior_count = point_count - 2
        matrix = np.zeros((interior_count, interior_count), dtype=float)
        rhs = np.array(projection_target[1:-1], copy=True, dtype=float)

        for row_index in range(interior_count):
            parameter_index = row_index + 1
            matrix[row_index, row_index] = 1.0 + 2.0 * spacing_weight
            rhs[row_index] += spacing_weight * (
                edge_fractions[parameter_index - 1] - edge_fractions[parameter_index]
            )

            if row_index > 0:
                matrix[row_index, row_index - 1] = -spacing_weight
            if row_index < interior_count - 1:
                matrix[row_index, row_index + 1] = -spacing_weight
            else:
                rhs[row_index] += spacing_weight

        solution = np.zeros(point_count, dtype=float)
        solution[0] = 0.0
        solution[-1] = 1.0
        solution[1:-1] = np.linalg.solve(matrix, rhs)
        return solution

    @classmethod
    def _sliding_target_parameters(cls, x, y, side, boundary, current_parameters):
        adjacent_column = -2 if side == 'top' else 1
        adjacent = cls._boundary_row(x, y, adjacent_column)
        _, local_target = cls._project_points_onto_polyline(
            boundary.geometry,
            adjacent,
        )
        local_spacing = np.linalg.norm(np.diff(adjacent, axis=0), axis=1)

        pairs = cls._control_row_pairs(
            x,
            y,
            side,
            boundary.control_layers,
        )

        if pairs:
            weights = np.linspace(float(len(pairs)), 1.0, len(pairs))
            weights /= np.sum(weights)
            pair_target = np.zeros(x.shape[0], dtype=float)
            pair_spacing = np.zeros(x.shape[0] - 1, dtype=float)

            for weight, (near, far) in zip(weights, pairs):
                step_vectors = near - far
                extrapolated = near + cls.SLIDING_CONTINUATION_FACTOR * step_vectors
                _, projected_parameters = cls._project_points_onto_polyline(
                    boundary.geometry,
                    extrapolated,
                )
                pair_target += weight * projected_parameters
                pair_spacing += weight * np.linalg.norm(
                    np.diff(near, axis=0),
                    axis=1,
                )
        else:
            pair_target = local_target
            pair_spacing = local_spacing

        if (
            boundary.control_origins is not None and
            boundary.control_directions is not None
        ):
            ray_target = cls._ray_parameters_on_control_segment(
                boundary.geometry,
                boundary.control_origins,
                boundary.control_directions,
                boundary.control_segment,
            )
            projection_target = cls._smooth_profile(
                (
                    cls.PAIR_TARGET_BLEND * pair_target +
                    cls.ARC_RAY_TARGET_BLEND * ray_target +
                    cls.PAIR_LOCAL_TARGET_BLEND * local_target +
                    cls.PAIR_CURRENT_TARGET_BLEND * current_parameters
                ),
                max(boundary.smoothing_passes, 1),
            )
            projection_target[0] = 0.0
            projection_target[-1] = 1.0
            uniform_spacing = np.full_like(local_spacing, np.mean(local_spacing))
            spacing_target = (
                cls.PAIR_SPACING_BLEND * pair_spacing +
                cls.PAIR_LOCAL_SPACING_BLEND * local_spacing +
                cls.PAIR_UNIFORM_SPACING_BLEND * uniform_spacing
            )
            spacing_target = np.maximum(spacing_target, cls.EPSILON)
            spacing_target = cls._smooth_profile(
                spacing_target,
                max(boundary.smoothing_passes, 1),
            )
            edge_fractions = spacing_target / np.sum(spacing_target)
            return cls._solve_parameter_distribution(
                projection_target,
                edge_fractions,
                boundary.spacing_weight,
            )

        projection_target = pair_target
        spacing_target = pair_spacing

        projection_target = cls._smooth_profile(
            projection_target,
            boundary.smoothing_passes,
        )
        projection_target[0] = 0.0
        projection_target[-1] = 1.0

        spacing_target = np.maximum(spacing_target, cls.EPSILON)
        spacing_target = cls._smooth_profile(
            spacing_target,
            boundary.smoothing_passes,
        )
        spacing_target = np.maximum(spacing_target, cls.EPSILON)
        edge_fractions = spacing_target / np.sum(spacing_target)

        target = cls._solve_parameter_distribution(
            projection_target,
            edge_fractions,
            boundary.spacing_weight,
        )
        return target

    @classmethod
    def _apply_boundary_guide(cls, x, y, side, guide):
        if guide.relaxation <= 0.0:
            return

        interior_layers = max(0, x.shape[1] - 2)
        if interior_layers <= 0:
            return

        boundary_column = 0 if side == 'bottom' else -1
        direction = 1.0 if side == 'bottom' else -1.0
        boundary = np.column_stack((x[:, boundary_column], y[:, boundary_column]))
        layers = min(guide.layers, interior_layers)
        scale_factors = guide.layer_scale_factors

        for layer in range(1, layers + 1):
            weight = guide.relaxation * (guide.decay ** (layer - 1))
            if weight <= 0.0:
                continue

            if scale_factors is None:
                target = boundary + direction * float(layer) * guide.target_vectors
            else:
                target = boundary + direction * scale_factors[layer - 1][:, None] * guide.target_vectors

            column = layer if side == 'bottom' else -layer - 1
            x[1:-1, column] = (
                (1.0 - weight) * x[1:-1, column] +
                weight * target[1:-1, 0]
            )
            y[1:-1, column] = (
                (1.0 - weight) * y[1:-1, column] +
                weight * target[1:-1, 1]
            )

    @classmethod
    def _apply_sliding_boundary(cls, x, y, side, boundary, parameters):
        if boundary.relaxation <= 0.0 or len(parameters) <= 2:
            sampled_points, _ = cls._sample_polyline(boundary.geometry, parameters)
            return sampled_points, parameters

        target_parameters = cls._sliding_target_parameters(
            x,
            y,
            side,
            boundary,
            parameters,
        )
        min_spacing = cls._parameter_spacing(
            boundary.geometry,
            boundary.min_spacing_fraction,
        )

        updated_parameters = (
            (1.0 - boundary.relaxation) * parameters +
            boundary.relaxation * target_parameters
        )
        updated_parameters = cls._smooth_profile(
            updated_parameters,
            boundary.smoothing_passes,
        )
        updated_parameters = cls._guard_parameters(updated_parameters, min_spacing)

        sampled_points, _ = cls._sample_polyline(boundary.geometry, updated_parameters)
        return sampled_points, updated_parameters

    def smooth(self, iterations=10, tolerance=1.0e-3,
               boundary_condition=None, boundary_guides=None,
               sliding_boundaries=None, relaxation=None,
               verbose=False, log_interval=None):
        x = np.array(self.x, copy=True, dtype=float)
        y = np.array(self.y, copy=True, dtype=float)

        iterations = int(iterations)
        log_interval = (
            self.DEFAULT_LOG_INTERVAL if log_interval is None else max(1, int(log_interval))
        )
        if relaxation is None:
            relaxation = self.DEFAULT_RELAXATION
        relaxation = float(np.clip(relaxation, 0.0, 1.0))

        if x.shape[0] < 3 or x.shape[1] < 3 or iterations <= 0:
            return x, y

        if boundary_condition is None:
            normalized_boundary = None
        else:
            normalized_boundary = str(boundary_condition).strip().lower()

        if normalized_boundary not in (None, 'neumann'):
            raise ValueError(
                f'Unsupported elliptic boundary condition: {boundary_condition}'
            )

        normalized_guides = self._normalize_boundary_guides(boundary_guides, x.shape)
        normalized_sliding = self._normalize_sliding_boundaries(sliding_boundaries, x.shape)

        sliding_parameters = {
            side: self._polyline_parameters(boundary.geometry)
            for side, boundary in normalized_sliding.items()
        }

        xn = np.array(x, copy=True, dtype=float)
        yn = np.array(y, copy=True, dtype=float)
        interior = np.s_[1:-1, 1:-1]

        normals_bottom = None
        if normalized_boundary == 'neumann':
            normals_bottom = self.curveNormals(x[:, 0], y[:, 0])[1:-1]

        for side, boundary in normalized_sliding.items():
            sampled_points, updated_parameters = self._apply_sliding_boundary(
                x,
                y,
                side,
                boundary,
                sliding_parameters[side],
            )
            sliding_parameters[side] = updated_parameters
            if side == 'bottom':
                x[:, 0] = sampled_points[:, 0]
                y[:, 0] = sampled_points[:, 1]
            else:
                x[:, -1] = sampled_points[:, 0]
                y[:, -1] = sampled_points[:, 1]

        for iteration in range(1, iterations + 1):
            xn[:, :] = x
            yn[:, :] = y

            x_ip1 = x[2:, 1:-1]
            x_im1 = x[:-2, 1:-1]
            x_jp1 = x[1:-1, 2:]
            x_jm1 = x[1:-1, :-2]
            y_ip1 = y[2:, 1:-1]
            y_im1 = y[:-2, 1:-1]
            y_jp1 = y[1:-1, 2:]
            y_jm1 = y[1:-1, :-2]

            alpha = 0.25 * ((x_jp1 - x_jm1) ** 2 + (y_jp1 - y_jm1) ** 2)
            gamma = 0.25 * ((x_ip1 - x_im1) ** 2 + (y_ip1 - y_im1) ** 2)
            beta = 0.0625 * (
                (x_ip1 - x_im1) * (x_jp1 - x_jm1) +
                (y_ip1 - y_im1) * (y_jp1 - y_jm1)
            )
            denominator = alpha + gamma + self.EPSILON

            x_candidate = -0.5 / denominator * (
                2.0 * beta * (
                    x[2:, 2:] - x[:-2, 2:] - x[2:, :-2] + x[:-2, :-2]
                ) -
                alpha * (x_ip1 + x_im1) -
                gamma * (x_jp1 + x_jm1)
            )
            y_candidate = -0.5 / denominator * (
                2.0 * beta * (
                    y[2:, 2:] - y[:-2, 2:] - y[2:, :-2] + y[:-2, :-2]
                ) -
                alpha * (y_ip1 + y_im1) -
                gamma * (y_jp1 + y_jm1)
            )

            xn[interior] = (
                (1.0 - relaxation) * x[interior] +
                relaxation * x_candidate
            )
            yn[interior] = (
                (1.0 - relaxation) * y[interior] +
                relaxation * y_candidate
            )

            if normalized_boundary == 'neumann':
                boundary_points = np.column_stack((xn[1:-1, 0], yn[1:-1, 0]))
                interior_points = np.column_stack((xn[1:-1, 1], yn[1:-1, 1]))
                normal_scale = np.sum(
                    (interior_points - boundary_points) * normals_bottom,
                    axis=1,
                ) / np.maximum(
                    np.sum(normals_bottom * normals_bottom, axis=1),
                    self.EPSILON,
                )
                projected = boundary_points + normal_scale[:, None] * normals_bottom
                xn[1:-1, 1] = projected[:, 0]
                yn[1:-1, 1] = projected[:, 1]

            for side, guide in normalized_guides.items():
                self._apply_boundary_guide(xn, yn, side, guide)

            for side, boundary in normalized_sliding.items():
                sampled_points, updated_parameters = self._apply_sliding_boundary(
                    xn,
                    yn,
                    side,
                    boundary,
                    sliding_parameters[side],
                )
                sliding_parameters[side] = updated_parameters
                if side == 'bottom':
                    xn[:, 0] = sampled_points[:, 0]
                    yn[:, 0] = sampled_points[:, 1]
                else:
                    xn[:, -1] = sampled_points[:, 0]
                    yn[:, -1] = sampled_points[:, 1]

            residual = np.max(np.abs(xn - x)) + np.max(np.abs(yn - y))

            if verbose and self._should_log_iteration(
                iteration,
                iterations,
                log_interval,
            ):
                logger.info(f'Iteration={iteration:3d}, residual={residual:.3e}')

            x, xn = xn, x
            y, yn = yn, y
            if residual < tolerance:
                break

        return x, y


class Elliptic(EllipticSolver):
    """Backward-compatible wrapper preserving the former ulines API."""

    def __init__(self, ulines):
        self.ulines = ulines
        x, y = self._map_ulines(ulines)
        super().__init__(x, y)

    @staticmethod
    def _map_ulines(ulines):
        ny = len(ulines)
        nx = len(ulines[0]) if ulines else 0
        x = np.empty((nx, ny), dtype=float)
        y = np.empty_like(x)

        for j_index, uline in enumerate(ulines):
            coordinates = np.asarray(uline, dtype=float)
            x[:, j_index] = coordinates[:, 0]
            y[:, j_index] = coordinates[:, 1]

        return x, y

    def _map_to_ulines(self, x, y):
        ulines = []
        for j_index, uline in enumerate(self.ulines):
            new_uline = []
            for i_index, _ in enumerate(uline):
                new_uline.append((float(x[i_index, j_index]), float(y[i_index, j_index])))
            ulines.append(new_uline)
        return ulines

    def smooth(self, iterations=10, tolerance=1.0e-3, bnd_type=None,
               boundary_guides=None, sliding_boundaries=None,
               relaxation=None, verbose=False, log_interval=None):
        x, y = super().smooth(
            iterations=iterations,
            tolerance=tolerance,
            boundary_condition=bnd_type,
            boundary_guides=boundary_guides,
            sliding_boundaries=sliding_boundaries,
            relaxation=relaxation,
            verbose=verbose,
            log_interval=log_interval,
        )
        return self._map_to_ulines(x, y)
