from __future__ import annotations

from typing import Sequence

import numpy as np

from QuadMonitor import LineMetricField, LineMonitor


MINIMUM_LENGTH = 1.0e-15


def _as_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(points, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError('Polyline points must be an N x 2 array.')
    return array


def _as_monitor(monitor, point_count: int) -> LineMonitor:
    if isinstance(monitor, LineMonitor):
        line_monitor = monitor
    else:
        line_monitor = LineMonitor(monitor)

    if len(line_monitor.values) != point_count:
        raise ValueError('Monitor values must match the line point count.')
    return line_monitor


def _as_metric(metric, point_count: int) -> LineMetricField:
    if isinstance(metric, LineMetricField):
        line_metric = metric
    else:
        line_metric = LineMetricField(metric)

    if len(line_metric.tensors) != point_count:
        raise ValueError('Metric tensors must match the line point count.')
    return line_metric


def polyline_arc_lengths(points: Sequence[Sequence[float]]) -> np.ndarray:
    points_array = _as_points(points)
    if len(points_array) < 2:
        return np.array([], dtype=float)
    return np.linalg.norm(points_array[1:] - points_array[:-1], axis=1)


def weighted_segment_lengths(points: Sequence[Sequence[float]], monitor=None,
                             metric=None) -> np.ndarray:
    points_array = _as_points(points)
    if monitor is not None and metric is not None:
        raise ValueError('Provide either a monitor or a metric, not both.')

    if len(points_array) < 2:
        return np.array([], dtype=float)

    if metric is not None:
        return _as_metric(metric, len(points_array)).segment_lengths(points_array)

    arc_lengths = polyline_arc_lengths(points_array)
    if monitor is None:
        return arc_lengths

    monitor_values = _as_monitor(monitor, len(points_array)).for_points(points_array)
    segment_monitor = 0.5 * (monitor_values[:-1] + monitor_values[1:])
    return segment_monitor * arc_lengths


def _cumulative_profile(segment_lengths: np.ndarray) -> np.ndarray:
    if segment_lengths.size == 0:
        return np.array([0.0], dtype=float)
    return np.concatenate(([0.0], np.cumsum(segment_lengths)))


def _compress_profile(cumulative: np.ndarray, points: np.ndarray):
    if cumulative.size != len(points):
        raise ValueError('Cumulative profile must match the point count.')

    if cumulative.size <= 1:
        return cumulative, points

    keep = np.ones(cumulative.size, dtype=bool)
    keep[1:] = np.diff(cumulative) > MINIMUM_LENGTH
    keep[0] = True
    keep[-1] = True
    return cumulative[keep], points[keep]


def redistribute_polyline(points: Sequence[Sequence[float]], point_count: int | None = None,
                          monitor=None, metric=None) -> np.ndarray:
    points_array = _as_points(points)
    if point_count is None:
        point_count = len(points_array)
    point_count = int(point_count)

    if point_count < 0:
        raise ValueError('Point count must be non-negative.')
    if len(points_array) == 0:
        return np.empty((0, 2), dtype=float)
    if len(points_array) == 1:
        return np.repeat(points_array, point_count, axis=0)

    segment_lengths = weighted_segment_lengths(
        points_array,
        monitor=monitor,
        metric=metric,
    )
    cumulative = _cumulative_profile(segment_lengths)

    if cumulative[-1] <= MINIMUM_LENGTH:
        cumulative = _cumulative_profile(polyline_arc_lengths(points_array))

    if cumulative[-1] <= MINIMUM_LENGTH:
        return np.repeat(points_array[:1], point_count, axis=0)

    cumulative, points_array = _compress_profile(cumulative, points_array)
    targets = np.linspace(0.0, cumulative[-1], point_count)
    x_values = np.interp(targets, cumulative, points_array[:, 0])
    y_values = np.interp(targets, cumulative, points_array[:, 1])
    return np.column_stack((x_values, y_values))
