from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from BlockMesh import BlockMesh
from Elliptic import EllipticSolver


@dataclass(slots=True)
class ExperimentalOGridSettings:
    name: str = 'block_experimental_o_grid'
    surface_points: int = 0
    normal_divisions: int = 100
    first_layer_thickness: float = 0.004
    farfield_shape: str = 'wind_tunnel'
    initial_smoothing_iterations: int = 100
    final_smoothing_iterations: int = 20
    smoothing_tolerance: float = 1.0e-5
    relaxation: float = 0.6

    def __post_init__(self):
        self.surface_points = max(0, int(self.surface_points))
        self.normal_divisions = max(4, int(self.normal_divisions))
        self.first_layer_thickness = max(1.0e-12, float(self.first_layer_thickness))

        shape = str(self.farfield_shape).strip().lower()
        if shape in ('wt', 'windtunnel', 'wind tunnel', 'wind-tunnel'):
            shape = 'wind_tunnel'
        if shape not in ('circle', 'wind_tunnel'):
            shape = 'wind_tunnel'
        self.farfield_shape = shape

        self.initial_smoothing_iterations = max(
            0,
            int(self.initial_smoothing_iterations),
        )
        self.final_smoothing_iterations = max(
            0,
            int(self.final_smoothing_iterations),
        )
        self.smoothing_tolerance = max(1.0e-12, float(self.smoothing_tolerance))
        self.relaxation = float(np.clip(self.relaxation, 0.01, 1.0))


class ExperimentalOGridGenerator:
    """Experimental multi-block O-grid generator."""

    block_suffixes = ('top', 'left', 'bottom', 'right')
    minimum_closed_point_count = 13
    wt_le_station = 0.10
    wt_te_station = 0.90

    def build_blocks(self, contour, *, radius: float, wake_length: float,
                     settings: ExperimentalOGridSettings,
                     trailing_edge_settings=None) -> list[BlockMesh]:
        if settings.farfield_shape == 'circle':
            inner_segments = self._build_circle_inner_segments(
                contour,
                surface_points=settings.surface_points,
                trailing_edge_settings=trailing_edge_settings,
            )
            outer_segments = self._build_circle_outer_segments(
                radius=float(radius),
                segment_lengths=[len(segment) for segment in inner_segments],
            )
        else:
            inner_segments = self._build_wind_tunnel_inner_segments(
                contour,
                surface_points=settings.surface_points,
                radius=float(radius),
                wake_length=float(wake_length),
                trailing_edge_settings=trailing_edge_settings,
            )
            outer_segments = self._build_wind_tunnel_outer_segments(
                radius=float(radius),
                wake_length=float(wake_length),
                segment_lengths=[len(segment) for segment in inner_segments],
            )

        blocks = []
        for suffix, inner_segment, outer_segment in zip(
                self.block_suffixes,
                inner_segments,
                outer_segments):
            block = self._build_block(
                inner_segment,
                outer_segment,
                settings=settings,
                name=f'{settings.name}_{suffix}',
            )
            blocks.append(block)

        return blocks

    @classmethod
    def _raw_points(cls, contour) -> np.ndarray:
        points = np.column_stack(contour).astype(float, copy=False)
        if points.ndim != 2 or points.shape[1] != 2 or len(points) < 4:
            raise ValueError('Experimental O-grid requires a valid 2D contour.')
        return points

    @classmethod
    def _te_divisions(cls, trailing_edge_settings) -> int:
        if trailing_edge_settings is None:
            return 3
        return max(
            1,
            int(getattr(trailing_edge_settings, 'trailing_edge_divisions', 3)),
        )

    @classmethod
    def _prepare_closed_boundary(cls, contour, surface_points: int, *,
                                 trailing_edge_settings=None) -> np.ndarray:
        points = cls._raw_points(contour)
        is_closed = np.allclose(points[0], points[-1], atol=1.0e-8)
        if not is_closed:
            te_segment = cls._sample_segment_count(
                points[-1],
                points[0],
                cls._te_divisions(trailing_edge_settings) + 1,
            )
            points = cls._compose_segments(points, te_segment)
        elif surface_points <= 0:
            points[-1] = points[0]

        if surface_points > 0 and surface_points != len(points):
            points = cls._resample_polyline_count(points, surface_points)
            points[-1] = points[0]

        if len(points) < cls.minimum_closed_point_count:
            points = cls._resample_polyline_count(
                points,
                cls.minimum_closed_point_count,
            )
            points[-1] = points[0]

        if not np.allclose(points[0], points[-1], atol=1.0e-8):
            points = np.vstack((points, points[0]))

        return points

    @classmethod
    def _build_circle_inner_segments(cls, contour, *, surface_points: int,
                                     trailing_edge_settings=None) -> list[np.ndarray]:
        inner_boundary = cls._prepare_closed_boundary(
            contour,
            surface_points,
            trailing_edge_settings=trailing_edge_settings,
        )
        return cls._split_closed_boundary(inner_boundary)

    @classmethod
    def _build_wind_tunnel_inner_segments(cls, contour, *, surface_points: int,
                                          radius: float, wake_length: float,
                                          trailing_edge_settings=None
                                          ) -> list[np.ndarray]:
        points = cls._raw_points(contour)
        closed_boundary = cls._prepare_closed_boundary(
            contour,
            surface_points,
            trailing_edge_settings=trailing_edge_settings,
        )
        total_intervals = max(4, len(closed_boundary) - 1)

        upper_surface, lower_surface = cls._split_upper_lower_surfaces(points)
        outer_lengths = cls._wind_tunnel_outer_lengths(
            radius=float(radius),
            wake_length=float(wake_length),
        )
        segment_intervals = cls._allocate_segment_intervals(
            total_intervals,
            outer_lengths,
        )

        dense_count = max(200, 4 * max(segment_intervals) + 1)
        upper_dense = cls._resample_polyline_count(upper_surface, dense_count)
        lower_dense = cls._resample_polyline_count(lower_surface, dense_count)

        x_min = float(np.min(points[:, 0]))
        x_max = float(np.max(points[:, 0]))
        chord = max(x_max - x_min, 1.0e-9)
        x_le_limit = x_min + cls.wt_le_station * chord
        x_te_limit = x_min + cls.wt_te_station * chord

        upper_te_index = cls._first_index_leq(upper_dense[:, 0], x_te_limit)
        upper_le_index = cls._first_index_leq(upper_dense[:, 0], x_le_limit)
        if upper_le_index <= upper_te_index:
            upper_te_index = max(0, min(upper_te_index, len(upper_dense) - 3))
            upper_le_index = min(len(upper_dense) - 2, upper_te_index + 1)

        lower_le_index = cls._first_index_geq(lower_dense[:, 0], x_le_limit)
        lower_te_index = cls._first_index_geq(lower_dense[:, 0], x_te_limit)
        if lower_te_index <= lower_le_index:
            lower_le_index = max(0, min(lower_le_index, len(lower_dense) - 3))
            lower_te_index = min(len(lower_dense) - 2, lower_le_index + 1)

        closure = cls._te_closure_segment(
            lower_dense[-1],
            upper_dense[0],
            te_divisions=cls._te_divisions(trailing_edge_settings),
        )

        top_polyline = upper_dense[upper_te_index:upper_le_index + 1]
        left_polyline = cls._compose_segments(
            upper_dense[upper_le_index:],
            lower_dense[:lower_le_index + 1],
        )
        bottom_polyline = lower_dense[lower_le_index:lower_te_index + 1]
        right_polyline = cls._compose_segments(
            lower_dense[lower_te_index:],
            closure,
            upper_dense[:upper_te_index + 1],
        )

        polylines = (
            top_polyline,
            left_polyline,
            bottom_polyline,
            right_polyline,
        )

        return [
            cls._resample_polyline_count(polyline, intervals + 1)
            for polyline, intervals in zip(polylines, segment_intervals)
        ]

    @classmethod
    def _split_upper_lower_surfaces(cls, points: np.ndarray
                                    ) -> tuple[np.ndarray, np.ndarray]:
        is_closed = np.allclose(points[0], points[-1], atol=1.0e-8)
        if is_closed:
            open_points = np.asarray(points[:-1], dtype=float)
        else:
            open_points = np.asarray(points, dtype=float)

        le_index = int(np.argmin(open_points[:, 0]))
        upper = np.asarray(open_points[:le_index + 1], dtype=float)
        lower = np.asarray(open_points[le_index:], dtype=float)
        if len(upper) < 2 or len(lower) < 2:
            raise ValueError('Experimental O-grid requires distinct upper and lower surfaces.')
        return upper, lower

    @staticmethod
    def _first_index_leq(values: np.ndarray, target: float) -> int:
        matches = np.flatnonzero(values <= target)
        if matches.size:
            return int(matches[0])
        return len(values) - 1

    @staticmethod
    def _first_index_geq(values: np.ndarray, target: float) -> int:
        matches = np.flatnonzero(values >= target)
        if matches.size:
            return int(matches[0])
        return len(values) - 1

    @classmethod
    def _te_closure_segment(cls, lower_te: np.ndarray, upper_te: np.ndarray, *,
                            te_divisions: int) -> np.ndarray:
        lower_te = np.asarray(lower_te, dtype=float)
        upper_te = np.asarray(upper_te, dtype=float)
        if np.allclose(lower_te, upper_te, atol=1.0e-10):
            return lower_te[np.newaxis, :]
        return cls._sample_segment_count(
            lower_te,
            upper_te,
            max(2, int(te_divisions) + 1),
        )

    @staticmethod
    def _polyline_cumulative(points: np.ndarray) -> np.ndarray:
        if len(points) == 0:
            return np.zeros(0, dtype=float)
        deltas = np.diff(points, axis=0)
        segment_lengths = np.linalg.norm(deltas, axis=1)
        return np.concatenate(([0.0], np.cumsum(segment_lengths)))

    @classmethod
    def _resample_polyline_count(cls, points: np.ndarray, count: int) -> np.ndarray:
        cumulative = cls._polyline_cumulative(points)
        if len(cumulative) == 0 or np.isclose(cumulative[-1], 0.0):
            return np.repeat(points[:1], count, axis=0)
        targets = np.linspace(0.0, cumulative[-1], count)
        return cls._sample_polyline_distances(points, targets)

    @classmethod
    def _sample_polyline_distances(cls, points: np.ndarray,
                                   distances: np.ndarray) -> np.ndarray:
        cumulative = cls._polyline_cumulative(points)
        if len(cumulative) == 0 or np.isclose(cumulative[-1], 0.0):
            return np.repeat(points[:1], len(distances), axis=0)
        distances = np.asarray(distances, dtype=float)
        distances = np.clip(distances, 0.0, cumulative[-1])
        x_values = np.interp(distances, cumulative, points[:, 0])
        y_values = np.interp(distances, cumulative, points[:, 1])
        return np.column_stack((x_values, y_values))

    @staticmethod
    def _solve_growth_ratio(length: float, first_spacing: float,
                            segments: int) -> float:
        if segments <= 1 or length <= 0.0 or first_spacing <= 0.0:
            return 1.0

        def series_sum(growth: float) -> float:
            if np.isclose(growth, 1.0):
                return first_spacing * segments
            return first_spacing * (1.0 - growth ** segments) / (1.0 - growth)

        base = series_sum(1.0)
        if np.isclose(base, length, rtol=1.0e-10, atol=1.0e-12):
            return 1.0

        if base > length:
            low = 1.0e-6
            high = 1.0
        else:
            low = 1.0
            high = 2.0
            while series_sum(high) < length and high < 1.0e6:
                high *= 2.0

        for _ in range(120):
            mid = 0.5 * (low + high)
            value = series_sum(mid)
            if value < length:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    @classmethod
    def _geometric_distances(cls, length: float, point_count: int,
                             first_spacing: float) -> np.ndarray:
        if point_count <= 1:
            return np.zeros(1, dtype=float)
        if length <= 0.0:
            return np.zeros(point_count, dtype=float)

        segments = point_count - 1
        growth = cls._solve_growth_ratio(length, first_spacing, segments)
        distances = np.zeros(point_count, dtype=float)
        spacing = float(first_spacing)
        for index in range(1, point_count):
            distances[index] = distances[index - 1] + spacing
            spacing *= growth
        if distances[-1] <= 0.0:
            return np.linspace(0.0, length, point_count)
        return distances * (length / distances[-1])

    @classmethod
    def _sample_segment_with_first_spacing(cls, start: np.ndarray,
                                           end: np.ndarray, count: int,
                                           first_spacing: float) -> np.ndarray:
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        count = max(1, int(count))
        if count == 1:
            return start[np.newaxis, :]

        vector = end - start
        length = float(np.linalg.norm(vector))
        if length <= 0.0:
            return np.repeat(start[np.newaxis, :], count, axis=0)

        distances = cls._geometric_distances(length, count, first_spacing)
        direction = vector / length
        return start + distances[:, np.newaxis] * direction

    @classmethod
    def _sample_segment_count(cls, start: np.ndarray, end: np.ndarray,
                              count: int) -> np.ndarray:
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        length = float(np.linalg.norm(end - start))
        return cls._sample_segment_with_first_spacing(
            start,
            end,
            count,
            first_spacing=(length / max(1, count - 1)) if count > 1 else length,
        )

    @staticmethod
    def _compose_segments(*segments) -> np.ndarray:
        combined = []
        for segment in segments:
            points = np.asarray(segment, dtype=float)
            if points.size == 0:
                continue
            if points.ndim != 2 or points.shape[1] != 2:
                raise ValueError('Boundary segments must be N x 2 point arrays.')
            if not combined:
                combined.append(points)
                continue

            previous = combined[-1][-1]
            if np.allclose(points[0], previous, atol=1.0e-10):
                combined.append(points[1:])
            else:
                combined.append(points)

        if not combined:
            return np.empty((0, 2), dtype=float)
        return np.vstack(combined)

    @classmethod
    def _split_closed_boundary(cls, boundary: np.ndarray) -> list[np.ndarray]:
        if len(boundary) < 5:
            raise ValueError('Experimental O-grid requires at least 4 contour points.')
        if not np.allclose(boundary[0], boundary[-1], atol=1.0e-8):
            raise ValueError('Experimental O-grid requires a closed inner boundary.')

        cumulative = cls._polyline_cumulative(boundary)
        total_length = cumulative[-1]
        unique_count = len(boundary) - 1
        if unique_count < 4:
            raise ValueError('Experimental O-grid requires at least 4 contour points.')

        indices = []
        previous = 0
        targets = (0.25, 0.50, 0.75)
        for offset, fraction in enumerate(targets, start=1):
            index = int(np.searchsorted(cumulative, fraction * total_length))
            minimum = previous + 1
            maximum = unique_count - (len(targets) - offset + 1)
            index = max(minimum, min(index, maximum))
            indices.append(index)
            previous = index

        q1, q2, q3 = indices
        segments = [
            np.asarray(boundary[0:q1 + 1], dtype=float),
            np.asarray(boundary[q1:q2 + 1], dtype=float),
            np.asarray(boundary[q2:q3 + 1], dtype=float),
            np.vstack((boundary[q3:-1], boundary[0])),
        ]

        for segment in segments:
            if len(segment) < 2:
                raise ValueError('Experimental O-grid produced an invalid boundary split.')

        return segments

    @staticmethod
    def _allocate_segment_intervals(total_intervals: int,
                                    lengths: tuple[float, ...] | list[float]
                                    ) -> list[int]:
        weights = np.asarray(lengths, dtype=float)
        weights = np.maximum(weights, 1.0e-12)
        total_intervals = max(len(weights), int(total_intervals))

        base = np.ones(len(weights), dtype=int)
        remaining = total_intervals - int(np.sum(base))
        if remaining <= 0:
            return base.tolist()

        scaled = remaining * weights / float(np.sum(weights))
        additions = np.floor(scaled).astype(int)
        base += additions
        difference = remaining - int(np.sum(additions))

        if difference > 0:
            fractions = scaled - additions
            order = np.argsort(fractions)[::-1]
            for index in range(difference):
                base[order[index % len(order)]] += 1

        return base.tolist()

    @staticmethod
    def _wind_tunnel_outer_lengths(*, radius: float,
                                   wake_length: float) -> tuple[float, float, float, float]:
        horizontal = max(1.0e-6, 1.0 + max(0.0, float(wake_length)))
        left_arc = max(1.0e-6, np.pi * max(1.0e-6, float(radius)))
        right_height = max(1.0e-6, 2.0 * max(1.0e-6, float(radius)))
        return horizontal, left_arc, horizontal, right_height

    @classmethod
    def _build_wind_tunnel_outer_segments(cls, *, radius: float,
                                          wake_length: float,
                                          segment_lengths: list[int]
                                          ) -> list[np.ndarray]:
        if len(segment_lengths) != 4:
            raise ValueError('Experimental O-grid expects four segment lengths.')

        x_right = 1.0 + max(0.0, float(wake_length))
        top_right = np.array((x_right, radius), dtype=float)
        top_left = np.array((0.0, radius), dtype=float)
        bottom_left = np.array((0.0, -radius), dtype=float)
        bottom_right = np.array((x_right, -radius), dtype=float)

        return [
            cls._sample_segment_count(top_right, top_left, segment_lengths[0]),
            cls._sample_half_circle(
                center=np.array((0.0, 0.0), dtype=float),
                radius=radius,
                start_angle=0.5 * np.pi,
                end_angle=1.5 * np.pi,
                count=segment_lengths[1],
            ),
            cls._sample_segment_count(bottom_left, bottom_right, segment_lengths[2]),
            cls._sample_segment_count(bottom_right, top_right, segment_lengths[3]),
        ]

    @classmethod
    def _build_circle_outer_segments(cls, *, radius: float,
                                     segment_lengths: list[int]) -> list[np.ndarray]:
        if len(segment_lengths) != 4:
            raise ValueError('Experimental O-grid expects four segment lengths.')

        center = np.array((0.5, 0.0), dtype=float)
        return [
            cls._sample_half_circle(
                center=center,
                radius=radius,
                start_angle=0.0,
                end_angle=0.5 * np.pi,
                count=segment_lengths[0],
            ),
            cls._sample_half_circle(
                center=center,
                radius=radius,
                start_angle=0.5 * np.pi,
                end_angle=np.pi,
                count=segment_lengths[1],
            ),
            cls._sample_half_circle(
                center=center,
                radius=radius,
                start_angle=np.pi,
                end_angle=1.5 * np.pi,
                count=segment_lengths[2],
            ),
            cls._sample_half_circle(
                center=center,
                radius=radius,
                start_angle=1.5 * np.pi,
                end_angle=2.0 * np.pi,
                count=segment_lengths[3],
            ),
        ]

    @staticmethod
    def _sample_half_circle(center: np.ndarray, radius: float,
                            start_angle: float, end_angle: float,
                            count: int) -> np.ndarray:
        count = max(2, int(count))
        angles = np.linspace(start_angle, end_angle, count)
        center = np.asarray(center, dtype=float)
        return np.column_stack((
            center[0] + radius * np.cos(angles),
            center[1] + radius * np.sin(angles),
        ))

    @classmethod
    def _build_block(cls, inner_segment: np.ndarray, outer_segment: np.ndarray, *,
                     settings: ExperimentalOGridSettings, name: str) -> BlockMesh:
        left_boundary = cls._sample_segment_with_first_spacing(
            inner_segment[0],
            outer_segment[0],
            settings.normal_divisions + 1,
            settings.first_layer_thickness,
        )
        right_boundary = cls._sample_segment_with_first_spacing(
            inner_segment[-1],
            outer_segment[-1],
            settings.normal_divisions + 1,
            settings.first_layer_thickness,
        )

        block = BlockMesh(name=name)
        block.transfinite(
            boundary=[
                inner_segment.tolist(),
                outer_segment.tolist(),
                left_boundary.tolist(),
                right_boundary.tolist(),
            ]
        )

        x_grid, y_grid = cls._ulines_to_grid(block.getULines())
        x_grid, y_grid = cls._refine_block(x_grid, y_grid, settings)
        block.setUlines(cls._grid_to_ulines(x_grid, y_grid))
        return block

    @classmethod
    def _refine_block(cls, x_grid: np.ndarray, y_grid: np.ndarray,
                      settings: ExperimentalOGridSettings
                      ) -> tuple[np.ndarray, np.ndarray]:
        x_grid, y_grid = cls._smooth_grid(
            x_grid,
            y_grid,
            iterations=settings.initial_smoothing_iterations,
            tolerance=settings.smoothing_tolerance,
            relaxation=settings.relaxation,
        )
        x_grid, y_grid = cls._apply_normal_spacing(
            x_grid,
            y_grid,
            first_layer=settings.first_layer_thickness,
        )
        x_grid, y_grid = cls._smooth_grid(
            x_grid,
            y_grid,
            iterations=settings.final_smoothing_iterations,
            tolerance=settings.smoothing_tolerance,
            relaxation=settings.relaxation,
        )
        x_grid, y_grid = cls._apply_normal_spacing(
            x_grid,
            y_grid,
            first_layer=settings.first_layer_thickness,
        )
        return x_grid, y_grid

    @staticmethod
    def _smooth_grid(x_grid: np.ndarray, y_grid: np.ndarray, *,
                     iterations: int, tolerance: float,
                     relaxation: float) -> tuple[np.ndarray, np.ndarray]:
        if iterations <= 0:
            return x_grid, y_grid
        solver = EllipticSolver(x_grid, y_grid)
        return solver.smooth(
            iterations=iterations,
            tolerance=tolerance,
            boundary_condition='neumann',
            relaxation=relaxation,
        )

    @classmethod
    def _apply_normal_spacing(cls, x_grid: np.ndarray, y_grid: np.ndarray, *,
                              first_layer: float) -> tuple[np.ndarray, np.ndarray]:
        spaced_x = np.array(x_grid, copy=True, dtype=float)
        spaced_y = np.array(y_grid, copy=True, dtype=float)
        point_count = x_grid.shape[1]

        for i_index in range(x_grid.shape[0]):
            curve = np.column_stack((x_grid[i_index, :], y_grid[i_index, :]))
            cumulative = cls._polyline_cumulative(curve)
            total_length = cumulative[-1]
            if total_length <= 0.0:
                continue
            targets = cls._geometric_distances(
                total_length,
                point_count,
                min(first_layer, 0.5 * total_length),
            )
            sampled = cls._sample_polyline_distances(curve, targets)
            spaced_x[i_index, :] = sampled[:, 0]
            spaced_y[i_index, :] = sampled[:, 1]

        return spaced_x, spaced_y

    @staticmethod
    def _ulines_to_grid(ulines) -> tuple[np.ndarray, np.ndarray]:
        ny = len(ulines)
        nx = len(ulines[0]) if ulines else 0
        x_grid = np.empty((nx, ny), dtype=float)
        y_grid = np.empty_like(x_grid)

        for j_index, uline in enumerate(ulines):
            coordinates = np.asarray(uline, dtype=float)
            x_grid[:, j_index] = coordinates[:, 0]
            y_grid[:, j_index] = coordinates[:, 1]

        return x_grid, y_grid

    @staticmethod
    def _grid_to_ulines(x_grid: np.ndarray, y_grid: np.ndarray):
        ulines = []
        for j_index in range(x_grid.shape[1]):
            ulines.append([
                (float(x_grid[i_index, j_index]), float(y_grid[i_index, j_index]))
                for i_index in range(x_grid.shape[0])
            ])
        return ulines
