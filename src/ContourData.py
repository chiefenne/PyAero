from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(slots=True)
class SplineData:
    coordinates: tuple[Any, Any]
    fit_parameters: Any
    sample_parameters: Any
    first_derivative: tuple[Any, Any]
    second_derivative: tuple[Any, Any]
    spline: Any

    @property
    def point_count(self) -> int:
        return len(self.coordinates[0])


@dataclass(slots=True)
class CurvatureData:
    gradient: Any
    curvature: Any
    radius: Any
    center_x: Any
    center_y: Any

    def series(self, quantity: str):
        selector = {
            'gradient': self.gradient,
            'curvature': self.curvature,
            'radius': self.radius,
        }
        try:
            return selector[quantity]
        except KeyError as error:
            raise ValueError(f'Unsupported contour quantity: {quantity}') from error


@dataclass(slots=True)
class CamberData:
    method: str
    coordinates: tuple[Any, Any]
    radius: Any
    upper_contact: tuple[Any, Any]
    lower_contact: tuple[Any, Any]
    upper_parameters: Any
    lower_parameters: Any
    display_indices: Any
    valid: Any
    fallback_used: Any

    @property
    def point_count(self) -> int:
        return len(self.coordinates[0])

    @property
    def display_count(self) -> int:
        return len(self.display_indices)

    def display_coordinates(self):
        return (
            self.coordinates[0][self.display_indices],
            self.coordinates[1][self.display_indices],
        )

    def polyline_coordinates(self, start_at_le_tangency: bool = True):
        if not start_at_le_tangency or self.point_count == 0:
            return self.coordinates

        x_start = 0.5 * (
            self.upper_contact[0][0] + self.lower_contact[0][0]
        )
        y_start = 0.5 * (
            self.upper_contact[1][0] + self.lower_contact[1][0]
        )

        if self.point_count == 1:
            return (
                self.coordinates[0][:1] * 0.0 + x_start,
                self.coordinates[1][:1] * 0.0 + y_start,
            )

        start_index = 1
        first_center = np.array(
            (self.coordinates[0][0], self.coordinates[1][0]),
            dtype=float,
        )
        start_point = np.array((x_start, y_start), dtype=float)
        first_radius = float(self.radius[0])

        if first_radius > 0.0 and np.linalg.norm(first_center - start_point) > 1.0e-9:
            centers = np.column_stack(self.coordinates)
            distances = np.linalg.norm(centers - first_center, axis=1)
            threshold = max(first_radius * 1.02, first_radius + 1.0e-6)
            outside = np.flatnonzero(distances > threshold)
            outside = outside[outside > 0]
            if outside.size:
                start_index = int(outside[0])

        x_coordinates = np.concatenate((
            np.array((x_start,), dtype=float),
            self.coordinates[0][start_index:],
        ))
        y_coordinates = np.concatenate((
            np.array((y_start,), dtype=float),
            self.coordinates[1][start_index:],
        ))
        return x_coordinates, y_coordinates

    def display_radius(self):
        return self.radius[self.display_indices]

    def display_upper_contact(self):
        return (
            self.upper_contact[0][self.display_indices],
            self.upper_contact[1][self.display_indices],
        )

    def display_lower_contact(self):
        return (
            self.lower_contact[0][self.display_indices],
            self.lower_contact[1][self.display_indices],
        )
