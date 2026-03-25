from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Iterable, Sequence

import numpy as np


Point2D = tuple[float, float]


def _as_point(point: Sequence[float]) -> Point2D:
    if len(point) != 2:
        raise ValueError('Expected a 2D point.')
    return float(point[0]), float(point[1])


def _as_points(points: Iterable[Sequence[float]]) -> list[Point2D]:
    return [_as_point(point) for point in points]


def _resample_points(points: list[Point2D], resolution: int,
                     closed: bool) -> list[Point2D]:
    if resolution <= 0:
        raise ValueError('Resolution must be positive.')
    if len(points) <= 1 or resolution <= len(points):
        return list(points)

    coordinates = np.asarray(points, dtype=float)
    if closed and not np.allclose(coordinates[0], coordinates[-1]):
        coordinates = np.vstack([coordinates, coordinates[0]])

    deltas = np.diff(coordinates, axis=0)
    segment_lengths = np.linalg.norm(deltas, axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])

    if np.isclose(cumulative[-1], 0.0):
        return [tuple(coordinates[0])] * resolution

    targets = np.linspace(0.0, cumulative[-1], resolution)
    x = np.interp(targets, cumulative, coordinates[:, 0])
    y = np.interp(targets, cumulative, coordinates[:, 1])
    return list(zip(x.tolist(), y.tolist()))


class Shape(ABC):
    """Base class for geometry primitives used by the domain layer."""

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @property
    @abstractmethod
    def is_closed(self) -> bool:
        """Whether the shape is intended to be geometrically closed."""

    @abstractmethod
    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        """Return sampled points for the shape."""

    def to_polygon(self, resolution: int | None = None) -> list[Point2D]:
        return self.sample_points(resolution=resolution)

    def as_array(self, resolution: int | None = None) -> np.ndarray:
        return np.asarray(self.to_polygon(resolution=resolution), dtype=float)

    def bounds(self, resolution: int | None = None) -> tuple[float, float, float, float]:
        coordinates = self.as_array(resolution=resolution)
        if coordinates.size == 0:
            raise ValueError('Cannot compute bounds for an empty shape.')
        xmin = float(np.min(coordinates[:, 0]))
        xmax = float(np.max(coordinates[:, 0]))
        ymin = float(np.min(coordinates[:, 1]))
        ymax = float(np.max(coordinates[:, 1]))
        return xmin, xmax, ymin, ymax

    def display(self, resolution: int | None = None) -> list[Point2D]:
        """Return a drawable point representation for GUI adapters."""
        return self.to_polygon(resolution=resolution)


class Line(Shape):
    def __init__(self, p1=None, p2=None, x1=None, y1=None, x2=None, y2=None,
                 coords=None, name: str | None = None):
        super().__init__(name=name)

        if coords is not None:
            if len(coords) != 4:
                raise ValueError(
                    'Provide four values as (x1, y1, x2, y2).'
                )
            x1, y1, x2, y2 = coords
        elif p1 is not None and p2 is not None:
            x1, y1 = p1
            x2, y2 = p2

        if None in (x1, y1, x2, y2):
            raise ValueError(
                'Provide either two points or four coordinates.'
            )

        self.start = _as_point((x1, y1))
        self.end = _as_point((x2, y2))

    @property
    def is_closed(self) -> bool:
        return False

    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        points = [self.start, self.end]
        if resolution is None:
            return points
        return _resample_points(points, resolution=resolution, closed=False)


class Polyline(Shape):
    def __init__(self, vertices: Iterable[Sequence[float]], closed: bool = False,
                 name: str | None = None):
        super().__init__(name=name)
        self.vertices = _as_points(vertices)
        if len(self.vertices) < 2:
            raise ValueError('A polyline needs at least two points.')
        self._is_closed = bool(closed)

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        points = list(self.vertices)
        if self._is_closed and points[0] != points[-1]:
            points.append(points[0])
        if resolution is None:
            return points
        return _resample_points(points, resolution=resolution,
                                closed=self._is_closed)


class Polygon(Polyline):
    def __init__(self, vertices: Iterable[Sequence[float]],
                 name: str | None = None):
        super().__init__(vertices=vertices, closed=True, name=name)


class Rectangle(Polygon):
    def __init__(self, width=None, height=None, center=None, lower_left=None,
                 upper_right=None, name: str | None = None):
        if lower_left is not None and upper_right is not None:
            x1, y1 = _as_point(lower_left)
            x2, y2 = _as_point(upper_right)
            width = x2 - x1
            height = y2 - y1
            center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        elif width is None or height is None or center is None:
            raise ValueError(
                'Provide either (width, height, center) or '
                '(lower_left, upper_right).'
            )

        cx, cy = _as_point(center)
        half_width = float(width) / 2.0
        half_height = float(height) / 2.0
        vertices = [
            (cx - half_width, cy - half_height),
            (cx + half_width, cy - half_height),
            (cx + half_width, cy + half_height),
            (cx - half_width, cy + half_height),
        ]
        super().__init__(vertices=vertices, name=name or 'Rectangle')
        self.width = float(width)
        self.height = float(height)
        self.center = (cx, cy)


class Arc(Shape):
    def __init__(self, center=None, radius=None, start_angle=0.0,
                 end_angle=math.pi, start_point=None, end_point=None,
                 name: str | None = None):
        super().__init__(name=name)

        if center is None:
            raise ValueError('A center point is required.')
        self.center = _as_point(center)

        if radius is not None:
            self.radius = float(radius)
            self.start_angle = self._coerce_angle(start_angle)
            self.end_angle = self._coerce_angle(end_angle)
        elif start_point is not None and end_point is not None:
            start = np.asarray(_as_point(start_point), dtype=float)
            end = np.asarray(_as_point(end_point), dtype=float)
            center_array = np.asarray(self.center, dtype=float)
            self.radius = float(np.linalg.norm(end - start) / 2.0)
            self.start_angle = math.atan2(
                start[1] - center_array[1], start[0] - center_array[0]
            )
            self.end_angle = math.atan2(
                end[1] - center_array[1], end[0] - center_array[0]
            )
        else:
            raise ValueError(
                'Provide either (center, radius, start_angle, end_angle) '
                'or (center, start_point, end_point).'
            )

    @staticmethod
    def _coerce_angle(angle: float) -> float:
        if abs(angle) > 2.0 * math.pi:
            return math.radians(angle)
        return float(angle)

    @property
    def is_closed(self) -> bool:
        return False

    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        resolution = resolution or 100
        if resolution < 2:
            raise ValueError('An arc needs at least two sample points.')
        angles = np.linspace(self.start_angle, self.end_angle, resolution)
        x = self.center[0] + self.radius * np.cos(angles)
        y = self.center[1] + self.radius * np.sin(angles)
        return list(zip(x.tolist(), y.tolist()))


class Circle(Arc):
    def __init__(self, center=None, radius=None, diameter=None,
                 name: str | None = None):
        if center is None:
            raise ValueError('A center point is required.')
        if radius is None and diameter is None:
            raise ValueError('Provide either a radius or a diameter.')
        if radius is None:
            radius = float(diameter) / 2.0
        super().__init__(
            center=center,
            radius=radius,
            start_angle=0.0,
            end_angle=2.0 * math.pi,
            name=name or 'Circle',
        )

    @property
    def is_closed(self) -> bool:
        return True

    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        points = super().sample_points(resolution=resolution or 180)
        if points[0] != points[-1]:
            points.append(points[0])
        return points


class Spline(Shape):
    """Polyline-based spline placeholder for the rewrite scaffolding."""

    def __init__(self, points: Iterable[Sequence[float]] | tuple[Sequence[float], Sequence[float]],
                 closed: bool = False, name: str | None = None):
        super().__init__(name=name)

        if isinstance(points, tuple) and len(points) == 2:
            x_values, y_values = points
            points = list(zip(x_values, y_values))

        self.points = _as_points(points)
        if len(self.points) < 2:
            raise ValueError('A spline needs at least two support points.')
        self._is_closed = bool(closed)

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    def sample_points(self, resolution: int | None = None) -> list[Point2D]:
        points = list(self.points)
        if self._is_closed and points[0] != points[-1]:
            points.append(points[0])
        if resolution is None:
            return points
        return _resample_points(points, resolution=resolution,
                                closed=self._is_closed)
