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
- **Trailing-edge awareness**: sharp and blunt TEs are both first-class. TE
  type is detected from the prepared spline, never a user switch, and every
  topology adapts its frame to it (see "Trailing-edge handling") — the TE
  type changes the mesh topology, not just local spacing.
- A **post-smoothing stage** as a fourth orthogonal choice
  (none / Laplacian / elliptic / angle-based): specified now so the
  architecture accounts for it, implemented as its own later phase.
- Extensible: more algorithms, topologies, smoothers, and options can be
  added without touching existing ones.

## Non-goals

- Changing or removing any of the five existing engines. They stay selectable
  and untouched until the new framework proves itself.
- H-mesh in the first deliverable (phase 4, own design pass — its LE/TE
  singular points need block decomposition the O/C frames do not).
- Mesh smoothers in the first deliverable — the smoothing stage is specified
  below but lands as its own later phase (phase 5); the interfaces are fixed
  now so no rework is needed then.
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
| `GridSmoothers.py` | Post-smoothing stage (phase 5) |
| `StructuredEngine.py` | Orchestrator: settings, dispatch, `BlockMesh` emission |

The engine emits ordinary `BlockMesh` objects and registers them on
`Windtunnel` exactly like existing engines (`registerBlock`,
`buildMeshModel`), so mesh export, quality assessment, and scene drawing work
unchanged.

### Core abstractions

**GridFrame** — what a topology builder produces: the four
computational-domain boundary polylines (wall, outer, and the two side/cut
boundaries), plus metadata (TE type; periodic seam for O; wake cut or wake
strip for C). A builder returns one or *more* frames: one for O-grids and
sharp-TE C-meshes, two for a blunt-TE C-mesh (main block + wake strip, see
"Trailing-edge handling"). Volume algorithms consume a frame and return a
structured point array; they never know which topology or tunnel shape
produced it.

**Tunnel shape** — a parametric outer curve the topology samples from:
`legacy` (current half-circle + rectangle, existing height/length parameters)
or `circular` (user radius). Adding a shape means adding one sampler.

**Volume algorithm** — `TFI`, `elliptic`, `hyperbolic`; each takes
(frame, algorithm settings, boundary control) and fills the interior.

### Wall-distribution invariant

Frame builders take airfoil boundary nodes verbatim from
`spline_data.coordinates`. For C-mesh, the wake line continues from the TE
with the TE's local spacing and a growth ratio toward the outlet. For O-grid
with a blunt TE, the TE gap nodes are appended to close the loop (details in
"Trailing-edge handling"). A dedicated test asserts node-for-node equality
between contour and the wall row of every generated mesh, for every
algorithm.

### Trailing-edge handling

TE type is detected from `spline_data.coordinates` — sharp if the contour
endpoints coincide within tolerance, blunt otherwise (raw Selig-style data
and PyAero's TE-thickness tool both produce blunt TEs). No user switch. Each
topology builder branches on it because the TE type changes the frame, not
just spacing:

- **O-grid, blunt TE**: gap nodes are inserted across the base to close the
  wall loop; the two base corners become convex corners of the wall
  boundary.
- **O-grid, sharp TE**: the wall loop closes at a single TE point with a
  tangent discontinuity (wedge). The mesh line leaving the TE follows the
  exterior-angle bisector. Cells adjacent to the wedge are inherently
  skewed: elliptic relaxes this, TFI inherits the kink into the interior
  (the smoother stage is the designated cleanup), hyperbolic applies local
  normal smoothing at the corner node.
- **C-mesh, sharp TE**: the classic single wake cut from the TE point; the
  upper and lower cut lines coincide node-for-node, which is exactly the
  matched-cut condition the hyperbolic march uses.
- **C-mesh, blunt TE**: the base cannot collapse to a point without
  violating the wall invariant, so the topology gains a second block — an
  H-type **wake strip** behind the base. Its inflow boundary is the base
  nodes verbatim, its upper/lower boundaries are the two now-distinct wake
  cuts. The strip is TFI-meshed in all cases; the main C block treats the
  strip edges as prescribed boundaries instead of a matched cut. The engine
  registers both blocks (`Windtunnel` already handles multi-block
  registration), and shared boundary polylines guarantee node-matched
  interfaces.

The ortho block branches too: at a sharp TE and at blunt-TE base corners the
analytic normal is discontinuous. Within a small blend region around such a
corner, normals are smoothly blended toward the corner bisector — exact
perpendicularity holds everywhere outside these regions, and the blend
replaces the normal fan a convex corner would otherwise require.

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
  condition for sharp-TE C, prescribed wake-strip edges for blunt-TE C
  (see "Trailing-edge handling").

### Mesh smoothers (later phase)

Smoothing is the fourth orthogonal stage: an optional post-pass on the
structured point array of any frame, independent of topology, tunnel shape,
and volume algorithm. `GridSmoothers.py` defines one interface —
(grid, frame metadata, constraints) → grid — where the constraints protect
the framework's invariants: the wall row is always frozen, ortho-block
layers can be frozen or height-preserved, and outer-boundary nodes are
either frozen or allowed to slide along the tunnel curve only.

Planned smoothers:

- **Constrained Laplacian**: cheap local averaging under the constraint set
  above; the go-to relief for TFI kinks such as the sharp-TE wedge without
  paying for a full elliptic solve.
- **Elliptic (Winslow) smoothing**: `GridElliptic` reused in smoothing mode
  — a few iterations starting from an existing grid instead of from the TFI
  initial grid. One solver, two roles; this is why the elliptic solver's
  entry point takes an initial grid rather than building its own.
- **Angle-based / orthogonality smoothing**: local skewness optimization
  targeting near-wall and near-corner cells — the sharp-TE wedge and
  blunt-TE base corners are the primary customers.

Because smoothers see only (grid, frame metadata, constraints), any new
smoother composes with every existing topology × tunnel × algorithm
combination for free. Smoothers report the quality metric before and after
and never run implicitly (GUI default: none).

### GUI

One new "Structured" entry in the existing engine selector
([src/ToolboxPagesMeshing.py](../../../src/ToolboxPagesMeshing.py)), with a
settings group: topology (O/C), tunnel shape (legacy/circular + parameters),
algorithm (TFI/elliptic/hyperbolic), ortho-block controls (layers, first
height, growth), outer-boundary controls (distribution, angle), plus
algorithm-specific sub-groups following the existing
`mesh_engine_specific_groups` pattern. Phase 5 adds a smoother sub-group
(selector, default none, plus iteration count). TE type is shown as
detected information, not a control.

## Phasing (each phase independently usable)

1. **Phase 1** — DELIVERED: `StructuredCore` + both topologies × both
   tunnels + TFI + ortho block + engine + GUI group + tests — a working,
   selectable mesher. Both TE types are handled from the start: the
   frames differ per TE type, so this cannot be retrofitted.
2. **Phase 2** — DELIVERED: elliptic solver (`GridElliptic.py`) with
   Thomas–Middlecoff control functions and simplified Sorenson-style
   outer-boundary orthogonality forcing.
3. **Phase 3** — DELIVERED: hyperbolic marching (`GridHyperbolic.py`),
   adaptive height-fraction hand-off onto a TFI fill in place of a fixed
   blend — see the phase-2/3/5 plan's execution notes for why.
4. **Phase 4**: H-mesh topology (own design pass) — NOT started; still
   requires its own design pass with the user before implementation.
5. **Phase 5** — DELIVERED: mesh smoothers (`GridSmoothers.py`) —
   Laplacian, elliptic (delegating to `GridElliptic.solve`), and
   angle-based (Thales-circle projection), all behind a quality guard
   that reverts any degrading pass.

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
  topology × tunnel × algorithm combination shipped — and every combination
  runs with both a sharp-TE and a blunt-TE contour (blunt variants produced
  with the existing TE-thickness tool), since the frames differ per TE type.
- Blunt-TE C-mesh: node-for-node interface match between the main C block
  and the wake strip; the base nodes appear verbatim in the strip's inflow
  row.
- Ortho block: angle between wall tangent and first mesh edge = 90° to tight
  tolerance at every wall node outside the TE corner-blend regions; inside
  them, no offset-curve crossing; thinning triggers on a synthetic
  high-curvature case instead of folding.
- Elliptic: outer-boundary angle converges to prescribed value.
- Hyperbolic: no layer crossing; outer row matches prescribed tunnel
  distribution exactly after the blend.
- Smoothers (phase 5): wall row bit-identical before and after; declared
  constraints hold (ortho-block heights, outer-boundary nodes on the tunnel
  curve); quality metric never degrades on the shipped test airfoils.
