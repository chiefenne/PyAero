from __future__ import annotations

import numpy as np
from scipy import optimize

import CamberMedialAxis
from CSTAirfoil import METHOD_CST_MODIFIED
from ContourData import CamberData
from MathUtils import VectorUtils

import logging
logger = logging.getLogger(__name__)


CAMBER_METHOD_INSCRIBED_CIRCLES = 'inscribed_circles'
CAMBER_METHOD_CST = 'cst_camber_thickness'
CAMBER_METHOD_LEGACY = 'legacy_midpoint'


class CamberBuilder:
    DEFAULT_METHOD = None
    DEFAULT_CALCULATION_POINTS = 240
    DEFAULT_DISPLAY_CIRCLES = 17
    CLEARANCE_MAX_ITERATIONS = 48
    CLEARANCE_PARAMETER_TOLERANCE = 1.0e-7
    CLEARANCE_SAMPLE_COUNT = 320

    def build(
        self,
        spline_data,
        le_id,
        rc,
        xc,
        yc,
        xle,
        yle,
        method=None,
        calculation_points=None,
        display_circles=None,
    ):
        self.spline_data = spline_data
        self.t_le = float(spline_data.leading_edge_parameter_value())
        self._clearance_samples = None

        point_count = calculation_points or max(
            self.DEFAULT_CALCULATION_POINTS,
            spline_data.point_count,
        )
        point_count = max(40, int(point_count))
        display_count = max(3, int(display_circles or self.DEFAULT_DISPLAY_CIRCLES))

        active_method = method or self._default_method()

        if active_method == CAMBER_METHOD_LEGACY:
            legacy = self._build_legacy(
                point_count=point_count,
                display_count=display_count,
            )
            self._log_metrics(legacy, label='legacy midpoint')
            return legacy
        if active_method == CAMBER_METHOD_CST:
            cst_camber = self._build_cst(
                point_count=point_count,
                display_count=display_count,
            )
            self._log_metrics(cst_camber, label='CST')
            return cst_camber
        if active_method != CAMBER_METHOD_INSCRIBED_CIRCLES:
            raise ValueError(f'Unsupported camber method: {active_method}')

        legacy = self._build_legacy(point_count=point_count, display_count=display_count)
        inscribed = self._build_inscribed(
            legacy,
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

    def _default_method(self):
        if getattr(self.spline_data, 'method', None) == METHOD_CST_MODIFIED:
            return CAMBER_METHOD_CST
        return CAMBER_METHOD_LEGACY

    def _upper_parameter(self, station):
        return self.spline_data.upper_surface_parameters(station)

    def _lower_parameter(self, station):
        return self.spline_data.lower_surface_parameters(station)

    def _evaluate_point(self, parameter):
        x, y = self.spline_data.evaluate(parameter, der=0)
        return np.array((float(x), float(y)), dtype=float)

    def _evaluate_derivative(self, parameter):
        dx, dy = self.spline_data.evaluate(parameter, der=1)
        return np.array((float(dx), float(dy)), dtype=float)

    def _point_and_derivative(self, parameter):
        return self._evaluate_point(parameter), self._evaluate_derivative(parameter)

    def _legacy_parameters(self, point_count):
        stations = np.linspace(0.0, 1.0, point_count)
        upper_parameters = self._upper_parameter(stations)
        lower_parameters = self._lower_parameter(stations)
        return stations, upper_parameters, lower_parameters

    def _surface_midline_data(
        self,
        point_count,
        display_count,
        method_name,
        use_clearance_circles=False,
    ):
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
        circle_radius = None

        if use_clearance_circles:
            circle_radius = np.array(radius, copy=True)
            self._prepare_clearance_samples()
            for index in display_indices:
                clearance = self._clearance_radius(centers[index])
                circle_radius[index] = min(circle_radius[index], clearance)

        valid = np.ones(point_count, dtype=bool)
        fallback_used = np.zeros(point_count, dtype=bool)

        return CamberData(
            method=method_name,
            coordinates=(centers[:, 0], centers[:, 1]),
            radius=radius,
            circle_radius=circle_radius,
            upper_contact=(upper[:, 0], upper[:, 1]),
            lower_contact=(lower[:, 0], lower[:, 1]),
            upper_parameters=upper_parameters,
            lower_parameters=lower_parameters,
            display_indices=display_indices,
            valid=valid,
            fallback_used=fallback_used,
        )

    def _build_legacy(self, point_count, display_count):
        return self._surface_midline_data(
            point_count=point_count,
            display_count=display_count,
            method_name=CAMBER_METHOD_LEGACY,
            use_clearance_circles=False,
        )

    def _build_cst(self, point_count, display_count):
        return self._surface_midline_data(
            point_count=point_count,
            display_count=display_count,
            method_name=CAMBER_METHOD_CST,
            use_clearance_circles=True,
        )

    def _prepare_clearance_samples(self):
        if self._clearance_samples is not None:
            return

        sample_count = max(24, int(self.CLEARANCE_SAMPLE_COUNT))
        sample_sets = []
        for bounds in ((0.0, self.t_le), (self.t_le, 1.0)):
            lower, upper = bounds
            if upper <= lower:
                parameters = np.array((lower,), dtype=float)
            else:
                parameters = np.linspace(lower, upper, sample_count)
            points = np.column_stack(self.spline_data.evaluate(parameters, der=0))
            sample_sets.append((parameters, points))
        self._clearance_samples = tuple(sample_sets)

    def _distance_squared_to_center(self, parameter, center):
        delta = self._evaluate_point(parameter) - center
        return float(np.dot(delta, delta))

    def _side_clearance_radius(self, center, parameters, points):
        if len(parameters) == 0:
            return np.inf

        distances_sq = np.sum((points - center) ** 2, axis=1)
        index = int(np.argmin(distances_sq))
        best_sq = float(distances_sq[index])

        lower_index = max(0, index - 1)
        upper_index = min(len(parameters) - 1, index + 1)
        lower_parameter = float(parameters[lower_index])
        upper_parameter = float(parameters[upper_index])

        if upper_parameter > lower_parameter:
            result = optimize.minimize_scalar(
                lambda parameter: self._distance_squared_to_center(parameter, center),
                bounds=(lower_parameter, upper_parameter),
                method='bounded',
                options={
                    'xatol': self.CLEARANCE_PARAMETER_TOLERANCE,
                    'maxiter': self.CLEARANCE_MAX_ITERATIONS,
                },
            )
            candidates = [lower_parameter, upper_parameter]
            if result.success:
                candidates.append(float(result.x))
            for parameter in candidates:
                best_sq = min(
                    best_sq,
                    self._distance_squared_to_center(parameter, center),
                )

        return np.sqrt(max(0.0, best_sq))

    def _clearance_radius(self, center):
        best_radius = np.inf
        for parameters, points in self._clearance_samples:
            best_radius = min(
                best_radius,
                self._side_clearance_radius(center, parameters, points),
            )
        if not np.isfinite(best_radius):
            return 0.0
        return float(best_radius)

    def _build_inscribed(self, legacy, rc, xc, yc, xle, yle, display_count):
        return CamberMedialAxis.trace(
            spline_data=self.spline_data,
            t_le=self.t_le,
            legacy=legacy,
            rc=rc, xc=xc, yc=yc, xle=xle, yle=yle,
            point_count=legacy.point_count,
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
