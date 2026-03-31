from __future__ import annotations

import numpy as np
from scipy import optimize

from ContourData import CamberData
from MathUtils import VectorUtils

import logging
logger = logging.getLogger(__name__)


CAMBER_METHOD_INSCRIBED_CIRCLES = 'inscribed_circles'
CAMBER_METHOD_LEGACY = 'legacy_midpoint'


class CamberBuilder:
    DEFAULT_METHOD = CAMBER_METHOD_INSCRIBED_CIRCLES
    DEFAULT_CALCULATION_POINTS = 240
    DEFAULT_DISPLAY_CIRCLES = 17
    NORMAL_SEARCH_MARGIN = 0.08
    MAX_INSCRIBED_ITERATIONS = 7
    CENTER_TOLERANCE = 1.0e-7
    RADIUS_TOLERANCE = 1.0e-5
    MIN_RADIUS = 1.0e-8
    MIN_NORMAL_DETERMINANT = 1.0e-8

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

        point_count = calculation_points or max(
            self.DEFAULT_CALCULATION_POINTS,
            spline_data.point_count,
        )
        point_count = max(40, int(point_count))
        display_count = max(3, int(display_circles or self.DEFAULT_DISPLAY_CIRCLES))

        legacy = self._build_legacy(point_count=point_count, display_count=display_count)
        active_method = method or self.DEFAULT_METHOD

        if active_method == CAMBER_METHOD_LEGACY:
            self._log_metrics(legacy, label='legacy midpoint')
            return legacy
        if active_method != CAMBER_METHOD_INSCRIBED_CIRCLES:
            raise ValueError(f'Unsupported camber method: {active_method}')

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

    def _build_legacy(self, point_count, display_count):
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
            method=CAMBER_METHOD_LEGACY,
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

    def _build_inscribed(self, legacy, rc, xc, yc, xle, yle, display_count):
        point_count = legacy.point_count
        legacy_centers = np.column_stack(legacy.coordinates)
        legacy_upper = np.column_stack(legacy.upper_contact)
        legacy_lower = np.column_stack(legacy.lower_contact)

        centers = np.array(legacy_centers, copy=True)
        radii = np.array(legacy.radius, copy=True)
        upper = np.array(legacy_upper, copy=True)
        lower = np.array(legacy_lower, copy=True)
        upper_parameters = np.array(legacy.upper_parameters, copy=True)
        lower_parameters = np.array(legacy.lower_parameters, copy=True)
        valid = np.zeros(point_count, dtype=bool)
        fallback_used = np.ones(point_count, dtype=bool)

        # The leading-edge circle is the first maximal inscribed circle.
        centers[0] = np.array((xc, yc), dtype=float)
        radii[0] = float(rc)
        upper[0] = np.array((xle, yle), dtype=float)
        lower[0] = np.array((xle, yle), dtype=float)
        upper_parameters[0] = self.t_le
        lower_parameters[0] = self.t_le
        valid[0] = np.isfinite(rc) and rc > self.MIN_RADIUS
        fallback_used[0] = False

        previous_upper = upper_parameters[0]
        previous_lower = lower_parameters[0]

        for index in range(1, point_count):
            seed_center = legacy_centers[index]
            result = self._solve_station(
                center_seed=seed_center,
                previous_upper=previous_upper,
                previous_lower=previous_lower,
                legacy_upper=legacy.upper_parameters[index],
                legacy_lower=legacy.lower_parameters[index],
            )

            if result is None:
                previous_upper = legacy.upper_parameters[index]
                previous_lower = legacy.lower_parameters[index]
                continue

            centers[index] = result['center']
            radii[index] = result['radius']
            upper[index] = result['upper_point']
            lower[index] = result['lower_point']
            upper_parameters[index] = result['upper_parameter']
            lower_parameters[index] = result['lower_parameter']
            valid[index] = True
            fallback_used[index] = False
            previous_upper = result['upper_parameter']
            previous_lower = result['lower_parameter']

        display_indices = self._display_indices(centers, display_count)
        return CamberData(
            method=CAMBER_METHOD_INSCRIBED_CIRCLES,
            coordinates=(centers[:, 0], centers[:, 1]),
            radius=radii,
            upper_contact=(upper[:, 0], upper[:, 1]),
            lower_contact=(lower[:, 0], lower[:, 1]),
            upper_parameters=upper_parameters,
            lower_parameters=lower_parameters,
            display_indices=display_indices,
            valid=valid,
            fallback_used=fallback_used,
        )

    def _station_bounds(self, previous, legacy_parameter, lower_limit, upper_limit):
        low = min(previous, legacy_parameter) - self.NORMAL_SEARCH_MARGIN
        high = max(previous, legacy_parameter) + self.NORMAL_SEARCH_MARGIN
        low = max(lower_limit, low)
        high = min(upper_limit, high)
        if high <= low:
            return lower_limit, upper_limit
        return low, high

    def _closest_parameter(self, center, bounds):
        lower, upper = bounds
        if upper <= lower:
            return lower

        def objective(parameter):
            point = self._evaluate_point(parameter)
            delta = point - center
            return float(np.dot(delta, delta))

        result = optimize.minimize_scalar(
            objective,
            bounds=(lower, upper),
            method='bounded',
            options={'xatol': 1.0e-6, 'maxiter': 80},
        )
        return float(result.x if result.success else 0.5 * (lower + upper))

    def _inward_normal(self, derivative, point, center_reference):
        tangent = VectorUtils.unit_vector(np.asarray(derivative, dtype=float))
        left = np.array((-tangent[1], tangent[0]), dtype=float)
        right = -left

        if np.dot(center_reference - point, left) >= np.dot(center_reference - point, right):
            return left
        return right

    def _intersect_normals(self, upper_point, upper_normal, lower_point, lower_normal):
        matrix = np.column_stack((upper_normal, -lower_normal))
        determinant = float(np.linalg.det(matrix))
        if abs(determinant) < self.MIN_NORMAL_DETERMINANT:
            return None

        try:
            distance_upper, distance_lower = np.linalg.solve(
                matrix,
                lower_point - upper_point,
            )
        except np.linalg.LinAlgError:
            return None

        if distance_upper <= self.MIN_RADIUS or distance_lower <= self.MIN_RADIUS:
            return None

        center = upper_point + distance_upper * upper_normal
        return center, float(distance_upper), float(distance_lower)

    def _validate_solution(
        self,
        center,
        upper_parameter,
        lower_parameter,
        upper_bounds,
        lower_bounds,
    ):
        upper_parameter = self._closest_parameter(center, upper_bounds)
        lower_parameter = self._closest_parameter(center, lower_bounds)

        upper_point, upper_derivative = self._point_and_derivative(upper_parameter)
        lower_point, lower_derivative = self._point_and_derivative(lower_parameter)
        upper_normal = self._inward_normal(upper_derivative, upper_point, center)
        lower_normal = self._inward_normal(lower_derivative, lower_point, center)

        intersection = self._intersect_normals(
            upper_point,
            upper_normal,
            lower_point,
            lower_normal,
        )
        if intersection is None:
            return None

        center, upper_radius, lower_radius = intersection
        radius = 0.5 * (upper_radius + lower_radius)
        if radius <= self.MIN_RADIUS:
            return None

        if abs(upper_radius - lower_radius) > max(self.RADIUS_TOLERANCE, 0.01 * radius):
            return None

        return {
            'center': center,
            'radius': radius,
            'upper_point': upper_point,
            'lower_point': lower_point,
            'upper_parameter': upper_parameter,
            'lower_parameter': lower_parameter,
        }

    def _solve_station(self, center_seed, previous_upper, previous_lower, legacy_upper, legacy_lower):
        upper_bounds = self._station_bounds(
            previous_upper,
            legacy_upper,
            lower_limit=0.0,
            upper_limit=self.t_le,
        )
        lower_bounds = self._station_bounds(
            previous_lower,
            legacy_lower,
            lower_limit=self.t_le,
            upper_limit=1.0,
        )

        center = np.array(center_seed, dtype=float)
        upper_parameter = float(np.clip(legacy_upper, *upper_bounds))
        lower_parameter = float(np.clip(legacy_lower, *lower_bounds))

        for _ in range(self.MAX_INSCRIBED_ITERATIONS):
            upper_parameter = self._closest_parameter(center, upper_bounds)
            lower_parameter = self._closest_parameter(center, lower_bounds)

            upper_point, upper_derivative = self._point_and_derivative(upper_parameter)
            lower_point, lower_derivative = self._point_and_derivative(lower_parameter)
            upper_normal = self._inward_normal(upper_derivative, upper_point, center)
            lower_normal = self._inward_normal(lower_derivative, lower_point, center)

            intersection = self._intersect_normals(
                upper_point,
                upper_normal,
                lower_point,
                lower_normal,
            )
            if intersection is None:
                return None

            center_candidate, upper_radius, lower_radius = intersection
            if np.linalg.norm(center_candidate - center) < self.CENTER_TOLERANCE and \
                    abs(upper_radius - lower_radius) < self.RADIUS_TOLERANCE:
                center = center_candidate
                break
            center = center_candidate

        return self._validate_solution(
            center,
            upper_parameter,
            lower_parameter,
            upper_bounds,
            lower_bounds,
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
            'Maximum thickness (%s): %5.2f %% at %5.2f %% chord',
            label,
            thickness[max_thickness_id] * 100.0,
            x_coordinates[max_thickness_id] * 100.0,
        )
        logger.info(
            'Maximum camber (%s): %5.2f %% at %5.2f %% chord',
            label,
            y_coordinates[max_camber_id] * 100.0,
            x_coordinates[max_camber_id] * 100.0,
        )
