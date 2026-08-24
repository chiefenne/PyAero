from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


MINIMUM_MONITOR_VALUE = 1.0e-12


def _as_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(points, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError('Monitor points must be an N x 2 array.')
    return array


def _as_positive_values(values, name: str, minimum_value: float) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError(f'{name} must be a 1D array.')
    return np.maximum(array, minimum_value)


def _rotation_matrices(angles) -> np.ndarray:
    radians = np.asarray(angles, dtype=float)
    cosines = np.cos(radians)
    sines = np.sin(radians)
    rotation = np.empty((radians.size, 2, 2), dtype=float)
    rotation[:, 0, 0] = cosines
    rotation[:, 0, 1] = -sines
    rotation[:, 1, 0] = sines
    rotation[:, 1, 1] = cosines
    return rotation


@dataclass(frozen=True)
class LineMonitor:
    values: np.ndarray
    minimum_value: float = MINIMUM_MONITOR_VALUE

    def __post_init__(self):
        minimum_value = max(float(self.minimum_value), MINIMUM_MONITOR_VALUE)
        values = _as_positive_values(self.values, 'Monitor values', minimum_value)
        object.__setattr__(self, 'minimum_value', minimum_value)
        object.__setattr__(self, 'values', values)

    @classmethod
    def uniform(cls, point_count: int, value: float = 1.0):
        point_count = int(point_count)
        if point_count < 0:
            raise ValueError('Point count must be non-negative.')
        return cls(np.full(point_count, float(value), dtype=float))

    @classmethod
    def from_point_sizes(cls, sizes, exponent: float = 2.0,
                         minimum_value: float = MINIMUM_MONITOR_VALUE):
        minimum_value = max(float(minimum_value), MINIMUM_MONITOR_VALUE)
        size_values = _as_positive_values(sizes, 'Point sizes', minimum_value)
        return cls(size_values ** (-float(exponent)), minimum_value=minimum_value)

    def for_points(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        points_array = _as_points(points)
        if len(points_array) != len(self.values):
            raise ValueError(
                'Monitor values must match the line point count.'
            )
        return self.values


@dataclass(frozen=True)
class LineMetricField:
    tensors: np.ndarray
    minimum_eigenvalue: float = MINIMUM_MONITOR_VALUE

    def __post_init__(self):
        minimum_eigenvalue = max(
            float(self.minimum_eigenvalue),
            MINIMUM_MONITOR_VALUE,
        )
        tensors = np.asarray(self.tensors, dtype=float)
        if tensors.ndim != 3 or tensors.shape[1:] != (2, 2):
            raise ValueError('Metric tensors must be an N x 2 x 2 array.')

        symmetric = 0.5 * (tensors + np.swapaxes(tensors, 1, 2))
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        clamped = np.maximum(eigenvalues, minimum_eigenvalue)
        spd_tensors = np.einsum(
            'nij,nj,nkj->nik',
            eigenvectors,
            clamped,
            eigenvectors,
        )

        object.__setattr__(self, 'minimum_eigenvalue', minimum_eigenvalue)
        object.__setattr__(self, 'tensors', spd_tensors)

    @classmethod
    def uniform(cls, point_count: int, size: float = 1.0):
        point_count = int(point_count)
        if point_count < 0:
            raise ValueError('Point count must be non-negative.')
        size = max(float(size), MINIMUM_MONITOR_VALUE)
        tensor = np.eye(2, dtype=float) / (size * size)
        return cls(np.repeat(tensor[np.newaxis, :, :], point_count, axis=0))

    @classmethod
    def from_isotropic_sizes(cls, sizes,
                             minimum_eigenvalue: float = MINIMUM_MONITOR_VALUE):
        minimum_eigenvalue = max(
            float(minimum_eigenvalue),
            MINIMUM_MONITOR_VALUE,
        )
        size_values = _as_positive_values(
            sizes,
            'Isotropic sizes',
            np.sqrt(minimum_eigenvalue),
        )
        tensor_values = 1.0 / (size_values * size_values)
        tensors = np.zeros((size_values.size, 2, 2), dtype=float)
        tensors[:, 0, 0] = tensor_values
        tensors[:, 1, 1] = tensor_values
        return cls(tensors, minimum_eigenvalue=minimum_eigenvalue)

    @classmethod
    def from_principal_sizes(cls, size_1, size_2, angles=0.0,
                             minimum_eigenvalue: float = MINIMUM_MONITOR_VALUE):
        minimum_eigenvalue = max(
            float(minimum_eigenvalue),
            MINIMUM_MONITOR_VALUE,
        )
        first = _as_positive_values(
            size_1,
            'Principal size 1',
            np.sqrt(minimum_eigenvalue),
        )
        second = _as_positive_values(
            size_2,
            'Principal size 2',
            np.sqrt(minimum_eigenvalue),
        )

        if first.shape != second.shape:
            raise ValueError('Principal size arrays must have matching shapes.')

        angle_values = np.asarray(angles, dtype=float)
        if angle_values.ndim == 0:
            angle_values = np.full(first.size, float(angle_values), dtype=float)
        if angle_values.ndim != 1 or angle_values.size != first.size:
            raise ValueError('Metric angles must match the line point count.')

        diagonal = np.zeros((first.size, 2, 2), dtype=float)
        diagonal[:, 0, 0] = 1.0 / (first * first)
        diagonal[:, 1, 1] = 1.0 / (second * second)

        rotations = _rotation_matrices(angle_values)
        tensors = np.einsum(
            'nij,njk,nlk->nil',
            rotations,
            diagonal,
            rotations,
        )
        return cls(tensors, minimum_eigenvalue=minimum_eigenvalue)

    def for_points(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        points_array = _as_points(points)
        if len(points_array) != len(self.tensors):
            raise ValueError(
                'Metric tensors must match the line point count.'
            )
        return self.tensors

    def density_values(self) -> np.ndarray:
        determinants = np.linalg.det(self.tensors)
        return np.sqrt(np.maximum(determinants, 0.0))

    def density_monitor(self) -> LineMonitor:
        return LineMonitor(self.density_values())

    def segment_lengths(self, points: Sequence[Sequence[float]]) -> np.ndarray:
        points_array = _as_points(points)
        tensors = self.for_points(points_array)

        if len(points_array) < 2:
            return np.array([], dtype=float)

        segments = points_array[1:] - points_array[:-1]
        segment_tensors = 0.5 * (tensors[:-1] + tensors[1:])
        lengths_squared = np.einsum(
            'ni,nij,nj->n',
            segments,
            segment_tensors,
            segments,
        )
        return np.sqrt(np.maximum(lengths_squared, 0.0))
