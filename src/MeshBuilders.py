from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
from scipy import interpolate


def _to_point_tuple(point) -> tuple[float, float]:
    return float(point[0]), float(point[1])


@dataclass(slots=True)
class AirfoilBlockSettings:
    name: str = 'block_airfoil'
    divisions: int = 15
    growth: float = 3.0
    thickness: float = 0.04


@dataclass(slots=True)
class TrailingEdgeBlockSettings:
    name: str = 'block_TE'
    trailing_edge_divisions: int = 3
    thickness: float = 0.04
    divisions: int = 10
    growth: float = 1.05


@dataclass(slots=True)
class TunnelBlockSettings:
    name: str = 'block_tunnel'
    tunnel_height: float = 2.0
    divisions_height: int = 100
    height_growth: float = 10.0
    distribution: str = 'symmetric'
    smoothing_algorithm: str = 'simple'
    smoothing_iterations: int = 10
    smoothing_tolerance: float = 1.0e-3


@dataclass(slots=True)
class WakeBlockSettings:
    name: str = 'block_tunnel_wake'
    tunnel_wake: float = 2.0
    divisions: int = 100
    growth: float = 0.1
    spread: float = 0.4


class LegacyBlockMeshBuilder:
    """Reusable builders around the legacy BlockMesh implementation."""

    c_curve_segment_samples = 10
    c_curve_arc_samples = 200
    side_transition_span = 30
    chord_length = 1.0

    def __init__(self, block_mesh_cls, create_smoother):
        self.block_mesh_cls = block_mesh_cls
        self.create_smoother = create_smoother

    def build_airfoil_block(self, contour,
                            settings: AirfoilBlockSettings):
        if contour is None:
            raise ValueError('Airfoil contour data is required before building the airfoil block.')

        x, y = contour
        line = list(zip(x, y))
        block = self.block_mesh_cls(name=settings.name)
        block.addLine(line)
        block.extrudeLine_cell_thickness(
            line,
            cell_thickness=settings.thickness,
            growth=settings.growth,
            divisions=settings.divisions,
            direction=3,
        )
        return block

    def build_trailing_edge_block(self, airfoil_block, has_trailing_edge: bool,
                                  settings: TrailingEdgeBlockSettings):
        if airfoil_block is None:
            raise ValueError('Airfoil block is required before building the trailing edge block.')

        line = self._compose_trailing_edge_line(
            airfoil_block,
            has_trailing_edge=has_trailing_edge,
            trailing_edge_divisions=settings.trailing_edge_divisions,
        )
        block = self.block_mesh_cls(name=settings.name)
        block.addLine(line)
        block.extrudeLine_cell_thickness(
            line,
            cell_thickness=settings.thickness,
            growth=settings.growth,
            divisions=settings.divisions,
            direction=4,
        )
        block.distribute(direction='u', number=-1)
        block.transfinite()
        return block

    def build_tunnel_block(self, airfoil_block, trailing_edge_block,
                           settings: TunnelBlockSettings):
        if airfoil_block is None or trailing_edge_block is None:
            raise ValueError('Airfoil and trailing edge blocks are required before building the tunnel block.')

        inner_line = self._compose_tunnel_inner_line(
            trailing_edge_block,
            airfoil_block,
        )
        block = self.block_mesh_cls(name=settings.name)
        block.addLine(inner_line)
        block.addLine(
            self._build_tunnel_outer_curve(
                inner_line=inner_line,
                tunnel_height=settings.tunnel_height,
                distribution=settings.distribution,
            )
        )

        upper_start = np.array(
            (block.getULines()[0][0][0], settings.tunnel_height),
            dtype=float,
        )
        lower_end = np.array(
            (block.getULines()[0][-1][0], -settings.tunnel_height),
            dtype=float,
        )
        first_inner = np.array(block.getULines()[0][0], dtype=float)
        last_inner = np.array(block.getULines()[0][-1], dtype=float)

        left = self.block_mesh_cls.makeLine(
            first_inner,
            upper_start,
            divisions=settings.divisions_height,
            ratio=settings.height_growth,
        )
        right = self.block_mesh_cls.makeLine(
            last_inner,
            lower_end,
            divisions=settings.divisions_height,
            ratio=settings.height_growth,
        )

        block.transfinite(
            boundary=[
                block.getULines()[0],
                block.getULines()[-1],
                left,
                right,
            ]
        )

        blended_block = self.block_mesh_cls(name=settings.name)
        for uline in self._blend_tunnel_lines(block):
            blended_block.addLine(uline)

        self._apply_tunnel_side_interpolation(blended_block)

        smoother = self.create_smoother(settings.smoothing_algorithm)
        return smoother.smooth(
            blended_block,
            iterations=settings.smoothing_iterations,
            tolerance=settings.smoothing_tolerance,
        )

    def build_wake_block(self, tunnel_block, trailing_edge_block,
                         tunnel_height: float,
                         settings: WakeBlockSettings):
        if tunnel_block is None or trailing_edge_block is None:
            raise ValueError('Tunnel and trailing edge blocks are required before building the wake block.')
        if tunnel_height is None:
            raise ValueError('Tunnel height must be known before building the wake block.')

        block = self.block_mesh_cls(name=settings.name)
        inner_line = self._compose_wake_inner_line(
            tunnel_block,
            trailing_edge_block,
        )
        block.addLine(inner_line)

        upper_start = np.array(
            (trailing_edge_block.getULines()[-1][0][0], tunnel_height),
            dtype=float,
        )
        lower_start = np.array(
            (trailing_edge_block.getULines()[-1][-1][0], -tunnel_height),
            dtype=float,
        )
        upper_end = np.array(
            (settings.tunnel_wake + self.chord_length, tunnel_height),
            dtype=float,
        )
        lower_end = np.array(
            (settings.tunnel_wake + self.chord_length, -tunnel_height),
            dtype=float,
        )

        upper = self.block_mesh_cls.makeLine(
            upper_end,
            upper_start,
            divisions=settings.divisions,
            ratio=1.0 / settings.growth,
        )
        lower = self.block_mesh_cls.makeLine(
            lower_end,
            lower_start,
            divisions=settings.divisions,
            ratio=1.0 / settings.growth,
        )
        right = self.block_mesh_cls.makeLine(
            lower_end,
            upper_end,
            divisions=len(inner_line) - 1,
            ratio=1.0,
        )

        block.transfinite(boundary=[upper, lower, right, inner_line])

        split_line = self._find_wake_split_line(
            block.getULines()[0],
            wake_length=settings.tunnel_wake,
            spread=settings.spread,
        )
        block.distribute(direction='v', number=split_line)

        vline_count = len(block.getVLines())
        uline_count = len(block.getULines())
        block.transfinite(
            ij=[vline_count + split_line, vline_count - 1, 0, uline_count - 1]
        )
        block.transfinite(
            ij=[0, vline_count + split_line, 0, uline_count - 1]
        )
        return block

    def _compose_trailing_edge_line(self, airfoil_block, has_trailing_edge: bool,
                                    trailing_edge_divisions: int):
        first = airfoil_block.getLine(number=0, direction='v')
        last = airfoil_block.getLine(number=-1, direction='v')
        first = copy.deepcopy(first)
        last_reversed = copy.deepcopy(last)
        last_reversed.reverse()

        line = copy.deepcopy(last_reversed)
        if has_trailing_edge:
            vector = np.array(first[0], dtype=float) - np.array(last[0], dtype=float)
            for index in range(1, trailing_edge_divisions):
                point = last_reversed[-1] + float(index) / trailing_edge_divisions * vector
                line.append(_to_point_tuple(point))
            line += first
        else:
            line += first[1:]
        return line

    def _compose_tunnel_inner_line(self, trailing_edge_block, airfoil_block):
        line = copy.deepcopy(trailing_edge_block.getVLines()[-1])
        line.reverse()
        del line[-1]
        line += copy.deepcopy(airfoil_block.getULines()[-1])
        del line[-1]
        line += copy.deepcopy(trailing_edge_block.getVLines()[0])
        return line

    def _build_tunnel_outer_curve(self, inner_line, tunnel_height: float,
                                  distribution: str):
        p1 = np.array((inner_line[0][0], tunnel_height), dtype=float)
        p2 = np.array((0.0, tunnel_height), dtype=float)
        p3 = np.array((0.0, -tunnel_height), dtype=float)
        p4 = np.array((inner_line[-1][0], -tunnel_height), dtype=float)

        line = self._sample_segment(
            p1, p2, self.c_curve_segment_samples, include_last=False
        )
        line += self._sample_half_circle(
            radius=tunnel_height,
            start_degrees=90.0,
            end_degrees=270.0,
            samples=self.c_curve_arc_samples,
            include_last=False,
        )
        line += self._sample_segment(
            p3, p4, self.c_curve_segment_samples, include_last=True
        )

        curve = np.asarray(line, dtype=float)
        tck, _ = interpolate.splprep(curve.T, s=0, k=1)
        lower, upper = self._distribution_interval(distribution)
        xx = np.linspace(lower, upper, len(inner_line))
        t = (np.tanh(xx) + 1.0) / 2.0
        xs, ys = interpolate.splev(t, tck, der=0)
        return list(zip(xs.tolist(), ys.tolist()))

    def _blend_tunnel_lines(self, block):
        old_ulines = copy.deepcopy(block.getULines())
        line_count = len(old_ulines)
        x_inner, y_inner = list(zip(*old_ulines[0]))
        normals = self.block_mesh_cls.curveNormals(
            np.asarray(x_inner, dtype=float),
            np.asarray(y_inner, dtype=float),
        )

        blended_lines = []
        for j, uline in enumerate(old_ulines):
            if j == 0 or j == line_count - 1:
                blended_lines.append(uline)
                continue

            blended = []
            for i, point in enumerate(uline):
                if i == 0 or i == len(uline) - 1:
                    blended.append(point)
                    continue

                outer_point = np.array(point, dtype=float)
                inner_point = np.array(old_ulines[0][i], dtype=float)
                normal = normals[i]
                offset = outer_point - inner_point
                distance = np.dot(offset, normal) / np.linalg.norm(normal)
                projected = inner_point + distance * normal
                blend = float(j) / float(line_count)
                exponent = 0.6
                new_point = (1.0 - blend**exponent) * projected + \
                    blend**exponent * outer_point
                blended.append(_to_point_tuple(new_point))

            blended_lines.append(blended)

        return blended_lines

    def _apply_tunnel_side_interpolation(self, block):
        vline_count = len(block.getVLines())
        uline_count = len(block.getULines())
        side_span = min(self.side_transition_span, vline_count - 1)
        if side_span <= 0:
            return

        block.transfinite(ij=[0, side_span, 0, uline_count - 1])
        block.transfinite(
            ij=[vline_count - side_span - 1, vline_count - 1, 0, uline_count - 1]
        )

    def _compose_wake_inner_line(self, tunnel_block, trailing_edge_block):
        line = copy.deepcopy(tunnel_block.getVLines()[-1])
        line.reverse()
        del line[-1]
        line += copy.deepcopy(trailing_edge_block.getULines()[-1])
        del line[-1]
        line += copy.deepcopy(tunnel_block.getVLines()[0])
        return line

    def _find_wake_split_line(self, line, wake_length: float, spread: float):
        threshold = self.chord_length + wake_length * spread
        line_length = len(line)
        for index, point in enumerate(line):
            if point[0] < threshold:
                return index - line_length
        return -(line_length // 2)

    @staticmethod
    def _distribution_interval(distribution: str):
        intervals = {
            'symmetric': (-1.3, 1.3),
            'lower': (-1.2, 1.5),
            'upper': (-1.5, 1.2),
        }
        return intervals.get(distribution, intervals['symmetric'])

    @staticmethod
    def _sample_segment(start, end, samples: int, include_last: bool):
        vector = end - start
        points = []
        for parameter in np.linspace(0.0, 1.0, samples):
            points.append(_to_point_tuple(start + parameter * vector))
        if not include_last and points:
            points.pop()
        return points

    @staticmethod
    def _sample_half_circle(radius: float, start_degrees: float,
                            end_degrees: float, samples: int,
                            include_last: bool):
        points = []
        for angle in np.linspace(start_degrees, end_degrees, samples):
            radians = np.radians(angle)
            points.append(
                (
                    float(radius * np.cos(radians)),
                    float(radius * np.sin(radians)),
                )
            )
        if not include_last and points:
            points.pop()
        return points
