from __future__ import annotations

import numpy as np

import CamberMedialAxis
from ContourData import CamberData
from MathUtils import VectorUtils

import logging
logger = logging.getLogger(__name__)


CAMBER_METHOD_INSCRIBED_CIRCLES = 'inscribed_circles'


class CamberBuilder:
    DEFAULT_CALCULATION_POINTS = 240
    DEFAULT_DISPLAY_CIRCLES = 17

    def build(
        self,
        spline_data,
        rc,
        xc,
        yc,
        xle,
        yle,
        calculation_points=None,
        display_circles=None,
    ):
        self.spline_data = spline_data
        self.t_le = float(spline_data.leading_edge_parameter_value())

        point_count = calculation_points or max(
            self.DEFAULT_CALCULATION_POINTS,
            spline_data.point_count,
        )
        point_count = max(40, int(point_count))
        display_count = max(3, int(display_circles or self.DEFAULT_DISPLAY_CIRCLES))

        naive_midline = self._build_naive_midline(
            point_count=point_count,
            display_count=display_count,
        )
        inscribed = self._build_inscribed(
            naive_midline,
            rc=rc,
            xc=xc,
            yc=yc,
            xle=xle,
            yle=yle,
            display_count=display_count,
        )
        self._log_metrics(inscribed, label='inscribed circles')
        fallback_count = int(np.count_nonzero(inscribed.fallback_used))
        if fallback_count:
            logger.info(
                'Camber inscribed-circle fallback used for %d of %d stations.',
                fallback_count,
                inscribed.point_count,
            )
        return inscribed

    def _upper_parameter(self, station):
        return self.spline_data.upper_surface_parameters(station)

    def _lower_parameter(self, station):
        return self.spline_data.lower_surface_parameters(station)

    def _legacy_parameters(self, point_count):
        stations = np.linspace(0.0, 1.0, point_count)
        upper_parameters = self._upper_parameter(stations)
        lower_parameters = self._lower_parameter(stations)
        return stations, upper_parameters, lower_parameters

    def _build_naive_midline(self, point_count, display_count):
        """Simple upper/lower-surface-midpoint construction. Not exposed as
        a user-selectable camber method -- it exists purely to seed the
        medial-axis tracer's trailing-edge blend fallback (see
        CamberMedialAxis._append_legacy_tail), for the stretch near a sharp
        trailing edge where a true inscribed circle isn't well-conditioned.
        """
        stations, upper_parameters, lower_parameters = self._legacy_parameters(point_count)
        del stations

        upper = np.array(
            self.spline_data.evaluate(upper_parameters, der=0),
            dtype=float,
        ).T
        lower = np.array(
            self.spline_data.evaluate(lower_parameters, der=0),
            dtype=float,
        ).T

        centers = 0.5 * (upper + lower)
        radius = 0.5 * VectorUtils.vector_length(upper - lower)
        display_indices = self._display_indices(centers, display_count)

        valid = np.ones(point_count, dtype=bool)
        fallback_used = np.zeros(point_count, dtype=bool)

        return CamberData(
            method='legacy_midpoint',
            coordinates=(centers[:, 0], centers[:, 1]),
            radius=radius,
            upper_contact=(upper[:, 0], upper[:, 1]),
            lower_contact=(lower[:, 0], lower[:, 1]),
            upper_parameters=upper_parameters,
            lower_parameters=lower_parameters,
            display_indices=display_indices,
            valid=valid,
            fallback_used=fallback_used,
        )

    def _build_inscribed(self, naive_midline, rc, xc, yc, xle, yle, display_count):
        return CamberMedialAxis.trace(
            spline_data=self.spline_data,
            t_le=self.t_le,
            legacy=naive_midline,
            rc=rc, xc=xc, yc=yc, xle=xle, yle=yle,
            point_count=naive_midline.point_count,
            display_count=display_count,
        )

    def _display_indices(self, centers, display_count):
        count = len(centers)
        if count == 0:
            return np.array([], dtype=int)
        if count <= display_count:
            return np.arange(count, dtype=int)

        deltas = np.diff(centers, axis=0)
        arclength = np.zeros(count, dtype=float)
        arclength[1:] = np.cumsum(VectorUtils.vector_length(deltas))
        total_length = float(arclength[-1])
        if total_length <= 0.0:
            return np.linspace(0, count - 1, display_count).astype(int)

        targets = np.linspace(0.0, total_length, display_count)
        indices = []
        for target in targets:
            indices.append(int(np.argmin(np.abs(arclength - target))))
        return np.array(sorted(set(indices)), dtype=int)

    def _log_metrics(self, camber_data, label):
        if camber_data.point_count == 0:
            return

        y_coordinates = np.asarray(camber_data.coordinates[1], dtype=float)
        x_coordinates = np.asarray(camber_data.coordinates[0], dtype=float)
        thickness = 2.0 * np.asarray(camber_data.radius, dtype=float)

        max_camber_id = int(np.argmax(y_coordinates))
        max_thickness_id = int(np.argmax(thickness))

        logger.info(
            'Maximum thickness (%s): %5.2f%% @ %5.2f%% chord',
            label,
            thickness[max_thickness_id] * 100.0,
            x_coordinates[max_thickness_id] * 100.0,
        )
        logger.info(
            'Maximum camber (%s): %5.2f%% @ %5.2f%% chord',
            label,
            y_coordinates[max_camber_id] * 100.0,
            x_coordinates[max_camber_id] * 100.0,
        )
