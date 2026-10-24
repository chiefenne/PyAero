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
  each cut running TE corner -> outlet. The outer row is split at the two
  TE anchors (where the grid line leaving the TE meets the tunnel) into
  the same three segments, so the TE line lands exactly on the anchor.
  The anchor is set as a fraction (0 = straight up/down from the TE,
  1 = ``ANCHOR_OUTLET_RESERVE`` short of the outlet) or as an angle from
  the vertical; the angle is the same above and below. Sharp TE: both cuts coincide
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
    polyline_cumulative,
    sample_polyline_at,
    sample_te_base,
)

ARC_SAMPLES = 360
STRAIGHT_SAMPLES_PER_UNIT = 40
# Share of the wake length kept between the furthest TE anchor and the
# outlet, so the downstream lines still exit through the tunnel walls.
ANCHOR_OUTLET_RESERVE = 0.1


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


def _polygon_centroid(loop: np.ndarray) -> np.ndarray:
    """Area centroid of a closed polygon (first point == last point)."""
    x, y = loop[:-1, 0], loop[:-1, 1]
    x_next, y_next = loop[1:, 0], loop[1:, 1]
    cross = x * y_next - x_next * y
    area = 0.5 * np.sum(cross)
    if abs(area) < 1.0e-12:
        return loop[:-1].mean(axis=0)
    cx = np.sum((x + x_next) * cross) / (6.0 * area)
    cy = np.sum((y + y_next) * cross) / (6.0 * area)
    return np.array([cx, cy])


def _te_bisector(contour: np.ndarray) -> np.ndarray:
    """Downstream direction bisecting the TE wedge exterior (horizontal
    for symmetric airfoils, tilted by camber/reflex)."""
    upper = contour[0] - contour[1]
    lower = contour[-1] - contour[-2]
    upper = upper / (np.linalg.norm(upper) or 1.0)
    lower = lower / (np.linalg.norm(lower) or 1.0)
    bisector = upper + lower
    norm = np.linalg.norm(bisector)
    if norm <= 1.0e-12 or bisector[0] <= 0.0:
        return np.array([1.0, 0.0])
    return bisector / norm


def _curved_seam(te_point: np.ndarray, bisector: np.ndarray,
                 seam_target: np.ndarray, first_spacing: float,
                 count: int, control_fraction: float = 0.15) -> np.ndarray:
    """O-grid seam line: quadratic Bezier leaving the TE along the wedge
    bisector and bending onto the outer seam point. The bisector start
    gives the near-wall cells on both sides of the seam equal room (a
    straight seam folds cells at reflexed/cambered trailing edges)."""
    seam_length = float(np.linalg.norm(seam_target - te_point))
    control = te_point + bisector * control_fraction * seam_length
    parameters = np.linspace(0.0, 1.0, 600)[:, None]
    bezier = ((1.0 - parameters) ** 2 * te_point[None, :] +
              2.0 * (1.0 - parameters) * parameters * control[None, :] +
              parameters ** 2 * seam_target[None, :])
    distances = geometric_distances(
        polyline_cumulative(bezier)[-1], first_spacing, count)
    return sample_polyline_at(bezier, distances)


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
                   seam_direction: np.ndarray | None = None) -> np.ndarray:
    """Dense closed (CCW) O-grid outer polyline.

    The loop starts/ends at the seam point where the ray from the TE
    along ``seam_direction`` (default +x) meets the outer shape.
    """
    height = settings.tunnel_height
    x_te = float(te_point[0])
    x_outlet = x_te + settings.wake_length

    direction = np.array([1.0, 0.0]) if seam_direction is None \
        else np.asarray(seam_direction, dtype=float)
    norm = np.linalg.norm(direction)
    if norm <= 0.0 or direction[0] <= 0.0:
        direction = np.array([1.0, 0.0])
    else:
        direction = direction / norm

    if settings.tunnel_shape == 'legacy':
        # intersect the ray with the outlet plane x = x_outlet
        travel = (x_outlet - x_te) / direction[0]
        y_seam = float(te_point[1]) + travel * direction[1]
        if abs(y_seam) >= height:
            raise ValueError('Tunnel height must exceed the TE ray offset '
                             'at the outlet.')
        pieces = (
            _straight((x_outlet, y_seam), (x_outlet, height)),
            _straight((x_outlet, height), (x_te, height)),
            _arc((x_te, 0.0), height, 0.5 * np.pi, 1.5 * np.pi),
            _straight((x_te, -height), (x_outlet, -height)),
            _straight((x_outlet, -height), (x_outlet, y_seam)),
        )
    elif settings.tunnel_shape == 'circular':
        # intersect the ray with the circle around mid-chord
        center = np.array([0.5, 0.0])
        seam_point = _ray_circle_exit(te_point, direction, center, height)
        theta_seam = float(np.arctan2(seam_point[1] - center[1],
                                      seam_point[0] - center[0]))
        pieces = (
            _arc(center, height, theta_seam, theta_seam + 2.0 * np.pi),
        )
    else:
        raise ValueError(
            f'Unknown tunnel shape: {settings.tunnel_shape!r}.')
    return _dedupe(np.vstack(pieces))


def _distribute_outer(outline: np.ndarray, count: int,
                      settings: StructuredMeshSettings) -> np.ndarray:
    """O-grid outer row on the closed outline."""
    control = settings.boundary_control
    if control.distribution == 'uniform' or control.clustering_ratio == 1.0:
        outer = distribute_on_polyline(outline, count, 'uniform')
    else:
        # Cluster toward the seam: split at the arclength midpoint (the
        # seam-opposite point), cluster each half toward its seam end.
        half_count = count // 2 + 1
        rest_count = count - half_count + 1
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
    outer[-1] = outer[0]
    return outer


def _ray_circle_exit(origin, direction, center, radius) -> np.ndarray:
    """Point where the ray from ``origin`` (inside the circle) along the
    unit ``direction`` leaves the circle."""
    origin = np.asarray(origin, dtype=float)
    offset = origin - center
    b = float(np.dot(offset, direction))
    c = float(np.dot(offset, offset)) - radius ** 2
    discriminant = b * b - c
    if discriminant <= 0.0 or c >= 0.0:
        raise ValueError('Farfield radius must enclose the airfoil.')
    return origin + (-b + np.sqrt(discriminant)) * direction


def _te_anchor_x(settings: StructuredMeshSettings, te_point: np.ndarray,
                 side: float) -> float:
    """x of the TE anchor on the upper (side=+1) or lower (side=-1)
    tunnel wall, clamped to leave the outlet reserve free."""
    x_te = float(te_point[0])
    x_max = x_te + (1.0 - ANCHOR_OUTLET_RESERVE) * settings.wake_length
    value = settings.te_anchor_value
    if settings.te_anchor_mode == 'fraction':
        if not 0.0 <= value <= 1.0:
            raise ValueError('TE anchor fraction must lie in [0, 1].')
        return x_te + value * (x_max - x_te)
    if settings.te_anchor_mode != 'angle':
        raise ValueError(
            f'Unknown TE anchor mode: {settings.te_anchor_mode!r}.')
    if not 0.0 <= value < 90.0:
        raise ValueError('TE anchor angle must lie in [0, 90) degrees.')
    angle = np.radians(value)
    if settings.tunnel_shape == 'legacy':
        rise = settings.tunnel_height - side * float(te_point[1])
        x_anchor = x_te + rise * np.tan(angle)
    else:
        direction = np.array([np.sin(angle), side * np.cos(angle)])
        x_anchor = float(_ray_circle_exit(
            te_point, direction, np.array([0.5, 0.0]),
            settings.tunnel_height)[0])
    return min(x_anchor, x_max)


def c_outline_segments(settings: StructuredMeshSettings,
                       te_point: np.ndarray):
    """Dense C-mesh outer polylines, CCW: upper wake (outlet -> upper
    anchor), contour (upper anchor -> apex -> lower anchor), lower wake
    (lower anchor -> outlet)."""
    height = settings.tunnel_height
    x_te = float(te_point[0])
    x_outlet = x_te + settings.wake_length
    x_upper = _te_anchor_x(settings, te_point, 1.0)
    x_lower = _te_anchor_x(settings, te_point, -1.0)

    if settings.tunnel_shape == 'legacy':
        upper_wake = _straight((x_outlet, height), (x_upper, height))
        contour_part = np.vstack((
            _straight((x_upper, height), (x_te, height)),
            _arc((x_te, 0.0), height, 0.5 * np.pi, 1.5 * np.pi),
            _straight((x_te, -height), (x_lower, -height)),
        ))
        lower_wake = _straight((x_lower, -height), (x_outlet, -height))
    elif settings.tunnel_shape == 'circular':
        offset = x_outlet - 0.5
        if offset >= 0.95 * height:
            raise ValueError(
                'Wake length reaches past the circular farfield; '
                'increase the radius or shorten the wake.')
        theta_outlet = np.arccos(offset / height)
        theta_upper = np.arccos((x_upper - 0.5) / height)
        theta_lower = 2.0 * np.pi - np.arccos((x_lower - 0.5) / height)
        center = (0.5, 0.0)
        upper_wake = _arc(center, height, theta_outlet, theta_upper)
        contour_part = _arc(center, height, theta_upper, theta_lower)
        lower_wake = _arc(center, height, theta_lower,
                          2.0 * np.pi - theta_outlet)
    else:
        raise ValueError(
            f'Unknown tunnel shape: {settings.tunnel_shape!r}.')
    return _dedupe(upper_wake), _dedupe(contour_part), _dedupe(lower_wake)


def _wake_outer(segment: np.ndarray, count: int, anchor_spacing: float,
                settings: StructuredMeshSettings) -> np.ndarray:
    """Outer nodes on a wake segment running anchor -> outlet.

    Uniform: geometric growth from the contour-segment spacing at the
    anchor (no spacing jump across it). Clustered: fine at the outlet,
    ``clustering_ratio`` times coarser at the anchor.
    """
    control = settings.boundary_control
    length = polyline_cumulative(segment)[-1]
    if control.distribution == 'clustered' and control.clustering_ratio != 1.0:
        return distribute_on_polyline(
            segment[::-1], count, 'clustered',
            control.clustering_ratio)[::-1]
    distances = geometric_distances(length, anchor_spacing, count)
    return sample_polyline_at(segment, distances)


def _distribute_c_outer(settings: StructuredMeshSettings,
                        te_point: np.ndarray, wake_count: int,
                        contour_count: int):
    upper_wake, contour_part, lower_wake = c_outline_segments(
        settings, te_point)
    middle = distribute_on_polyline(contour_part, contour_count, 'uniform')
    anchor_spacing = (polyline_cumulative(contour_part)[-1] /
                      (contour_count - 1))
    upper = _wake_outer(upper_wake[::-1], wake_count, anchor_spacing,
                        settings)[::-1]
    lower = _wake_outer(lower_wake, wake_count, anchor_spacing, settings)
    outer = np.vstack((upper[:-1], middle, lower[1:]))
    return outer, (middle[0], middle[-1])


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
    outer, te_anchors = _distribute_c_outer(
        settings, te_point, len(upper_cut), len(contour))
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
            'te_anchors': te_anchors,
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
    center = _polygon_centroid(wall)
    seam_direction = te_point - center
    outline = tunnel_outline(settings, te_point,
                             seam_direction=seam_direction)
    outer = _distribute_outer(outline, len(wall), settings)
    seam = _curved_seam(te_point, _te_bisector(contour), outer[0],
                        settings.first_layer_thickness,
                        settings.normal_divisions + 1)
    frame = GridFrame(
        wall=wall, outer=outer,
        side_start=seam, side_end=seam.copy(),
        kind='o', te_type=te_type, periodic=True,
        metadata={'contour_slice': contour_slice},
    )
    return validate_frame(frame)
