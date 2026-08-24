from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from MathUtils import VectorUtils


AREA_TOLERANCE = 1.0e-12


def _as_vertices(vertices: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(vertices, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError(
            'Quadrilateral quality expects vertices as an N x 2 array.'
        )
    return array


def _as_connectivity(connectivity: Sequence[Sequence[int]]) -> np.ndarray:
    array = np.asarray(connectivity, dtype=int)
    if array.size == 0:
        return np.empty((0, 4), dtype=int)
    if array.ndim != 2 or array.shape[1] != 4:
        raise ValueError(
            'Quadrilateral quality expects connectivity as an M x 4 array.'
        )
    return array


@dataclass(frozen=True)
class QuadQualityReport:
    criterion: str
    values: np.ndarray
    signed_areas: np.ndarray

    def __post_init__(self):
        values = np.asarray(self.values, dtype=float)
        signed_areas = np.asarray(self.signed_areas, dtype=float)

        if values.ndim != 1:
            raise ValueError('Quadrilateral quality values must be a 1D array.')
        if signed_areas.ndim != 1:
            raise ValueError('Quadrilateral signed areas must be a 1D array.')
        if values.shape != signed_areas.shape:
            raise ValueError(
                'Quadrilateral quality values and signed areas must have '
                'matching shapes.'
            )

        object.__setattr__(self, 'values', values)
        object.__setattr__(self, 'signed_areas', signed_areas)

    @property
    def cell_count(self) -> int:
        return int(self.values.size)

    @property
    def minimum_value(self) -> float | None:
        if not self.values.size:
            return None
        return float(np.min(self.values))

    @property
    def maximum_value(self) -> float | None:
        if not self.values.size:
            return None
        return float(np.max(self.values))

    @property
    def mean_value(self) -> float | None:
        if not self.values.size:
            return None
        return float(np.mean(self.values))

    @property
    def minimum_signed_area(self) -> float | None:
        if not self.signed_areas.size:
            return None
        return float(np.min(self.signed_areas))

    @property
    def has_inverted_cells(self) -> bool:
        return bool(np.any(self.signed_areas < -AREA_TOLERANCE))

    @property
    def has_degenerate_cells(self) -> bool:
        return bool(np.any(np.abs(self.signed_areas) <= AREA_TOLERANCE))

    @property
    def inverted_cell_indices(self) -> np.ndarray:
        return np.flatnonzero(self.signed_areas < -AREA_TOLERANCE)


class QuadQualityEvaluator:
    """Reusable quality evaluation for planar quadrilateral meshes."""

    supported_criteria = ('k2inf',)

    @classmethod
    def evaluate(cls, vertices, connectivity, criterion='k2inf'):
        normalized_criterion = str(criterion).strip().lower()
        if normalized_criterion not in cls.supported_criteria:
            raise ValueError(
                f'Unknown mesh quality criterion: {criterion}'
            )

        vertices_array = _as_vertices(vertices)
        connectivity_array = _as_connectivity(connectivity)

        signed_areas = cls.signed_areas(vertices_array, connectivity_array)
        if normalized_criterion == 'k2inf':
            values = cls.k2inf(vertices_array, connectivity_array)

        return QuadQualityReport(
            criterion=normalized_criterion,
            values=values,
            signed_areas=signed_areas,
        )

    @staticmethod
    def signed_areas(vertices, connectivity) -> np.ndarray:
        vertices_array = _as_vertices(vertices)
        connectivity_array = _as_connectivity(connectivity)

        if connectivity_array.size == 0:
            return np.array([], dtype=float)

        cells = vertices_array[connectivity_array]
        x_values = cells[:, :, 0]
        y_values = cells[:, :, 1]
        return 0.5 * np.sum(
            x_values * np.roll(y_values, -1, axis=1) -
            y_values * np.roll(x_values, -1, axis=1),
            axis=1,
        )

    @staticmethod
    def k2inf(vertices, connectivity) -> np.ndarray:
        vertices_array = _as_vertices(vertices)
        connectivity_array = _as_connectivity(connectivity)

        if connectivity_array.size == 0:
            return np.array([], dtype=float)

        v12 = vertices_array[connectivity_array[:, 1]] - vertices_array[
            connectivity_array[:, 0]
        ]
        v23 = vertices_array[connectivity_array[:, 2]] - vertices_array[
            connectivity_array[:, 1]
        ]
        v34 = vertices_array[connectivity_array[:, 3]] - vertices_array[
            connectivity_array[:, 2]
        ]
        v41 = vertices_array[connectivity_array[:, 0]] - vertices_array[
            connectivity_array[:, 3]
        ]

        a = np.linalg.norm(v12, axis=1)
        b = np.linalg.norm(v23, axis=1)
        c = np.linalg.norm(v34, axis=1)
        d = np.linalg.norm(v41, axis=1)

        alpha = VectorUtils.angle_between(v12, -v41)
        beta = VectorUtils.angle_between(v23, -v12)
        gamma = VectorUtils.angle_between(v34, -v23)
        delta = VectorUtils.angle_between(v41, -v34)

        sin_alpha = np.sin(alpha)
        sin_beta = np.sin(beta)
        sin_gamma = np.sin(gamma)
        sin_delta = np.sin(delta)

        def _quality_ratio(first, second, sine_values):
            denominator = first * second * sine_values
            return np.divide(
                first**2 + second**2,
                denominator,
                out=np.full_like(first, np.inf, dtype=float),
                where=np.abs(denominator) > AREA_TOLERANCE,
            )

        ka = _quality_ratio(a, d, sin_alpha)
        kb = _quality_ratio(a, b, sin_beta)
        kc = _quality_ratio(b, c, sin_gamma)
        kd = _quality_ratio(c, d, sin_delta)
        return 0.5 * np.max(np.stack((ka, kb, kc, kd)), axis=0)
