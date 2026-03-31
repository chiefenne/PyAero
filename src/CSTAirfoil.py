from __future__ import annotations

from dataclasses import dataclass
from math import comb

import numpy as np

from ContourData import SplineData


METHOD_BSPLINE = 'bspline'
METHOD_CST_MODIFIED = 'cst_modified'


@dataclass(slots=True)
class CSTSurfaceFit:
    order: int
    coefficients: np.ndarray
    nose_coefficient: float
    trailing_edge_offset: float
    binomial_coefficients: np.ndarray
    exponent_s: np.ndarray
    exponent_tail: np.ndarray


def _as_coordinate_array(coordinates):
    x, y = coordinates
    return np.column_stack((
        np.asarray(x, dtype=float),
        np.asarray(y, dtype=float),
    ))


def _prepare_surface(points):
    surface = np.asarray(points, dtype=float)
    if surface.ndim != 2 or surface.shape[1] != 2 or len(surface) < 3:
        raise ValueError('At least three surface points are required for CST fitting.')

    order = np.argsort(surface[:, 0], kind='mergesort')
    surface = surface[order]

    rounded_x = np.round(surface[:, 0], decimals=12)
    unique_x, inverse = np.unique(rounded_x, return_inverse=True)

    if len(unique_x) == len(surface):
        return surface

    counts = np.bincount(inverse).astype(float)
    x_mean = np.bincount(inverse, weights=surface[:, 0]) / counts
    y_mean = np.bincount(inverse, weights=surface[:, 1]) / counts
    return np.column_stack((x_mean, y_mean))


def split_airfoil_surfaces(coordinates):
    contour = _as_coordinate_array(coordinates)
    if len(contour) < 5:
        raise ValueError('At least five contour points are required for CST fitting.')

    le_index = int(np.argmin(contour[:, 0]))
    upper = _prepare_surface(contour[:le_index + 1][::-1])
    lower = _prepare_surface(contour[le_index:])
    return upper, lower


def _standard_basis_value(s, order, index):
    s = np.asarray(s, dtype=float)
    exponent_s = 2 * index + 1
    exponent_tail = order - index + 1
    return comb(order, index) * (
        np.power(s, exponent_s) *
        np.power(1.0 - s * s, exponent_tail)
    )


def _standard_basis_first_derivative(s, order, index):
    s = np.asarray(s, dtype=float)
    exponent_s = 2 * index + 1
    exponent_tail = order - index + 1
    tail = 1.0 - s * s
    coefficient = float(comb(order, index))

    first = exponent_s * np.power(s, exponent_s - 1) * np.power(tail, exponent_tail)
    second = (
        -2.0 * exponent_tail *
        np.power(s, exponent_s + 1) *
        np.power(tail, exponent_tail - 1)
    )
    return coefficient * (first + second)


def _standard_basis_second_derivative(s, order, index):
    s = np.asarray(s, dtype=float)
    exponent_s = 2 * index + 1
    exponent_tail = order - index + 1
    tail = 1.0 - s * s
    coefficient = float(comb(order, index))

    derivative = np.zeros_like(s, dtype=float)
    if exponent_s >= 2:
        derivative += (
            exponent_s * (exponent_s - 1) *
            np.power(s, exponent_s - 2) *
            np.power(tail, exponent_tail)
        )

    derivative += (
        -2.0 * exponent_tail * (2 * exponent_s + 1) *
        np.power(s, exponent_s) *
        np.power(tail, exponent_tail - 1)
    )

    if exponent_tail >= 2:
        derivative += (
            4.0 * exponent_tail * (exponent_tail - 1) *
            np.power(s, exponent_s + 2) *
            np.power(tail, exponent_tail - 2)
        )

    return coefficient * derivative


def _nose_basis_value(s):
    s = np.asarray(s, dtype=float)
    return s * s * (1.0 - s * s)


def _nose_basis_first_derivative(s):
    s = np.asarray(s, dtype=float)
    return 2.0 * s - 4.0 * np.power(s, 3)


def _nose_basis_second_derivative(s):
    s = np.asarray(s, dtype=float)
    return 2.0 - 12.0 * s * s


def _fit_surface(points, order):
    surface = _prepare_surface(points)
    x = np.clip(surface[:, 0], 0.0, 1.0)
    y = surface[:, 1]

    if len(surface) < 3:
        raise ValueError('At least three points are required per surface for CST fitting.')

    capped_order = min(max(1, int(order)), max(1, len(surface) - 2))
    s = np.sqrt(x)
    trailing_edge_offset = float(y[-1])
    rhs = y - trailing_edge_offset * x

    basis_columns = [
        _standard_basis_value(s, capped_order, index)
        for index in range(capped_order + 1)
    ]
    basis_columns.append(_nose_basis_value(s))
    design_matrix = np.column_stack(basis_columns)

    coefficients, _residuals, _rank, _singular_values = np.linalg.lstsq(
        design_matrix,
        rhs,
        rcond=None,
    )

    exponents = np.arange(capped_order + 1, dtype=int)

    return CSTSurfaceFit(
        order=capped_order,
        coefficients=np.asarray(coefficients[:-1], dtype=float),
        nose_coefficient=float(coefficients[-1]),
        trailing_edge_offset=trailing_edge_offset,
        binomial_coefficients=np.array(
            [comb(capped_order, index) for index in exponents],
            dtype=float,
        ),
        exponent_s=2 * exponents + 1,
        exponent_tail=capped_order - exponents + 1,
    )


def _surface_basis_matrices(surface, s):
    s = np.asarray(s, dtype=float)
    s_row = np.atleast_1d(s)[None, :]
    tail_row = 1.0 - s_row * s_row

    binomial = surface.binomial_coefficients[:, None]
    exponent_s = surface.exponent_s[:, None]
    exponent_tail = surface.exponent_tail[:, None]

    basis = (
        binomial *
        np.power(s_row, exponent_s) *
        np.power(tail_row, exponent_tail)
    )
    first_derivative = (
        binomial * (
            exponent_s *
            np.power(s_row, exponent_s - 1) *
            np.power(tail_row, exponent_tail) -
            2.0 * exponent_tail *
            np.power(s_row, exponent_s + 1) *
            np.power(tail_row, exponent_tail - 1)
        )
    )

    second_derivative = np.zeros_like(basis, dtype=float)
    exponent_s_flat = surface.exponent_s
    exponent_tail_flat = surface.exponent_tail

    mask_s = exponent_s_flat >= 2
    if np.any(mask_s):
        second_derivative[mask_s] += (
            surface.binomial_coefficients[mask_s, None] *
            exponent_s_flat[mask_s, None] *
            (exponent_s_flat[mask_s, None] - 1) *
            np.power(s_row, exponent_s_flat[mask_s, None] - 2) *
            np.power(tail_row, exponent_tail_flat[mask_s, None])
        )

    second_derivative += (
        -2.0 *
        surface.binomial_coefficients[:, None] *
        exponent_tail *
        (2 * exponent_s + 1) *
        np.power(s_row, exponent_s) *
        np.power(tail_row, exponent_tail - 1)
    )

    mask_tail = exponent_tail_flat >= 2
    if np.any(mask_tail):
        second_derivative[mask_tail] += (
            4.0 *
            surface.binomial_coefficients[mask_tail, None] *
            exponent_tail_flat[mask_tail, None] *
            (exponent_tail_flat[mask_tail, None] - 1) *
            np.power(s_row, exponent_s_flat[mask_tail, None] + 2) *
            np.power(tail_row, exponent_tail_flat[mask_tail, None] - 2)
        )

    return basis, first_derivative, second_derivative


class ModifiedCSTAirfoilEvaluator:
    DENSE_ARCLENGTH_SAMPLES = 1024

    def __init__(self, upper_surface, lower_surface):
        self.upper_surface = upper_surface
        self.lower_surface = lower_surface
        self.leading_edge_parameter = self._leading_edge_parameter_from_arclength()

    @classmethod
    def fit(cls, coordinates, order=8):
        upper_points, lower_points = split_airfoil_surfaces(coordinates)
        return cls(
            upper_surface=_fit_surface(upper_points, order=order),
            lower_surface=_fit_surface(lower_points, order=order),
        )

    @property
    def order(self):
        return max(self.upper_surface.order, self.lower_surface.order)

    def surface_parameters(self, stations, side):
        stations = np.asarray(stations, dtype=float)
        root = np.sqrt(np.clip(stations, 0.0, 1.0))
        if side == 'upper':
            return self.leading_edge_parameter * (1.0 - root)
        if side == 'lower':
            return self.leading_edge_parameter + (
                (1.0 - self.leading_edge_parameter) * root
            )
        raise ValueError(f'Unsupported CST surface side: {side}')

    def fit_parameters_from_contour(self, coordinates):
        contour = _as_coordinate_array(coordinates)
        parameters = np.empty(len(contour), dtype=float)
        le_index = int(np.argmin(contour[:, 0]))

        upper_root = np.sqrt(np.clip(contour[:le_index + 1, 0], 0.0, 1.0))
        parameters[:le_index + 1] = self.leading_edge_parameter * (1.0 - upper_root)

        lower_root = np.sqrt(np.clip(contour[le_index:, 0], 0.0, 1.0))
        parameters[le_index:] = self.leading_edge_parameter + (
            (1.0 - self.leading_edge_parameter) * lower_root
        )

        return parameters

    def initial_sample_parameters(self, point_count):
        return np.linspace(0.0, 1.0, int(point_count))

    def evaluate(self, parameters, der=0):
        values = np.asarray(parameters, dtype=float)
        scalar_input = values.ndim == 0
        values = np.atleast_1d(values)

        x_result = np.empty_like(values, dtype=float)
        y_result = np.empty_like(values, dtype=float)

        upper_mask = values <= self.leading_edge_parameter
        lower_mask = ~upper_mask

        if np.any(upper_mask):
            x_upper, y_upper = self._evaluate_side(
                values[upper_mask],
                surface=self.upper_surface,
                upper_side=True,
                der=der,
            )
            x_result[upper_mask] = x_upper
            y_result[upper_mask] = y_upper

        if np.any(lower_mask):
            x_lower, y_lower = self._evaluate_side(
                values[lower_mask],
                surface=self.lower_surface,
                upper_side=False,
                der=der,
            )
            x_result[lower_mask] = x_lower
            y_result[lower_mask] = y_lower

        if scalar_input:
            return float(x_result[0]), float(y_result[0])
        return x_result, y_result

    def _leading_edge_parameter_from_arclength(self):
        upper_length = self._surface_arclength(self.upper_surface)
        lower_length = self._surface_arclength(self.lower_surface)
        total_length = upper_length + lower_length
        if total_length <= 0.0:
            return 0.5
        return upper_length / total_length

    def _surface_arclength(self, surface):
        s = np.linspace(0.0, 1.0, self.DENSE_ARCLENGTH_SAMPLES)
        dx_ds = 2.0 * s
        dy_ds = self._surface_y_derivative(surface, s)
        integrand = np.sqrt(dx_ds * dx_ds + dy_ds * dy_ds)
        return float(np.trapz(integrand, s))

    def _evaluate_side(self, parameters, surface, upper_side, der):
        if upper_side:
            delta = max(self.leading_edge_parameter, 1.0e-12)
            s = 1.0 - parameters / delta
            ds_dt = -1.0 / delta
        else:
            delta = max(1.0 - self.leading_edge_parameter, 1.0e-12)
            s = (parameters - self.leading_edge_parameter) / delta
            ds_dt = 1.0 / delta

        s = np.clip(s, 0.0, 1.0)
        x = s * s
        y = self._surface_y(surface, s)

        if der == 0:
            return x, y
        if der == 1:
            return 2.0 * s * ds_dt, self._surface_y_derivative(surface, s) * ds_dt
        if der == 2:
            scale = ds_dt * ds_dt
            return np.full_like(s, 2.0 * scale), self._surface_y_second_derivative(surface, s) * scale
        raise ValueError(f'Unsupported derivative order: {der}')

    def _surface_y(self, surface, s):
        values = np.asarray(s, dtype=float)
        basis, _first_derivative, _second_derivative = _surface_basis_matrices(
            surface,
            values,
        )
        values = np.dot(surface.coefficients, basis)
        values += surface.nose_coefficient * _nose_basis_value(s)
        values += surface.trailing_edge_offset * (np.asarray(s, dtype=float) ** 2)
        return values

    def _surface_y_derivative(self, surface, s):
        values = np.asarray(s, dtype=float)
        _basis, first_derivative, _second_derivative = _surface_basis_matrices(
            surface,
            values,
        )
        derivatives = np.dot(surface.coefficients, first_derivative)
        derivatives += surface.nose_coefficient * _nose_basis_first_derivative(s)
        derivatives += 2.0 * surface.trailing_edge_offset * values
        return derivatives

    def _surface_y_second_derivative(self, surface, s):
        values = np.asarray(s, dtype=float)
        _basis, _first_derivative, second_derivative = _surface_basis_matrices(
            surface,
            values,
        )
        derivatives = np.dot(surface.coefficients, second_derivative)
        derivatives += surface.nose_coefficient * _nose_basis_second_derivative(s)
        derivatives += 2.0 * surface.trailing_edge_offset
        return derivatives


def build_modified_cst_spline_data(
    coordinates,
    point_count=None,
    order=8,
    sample_parameters=None,
):
    evaluator = ModifiedCSTAirfoilEvaluator.fit(coordinates, order=order)
    fit_parameters = evaluator.fit_parameters_from_contour(coordinates)

    if sample_parameters is None:
        sample_count = point_count if point_count is not None else len(fit_parameters)
        sample_parameters = evaluator.initial_sample_parameters(sample_count)

    sample_parameters = np.asarray(sample_parameters, dtype=float)
    coordinates_sampled = evaluator.evaluate(sample_parameters, der=0)
    first_derivative = evaluator.evaluate(sample_parameters, der=1)
    second_derivative = evaluator.evaluate(sample_parameters, der=2)

    return SplineData(
        coordinates=coordinates_sampled,
        fit_parameters=fit_parameters,
        sample_parameters=sample_parameters,
        first_derivative=first_derivative,
        second_derivative=second_derivative,
        spline=None,
        method=METHOD_CST_MODIFIED,
        evaluator=evaluator,
        metadata={
            'order': evaluator.order,
            'label': 'CST',
        },
        leading_edge_parameter=float(evaluator.leading_edge_parameter),
    )


def cst_parameters_from_spline_data(spline_data):
    if spline_data is None:
        raise ValueError('No prepared contour available.')
    if getattr(spline_data, 'method', None) != METHOD_CST_MODIFIED:
        raise ValueError('Prepared contour is not using CST.')

    evaluator = getattr(spline_data, 'evaluator', None)
    if evaluator is None:
        raise ValueError('No CST evaluator available for this contour.')

    def _surface_parameters(name, surface):
        return {
            'name': name,
            'order': int(surface.order),
            'coefficients': np.asarray(surface.coefficients, dtype=float).tolist(),
            'nose_coefficient': float(surface.nose_coefficient),
            'trailing_edge_offset': float(surface.trailing_edge_offset),
        }

    return {
        'method': 'CST',
        'order': int(evaluator.order),
        'leading_edge_parameter': float(evaluator.leading_edge_parameter),
        'upper_surface': _surface_parameters('upper', evaluator.upper_surface),
        'lower_surface': _surface_parameters('lower', evaluator.lower_surface),
    }


def format_cst_parameters_text(parameter_data):
    def _surface_lines(title, surface):
        lines = [
            f'{title}',
            f'  Order: {surface["order"]}',
            f'  Nose coefficient: {surface["nose_coefficient"]:.16g}',
            f'  Trailing-edge offset: {surface["trailing_edge_offset"]:.16g}',
            '  Coefficients:',
        ]
        for index, value in enumerate(surface['coefficients']):
            lines.append(f'    A{index}: {value:.16g}')
        return lines

    lines = [
        'CST parameters',
        f'Order: {parameter_data["order"]}',
        f'Leading-edge parameter: {parameter_data["leading_edge_parameter"]:.16g}',
        '',
    ]
    lines.extend(_surface_lines('Upper surface', parameter_data['upper_surface']))
    lines.append('')
    lines.extend(_surface_lines('Lower surface', parameter_data['lower_surface']))
    return '\n'.join(lines)
