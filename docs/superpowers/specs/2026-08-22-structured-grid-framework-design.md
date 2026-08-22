# Structured grid-generation framework

Status: approved for planning
Date: 2026-08-22

## Problem

PyAero's meshing currently dispatches on an `engine` string in
`Windtunnel.makeMesh()` ([src/Meshing.py](../../../src/Meshing.py)) to five
paths (`metric_based`, `hybrid`, `hybrid_staged`, `experimental_c`,
`experimental_o`). Each engine hardcodes its own combination of mesh topology,
wind-tunnel shape, and volume-mesh algorithm; there is no shared abstraction
for any of the three. The legacy block builder resamples the airfoil contour,
so mesh lines do not start exactly at the prepared spline points. Users cannot
choose among grid-generation algorithms (elliptic, hyperbolic, algebraic), and
adding a new topology or farfield shape means writing a new engine from
scratch.

## Goals

- A new, selectable "Structured" engine family in which **topology**,
  **tunnel shape**, and **volume algorithm** are three orthogonal, first-class
  choices.
- Hard invariant for every algorithm: mesh lines emerging from the airfoil
  start **exactly** at the prepared spline points (`spline_data.coordinates`),
  never resampled.
- Initial algorithm set: **TFI** (algebraic baseline, Hermite variant for
  tangent control), **elliptic** (Winslow/TTM with Steger–Sorenson-style
  control functions), **hyperbolic** (Steger–Chan-style layer marching).
- Initial topologies: **O-grid** and **C-mesh**; **H-mesh** follows as its own
  later design pass (the frame abstraction is designed with it in mind).
- Tunnel shapes: the **legacy** half-circle/rectangle shape and a **circular**
  farfield, user-selectable, each parametric.
- **Perpendicular near-wall block** (C-mesh, optionally O): a GUI-definable
  number of layers constructed with exact analytic spline normals —
  mathematically perpendicular by construction.
- **Outer-boundary point and tangent control** at the wind-tunnel boundary
  (not the airfoil): user-controlled point distribution plus desired
  mesh-line angle where lines meet the tunnel boundary.
- Extensible: more algorithms, topologies, and options can be added without
  touching existing ones.

## Non-goals

- Changing or removing any of the five existing engines. They stay selectable
  and untouched until the new framework proves itself.
- H-mesh in the first deliverable (phase 4, own design pass — its LE/TE
  singular points need block decomposition the O/C frames do not).
- 3D. Everything is 2D structured, consistent with the rest of PyAero.

## Architecture

### Modules (flat in `src/`, matching existing file granularity)

| Module | Responsibility |
|---|---|
| `StructuredCore.py` | Shared dataclasses (`GridFrame`, results, settings), resampling/distribution utilities |
| `StructuredTopologies.py` | O and C frame builders × both tunnel shapes |
| `OrthoLayers.py` | Exact-normal near-wall block |
| `GridTFI.py` | Transfinite interpolation (standard + Hermite) |
| `GridElliptic.py` | Elliptic solver with control functions |
| `GridHyperbolic.py` | Hyperbolic layer marching |
| `StructuredEngine.py` | Orchestrator: settings, dispatch, `BlockMesh` emission |

The engine emits ordinary `BlockMesh` objects and registers them on
`Windtunnel` exactly like existing engines (`registerBlock`,
`buildMeshModel`), so mesh export, quality assessment, and scene drawing work
unchanged.

### Core abstractions

**GridFrame** — what a topology builder produces: the four
computational-domain boundary polylines (wall, outer, and the two side/cut
boundaries), plus metadata (periodic seam for O; wake cut for C). Volume
algorithms consume a frame and return a structured point array; they never
know which topology or tunnel shape produced it.

**Tunnel shape** — a parametric outer curve the topology samples from:
`legacy` (current half-circle + rectangle, existing height/length parameters)
or `circular` (user radius). Adding a shape means adding one sampler.

**Volume algorithm** — `TFI`, `elliptic`, `hyperbolic`; each takes
(frame, algorithm settings, boundary control) and fills the interior.

### Wall-distribution invariant

Frame builders take airfoil boundary nodes verbatim from
`spline_data.coordinates`. For C-mesh, the wake line continues from the TE
with the TE's local spacing and a growth ratio toward the outlet. For O-grid
with a blunt TE, the TE gap nodes are appended to close the loop. A dedicated
test asserts node-for-node equality between contour and the wall row of every
generated mesh, for every algorithm.

### Perpendicular near-wall block (`OrthoLayers.py`)

For N layers (GUI; 0 = off), first-layer height h₁, growth ratio g:
layer k is `P(tᵢ) + hₖ·n(tᵢ)` with `n` the exact analytic spline normal from
`spline_data.evaluate(t, der=1)` rotated 90°. Safety: per-node maximum offset
distance is checked against the local radius of curvature (offset curves
self-intersect beyond it on the concave side); if requested total height
exceeds it anywhere, the block is thinned there with a logged warning rather
than folding. The block's outer rim becomes the inner boundary the selected
volume algorithm fills from — all three algorithms compose with it.

### Outer-boundary point and tangent control

`TunnelBoundaryControl` spec: point distribution along the tunnel boundary
(uniform / clustered toward outlet / custom ratio) + desired mesh-line angle
at the boundary (free, or orthogonal). Honored per algorithm:

- **TFI**: Hermite-type transfinite interpolation with boundary derivative
  terms — tangent control even in the algebraic baseline.
- **Elliptic**: Steger–Sorenson-style control functions — source terms P, Q
  iteratively adjusted to meet prescribed angle and first-cell spacing at the
  tunnel boundary.
- **Hyperbolic**: marches freely from the wall (its strength) and blends its
  final layers (fraction adjustable, default ~20%) onto the exact prescribed
  tunnel-boundary distribution. This is the standard resolution of the fact
  that hyperbolic marching does not naturally terminate on a prescribed
  boundary — the one real design tension in the matrix.

### Algorithms

- **TFI** (`GridTFI.py`): standard + Hermite variant; also supplies the
  elliptic solver's initial grid.
- **Elliptic** (`GridElliptic.py`): Winslow/TTM equations, vectorized SOR on
  the computational domain; GUI exposes iterations, relaxation, and the
  orthogonality toggle per boundary.
- **Hyperbolic** (`GridHyperbolic.py`): Steger–Chan-style layer marching
  (cell-area specification + orthogonality relation, implicit smoothing
  against front crossing); periodic in ξ for O-grids, matched wake-cut
  condition for C.

### GUI

One new "Structured" entry in the existing engine selector
([src/ToolboxPagesMeshing.py](../../../src/ToolboxPagesMeshing.py)), with a
settings group: topology (O/C), tunnel shape (legacy/circular + parameters),
algorithm (TFI/elliptic/hyperbolic), ortho-block controls (layers, first
height, growth), outer-boundary controls (distribution, angle), plus
algorithm-specific sub-groups following the existing
`mesh_engine_specific_groups` pattern.

## Phasing (each phase independently usable)

1. **Phase 1**: `StructuredCore` + both topologies × both tunnels + TFI +
   ortho block + engine + GUI group + tests — a working, selectable mesher.
2. **Phase 2**: elliptic solver with boundary controls.
3. **Phase 3**: hyperbolic marching.
4. **Phase 4**: H-mesh topology (own design pass).

## Error handling

Frame builders validate inputs (spline prepared, tunnel parameters sane) and
raise `ValueError` with user-readable messages surfaced through the existing
`_show_message` path. Volume algorithms detect inverted cells (via the
existing quality metric) and non-converged solves; they report rather than
silently return folded grids. The ortho block never folds — it thins with a
warning (see above).

## Testing

Real airfoils per established project practice (NACA0012, NACA2315,
MW-166-39-44-43), no GUI dependency:

- Wall-distribution invariant: node-for-node equality, every algorithm.
- No inverted cells (existing k2inf quality metric) for every
  topology × tunnel × algorithm combination shipped.
- Ortho block: angle between wall tangent and first mesh edge = 90° to tight
  tolerance at every wall node; thinning triggers on a synthetic
  high-curvature case instead of folding.
- Elliptic: outer-boundary angle converges to prescribed value.
- Hyperbolic: no layer crossing; outer row matches prescribed tunnel
  distribution exactly after the blend.
