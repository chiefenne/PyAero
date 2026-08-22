"""Topology builders for the Structured engine: O-grid and C-mesh frames.

Geometry conventions
--------------------
- Contour orientation: TE -> upper -> LE -> lower -> TE (counterclockwise).
  Outer curves are sampled in the same rotational direction so TFI cells
  stay positive.
- Legacy tunnel: half-circle of radius ``tunnel_height`` centered at
  ``(x_te, 0)`` upstream, horizontal walls ``y = +/- tunnel_height`` to the
  outlet plane ``x_outlet = x_te + wake_length``. For O the loop is closed
  by the vertical outlet segment.
- Circular tunnel: circle of radius ``tunnel_height`` centered at mid-chord
  ``(0.5, 0)``. For C it is truncated at the outlet plane.
- C-mesh wall row: ``upper_cut[::-1][:-1] + contour + lower_cut[1:]`` with
  each cut running TE corner -> outlet. Sharp TE: both cuts coincide
  node-for-node (matched cut). Blunt TE: distinct horizontal cuts bounding
  a constant-width wake strip meshed as a second frame.
- O-grid wall row: the contour closed either exactly at the sharp TE or by
  the blunt base nodes; the seam runs from the TE along the horizontal ray
  (+x) to the outer curve.
"""
from __future__ import annotations

import numpy as np

from StructuredCore import (
    GridFrame,
    StructuredMeshSettings,
    detect_te_type,
    distribute_on_polyline,
    geometric_distances,
    sample_te_base,
)

ARC_SAMPLES = 360
STRAIGHT_SAMPLES_PER_UNIT = 40


def build_frames(contour, settings: StructuredMeshSettings):
    contour = np.asarray(contour, dtype=float)
    te_type = detect_te_type(contour)
    if settings.topology == 'o':
        return [_build_o_frame(contour, settings, te_type)]
    if settings.topology == 'c':
        return _build_c_frames(contour, settings, te_type)
    raise ValueError(f'Unknown topology: {settings.topology!r}.')


def validate_frame(frame: GridFrame, tolerance: float = 1.0e-9) -> GridFrame:
    checks = (
        (frame.side_start[0], frame.wall[0], 'side_start/wall'),
        (frame.side_start[-1], frame.outer[0], 'side_start/outer'),
        (frame.side_end[0], frame.wall[-1], 'side_end/wall'),
        (frame.side_end[-1], frame.outer[-1], 'side_end/outer'),
    )
    for actual, expected, label in checks:
        if np.linalg.norm(actual - expected) > tolerance:
            raise ValueError(
                f'Inconsistent grid frame: {label} corners do not '
                f'coincide ({actual} vs {expected}).')
    if len(frame.outer) != len(frame.wall):
        raise ValueError('Grid frame wall and outer point counts differ.')
    if len(frame.side_start) != len(frame.side_end):
        raise ValueError('Grid frame side point counts differ.')
    return frame


def side_segment(p_wall: np.ndarray, p_outer: np.ndarray,
                 first_spacing: float, count: int) -> np.ndarray:
    p_wall = np.asarray(p_wall, dtype=float)
    p_outer = np.asarray(p_outer, dtype=float)
    length = float(np.linalg.norm(p_outer - p_wall))
    if length <= 0.0:
        raise ValueError('Degenerate frame side (wall touches outer).')
    distances = geometric_distances(length, first_spacing, count)
    direction = (p_outer - p_wall) / length
    return p_wall[None, :] + distances[:, None] * direction[None, :]


def _te_spacing(contour: np.ndarray) -> float:
    first = np.linalg.norm(contour[1] - contour[0])
    last = np.linalg.norm(contour[-1] - contour[-2])
    return 0.5 * (first + last)


def _wake_cut(start_point: np.ndarray, x_outlet: float, spacing: float,
              wake_points: int) -> np.ndarray:
    length = x_outlet - start_point[0]
    if length <= 0.0:
        raise ValueError('Wake length must reach past the trailing edge.')
    distances = geometric_distances(length, spacing, wake_points)
    cut = np.column_stack((
        start_point[0] + distances,
        np.full(wake_points, start_point[1]),
    ))
    cut[0] = start_point       # exact, no float drift
    return cut


def _dedupe(points: np.ndarray) -> np.ndarray:
    keep = np.ones(len(points), dtype=bool)
    keep[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1) > 1.0e-12
    return points[keep]


def _straight(p_from, p_to) -> np.ndarray:
    p_from = np.asarray(p_from, dtype=float)
    p_to = np.asarray(p_to, dtype=float)
    length = np.linalg.norm(p_to - p_from)
    count = max(2, int(np.ceil(length * STRAIGHT_SAMPLES_PER_UNIT)))
    fractions = np.linspace(0.0, 1.0, count)[:, None]
    return p_from[None, :] * (1.0 - fractions) + p_to[None, :] * fractions


def _arc(center, radius, theta_from, theta_to) -> np.ndarray:
    theta = np.linspace(theta_from, theta_to, ARC_SAMPLES)
    return np.column_stack((center[0] + radius * np.cos(theta),
                            center[1] + radius * np.sin(theta)))


def tunnel_outline(settings: StructuredMeshSettings, te_point: np.ndarray,
                   te_type: str) -> np.ndarray:
    """Dense outer-curve polyline: open for C, closed (CCW) for O."""
    height = settings.tunnel_height
    x_te = float(te_point[0])
    x_outlet = x_te + settings.wake_length

    if settings.topology == 'c':
        if settings.tunnel_shape == 'legacy':
            pieces = (
                _straight((x_outlet, height), (x_te, height)),
                _arc((x_te, 0.0), height, 0.5 * np.pi, 1.5 * np.pi),
                _straight((x_te, -height), (x_outlet, -height)),
            )
        elif settings.tunnel_shape == 'circular':
            offset = x_outlet - 0.5
            if offset >= 0.95 * height:
                raise ValueError(
                    'Wake length reaches past the circular farfield; '
                    'increase the radius or shorten the wake.')
            y_cut = np.sqrt(height ** 2 - offset ** 2)
            theta_outlet = np.arctan2(y_cut, offset)
            pieces = (
                _arc((0.5, 0.0), height, theta_outlet,
                     2.0 * np.pi - theta_outlet),
            )
        else:
            raise ValueError(
                f'Unknown tunnel shape: {settings.tunnel_shape!r}.')
        return _dedupe(np.vstack(pieces))

    # O topology: closed loop starting/ending at the seam point on the
    # horizontal ray from the TE, sampled counterclockwise.
    y_te = float(te_point[1])
    if settings.tunnel_shape == 'legacy':
        if abs(y_te) >= height:
            raise ValueError('Tunnel height must exceed the TE offset.')
        pieces = (
            _straight((x_outlet, y_te), (x_outlet, height)),
            _straight((x_outlet, height), (x_te, height)),
            _arc((x_te, 0.0), height, 0.5 * np.pi, 1.5 * np.pi),
            _straight((x_te, -height), (x_outlet, -height)),
            _straight((x_outlet, -height), (x_outlet, y_te)),
        )
    elif settings.tunnel_shape == 'circular':
        if abs(y_te) >= height:
            raise ValueError('Farfield radius must exceed the TE offset.')
        theta_seam = np.arcsin(y_te / height)
        pieces = (
            _arc((0.5, 0.0), height, theta_seam, theta_seam + 2.0 * np.pi),
        )
    else:
        raise ValueError(
            f'Unknown tunnel shape: {settings.tunnel_shape!r}.')
    return _dedupe(np.vstack(pieces))


def _distribute_outer(outline: np.ndarray, count: int,
                      settings: StructuredMeshSettings,
                      closed: bool) -> np.ndarray:
    control = settings.boundary_control
    if control.distribution == 'uniform' or control.clustering_ratio == 1.0:
        outer = distribute_on_polyline(outline, count, 'uniform')
    else:
        # Cluster toward the outlet ends: split at the arclength midpoint
        # (upstream apex for C, seam-opposite point for O), cluster each
        # half toward its outlet/seam end.
        half_count = count // 2 + 1
        rest_count = count - half_count + 1
        from StructuredCore import polyline_cumulative, sample_polyline_at
        cumulative = polyline_cumulative(outline)
        split_distance = 0.5 * cumulative[-1]
        split_index = int(np.searchsorted(cumulative, split_distance))
        split_point = sample_polyline_at(
            outline, np.array([split_distance]))[0]
        first_half = np.vstack((outline[:split_index], split_point[None, :]))
        second_half = np.vstack((split_point[None, :],
                                 outline[split_index:]))
        first = distribute_on_polyline(
            _dedupe(first_half), half_count, 'clustered',
            control.clustering_ratio)
        second = distribute_on_polyline(
            _dedupe(second_half)[::-1], rest_count, 'clustered',
            control.clustering_ratio)[::-1]
        outer = np.vstack((first, second[1:]))
    if closed:
        outer[-1] = outer[0]
    return outer


def _build_c_frames(contour: np.ndarray, settings: StructuredMeshSettings,
                    te_type: str):
    te_point = 0.5 * (contour[0] + contour[-1])
    x_outlet = float(te_point[0]) + settings.wake_length
    spacing = _te_spacing(contour)

    if te_type == 'sharp':
        cut = _wake_cut(te_point, x_outlet, spacing, settings.wake_points)
        upper_cut = cut
        lower_cut = cut
    else:
        upper_cut = _wake_cut(contour[0], x_outlet, spacing,
                              settings.wake_points)
        lower_cut = _wake_cut(contour[-1], x_outlet, spacing,
                              settings.wake_points)

    wall = np.vstack((upper_cut[::-1][:-1], contour, lower_cut[1:]))
    outline = tunnel_outline(settings, te_point, te_type)
    outer = _distribute_outer(outline, len(wall), settings, closed=False)
    side_count = settings.normal_divisions + 1
    side_start = side_segment(wall[0], outer[0],
                              settings.first_layer_thickness, side_count)
    side_end = side_segment(wall[-1], outer[-1],
                            settings.first_layer_thickness, side_count)
    contour_start = len(upper_cut) - 1
    main = GridFrame(
        wall=wall, outer=outer,
        side_start=side_start, side_end=side_end,
        kind='c', te_type=te_type,
        metadata={
            'wake_cut_matched': te_type == 'sharp',
            'x_outlet': x_outlet,
            'contour_slice': (contour_start, contour_start + len(contour)),
        },
    )
    validate_frame(main)
    if te_type == 'sharp':
        return [main]

    base = sample_te_base(contour[-1], contour[0], spacing)
    outlet_segment = np.column_stack((
        np.full(len(base), x_outlet),
        np.linspace(lower_cut[-1][1], upper_cut[-1][1], len(base)),
    ))
    strip = GridFrame(
        wall=lower_cut, outer=upper_cut,
        side_start=base, side_end=outlet_segment,
        kind='wake_strip', te_type='blunt',
        metadata={'base': base, 'x_outlet': x_outlet},
    )
    validate_frame(strip)
    return [main, strip]


def _build_o_frame(contour: np.ndarray, settings: StructuredMeshSettings,
                   te_type: str) -> GridFrame:
    spacing = _te_spacing(contour)
    if te_type == 'sharp':
        wall = contour.copy()
        wall[-1] = wall[0]           # exact loop closure
        contour_slice = (0, len(wall))
    else:
        base = sample_te_base(contour[-1], contour[0], spacing)
        wall = np.vstack((contour, base[1:]))
        contour_slice = (0, len(contour))

    te_point = wall[0]
    outline = tunnel_outline(settings, te_point, te_type)
    outer = _distribute_outer(outline, len(wall), settings, closed=True)
    seam = side_segment(te_point, outer[0],
                        settings.first_layer_thickness,
                        settings.normal_divisions + 1)
    frame = GridFrame(
        wall=wall, outer=outer,
        side_start=seam, side_end=seam.copy(),
        kind='o', te_type=te_type, periodic=True,
        metadata={'contour_slice': contour_slice},
    )
    return validate_frame(frame)
