from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from BlockMesh import BlockMesh
from Elliptic import EllipticSolver


@dataclass(slots=True)
class ExperimentalCGridSettings:
    name: str = 'block_experimental_c_grid'
    surface_points: int = 0
    normal_divisions: int = 100
    first_layer_thickness: float = 0.004
    wake_points: int = 75
    farfield_wake_length_ratio: float = 1.0
    farfield_wake_start_ratio: float = 10.0
    initial_smoothing_iterations: int = 100
    final_smoothing_iterations: int = 20
    local_te_smoothing_iterations: int = 10
    smoothing_tolerance: float = 1.0e-5
    relaxation: float = 0.6
    orthogonal_control_length: float = 0.5

    def __post_init__(self):
        self.surface_points = max(0, int(self.surface_points))
        self.normal_divisions = max(4, int(self.normal_divisions))
        self.first_layer_thickness = max(1.0e-12, float(self.first_layer_thickness))
        self.wake_points = max(4, int(self.wake_points))
        self.farfield_wake_length_ratio = float(
            np.clip(self.farfield_wake_length_ratio, 0.05, 1.0)
        )
        self.farfield_wake_start_ratio = max(
            1.0,
            float(self.farfield_wake_start_ratio),
        )
        self.initial_smoothing_iterations = max(
            0,
            int(self.initial_smoothing_iterations),
        )
        self.final_smoothing_iterations = max(
            0,
            int(self.final_smoothing_iterations),
        )
        self.local_te_smoothing_iterations = max(
            0,
            int(self.local_te_smoothing_iterations),
        )
        self.smoothing_tolerance = max(1.0e-12, float(self.smoothing_tolerance))
        self.relaxation = float(np.clip(self.relaxation, 0.01, 1.0))
        self.orthogonal_control_length = max(
            1.0e-6,
            float(self.orthogonal_control_length),
        )


class ExperimentalCGridGenerator:
    """Experimental C-grid generator with sharp- and finite-TE paths."""

    cut_interface_scale = 0.15

    def build_block(self, contour, *, radius: float, wake_length: float,
                    settings: ExperimentalCGridSettings) -> BlockMesh:
        contour_points = self._prepare_contour(
            contour,
            settings.surface_points,
            closed=True,
        )
        reference_te_x = self._reference_trailing_edge_x(contour_points)
        te_spacing = self._trailing_edge_spacing(contour_points)
        upper_wake, lower_wake = self._build_wake_branches(
            start_point=contour_points[0],
            end_point=contour_points[-1],
            reference_te_x=reference_te_x,
            wake_length=float(wake_length),
            point_count=settings.wake_points,
            first_spacing=te_spacing,
        )
        inner_boundary = self._compose_inner_boundary(
            contour_points,
            upper_wake,
            lower_wake,
        )
        outer_boundary = self._build_outer_boundary(
            reference_te_x=reference_te_x,
            radius=float(radius),
            wake_length=float(wake_length),
            upper_points=len(upper_wake),
            middle_points=len(contour_points),
            lower_points=len(lower_wake),
            te_spacing=te_spacing,
            wake_length_ratio=settings.farfield_wake_length_ratio,
            wake_start_ratio=settings.farfield_wake_start_ratio,
        )
        x_grid, y_grid = self._build_algebraic_grid(
            inner_boundary,
            outer_boundary,
            point_count=settings.normal_divisions + 1,
            control_length=settings.orthogonal_control_length,
        )
        x_grid, y_grid = self._refine_outer_grid(x_grid, y_grid, settings)
        return self._arrays_to_block(x_grid, y_grid, settings.name)

    def build_blunt_blocks(self, contour, *, radius: float, wake_length: float,
                           settings: ExperimentalCGridSettings,
                           trailing_edge_settings) -> list[BlockMesh]:
        contour_points = self._prepare_contour(
            contour,
            settings.surface_points,
            closed=False,
        )
        reference_te_x = self._reference_trailing_edge_x(contour_points)
        te_spacing = self._trailing_edge_spacing(contour_points)

        te_block = self._build_trailing_edge_patch(
            contour_points,
            trailing_edge_settings,
            name=f'{settings.name}_te_patch',
        )
        upper_side, lower_side = self._extract_patch_side_lines(
            te_block,
            contour_points,
        )
        downstream_face = self._extract_downstream_face(
            te_block,
            upper_side[-1],
            lower_side[-1],
        )
        cut_line = self._build_cut_line(
            downstream_face,
            reference_te_x=reference_te_x,
            wake_length=float(wake_length),
            first_layer=settings.first_layer_thickness,
        )

        upper_wake, lower_wake = self._build_wake_branches(
            start_point=downstream_face[0],
            end_point=downstream_face[-1],
            reference_te_x=reference_te_x,
            wake_length=float(wake_length),
            point_count=settings.wake_points,
            first_spacing=te_spacing,
            cut_line=cut_line,
        )

        surface_path = self._compose_segments(
            upper_side[::-1],
            contour_points,
            lower_side,
        )
        inner_boundary = self._compose_inner_boundary(
            surface_path,
            upper_wake,
            lower_wake,
        )
        outer_boundary = self._build_outer_boundary(
            reference_te_x=reference_te_x,
            radius=float(radius),
            wake_length=float(wake_length),
            upper_points=len(upper_wake),
            middle_points=len(surface_path),
            lower_points=len(lower_wake),
            te_spacing=te_spacing,
            wake_length_ratio=settings.farfield_wake_length_ratio,
            wake_start_ratio=settings.farfield_wake_start_ratio,
        )

        left_boundary = BlockMesh.makeLine(
            cut_line[0],
            outer_boundary[0],
            divisions=settings.normal_divisions,
            ratio=1.0,
        )
        right_boundary = BlockMesh.makeLine(
            cut_line[-1],
            outer_boundary[-1],
            divisions=settings.normal_divisions,
            ratio=1.0,
        )
        x_outer, y_outer = self._build_transfinite_grid(
            inner_boundary,
            outer_boundary,
            left_boundary,
            right_boundary,
        )
        x_outer, y_outer = self._refine_outer_grid(x_outer, y_outer, settings)

        wake_bridge = self._build_wake_bridge_block(
            downstream_face,
            cut_line,
            upper_wake,
            lower_wake,
            name=f'{settings.name}_wake_bridge',
            settings=settings,
        )

        return [
            te_block,
            wake_bridge,
            self._arrays_to_block(x_outer, y_outer, settings.name),
        ]

    @staticmethod
    def _prepare_contour(contour, surface_points: int, *,
                         closed: bool | None = None) -> np.ndarray:
        points = np.column_stack(contour).astype(float, copy=False)
        if points.ndim != 2 or points.shape[1] != 2 or len(points) < 4:
            raise ValueError('Experimental C-grid requires a valid 2D contour.')

        is_closed = np.allclose(points[0], points[-1], atol=1.0e-8)
        if closed is True and not is_closed:
            raise ValueError(
                'Experimental C-grid currently requires a sharp trailing edge.'
            )
        if closed is False and is_closed:
            raise ValueError(
                'Finite trailing-edge experimental meshing requires an open contour.'
            )

        if surface_points > 0 and surface_points != len(points):
            points = ExperimentalCGridGenerator._resample_polyline_count(
                points,
                surface_points,
            )
            if is_closed:
                points[-1] = points[0]

        return points

    @staticmethod
    def _reference_trailing_edge_x(contour_points: np.ndarray) -> float:
        return float(max(contour_points[0, 0], contour_points[-1, 0]))

    @staticmethod
    def _trailing_edge_spacing(contour_points: np.ndarray) -> float:
        upper = np.linalg.norm(contour_points[1] - contour_points[0])
        lower = np.linalg.norm(contour_points[-2] - contour_points[-1])
        spacing = 0.5 * (float(upper) + float(lower))
        return max(spacing, 1.0e-6)

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
    def _build_wake_branch(cls, start_point: np.ndarray, end_point: np.ndarray,
                           point_count: int, first_spacing: float) -> np.ndarray:
        return cls._sample_segment_with_first_spacing(
            start_point,
            end_point,
            point_count,
            first_spacing,
        )

    @classmethod
    def _build_wake_branches(cls, start_point: np.ndarray, end_point: np.ndarray,
                             reference_te_x: float, wake_length: float,
                             point_count: int, first_spacing: float,
                             cut_line: np.ndarray | None = None,
                             ) -> tuple[np.ndarray, np.ndarray]:
        if cut_line is None:
            cut_x = float(reference_te_x) + max(0.0, float(wake_length))
            cut_upper = np.array((cut_x, 0.0), dtype=float)
            cut_lower = np.array((cut_x, 0.0), dtype=float)
        else:
            cut_points = np.asarray(cut_line, dtype=float)
            cut_upper = np.array(cut_points[0], copy=True, dtype=float)
            cut_lower = np.array(cut_points[-1], copy=True, dtype=float)

        upper = cls._build_wake_branch(
            np.asarray(start_point, dtype=float),
            cut_upper,
            point_count,
            first_spacing,
        )
        lower = cls._build_wake_branch(
            np.asarray(end_point, dtype=float),
            cut_lower,
            point_count,
            first_spacing,
        )
        return upper, lower

    @classmethod
    def _compose_inner_boundary(cls, surface_path: np.ndarray,
                                upper_wake: np.ndarray,
                                lower_wake: np.ndarray) -> np.ndarray:
        return cls._compose_segments(
            upper_wake[::-1],
            surface_path,
            lower_wake,
        )

    @classmethod
    def _build_outer_middle_boundary(cls, start_x: float, radius: float,
                                     point_count: int) -> np.ndarray:
        start_x = max(0.5, float(start_x))
        radius = max(1.0e-6, float(radius))

        top_straight = np.array(
            [
                (start_x, radius),
                (0.5, radius),
            ],
            dtype=float,
        )
        arc_angles = np.linspace(0.5 * np.pi, 1.5 * np.pi, 256)
        arc = np.column_stack((
            0.5 + radius * np.cos(arc_angles),
            radius * np.sin(arc_angles),
        ))
        bottom_straight = np.array(
            [
                (0.5, -radius),
                (start_x, -radius),
            ],
            dtype=float,
        )
        path = np.vstack((
            top_straight[:-1],
            arc[:-1],
            bottom_straight,
        ))
        return cls._resample_polyline_count(path, point_count)

    @classmethod
    def _build_outer_boundary(cls, reference_te_x: float, radius: float,
                              wake_length: float, upper_points: int,
                              middle_points: int, lower_points: int,
                              te_spacing: float, wake_length_ratio: float,
                              wake_start_ratio: float) -> np.ndarray:
        cut_x = float(reference_te_x) + max(0.0, float(wake_length))
        outer_start_x = cut_x - wake_length_ratio * max(0.0, float(wake_length))
        outer_start_x = max(0.55, min(cut_x, outer_start_x))
        outer_spacing = max(1.0e-6, te_spacing * wake_start_ratio)

        upper = cls._sample_segment_with_first_spacing(
            np.array((outer_start_x, radius), dtype=float),
            np.array((cut_x, radius), dtype=float),
            upper_points,
            outer_spacing,
        )[::-1]
        middle = cls._build_outer_middle_boundary(
            outer_start_x,
            radius,
            middle_points,
        )
        lower = cls._sample_segment_with_first_spacing(
            np.array((outer_start_x, -radius), dtype=float),
            np.array((cut_x, -radius), dtype=float),
            lower_points,
            outer_spacing,
        )
        return cls._compose_segments(upper, middle, lower)

    @staticmethod
    def _build_algebraic_grid(inner_boundary: np.ndarray, outer_boundary: np.ndarray,
                              point_count: int,
                              control_length: float) -> tuple[np.ndarray, np.ndarray]:
        boundary_normals = BlockMesh.curveNormals(
            inner_boundary[:, 0],
            inner_boundary[:, 1],
            closed=False,
        )
        distances = np.linalg.norm(outer_boundary - inner_boundary, axis=1)
        controls = inner_boundary + (
            np.minimum(control_length, 0.35 * np.maximum(distances, 1.0e-6))
        )[:, np.newaxis] * boundary_normals

        parameters = np.linspace(0.0, 1.0, point_count)
        x_grid = np.empty((len(inner_boundary), point_count), dtype=float)
        y_grid = np.empty_like(x_grid)

        for index, eta in enumerate(parameters):
            omt = 1.0 - eta
            curve = (
                (omt * omt) * inner_boundary +
                2.0 * omt * eta * controls +
                (eta * eta) * outer_boundary
            )
            x_grid[:, index] = curve[:, 0]
            y_grid[:, index] = curve[:, 1]

        return x_grid, y_grid

    @classmethod
    def _build_transfinite_grid(cls, inner_boundary: np.ndarray,
                                outer_boundary: np.ndarray,
                                left_boundary, right_boundary
                                ) -> tuple[np.ndarray, np.ndarray]:
        seed = BlockMesh(name='experimental_c_grid_seed')
        seed.transfinite(
            boundary=[
                inner_boundary.tolist(),
                np.asarray(outer_boundary, dtype=float).tolist(),
                np.asarray(left_boundary, dtype=float).tolist(),
                np.asarray(right_boundary, dtype=float).tolist(),
            ]
        )
        return cls._ulines_to_grid(seed.getULines())

    @staticmethod
    def _smooth_grid(x_grid: np.ndarray, y_grid: np.ndarray, *,
                     iterations: int, tolerance: float,
                     relaxation: float,
                     boundary_condition: str | None = 'neumann'
                     ) -> tuple[np.ndarray, np.ndarray]:
        if iterations <= 0:
            return x_grid, y_grid
        solver = EllipticSolver(x_grid, y_grid)
        return solver.smooth(
            iterations=iterations,
            tolerance=tolerance,
            boundary_condition=boundary_condition,
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

    @classmethod
    def _refine_outer_grid(cls, x_grid: np.ndarray, y_grid: np.ndarray,
                           settings: ExperimentalCGridSettings
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

    @classmethod
    def _build_trailing_edge_patch(cls, contour_points: np.ndarray,
                                   trailing_edge_settings, *,
                                   name: str) -> BlockMesh:
        upper_te = np.asarray(contour_points[0], dtype=float)
        lower_te = np.asarray(contour_points[-1], dtype=float)
        count = max(2, int(trailing_edge_settings.trailing_edge_divisions) + 1)

        line = cls._sample_segment_count(lower_te, upper_te, count)
        tangents = np.diff(line, axis=0)
        average_tangent = np.mean(tangents, axis=0)
        normal = np.array((average_tangent[1], -average_tangent[0]), dtype=float)
        if normal[0] < 0.0:
            line = line[::-1]

        block = BlockMesh(name=name)
        block.addLine(line.tolist())
        block.extrudeLine_cell_thickness(
            line.tolist(),
            cell_thickness=trailing_edge_settings.thickness,
            growth=trailing_edge_settings.growth,
            divisions=trailing_edge_settings.divisions,
            direction=4,
        )
        block.distribute(direction='u', number=-1)
        block.transfinite()
        return block

    @staticmethod
    def _orient_line_to_start(line: np.ndarray, start_point: np.ndarray) -> np.ndarray:
        line = np.asarray(line, dtype=float)
        start_point = np.asarray(start_point, dtype=float)
        if np.linalg.norm(line[0] - start_point) <= np.linalg.norm(line[-1] - start_point):
            return line
        return line[::-1]

    @classmethod
    def _extract_patch_side_lines(cls, te_block: BlockMesh,
                                  contour_points: np.ndarray
                                  ) -> tuple[np.ndarray, np.ndarray]:
        vlines = [
            np.asarray(vline, dtype=float)
            for vline in te_block.getVLines()
        ]
        upper_side = max(vlines, key=lambda line: float(np.mean(line[:, 1])))
        lower_side = min(vlines, key=lambda line: float(np.mean(line[:, 1])))
        upper_side = cls._orient_line_to_start(upper_side, contour_points[0])
        lower_side = cls._orient_line_to_start(lower_side, contour_points[-1])
        return upper_side, lower_side

    @classmethod
    def _extract_downstream_face(cls, te_block: BlockMesh,
                                 downstream_upper: np.ndarray,
                                 downstream_lower: np.ndarray) -> np.ndarray:
        downstream_face = np.asarray(te_block.getULines()[-1], dtype=float)
        downstream_face = cls._orient_line_to_start(
            downstream_face,
            downstream_upper,
        )
        if np.linalg.norm(downstream_face[-1] - downstream_lower) > \
                np.linalg.norm(downstream_face[0] - downstream_lower):
            downstream_face = downstream_face[::-1]
        return downstream_face

    @classmethod
    def _build_cut_line(cls, downstream_face: np.ndarray, *,
                        reference_te_x: float, wake_length: float,
                        first_layer: float) -> np.ndarray:
        cut_x = float(reference_te_x) + max(0.0, float(wake_length))
        center_y = 0.5 * float(downstream_face[0, 1] + downstream_face[-1, 1])
        offsets = downstream_face[:, 1] - center_y
        offset_extent = float(np.max(np.abs(offsets)))
        if offset_extent <= 1.0e-12:
            target_half_height = max(1.0e-6, float(first_layer))
            cut_y = np.linspace(
                center_y + target_half_height,
                center_y - target_half_height,
                len(downstream_face),
            )
        else:
            target_half_height = max(
                float(first_layer),
                cls.cut_interface_scale * offset_extent,
            )
            scale = min(1.0, target_half_height / offset_extent)
            cut_y = center_y + scale * offsets

        return np.column_stack((
            np.full(len(downstream_face), cut_x, dtype=float),
            cut_y,
        ))

    @classmethod
    def _build_wake_bridge_block(cls, downstream_face: np.ndarray,
                                 cut_line: np.ndarray,
                                 upper_wake: np.ndarray,
                                 lower_wake: np.ndarray, *,
                                 name: str,
                                 settings: ExperimentalCGridSettings
                                 ) -> BlockMesh:
        block = BlockMesh(name=name)
        block.transfinite(
            boundary=[
                downstream_face.tolist(),
                cut_line.tolist(),
                upper_wake.tolist(),
                lower_wake.tolist(),
            ]
        )

        bridge_iterations = settings.local_te_smoothing_iterations
        if bridge_iterations > 0:
            x_grid, y_grid = cls._ulines_to_grid(block.getULines())
            x_grid, y_grid = cls._smooth_grid(
                x_grid,
                y_grid,
                iterations=bridge_iterations,
                tolerance=settings.smoothing_tolerance,
                relaxation=settings.relaxation,
                boundary_condition=None,
            )
            block.setUlines(cls._grid_to_ulines(x_grid, y_grid))
        return block

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

    @classmethod
    def _arrays_to_block(cls, x_grid: np.ndarray, y_grid: np.ndarray,
                         name: str) -> BlockMesh:
        block = BlockMesh(name=name)
        block.setUlines(cls._grid_to_ulines(x_grid, y_grid))
        return block

    @staticmethod
    def _grid_to_ulines(x_grid: np.ndarray, y_grid: np.ndarray):
        ulines = []
        for j_index in range(x_grid.shape[1]):
            ulines.append([
                (float(x_grid[i_index, j_index]), float(y_grid[i_index, j_index]))
                for i_index in range(x_grid.shape[0])
            ])
        return ulines
