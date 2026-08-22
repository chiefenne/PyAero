# Structured Grid Framework — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new selectable "Structured" mesh engine: O-grid and C-mesh frames × legacy/circular tunnel shapes × TFI (standard + Hermite), with the exact-normal ortho block and both sharp/blunt trailing edges handled from the start.

**Architecture:** Topology builders produce `GridFrame` objects (boundary polylines only); the TFI algorithm fills any frame into a structured point array; `OrthoLayers` optionally inserts exact-normal near-wall rows; `StructuredEngine` composes these and emits ordinary `BlockMesh` objects registered on `Windtunnel` exactly like the experimental engines. A blunt-TE C-mesh emits two blocks (main C + wake strip).

**Tech Stack:** Python 3.13, numpy, scipy (splprep/splev), PySide6 (GUI task only), pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-structured-grid-framework-design.md` (phases 2–5 of the spec — elliptic, hyperbolic, H-mesh, smoothers — are explicitly NOT in this plan).

## Global Constraints

- Wall invariant: airfoil wall nodes are taken **verbatim** from `spline_data.coordinates` — never resampled. (Spec: "mesh lines emerging from the airfoil start exactly at the prepared spline points".)
- TE type is **detected** from the contour endpoint gap, never a user switch.
- New modules are flat in `src/` (project convention): `StructuredCore.py`, `StructuredTopologies.py`, `OrthoLayers.py`, `GridTFI.py`, `StructuredEngine.py`.
- The engine emits `BlockMesh` objects with `ULines[0]` = wall row (same convention as `ExperimentalCGrid`), registered via `Windtunnel.registerBlock`, so export/quality/drawing work unchanged.
- Validation failures raise `ValueError` with user-readable messages (surfaced by the existing workflow `_show_message` path).
- Test python: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest` (system python lacks numpy/scipy/PySide6).
- Test airfoils (real data, existing files):
  - `lib_AE/Construct2D_2.1.4/sample_airfoils/naca0012.dat`
  - `lib_AE/Construct2D_2.1.4/sample_airfoils/naca2315.dat`
  - `boundary_layer_code/Airfoils/MW-166-39-44-43.dat`
- Contour orientation in this codebase: TE → upper surface → LE → lower surface → TE, i.e. `x` starts near 1.0, decreases to 0.0, increases back to 1.0; first `y` values positive. Sharp TE: first point == last point (within tolerance). Blunt TE: endpoints separated by the base gap.
- `spline_data` is `ContourData.SplineData`: `coordinates` is a **tuple** `(x_array, y_array)` (convert with `np.column_stack`), `sample_parameters` are the parameter values of those points, `evaluate(t, der=1)` gives exact tangents.
- Shared files `src/Meshing.py`, `src/ToolBox.py`, `src/ToolboxPagesMeshing.py` carry **unrelated uncommitted user work**. Never `git add` them wholesale: before staging, run `git diff <file>` — if it contains anything besides this task's hunks, leave the file unstaged and say so in the commit body ("wiring in <file> left unstaged, file carries unrelated WIP"). New files are always safe to stage.
- Commit style: imperative subject, no type prefix (matches `git log`), trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: StructuredCore — settings, frame dataclass, TE detection, distributions

**Files:**
- Create: `src/StructuredCore.py`
- Test: `tests/test_structured_core.py`

**Interfaces:**
- Consumes: nothing (foundation module; only numpy).
- Produces (used by every later task):
  - `TunnelBoundaryControl(distribution: str, clustering_ratio: float, angle_mode: str)`
  - `StructuredMeshSettings(topology, tunnel_shape, tunnel_height, wake_length, tfi_variant, normal_divisions, first_layer_thickness, wake_points, ortho_layers, ortho_growth, boundary_control)`
  - `GridFrame(wall, outer, side_start, side_end, kind, te_type, periodic, metadata)` — all boundary arrays `(n, 2)` float
  - `detect_te_type(contour: np.ndarray, tolerance: float = 1e-6) -> str` — `'sharp' | 'blunt'`
  - `contour_array(spline_data) -> np.ndarray` — `(n, 2)` from the coordinates tuple
  - `geometric_distances(length, first_spacing, count) -> np.ndarray` — monotone cumulative distances `0 … length`, first step == `first_spacing`, growth solved
  - `sample_te_base(p_from, p_to, spacing) -> np.ndarray` — gap nodes across a blunt base **including both endpoints**, symmetric spacing matched to `spacing`
  - `distribute_on_polyline(points, count, distribution='uniform', ratio=1.0) -> np.ndarray` — resample a polyline by arclength; `'uniform'` or `'clustered'` (geometric spacing, last/first == ratio)

- [x] **Step 1: Write the failing tests**

```python
# tests/test_structured_core.py
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import StructuredCore as core


def _sharp_contour():
    x = np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0])
    y = np.array([0.0, 0.05, 0.08, 0.0, -0.08, -0.05, 0.0])
    return np.column_stack((x, y))


def _blunt_contour():
    x = np.array([1.0, 0.75, 0.35, 0.0, 0.35, 0.75, 1.0])
    y = np.array([0.01, 0.05, 0.08, 0.0, -0.08, -0.05, -0.01])
    return np.column_stack((x, y))


def test_detect_te_type():
    assert core.detect_te_type(_sharp_contour()) == 'sharp'
    assert core.detect_te_type(_blunt_contour()) == 'blunt'


def test_geometric_distances_first_spacing_and_length():
    d = core.geometric_distances(length=2.0, first_spacing=0.01, count=30)
    assert d.shape == (30,)
    assert d[0] == 0.0
    assert np.isclose(d[-1], 2.0)
    assert np.isclose(d[1] - d[0], 0.01, rtol=1e-6)
    assert np.all(np.diff(d) > 0.0)
    # growth is monotone: each step at least as large as the previous
    steps = np.diff(d)
    assert np.all(steps[1:] >= steps[:-1] - 1e-12)


def test_sample_te_base_endpoints_verbatim():
    lower = np.array([1.0, -0.01])
    upper = np.array([1.0, 0.01])
    base = core.sample_te_base(lower, upper, spacing=0.004)
    assert np.allclose(base[0], lower)
    assert np.allclose(base[-1], upper)
    assert len(base) >= 3
    assert np.all(np.diff(base[:, 1]) > 0.0)


def test_distribute_on_polyline_uniform_and_clustered():
    line = np.column_stack((np.linspace(0.0, 10.0, 5), np.zeros(5)))
    uniform = core.distribute_on_polyline(line, 21, distribution='uniform')
    assert uniform.shape == (21, 2)
    assert np.allclose(uniform[0], line[0])
    assert np.allclose(uniform[-1], line[-1])
    assert np.allclose(np.diff(uniform[:, 0]), 0.5)

    clustered = core.distribute_on_polyline(
        line, 21, distribution='clustered', ratio=4.0)
    steps = np.diff(clustered[:, 0])
    assert np.isclose(steps[-1] / steps[0], 4.0, rtol=0.05)


def test_settings_defaults_valid():
    settings = core.StructuredMeshSettings()
    assert settings.topology in ('c', 'o')
    assert settings.tunnel_shape in ('legacy', 'circular')
    assert settings.boundary_control.distribution == 'uniform'
```

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_core.py -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'StructuredCore'`

- [x] **Step 3: Implement `src/StructuredCore.py`**

```python
"""Shared dataclasses and distribution utilities for the Structured engine.

See docs/superpowers/specs/2026-08-22-structured-grid-framework-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class TunnelBoundaryControl:
    distribution: str = 'uniform'      # 'uniform' | 'clustered'
    clustering_ratio: float = 1.0      # last/first spacing when clustered
    angle_mode: str = 'free'           # 'free' | 'orthogonal'


@dataclass(slots=True)
class StructuredMeshSettings:
    topology: str = 'c'                # 'c' | 'o'
    tunnel_shape: str = 'legacy'       # 'legacy' | 'circular'
    tunnel_height: float = 3.5         # legacy half-height / circular radius
    wake_length: float = 7.0           # TE to outlet (C-mesh only)
    tfi_variant: str = 'standard'      # 'standard' | 'hermite'
    normal_divisions: int = 60         # total wall->outer rows (incl. ortho)
    first_layer_thickness: float = 0.002
    wake_points: int = 60              # nodes along each wake cut (C-mesh)
    ortho_layers: int = 0              # 0 = ortho block off
    ortho_growth: float = 1.15
    boundary_control: TunnelBoundaryControl = field(
        default_factory=TunnelBoundaryControl
    )


@dataclass(slots=True)
class GridFrame:
    """Boundary frame a volume algorithm fills. All arrays are (n, 2) float.

    wall is row j=0, outer is row j=nj-1; side_start / side_end are the
    i=0 / i=ni-1 columns running wall -> outer. len(side_start) ==
    len(side_end) and side endpoints coincide with wall/outer endpoints.
    """
    wall: np.ndarray
    outer: np.ndarray
    side_start: np.ndarray
    side_end: np.ndarray
    kind: str                  # 'o' | 'c' | 'wake_strip'
    te_type: str               # 'sharp' | 'blunt'
    periodic: bool = False
    metadata: dict = field(default_factory=dict)


def contour_array(spline_data) -> np.ndarray:
    x, y = spline_data.coordinates
    return np.column_stack((np.asarray(x, float), np.asarray(y, float)))


def detect_te_type(contour: np.ndarray, tolerance: float = 1.0e-6) -> str:
    contour = np.asarray(contour, dtype=float)
    chord = float(np.ptp(contour[:, 0])) or 1.0
    gap = float(np.linalg.norm(contour[0] - contour[-1]))
    return 'sharp' if gap <= tolerance * chord else 'blunt'


def _growth_for_length(length: float, first_spacing: float,
                       divisions: int) -> float:
    """Solve sum_{k=0}^{divisions-1} first*g**k == length for g by bisection."""
    if divisions * first_spacing >= length:
        return 1.0
    low, high = 1.0 + 1.0e-12, 10.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        total = first_spacing * (mid ** divisions - 1.0) / (mid - 1.0)
        if total < length:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def geometric_distances(length: float, first_spacing: float,
                        count: int) -> np.ndarray:
    if count < 2:
        raise ValueError('geometric_distances needs count >= 2.')
    if first_spacing <= 0.0 or length <= 0.0:
        raise ValueError('length and first_spacing must be positive.')
    divisions = count - 1
    if divisions * first_spacing >= length:
        # First spacing too large to grow: fall back to uniform.
        return np.linspace(0.0, length, count)
    growth = _growth_for_length(length, first_spacing, divisions)
    steps = first_spacing * growth ** np.arange(divisions)
    distances = np.concatenate(([0.0], np.cumsum(steps)))
    distances *= length / distances[-1]
    return distances


def sample_te_base(p_from: np.ndarray, p_to: np.ndarray,
                   spacing: float) -> np.ndarray:
    p_from = np.asarray(p_from, dtype=float)
    p_to = np.asarray(p_to, dtype=float)
    gap = float(np.linalg.norm(p_to - p_from))
    if gap <= 0.0:
        raise ValueError('sample_te_base needs distinct endpoints.')
    divisions = max(2, int(round(gap / max(spacing, 1.0e-12))))
    fractions = np.linspace(0.0, 1.0, divisions + 1)[:, None]
    return p_from[None, :] * (1.0 - fractions) + p_to[None, :] * fractions


def _polyline_cumulative(points: np.ndarray) -> np.ndarray:
    deltas = np.diff(points, axis=0)
    return np.concatenate(([0.0], np.cumsum(np.hypot(deltas[:, 0],
                                                     deltas[:, 1]))))


def sample_polyline_at(points: np.ndarray,
                       distances: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    cumulative = _polyline_cumulative(points)
    distances = np.clip(distances, 0.0, cumulative[-1])
    x = np.interp(distances, cumulative, points[:, 0])
    y = np.interp(distances, cumulative, points[:, 1])
    return np.column_stack((x, y))


def distribute_on_polyline(points: np.ndarray, count: int,
                           distribution: str = 'uniform',
                           ratio: float = 1.0) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    length = _polyline_cumulative(points)[-1]
    if distribution == 'uniform' or ratio == 1.0:
        distances = np.linspace(0.0, length, count)
    elif distribution == 'clustered':
        growth = ratio ** (1.0 / (count - 2))
        steps = growth ** np.arange(count - 1)
        distances = np.concatenate(([0.0], np.cumsum(steps)))
        distances *= length / distances[-1]
    else:
        raise ValueError(
            f'Unknown boundary distribution: {distribution!r}.')
    return sample_polyline_at(points, distances)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_core.py -v`
Expected: all PASS

- [x] **Step 5: Commit**

```bash
git add src/StructuredCore.py tests/test_structured_core.py
git commit -m "Add StructuredCore: frame dataclasses, TE detection, distributions" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: StructuredTopologies — O and C frames × both tunnels × both TE types

**Files:**
- Create: `src/StructuredTopologies.py`
- Test: `tests/test_structured_topologies.py`

**Interfaces:**
- Consumes (Task 1): `GridFrame`, `StructuredMeshSettings`, `detect_te_type`, `geometric_distances`, `sample_te_base`, `sample_polyline_at`, `distribute_on_polyline`, `_polyline_cumulative`-style arclength via public helpers.
- Produces (used by Tasks 4–5):
  - `build_frames(contour: np.ndarray, settings: StructuredMeshSettings) -> list[GridFrame]` — the single entry point. One frame for O (any TE) and sharp-TE C; `[main_c_frame, wake_strip_frame]` for blunt-TE C.
  - `tunnel_outline(settings, te_point: np.ndarray, te_type: str) -> np.ndarray` — dense polyline of the outer curve (open for C, closed for O), before distribution is applied.

**Geometry conventions (bake these into the module docstring):**
- Contour orientation: TE → upper → LE → lower → TE (counterclockwise). Outer curves are sampled in the same rotational direction so TFI cells stay positive.
- **Legacy tunnel**: half-circle of radius `tunnel_height` centered at `(x_te, 0)` upstream, horizontal walls `y = ±tunnel_height` to the outlet plane `x_outlet = x_te + wake_length`. For O the loop is closed by the vertical outlet segment.
- **Circular tunnel**: circle of radius `tunnel_height` centered at `(0.5, 0.0)` (mid-chord). For C it is truncated at the outlet plane; **validate** `0.5 + tunnel_height > x_outlet + 0.05 * tunnel_height` else `ValueError('Wake length reaches past the circular farfield; increase radius or shorten wake.')`.
- **C-mesh wall row** = `upper_cut[::-1][:-1]` + `contour` + `lower_cut[1:]`, where each cut runs TE-corner → outlet with `wake_points` nodes at `geometric_distances(wake_length, te_spacing, wake_points)`; `te_spacing` = mean of the first and last contour segment lengths. Sharp TE: both cuts start at the single TE point and coincide node-for-node (`metadata['wake_cut_matched'] = True`). Blunt TE: the cuts start at `contour[0]` / `contour[-1]` and run horizontally (constant strip width).
- **O-grid wall row**: sharp → contour with last node snapped onto the first (closure; they already coincide within the sharp tolerance). Blunt → `contour` + `sample_te_base(contour[-1], contour[0], te_spacing)[1:]` so the base nodes close the loop and the final node equals `contour[0]`.
- **O seam**: intersection of the horizontal ray from the TE (+x direction) with the outer curve; the outer loop is sampled starting and ending there. `side_start` = `side_end` = straight segment TE → seam point with `geometric_distances(seam_length, first_layer_thickness, normal_divisions + 1)`; `periodic=True`.
- **C sides**: vertical outlet segments from each wall end to the matching outer corner, same geometric distribution.
- **Wake strip frame** (blunt C only): i runs downstream, j across the base. `wall` = lower cut, `outer` = upper cut, `side_start` = base nodes (lower corner → upper corner, verbatim the same array used to bound the main block), `side_end` = outlet segment with the same node count as the base. `metadata['base'] = base_nodes`, `kind='wake_strip'`.
- **Outer distribution**: apply `distribute_on_polyline(outline, ni_wall, settings.boundary_control.distribution, settings.boundary_control.clustering_ratio)` so `len(outer) == len(wall)`. For C with `'clustered'`, cluster toward **both** outlet ends symmetrically (split the outline at its upstream apex, cluster each half toward its outlet end, concatenate).
- Every frame's `side_start[0] == wall[0]`, `side_start[-1] == outer[0]`, `side_end[0] == wall[-1]`, `side_end[-1] == outer[-1]` — assert this in a module-level `validate_frame(frame)` helper that raises `ValueError` on violation; call it before returning.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_structured_topologies.py
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import StructuredCore as core
import StructuredTopologies as topo


def _load_dat(path):
    xs, ys = [], []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
        except ValueError:
            continue
    return np.column_stack((np.array(xs), np.array(ys)))


NACA0012 = PROJECT_ROOT / 'lib_AE' / 'Construct2D_2.1.4' / \
    'sample_airfoils' / 'naca0012.dat'


def _sharp_contour():
    contour = _load_dat(NACA0012)
    contour[-1] = contour[0]          # force exactly sharp
    return contour


def _blunt_contour(thickness=0.005, blend=0.6):
    contour = _load_dat(NACA0012)
    x, y = contour[:, 0], contour[:, 1].copy()
    ramp = np.clip((x - (1.0 - blend)) / blend, 0.0, 1.0) ** 2
    le_index = int(np.argmin(x))
    y[:le_index] += 0.5 * thickness * ramp[:le_index]     # upper surface
    y[le_index:] -= 0.5 * thickness * ramp[le_index:]     # lower surface
    return np.column_stack((x, y))


def _contour_embedded_in_wall(wall, contour):
    """True if contour appears as a contiguous verbatim slice of wall."""
    n = len(contour)
    for start in range(len(wall) - n + 1):
        if np.allclose(wall[start:start + n], contour, atol=1e-12):
            return True
    return False


def test_c_sharp_single_frame_wall_verbatim():
    settings = core.StructuredMeshSettings(topology='c')
    frames = topo.build_frames(_sharp_contour(), settings)
    assert len(frames) == 1
    frame = frames[0]
    assert frame.te_type == 'sharp'
    assert frame.metadata.get('wake_cut_matched') is True
    assert _contour_embedded_in_wall(frame.wall, _sharp_contour())
    assert len(frame.outer) == len(frame.wall)
    assert len(frame.side_start) == settings.normal_divisions + 1


def test_c_blunt_two_frames_shared_cuts_and_base():
    settings = core.StructuredMeshSettings(topology='c')
    contour = _blunt_contour()
    frames = topo.build_frames(contour, settings)
    assert len(frames) == 2
    main, strip = frames
    assert main.te_type == 'blunt'
    assert strip.kind == 'wake_strip'
    assert _contour_embedded_in_wall(main.wall, contour)
    base = strip.metadata['base']
    assert np.allclose(base[0], contour[-1])
    assert np.allclose(base[-1], contour[0])
    # strip boundaries are the same wake-cut nodes bounding the main wall
    wake_points = settings.wake_points
    lower_cut_in_main = main.wall[-wake_points:]
    upper_cut_in_main = main.wall[:wake_points][::-1]
    assert np.allclose(strip.wall, lower_cut_in_main)
    assert np.allclose(strip.outer, upper_cut_in_main)


def test_o_blunt_closed_loop_with_base():
    settings = core.StructuredMeshSettings(topology='o',
                                           tunnel_shape='circular')
    contour = _blunt_contour()
    frames = topo.build_frames(contour, settings)
    assert len(frames) == 1
    frame = frames[0]
    assert frame.periodic is True
    assert np.allclose(frame.wall[0], frame.wall[-1])
    assert _contour_embedded_in_wall(frame.wall, contour)


def test_o_sharp_both_tunnels():
    contour = _sharp_contour()
    for shape in ('legacy', 'circular'):
        settings = core.StructuredMeshSettings(topology='o',
                                               tunnel_shape=shape)
        frame = topo.build_frames(contour, settings)[0]
        assert np.allclose(frame.wall[0], frame.wall[-1])
        assert len(frame.outer) == len(frame.wall)


def test_circular_c_wake_too_long_raises():
    settings = core.StructuredMeshSettings(
        topology='c', tunnel_shape='circular',
        tunnel_height=2.0, wake_length=7.0)
    try:
        topo.build_frames(_sharp_contour(), settings)
    except ValueError as error:
        assert 'farfield' in str(error).lower() or \
               'wake' in str(error).lower()
    else:
        raise AssertionError('Expected ValueError for wake past farfield.')
```

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_topologies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'StructuredTopologies'`

- [x] **Step 3: Implement `src/StructuredTopologies.py`**

Implement exactly the conventions above. Skeleton with the non-obvious parts spelled out:

```python
from __future__ import annotations

import numpy as np

from StructuredCore import (
    GridFrame,
    StructuredMeshSettings,
    detect_te_type,
    distribute_on_polyline,
    geometric_distances,
    sample_polyline_at,
    sample_te_base,
)

DENSE_OUTLINE_POINTS = 720


def build_frames(contour, settings: StructuredMeshSettings):
    contour = np.asarray(contour, dtype=float)
    te_type = detect_te_type(contour)
    if settings.topology == 'o':
        return [_build_o_frame(contour, settings, te_type)]
    if settings.topology == 'c':
        return _build_c_frames(contour, settings, te_type)
    raise ValueError(f'Unknown topology: {settings.topology!r}.')


def _te_spacing(contour):
    first = np.linalg.norm(contour[1] - contour[0])
    last = np.linalg.norm(contour[-1] - contour[-2])
    return 0.5 * (first + last)


def _wake_cut(start_point, x_outlet, spacing, wake_points):
    length = x_outlet - start_point[0]
    distances = geometric_distances(length, spacing, wake_points)
    cut = np.column_stack((
        start_point[0] + distances,
        np.full(wake_points, start_point[1]),
    ))
    cut[0] = start_point       # exact, no float drift
    return cut


def side_segment(p_wall, p_outer, first_spacing, count):
    length = np.linalg.norm(p_outer - p_wall)
    distances = geometric_distances(length, first_spacing, count)
    direction = (p_outer - p_wall) / length
    return p_wall[None, :] + distances[:, None] * direction[None, :]
```

`_build_c_frames` (structure; fill in the straightforward parts):

1. `te_point` = midpoint of `contour[0]` and `contour[-1]`; `x_outlet = te_point[0] + settings.wake_length`.
2. Sharp: one cut from `te_point`; `upper_cut = lower_cut = _wake_cut(...)`. Blunt: `upper_cut = _wake_cut(contour[0], ...)`, `lower_cut = _wake_cut(contour[-1], ...)`.
3. `wall = np.vstack((upper_cut[::-1][:-1], contour, lower_cut[1:]))`.
4. Outline: `tunnel_outline(settings, te_point, te_type)` returns the open dense polyline from `(x_outlet, +H)` upstream over the top, around, back to `(x_outlet, -H)` (legacy: straight top wall → semicircle → straight bottom wall; circular: the truncated arc, endpoints exactly on the outlet plane).
5. `outer = distribute_on_polyline(outline, len(wall), distribution, ratio)` — for `'clustered'`, split the outline at the upstream apex (minimum x), distribute each half with clustering toward its outlet end, and `np.vstack` (drop the duplicated apex node).
6. Sides: `side_segment(wall[0], outer[0], first_layer_thickness, normal_divisions + 1)` and the same at the other end. Both wall/outer ends sit on the outlet plane, so the sides are vertical.
7. Main frame: `GridFrame(wall, outer, side_start, side_end, kind='c', te_type=te_type, metadata={'wake_cut_matched': te_type == 'sharp', 'x_outlet': x_outlet, 'contour_slice': (len(upper_cut) - 1, len(upper_cut) - 1 + len(contour))})`.
8. Blunt only — the strip: `base = sample_te_base(contour[-1], contour[0], _te_spacing(contour))`; `outlet_segment` = straight segment `(x_outlet, lower_cut[-1][1]) → (x_outlet, upper_cut[-1][1])` with `len(base)` nodes (uniform); `strip = GridFrame(wall=lower_cut, outer=upper_cut, side_start=base, side_end=outlet_segment, kind='wake_strip', te_type='blunt', metadata={'base': base})`. Return `[main, strip]`.

`_build_o_frame`:

1. Wall loop per the conventions block (snap-close sharp; append `base[1:]` for blunt, base from `contour[-1]` to `contour[0]`).
2. `te_point = wall[0]`; seam target = intersection of the ray `y = te_point[1], x >= te_point[0]` with the outer shape (legacy: the outlet segment at `x_outlet`; circular: circle point at that y, right half). Compute analytically per shape.
3. Outline: closed dense polyline sampled counterclockwise starting/ending at the seam target (legacy: outlet segment split at the seam point → up the outlet, along the top wall, semicircle, bottom wall, up the outlet back to seam; circular: full circle from seam angle).
4. `outer = distribute_on_polyline(outline, len(wall), ...)`; force `outer[-1] = outer[0]`.
5. `seam = side_segment(wall[0], outer[0], first_layer_thickness, normal_divisions + 1)`; frame with `side_start=seam, side_end=seam.copy(), periodic=True, kind='o'`.

Both builders end with `validate_frame(frame)` (endpoint-coincidence assertions, `ValueError` on failure) — also verify the circular-C wake-length constraint **before** building anything.

- [x] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_topologies.py tests/test_structured_core.py -v`
Expected: all PASS

- [x] **Step 5: Commit**

```bash
git add src/StructuredTopologies.py tests/test_structured_topologies.py
git commit -m "Add StructuredTopologies: O/C frames, both tunnels, sharp and blunt TE" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: GridTFI — standard and Hermite transfinite interpolation

**Files:**
- Create: `src/GridTFI.py`
- Modify: `src/StructuredCore.py` (add `cell_jacobians`)
- Test: `tests/test_grid_tfi.py`

**Interfaces:**
- Consumes (Tasks 1–2): `GridFrame`, `TunnelBoundaryControl`.
- Produces (used by Task 5):
  - `fill(frame: GridFrame, variant: str = 'standard', boundary_control: TunnelBoundaryControl | None = None) -> np.ndarray` — shape `(nj, ni, 2)`; `rows[0] == frame.wall`, `rows[-1] == frame.outer`, `rows[:, 0] == frame.side_start`, `rows[:, -1] == frame.side_end`, all exact (copied, not recomputed).
  - `StructuredCore.cell_jacobians(rows: np.ndarray) -> np.ndarray` — `(nj-1, ni-1)` signed quad areas (shoelace per cell), used by every downstream inversion test and by the engine's inverted-cell report.

Note: `BlockMesh.transfinite` exists but is an O(ni·nj) Python-loop method bound to the legacy list-of-tuples block model with no tangent control; `GridTFI` is vectorized on arrays and adds the Hermite variant, per the spec's module split. Do not modify `BlockMesh`.

**Method (write this in the module docstring):**
- Parameters: `eta_j` = mean of the two sides' normalized cumulative arclength (this carries the geometric first-layer clustering into the interior); `xi` per node: `xi[i, j] = (1 - eta_j) * xi_wall[i] + eta_j * xi_outer[i]` with `xi_wall`/`xi_outer` the normalized cumulative arclengths of wall and outer.
- **Standard variant** — Boolean-sum Coons patch, fully vectorized:
  `P = (1-eta)*wall + eta*outer + (1-xi)*side_start + xi*side_end − [(1-xi)(1-eta)*c1 + (1-xi)*eta*c2 + xi*(1-eta)*c3 + xi*eta*c4]` with corners `c1=wall[0], c2=outer[0], c3=wall[-1], c4=outer[-1]`. Then overwrite the four boundary rows/columns with the frame arrays verbatim.
- **Hermite variant** — transverse Hermite blending for tangent control:
  1. Per column i: `L_i = |outer_i − wall_i|`; wall derivative `D0_i = L_i · n_i` (unit wall normal from central differences on the wall polyline, pointing toward the outer boundary); outer derivative `D1_i`: `angle_mode == 'orthogonal'` → `L_i · m_i` with `m_i` the unit inward normal of the outer polyline; `'free'` → `outer_i − wall_i`.
  2. `P_h(i, j) = H00(eta_j)·wall_i + H01(eta_j)·outer_i + H10(eta_j)·D0_i + H11(eta_j)·D1_i` with `H00=2η³−3η²+1, H01=−2η³+3η², H10=η³−2η²+η, H11=η³−η²`.
  3. Side conformity by linear correction: `P(i,j) = P_h(i,j) + (1−xi_wall[i])·(side_start_j − P_h(0,j)) + xi_wall[i]·(side_end_j − P_h(ni−1,j))`.
  4. Overwrite boundary rows/columns verbatim as in the standard variant.
- Periodic O frames need no special casing: `side_start` equals `side_end`, so column 0 and column ni−1 coincide and the seam is C0 by construction.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_grid_tfi.py
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import GridTFI
import StructuredCore as core
import StructuredTopologies as topo
from test_structured_topologies import _blunt_contour, _sharp_contour


def _rect_frame(nx=11, ny=6, width=2.0, height=1.0):
    x = np.linspace(0.0, width, nx)
    y = np.linspace(0.0, height, ny)
    return core.GridFrame(
        wall=np.column_stack((x, np.zeros(nx))),
        outer=np.column_stack((x, np.full(nx, height))),
        side_start=np.column_stack((np.zeros(ny), y)),
        side_end=np.column_stack((np.full(ny, width), y)),
        kind='c', te_type='sharp',
    )


def test_standard_tfi_reproduces_rectangle():
    frame = _rect_frame()
    rows = GridTFI.fill(frame)
    assert rows.shape == (6, 11, 2)
    xs, ys = np.meshgrid(np.linspace(0, 2, 11), np.linspace(0, 1, 6))
    assert np.allclose(rows[..., 0], xs, atol=1e-12)
    assert np.allclose(rows[..., 1], ys, atol=1e-12)


def test_boundaries_verbatim_on_real_frame():
    settings = core.StructuredMeshSettings(topology='c')
    frame = topo.build_frames(_sharp_contour(), settings)[0]
    rows = GridTFI.fill(frame)
    assert np.array_equal(rows[0], frame.wall)
    assert np.array_equal(rows[-1], frame.outer)
    assert np.array_equal(rows[:, 0], frame.side_start)
    assert np.array_equal(rows[:, -1], frame.side_end)


def test_no_inverted_cells_o_and_c_both_te_types():
    for topology in ('c', 'o'):
        for shape in ('legacy', 'circular'):
            for contour in (_sharp_contour(), _blunt_contour()):
                settings = core.StructuredMeshSettings(
                    topology=topology, tunnel_shape=shape)
                for frame in topo.build_frames(contour, settings):
                    rows = GridTFI.fill(frame)
                    jacobians = core.cell_jacobians(rows)
                    assert np.all(np.abs(jacobians) > 1e-14), \
                        f'degenerate cell: {topology}/{shape}'
                    assert np.all(jacobians > 0) or np.all(jacobians < 0), \
                        f'inverted cells: {topology}/{shape}'


def test_hermite_orthogonal_angle_at_outer_boundary():
    control = core.TunnelBoundaryControl(angle_mode='orthogonal')
    settings = core.StructuredMeshSettings(
        topology='o', tunnel_shape='circular',
        boundary_control=control, tfi_variant='hermite')
    frame = topo.build_frames(_sharp_contour(), settings)[0]
    rows = GridTFI.fill(frame, variant='hermite', boundary_control=control)
    # angle between last mesh edge and outer-boundary tangent, interior nodes
    edge = rows[-1] - rows[-2]
    tangent = np.gradient(frame.outer, axis=0)
    cos = np.abs(np.sum(edge * tangent, axis=1)) / (
        np.linalg.norm(edge, axis=1) * np.linalg.norm(tangent, axis=1))
    angles = np.degrees(np.arccos(np.clip(cos, 0.0, 1.0)))
    assert np.median(np.abs(angles - 90.0)) < 10.0
```

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_grid_tfi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'GridTFI'`

- [x] **Step 3: Implement**

Add to `src/StructuredCore.py`:

```python
def cell_jacobians(rows: np.ndarray) -> np.ndarray:
    """Signed area of each quad cell of a (nj, ni, 2) structured array."""
    a = rows[:-1, :-1]
    b = rows[:-1, 1:]
    c = rows[1:, 1:]
    d = rows[1:, :-1]
    return 0.5 * (
        (a[..., 0] * b[..., 1] - b[..., 0] * a[..., 1]) +
        (b[..., 0] * c[..., 1] - c[..., 0] * b[..., 1]) +
        (c[..., 0] * d[..., 1] - d[..., 0] * c[..., 1]) +
        (d[..., 0] * a[..., 1] - a[..., 0] * d[..., 1])
    )
```

Implement `src/GridTFI.py` per the method docstring above; everything is numpy broadcasting over `(nj, ni, 2)`. Normalized arclength helper:

```python
def _normalized_arclength(points):
    deltas = np.diff(points, axis=0)
    cumulative = np.concatenate(
        ([0.0], np.cumsum(np.hypot(deltas[:, 0], deltas[:, 1]))))
    total = cumulative[-1]
    if total <= 0.0:
        return np.linspace(0.0, 1.0, len(points))
    return cumulative / total
```

Guard: `variant` other than `'standard' | 'hermite'` raises `ValueError`.

- [x] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_grid_tfi.py tests/test_structured_core.py -v`
Expected: all PASS

- [x] **Step 5: Commit**

```bash
git add src/GridTFI.py src/StructuredCore.py tests/test_grid_tfi.py
git commit -m "Add GridTFI: vectorized standard and Hermite transfinite interpolation" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: OrthoLayers — exact-normal near-wall block

**Files:**
- Create: `src/OrthoLayers.py`
- Test: `tests/test_ortho_layers.py`

**Interfaces:**
- Consumes (Task 1): `geometric_distances` for layer heights.
- Produces (used by Task 5):
  - `wall_normals(wall: np.ndarray, corner_indices: list[int], spline_data=None, contour_slice: tuple[int, int] | None = None, closed: bool = False, blend_width: int = 4) -> np.ndarray` — unit normals per wall node pointing into the mesh domain. Contour nodes (inside `contour_slice`) use **exact analytic spline tangents** `spline_data.evaluate(spline_data.sample_parameters, der=1)` rotated by −90° (`(ty, −tx)` — outward for the CCW contour orientation); all other nodes (wake cuts, base) use central differences on the wall polyline. Within `±blend_width` nodes of each index in `corner_indices`, normals are smoothed by repeated renormalized neighbor averaging (the corner-bisector blend from the spec); outside those windows they are untouched.
  - `layer_heights(layer_count: int, first_height: float, growth: float) -> np.ndarray` — cumulative heights, length `layer_count`, `h[0] = first_height`, geometric with `growth`.
  - `max_offset_heights(wall, normals, spline_data=None, contour_slice=None, safety: float = 0.5) -> np.ndarray` — per-node cap: `safety / max(kappa, 0)` where the curvature center lies on the domain side (`n · (center − p) > 0`, concave), `inf` elsewhere; curvature from `spline_data.evaluate(..., der=1)` and `der=2` (`kappa = |x'y'' − y'x''| / (x'² + y'²)^1.5`) on contour nodes, from finite differences on other nodes.
  - `build_layers(wall, normals, layer_count, first_height, growth, max_heights=None) -> np.ndarray` — `(layer_count + 1, ni, 2)`, row 0 is `wall` **verbatim** (`np.array_equal`). If the requested total height exceeds `max_heights` anywhere, per-node heights are scaled down (`scale = min(1, cap / total)`), the scale profile smoothed along i (moving average, 5 passes, window 5, clamped so it never exceeds 1), and a warning logged via `logging.getLogger(__name__)` — the block thins, it never folds.

**Corner indices come from the caller** (the engine, Task 5): the sharp-TE node, blunt base corners, and the contour/wake-cut junctions of a C wall row — computed from `frame.metadata['contour_slice']` and `frame.te_type`.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_ortho_layers.py
import sys
from pathlib import Path

import numpy as np
from scipy import interpolate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import OrthoLayers
import StructuredCore as core
from ContourData import SplineData
from test_structured_topologies import _load_dat, NACA0012


def _build_spline_data(contour, points=200, degree=3):
    x, y = contour[:, 0], contour[:, 1]
    tck, u = interpolate.splprep([x, y], s=0.0, k=degree)
    t = np.linspace(0.0, 1.0, points)
    coo = interpolate.splev(t, tck, der=0)
    der1 = interpolate.splev(t, tck, der=1)
    der2 = interpolate.splev(t, tck, der=2)
    return SplineData(
        coordinates=coo, fit_parameters=u, sample_parameters=t,
        first_derivative=der1, second_derivative=der2, spline=tck,
        method='bspline', metadata={'degree': degree},
        leading_edge_parameter=float(t[int(np.argmin(coo[0]))]),
    )


def test_exact_perpendicularity_outside_corner_blend():
    contour_raw = _load_dat(NACA0012)
    contour_raw[-1] = contour_raw[0]
    spline_data = _build_spline_data(contour_raw)
    wall = core.contour_array(spline_data)
    n = len(wall)
    corner = [0, n - 1]
    normals = OrthoLayers.wall_normals(
        wall, corner, spline_data=spline_data,
        contour_slice=(0, n), closed=True, blend_width=4)
    tangents = np.column_stack(spline_data.evaluate(
        spline_data.sample_parameters, der=1))
    dots = np.abs(np.sum(normals * tangents, axis=1)) / \
        np.linalg.norm(tangents, axis=1)
    interior = np.ones(n, dtype=bool)
    interior[:5] = interior[-5:] = False
    assert np.max(dots[interior]) < 1e-9        # mathematically perpendicular
    lengths = np.linalg.norm(normals, axis=1)
    assert np.allclose(lengths, 1.0, atol=1e-12)


def test_normals_point_away_from_body():
    contour_raw = _load_dat(NACA0012)
    contour_raw[-1] = contour_raw[0]
    spline_data = _build_spline_data(contour_raw)
    wall = core.contour_array(spline_data)
    normals = OrthoLayers.wall_normals(
        wall, [0, len(wall) - 1], spline_data=spline_data,
        contour_slice=(0, len(wall)), closed=True)
    centroid = wall.mean(axis=0)
    outward = np.sum((wall - centroid) * normals, axis=1)
    assert np.mean(outward > 0.0) > 0.95


def test_build_layers_wall_verbatim_and_no_fold():
    contour_raw = _load_dat(NACA0012)
    contour_raw[-1] = contour_raw[0]
    spline_data = _build_spline_data(contour_raw)
    wall = core.contour_array(spline_data)
    normals = OrthoLayers.wall_normals(
        wall, [0, len(wall) - 1], spline_data=spline_data,
        contour_slice=(0, len(wall)), closed=True)
    rows = OrthoLayers.build_layers(wall, normals, layer_count=8,
                                    first_height=0.001, growth=1.2)
    assert rows.shape == (9, len(wall), 2)
    assert np.array_equal(rows[0], wall)
    jacobians = core.cell_jacobians(rows)
    assert np.all(jacobians != 0.0)
    assert np.all(jacobians > 0) or np.all(jacobians < 0)


def test_thinning_on_concave_wall_instead_of_folding():
    # synthetic concave arc: offsetting toward the center must trigger caps
    theta = np.linspace(0.25 * np.pi, 0.75 * np.pi, 80)
    radius = 0.05
    wall = np.column_stack((radius * np.cos(theta),
                            -radius * np.sin(theta)))
    normals = OrthoLayers.wall_normals(wall, [])
    # ensure normals point toward the center (concave side) for this test
    to_center = -wall / np.linalg.norm(wall, axis=1)[:, None]
    if np.sum(normals * to_center) < 0:
        normals = -normals
    caps = np.full(len(wall), 0.5 * radius)
    rows = OrthoLayers.build_layers(wall, normals, layer_count=10,
                                    first_height=0.01, growth=1.2,
                                    max_heights=caps)
    total = np.linalg.norm(rows[-1] - rows[0], axis=1)
    assert np.all(total <= 0.5 * radius + 1e-9)      # thinned
    jacobians = core.cell_jacobians(rows)
    assert np.all(jacobians > 0) or np.all(jacobians < 0)   # not folded
```

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_ortho_layers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'OrthoLayers'`

- [x] **Step 3: Implement `src/OrthoLayers.py`**

Per the interface block above. Implementation notes:
- Contour tangent → normal: `t = evaluate(params, der=1)`; unit normal `(t_y, −t_x) / |t|` (outward for the CCW contour). Non-contour nodes: central differences (`np.gradient` on the wall array), same rotation; for `closed=True` wrap the difference stencil across the duplicate end node.
- Corner blend: for each corner index, over `window = range(idx − blend_width, idx + blend_width + 1)` (clipped / wrapped when closed), run 4 passes of `n[i] = normalize(n[i−1] + 2n[i] + n[i+1])` on those nodes only.
- `build_layers`: `heights = layer_heights(...)` cumulative; broadcast `wall[None] + (scaled per-node heights)[:, :, None-pattern] * normals`; scaling and smoothing exactly as described in the Produces block; warn with node count when any scale < 1.

- [x] **Step 4: Run tests to verify they pass**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_ortho_layers.py -v`
Expected: all PASS

- [x] **Step 5: Commit**

```bash
git add src/OrthoLayers.py tests/test_ortho_layers.py
git commit -m "Add OrthoLayers: exact-normal near-wall block with corner blend and thinning" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: StructuredEngine + Meshing.py wiring

**Files:**
- Create: `src/StructuredEngine.py`
- Modify: `src/Meshing.py` (settings field, lazy getter, dispatch — **carries unrelated WIP, see Global Constraints staging rule**)
- Test: `tests/test_structured_engine.py`

**Interfaces:**
- Consumes: `StructuredTopologies.build_frames`, `StructuredTopologies.side_segment`, `GridTFI.fill`, `OrthoLayers.wall_normals` / `max_offset_heights` / `build_layers`, `StructuredCore.cell_jacobians` / `contour_array` / `StructuredMeshSettings`, `BlockMesh` (`setUlines`, `as_ulines`).
- Produces:
  - `StructuredEngine.build_blocks(spline_data, settings: StructuredMeshSettings) -> list[tuple[str, BlockMesh]]` — `[('block_structured', main)]`, plus `('block_structured_wake_strip', strip)` for blunt-TE C.
  - `Windtunnel._makeStructuredMesh(settings, airfoil, progdialog)` and dispatch on `engine == 'structured'`; `WindtunnelMeshSettings.structured` field.

**Engine composition (module docstring):**

1. `contour = contour_array(spline_data)`; `frames = build_frames(contour, settings)`.
2. Per main frame (`kind` in `('o', 'c')`):
   - `corner_indices`: from `frame.metadata['contour_slice'] = (start, stop)` — for C: `[start, stop - 1]` (contour/wake junctions; these are also the blunt base corners) plus, sharp only, nothing extra (start/stop ARE the TE). For O: `[0, len(wall) - 1]` (TE closure node / base corners at loop ends).
   - `ortho_layers == 0` → `rows = GridTFI.fill(frame, settings.tfi_variant, settings.boundary_control)`.
   - `ortho_layers > 0` →
     `normals = wall_normals(frame.wall, corner_indices, spline_data=spline_data, contour_slice=frame.metadata.get('contour_slice'), closed=frame.periodic)`;
     `caps = max_offset_heights(frame.wall, normals, spline_data=spline_data, contour_slice=frame.metadata.get('contour_slice'))`;
     `ortho_rows = build_layers(frame.wall, normals, settings.ortho_layers, settings.first_layer_thickness, settings.ortho_growth, caps)`;
     reduced frame: `wall = ortho_rows[-1]`, same `outer`, sides `side_segment(ortho_rows[-1][0], frame.outer[0], last_ortho_step * settings.ortho_growth, settings.normal_divisions + 1 - settings.ortho_layers)` (and the analogue at the other end; for periodic frames `side_end = side_start.copy()`);
     `rows = np.vstack((ortho_rows, GridTFI.fill(reduced_frame, ...)[1:]))`.
     Validate `ortho_layers < normal_divisions` else `ValueError('Ortho layers must be fewer than total normal divisions.')`.
   - O-grid note (spec: ortho block "optionally O"): the composition above works for both topologies unchanged because the frame abstraction hides the difference.
3. Wake-strip frames: always plain `GridTFI.fill(frame, 'standard')` — no ortho, no Hermite (the strip is bounded by four prescribed lines).
4. Inverted-cell report per block: `jacobians = cell_jacobians(rows)`; if signs are mixed, `raise ValueError(f'Structured mesh has {count} inverted cells; adjust layer heights or divisions.')` (spec: report, never silently return folded grids).
5. Emit: `block = BlockMesh(name=...); block.setUlines(BlockMesh.as_ulines(rows))` — `rows[0]` is the wall so `ULines[0]` is the wall row, matching the `ExperimentalCGrid` convention.

**Meshing.py wiring (minimal diff, mirrors the experimental engines):**

```python
# imports (top of Meshing.py, alongside the Experimental imports)
from StructuredCore import StructuredMeshSettings, TunnelBoundaryControl
from StructuredEngine import StructuredEngine

# WindtunnelMeshSettings gains:
    structured: StructuredMeshSettings = field(
        default_factory=StructuredMeshSettings
    )

# Windtunnel.__init__ gains:
        self._structured_engine = None

# Windtunnel method (next to getExperimentalOGridGenerator):
    def getStructuredEngine(self):
        if self._structured_engine is None:
            self._structured_engine = StructuredEngine()
        return self._structured_engine

# Windtunnel method (next to _makeExperimentalMesh):
    def _makeStructuredMesh(self, settings: WindtunnelMeshSettings,
                            airfoil, progdialog):
        engine = self.getStructuredEngine()
        named_blocks = engine.build_blocks(
            spline_data=airfoil.spline_data,
            settings=settings.structured,
        )
        for attribute_name, block in named_blocks:
            self.registerBlock(attribute_name, block)
        self.tunnel_height = settings.structured.tunnel_height

        progdialog.setValue(70)
        if progdialog.wasCanceled():
            return False

        if not self._finalizeMeshGeneration(airfoil, progdialog):
            return False
        self.MeshQuality(crit='k2inf')
        return True

# makeMesh dispatch, after the experimental branch:
        if self.mesh_engine == 'structured':
            return self._makeStructuredMesh(settings, airfoil, progdialog)
```

- [x] **Step 1: Write the failing tests**

```python
# tests/test_structured_engine.py
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from scipy import interpolate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import Connect
import StructuredCore as core
from StructuredEngine import StructuredEngine
from test_ortho_layers import _build_spline_data
from test_structured_topologies import (
    NACA0012, _blunt_contour, _load_dat, _sharp_contour,
)

NACA2315 = PROJECT_ROOT / 'lib_AE' / 'Construct2D_2.1.4' / \
    'sample_airfoils' / 'naca2315.dat'
MW166 = PROJECT_ROOT / 'boundary_layer_code' / 'Airfoils' / \
    'MW-166-39-44-43.dat'


def _spline_data_for(contour):
    return _build_spline_data(np.asarray(contour, dtype=float))


def _minimum_cell_area(vertices, connectivity):
    points = np.asarray(vertices, dtype=float)
    areas = []
    for cell in np.asarray(connectivity, dtype=int):
        polygon = points[cell]
        x, y = polygon[:, 0], polygon[:, 1]
        areas.append(0.5 * abs(np.dot(x, np.roll(y, -1)) -
                               np.dot(y, np.roll(x, -1))))
    return min(areas) if areas else 0.0


class StructuredEngineMatrixTests(unittest.TestCase):
    def test_full_matrix_no_inverted_cells(self):
        engine = StructuredEngine()
        contours = {'sharp': _sharp_contour(), 'blunt': _blunt_contour()}
        for topology in ('c', 'o'):
            for shape in ('legacy', 'circular'):
                for te_name, contour in contours.items():
                    for ortho in (0, 6):
                        with self.subTest(topology=topology, shape=shape,
                                          te=te_name, ortho=ortho):
                            settings = core.StructuredMeshSettings(
                                topology=topology, tunnel_shape=shape,
                                normal_divisions=40, wake_points=40,
                                ortho_layers=ortho,
                            )
                            spline_data = _spline_data_for(contour)
                            named = engine.build_blocks(
                                spline_data=spline_data, settings=settings)
                            blocks = [block for _, block in named]
                            connector = Connect.Connect()
                            vertices, connectivity = \
                                connector.connectAllBlocks(blocks)
                            self.assertGreater(
                                _minimum_cell_area(vertices, connectivity),
                                1.0e-12)

    def test_wall_row_is_contour_verbatim_every_airfoil(self):
        engine = StructuredEngine()
        for dat in (NACA0012, NACA2315, MW166):
            contour = _load_dat(dat)
            spline_data = _spline_data_for(contour)
            prepared = core.contour_array(spline_data)
            for topology in ('c', 'o'):
                with self.subTest(airfoil=dat.name, topology=topology):
                    settings = core.StructuredMeshSettings(
                        topology=topology, normal_divisions=30,
                        wake_points=30)
                    named = engine.build_blocks(
                        spline_data=spline_data, settings=settings)
                    wall = np.asarray(named[0][1].getULines()[0])
                    found = any(
                        np.allclose(wall[s:s + len(prepared)], prepared,
                                    atol=1e-12)
                        for s in range(len(wall) - len(prepared) + 1))
                    self.assertTrue(found,
                                    'contour not verbatim in wall row')

    def test_blunt_c_interface_node_match(self):
        engine = StructuredEngine()
        spline_data = _spline_data_for(_blunt_contour())
        settings = core.StructuredMeshSettings(topology='c',
                                               normal_divisions=30,
                                               wake_points=30)
        named = dict(engine.build_blocks(spline_data=spline_data,
                                         settings=settings))
        self.assertIn('block_structured_wake_strip', named)
        main = np.asarray(named['block_structured'].getULines()[0])
        strip = named['block_structured_wake_strip']
        strip_lower = np.asarray(strip.getULines()[0])
        strip_upper = np.asarray(strip.getULines()[-1])
        wake_points = settings.wake_points
        self.assertTrue(np.allclose(strip_lower, main[-wake_points:]))
        self.assertTrue(np.allclose(strip_upper,
                                    main[:wake_points][::-1]))


class StructuredDispatchTests(unittest.TestCase):
    def test_makemesh_dispatches_structured(self):
        import Meshing
        with mock.patch.object(Meshing, 'get_main_window',
                               return_value=None):
            tunnel = Meshing.Windtunnel()
        spline_data = _spline_data_for(_sharp_contour())
        airfoil = mock.Mock()
        airfoil.spline_data = spline_data
        airfoil.has_spline = True
        airfoil.name = 'naca0012'
        airfoil.mesh_blocks = None
        settings = mock.Mock(spec=Meshing.WindtunnelMeshSettings)
        settings.engine = 'structured'
        settings.structured = core.StructuredMeshSettings(
            normal_divisions=25, wake_points=25)
        with mock.patch.object(tunnel, '_finalizeMeshGeneration',
                               return_value=True) as finalize, \
                mock.patch.object(tunnel, 'MeshQuality') as quality:
            result = tunnel.makeMesh(settings, airfoil=airfoil)
        self.assertTrue(result)
        finalize.assert_called_once()
        quality.assert_called_once_with(crit='k2inf')
        self.assertTrue(tunnel.blocks)
        self.assertEqual(tunnel.tunnel_height,
                         settings.structured.tunnel_height)


if __name__ == '__main__':
    unittest.main()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'StructuredEngine'`

- [x] **Step 3: Implement `src/StructuredEngine.py` and the Meshing.py wiring** exactly per the composition docstring and diff sketch above. If `mock.patch.object(Meshing, 'get_main_window', ...)` turns out unnecessary (headless `get_main_window()` already returns `None`), keep the patch anyway — it documents the test's independence from the GUI.

- [x] **Step 4: Run the full suite**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/ -v`
Expected: all new tests PASS; pre-existing tests unaffected (same pass/fail set as before this task — record the before state in Step 1 with a plain `pytest tests/` run).

- [x] **Step 5: Commit**

```bash
git add src/StructuredEngine.py tests/test_structured_engine.py
git diff --stat src/Meshing.py   # stage only if it shows just this task's hunks
git commit -m "Add StructuredEngine and wire structured engine into Windtunnel" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: GUI — Structured settings group and settings assembly

**Files:**
- Modify: `src/ToolboxPagesMeshing.py` (selector item, `_build_structured_group`, group registration — **carries unrelated WIP, staging rule applies**)
- Modify: `src/ToolBox.py` (`mesh_engine_changed` tunnel-group visibility, `mesh_generation_settings` structured field — **same staging rule**)
- Test: `tests/test_structured_gui.py`

**Interfaces:**
- Consumes: `Meshing.StructuredMeshSettings`, `Meshing.TunnelBoundaryControl` (re-exported by Task 5's import), existing helpers `make_page_label`, `configure_form_layout`.
- Produces: `ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox) -> StructuredMeshSettings` — a module-level function so the mapping is testable without a full ToolBox; `ToolBox.mesh_generation_settings` calls it.

**Widget list for `_build_structured_group(toolbox)`** (QFormLayout inside a `QGroupBox('Structured Grid')`, following `_build_metric_group`'s shape; intro label wordwrapped):

| Attribute on toolbox | Widget | Items / range, default |
|---|---|---|
| `structured_topology` | QComboBox | 'C-mesh'→`'c'`, 'O-grid'→`'o'` |
| `structured_tunnel_shape` | QComboBox | 'Legacy (half-circle + rectangle)'→`'legacy'`, 'Circular'→`'circular'` |
| `structured_tunnel_height` | QDoubleSpinBox | 0.5–50.0, default 3.5 ("Farfield radius / half-height") |
| `structured_wake_length` | QDoubleSpinBox | 0.5–50.0, default 7.0 |
| `structured_algorithm` | QComboBox | 'TFI (standard)'→`'standard'`, 'TFI (Hermite)'→`'hermite'` — phases 2/3 append elliptic/hyperbolic here |
| `structured_normal_divisions` | QSpinBox | 5–500, default 60 |
| `structured_first_layer` | QDoubleSpinBox | decimals 5, 1e-5–1.0, default 0.002 |
| `structured_wake_points` | QSpinBox | 5–500, default 60 |
| `structured_ortho_layers` | QSpinBox | 0–100, default 0 ("0 = off") |
| `structured_ortho_growth` | QDoubleSpinBox | 1.0–2.0, default 1.15 |
| `structured_outer_distribution` | QComboBox | 'Uniform'→`'uniform'`, 'Clustered to outlet'→`'clustered'` |
| `structured_outer_ratio` | QDoubleSpinBox | 1.0–20.0, default 2.0 |
| `structured_outer_angle` | QComboBox | 'Free'→`'free'`, 'Orthogonal'→`'orthogonal'` |

Intro label text: "Composable structured mesher: topology × tunnel shape × algorithm. Sharp vs blunt trailing edge is detected automatically from the prepared contour and changes the block topology (blunt C-mesh adds a wake strip)."

**Mapping function** (module level in ToolboxPagesMeshing.py):

```python
def structured_settings_from_toolbox(toolbox):
    import Meshing
    return Meshing.StructuredMeshSettings(
        topology=toolbox.structured_topology.currentData(),
        tunnel_shape=toolbox.structured_tunnel_shape.currentData(),
        tunnel_height=toolbox.structured_tunnel_height.value(),
        wake_length=toolbox.structured_wake_length.value(),
        tfi_variant=toolbox.structured_algorithm.currentData(),
        normal_divisions=toolbox.structured_normal_divisions.value(),
        first_layer_thickness=toolbox.structured_first_layer.value(),
        wake_points=toolbox.structured_wake_points.value(),
        ortho_layers=toolbox.structured_ortho_layers.value(),
        ortho_growth=toolbox.structured_ortho_growth.value(),
        boundary_control=Meshing.TunnelBoundaryControl(
            distribution=toolbox.structured_outer_distribution.currentData(),
            clustering_ratio=toolbox.structured_outer_ratio.value(),
            angle_mode=toolbox.structured_outer_angle.currentData(),
        ),
    )
```

**Other edits:**
- `_build_engine_group`: `toolbox.meshEngineSelector.addItem('Structured', userData='structured')`.
- `build_meshing_panel`: `structured_group = _build_structured_group(toolbox)`; add to `mesh_engine_specific_groups['structured']`; `layout.addWidget(structured_group)` next to `metric_group`.
- `ToolBox.mesh_engine_changed`: replace the unconditional `tunnel_group.setVisible(True)` block with `show_tunnel = self.mesh_engine != 'structured'` (the structured group owns its tunnel parameters); airfoil group already hides (structured is not in its show-list).
- `ToolBox.mesh_generation_settings`: add keyword `structured=ToolboxPagesMeshing.structured_settings_from_toolbox(self) if hasattr(self, 'structured_topology') else Meshing.StructuredMeshSettings()` (import ToolboxPagesMeshing at the top of ToolBox.py if not already imported).

- [x] **Step 1: Write the failing test**

```python
# tests/test_structured_gui.py
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6 import QtWidgets

import ToolboxPagesMeshing


def _toolbox_with_group():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert app is not None
    toolbox = SimpleNamespace()
    ToolboxPagesMeshing._build_structured_group(toolbox)
    return toolbox


def test_structured_group_defaults_map_to_settings():
    toolbox = _toolbox_with_group()
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.topology == 'c'
    assert settings.tunnel_shape == 'legacy'
    assert settings.tunnel_height == 3.5
    assert settings.tfi_variant == 'standard'
    assert settings.ortho_layers == 0
    assert settings.boundary_control.distribution == 'uniform'
    assert settings.boundary_control.angle_mode == 'free'


def test_structured_group_selection_roundtrip():
    toolbox = _toolbox_with_group()
    toolbox.structured_topology.setCurrentIndex(1)      # O-grid
    toolbox.structured_tunnel_shape.setCurrentIndex(1)  # circular
    toolbox.structured_algorithm.setCurrentIndex(1)     # hermite
    toolbox.structured_ortho_layers.setValue(8)
    settings = ToolboxPagesMeshing.structured_settings_from_toolbox(toolbox)
    assert settings.topology == 'o'
    assert settings.tunnel_shape == 'circular'
    assert settings.tfi_variant == 'hermite'
    assert settings.ortho_layers == 8
```

- [x] **Step 2: Run test to verify it fails**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/test_structured_gui.py -v`
Expected: FAIL with `AttributeError` (`_build_structured_group` / `structured_settings_from_toolbox` missing)

- [x] **Step 3: Implement the GUI edits** per the widget table and other-edits list. `_build_structured_group` must not require a full ToolBox — only setattr widgets on the object it is given and return the QGroupBox (that is what makes the test's SimpleNamespace work).

- [x] **Step 4: Run the full suite**

Run: `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest tests/ -v`
Expected: all PASS (same pre-existing failures as recorded in Task 5, none new)

- [x] **Step 5: Commit new test; report shared-file hunks**

```bash
git add tests/test_structured_gui.py
git diff --stat src/ToolboxPagesMeshing.py src/ToolBox.py  # stage only if clean of WIP
git commit -m "Add Structured engine GUI group and settings assembly" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [x] **Step 6: Manual verification handoff** — tell the user which shared files carry unstaged wiring and that the app is ready for their own run-through (their preferred verification): select "Structured" in the mesh engine selector, generate on a prepared contour, check both topologies and a blunt-TE contour.

---

## Self-Review (completed during planning)

- **Spec coverage (phase 1 scope):** topology × tunnel × TFI matrix → Tasks 2–3; wall invariant → Tasks 2 & 5 tests; TE detection + O/C blunt/sharp frames incl. wake strip → Task 2; ortho block with exact normals, corner blend, curvature thinning → Task 4; outer-boundary distribution + Hermite angle control → Tasks 2–3; engine + BlockMesh emission + error handling (`ValueError`, inverted-cell report) → Task 5; GUI group incl. "TE type is detected, not a control" → Task 6. Deferred per spec: elliptic (phase 2), hyperbolic (phase 3), H-mesh (phase 4), smoothers (phase 5) — the `structured_algorithm` combo and `GridElliptic`-takes-initial-grid convention leave their seams ready.
- **Type consistency:** `side_segment` (public, Task 2) is the one shared side-builder; `contour_slice` metadata key used identically in Tasks 2, 4, 5; `cell_jacobians` lives in `StructuredCore` (added Task 3, used Tasks 4–5).
- **Known judgment calls:** blunt-C wake strip is constant-width; O-grid seam is the horizontal ray from the TE; Hermite side-conformity via linear correction. All match the spec's phase-1 ambitions; elliptic smoothing (phase 2) is the designated cleanup for what TFI leaves imperfect.

## Execution notes (2026-08-22, all tasks completed)

Deviations from the plan text, discovered while executing:

- **O-grid seam is curved, not straight.** A straight horizontal seam folds
  near-wall cells on cambered/reflexed airfoils (MW-166: 28 inverted cells;
  the straight TE-bisector seam was worse, an angle-matched outer pairing
  worse still — both tried and deleted). The shipped solution
  (`StructuredTopologies._curved_seam`): a quadratic Bézier leaving the TE
  along the wedge bisector and bending onto the seam point where the
  centroid→TE ray meets the outer shape. Zero inverted cells on all three
  test airfoils; this also realizes the spec's "mesh line leaving the TE
  follows the exterior-angle bisector".
- `_sharp_contour()` snaps **both** endpoints to their midpoint (the raw
  Construct2D naca0012.dat has a ±0.00126 blunt gap; snapping one endpoint
  onto the other would kink the TE asymmetrically).
- Tests use `tunnel_height=10.0` for `tunnel_shape='circular'` — the legacy
  default 3.5 with wake 7.0 is geometrically invalid there and correctly
  raises the farfield `ValueError`.
- **Hermite limitation:** on strongly cambered airfoils the Hermite O-grid
  variant folds mid-field regardless of derivative magnitude (probed down
  to near-zero); the engine reports it via the inverted-cell `ValueError`
  instead of returning a folded grid. Symmetric/mild cases work (tested).
  The real fix is phase 2's elliptic solver with Steger–Sorenson control.
- `Meshing.py`, `ToolBox.py`, `ToolboxPages.py`, `ToolboxPagesMeshing.py`
  wiring hunks are intentionally uncommitted (files carry unrelated WIP);
  each commit message names its unstaged companions.
