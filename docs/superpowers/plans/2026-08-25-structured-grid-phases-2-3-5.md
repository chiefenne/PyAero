# Structured Grid Framework — Phases 2, 3, 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the structured engine's algorithm matrix: elliptic solver (phase 2), hyperbolic marching (phase 3), and the post-smoothing stage (phase 5). Phase 4 (H-mesh) is explicitly excluded — the spec requires its own design pass with the user first.

**Architecture:** Each algorithm consumes the phase-1 `GridFrame` and returns a `(nj, ni, 2)` rows array; the engine composition (ortho block, wake strip, inverted-cell guard, BlockMesh emission) is already in place and gains an `algorithm` dispatch. Smoothers are a fourth orthogonal stage applied to rows arrays under invariant-protecting constraints.

**Tech Stack:** Python 3.13, numpy, scipy; PySide6 for the GUI task.

**Spec:** `docs/superpowers/specs/2026-08-22-structured-grid-framework-design.md`. Phase-1 groundwork: `docs/superpowers/plans/2026-08-22-structured-grid-phase1.md` (all done).

## Global Constraints

- Everything from the phase-1 plan's Global Constraints still holds (wall verbatim, ValueError reporting, test python `/Users/andreas/miniforge3/envs/PyAero/bin/python -m pytest`, commit style with the Claude trailer).
- Test airfoils now live tracked at `tests/data/` (naca0012.dat, naca2315.dat, MW-166-39-44-43.dat).
- All four frame boundaries are Dirichlet for elliptic — bit-identical before/after. The O-grid **seam is interior** under periodic ξ and is allowed to move (both duplicate columns stay identical).
- New settings fields extend `StructuredMeshSettings` with defaults that keep phase-1 behavior when untouched (`algorithm='tfi'`, `smoother='none'`).
- `src/Elliptic.py` (legacy tunnel smoother) is NOT modified; `GridElliptic.py` is array-native (`(nj, ni, 2)`), adds periodic ξ and control functions the legacy solver lacks. Same reasoning as the phase-1 `BlockMesh.transfinite` decision.
- MW-166 is the hard regression case: strongly cambered + reflexed TE. Every new algorithm must pass it for both topologies.

---

### Task 1: GridElliptic — Winslow + Thomas–Middlecoff + periodic ξ

**Files:**
- Create: `src/GridElliptic.py`
- Test: `tests/test_grid_elliptic.py`

**Interfaces:**
- Consumes: `StructuredCore.cell_jacobians`, frames/TFI from phase 1 (tests only).
- Produces (Tasks 2, 5 rely on this exact signature):
  - `solve(rows, *, periodic=False, iterations=100, relaxation=0.8, tolerance=1.0e-8, control='thomas_middlecoff', outer_orthogonal=False, ortho_relaxation=0.3) -> tuple[np.ndarray, dict]` — returns `(new_rows, info)` with `info = {'iterations': int, 'residual': float, 'converged': bool}`. Takes an **initial grid**, never builds one — this is the dual-role entry point the spec reserves for phase-5 smoothing reuse.

**Method (module docstring):**
- Winslow/TTM interior update, Jacobi sweep with under-relaxation ω:
  `α = x_η·x_η, γ = x_ξ·x_ξ, β = x_ξ·x_η` (central differences), candidate node from the standard 9-point TTM stencil (same algebra as `Elliptic.EllipticSolver.smooth`, transposed to rows[j, i]).
- **Control functions** (`control='thomas_middlecoff'`): φ(ξ) from the wall and outer rows, ψ(η) from the two side columns via the TM boundary formulas `φ = −(x_ξ·x_ξξ)/(x_ξ·x_ξ)`, `ψ = −(x_η·x_ηη)/(x_η·x_η)`, linearly interpolated into the interior; source terms `α·φ·x_ξ/2·(spacing)` added to the stencil. Property this buys: a rectangle with geometric (clustered) spacing is a fixed point of the iteration — pure Winslow would uniformize it and destroy the first-layer clustering. `control='none'` disables (pure Winslow) for comparison tests.
- **Periodic ξ** (`periodic=True`, O-grids): solve on the ni−1 unique columns with `np.roll` neighbors; the seam column is interior and relaxes; after each sweep copy column 0 → column ni−1. Sides are then NOT Dirichlet (they are the seam); wall/outer rows stay Dirichlet.
- **Outer orthogonality** (`outer_orthogonal=True`): Sorenson-style forcing implemented as an under-relaxed correction of row nj−2 toward `outer + d_i·m_i` (m_i inward unit normal of the outer row, d_i the current normal distance), applied each sweep with `ortho_relaxation`. Simplified but honest — the full P,Q iteration is overkill at this grid scale.
- Residual: max node displacement per sweep; stop at `tolerance`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_grid_elliptic.py  (imports as in test_grid_tfi.py)
def _clustered_rect_frame(nx=15, ny=10):
    x = np.linspace(0.0, 2.0, nx)
    d = core.geometric_distances(1.0, 0.02, ny)
    return np.stack(np.meshgrid(x, d), axis=-1)  # build rows directly

def test_clustered_rectangle_is_fixed_point():
    rows = _clustered_rect_frame()
    out, info = GridElliptic.solve(rows, iterations=50)
    assert np.max(np.abs(out - rows)) < 1e-6      # TM preserves clustering

def test_pure_winslow_would_move_it():
    rows = _clustered_rect_frame()
    out, _ = GridElliptic.solve(rows, iterations=50, control='none')
    assert np.max(np.abs(out - rows)) > 1e-3      # documents why TM exists

def test_boundaries_dirichlet_and_wall_bitidentical():
    # C-frame NACA0012 TFI grid; all four boundaries np.array_equal after solve

def test_o_grid_periodic_seam_relaxes():
    # O-frame: solve(periodic=True); assert rows[:,0]==rows[:,-1] exactly,
    # wall/outer rows unchanged, and the seam moved (max delta > 1e-6)

def test_no_inverted_cells_after_elliptic_all_airfoils():
    # for naca0012 sharp + blunt, MW166: C and O frames, TFI init -> solve
    # (periodic for O); cell_jacobians single sign

def test_outer_orthogonality_improves_angle():
    # O circular naca0012: median |angle-90| at outer row strictly better
    # than the TFI initial grid and < 10 degrees

def test_info_reports_convergence():
    # residual decreases; info keys present
```

Write these as real tests with the loaders from `test_structured_topologies` / `test_ortho_layers` (same import pattern as `test_grid_tfi.py`).

- [ ] **Step 2: Run to verify failure** (`ModuleNotFoundError: GridElliptic`)
- [ ] **Step 3: Implement `src/GridElliptic.py`** per the method block
- [ ] **Step 4: Full suite green**
- [ ] **Step 5: Commit** `Add GridElliptic: Winslow/TM elliptic solver with periodic seam and orthogonality forcing`

---

### Task 2: Elliptic engine + GUI wiring

**Files:**
- Modify: `src/StructuredCore.py` (settings fields), `src/StructuredEngine.py` (algorithm dispatch), `src/ToolboxPagesMeshing.py` (algorithm combo + iterations widget, settings mapping)
- Test: extend `tests/test_structured_engine.py`, `tests/test_structured_gui.py`

**Interfaces:**
- `StructuredMeshSettings` gains: `algorithm: str = 'tfi'` (`'tfi' | 'elliptic'`, `'hyperbolic'` joins in Task 4), `elliptic_iterations: int = 150`, `elliptic_relaxation: float = 0.8`.
- Engine `_fill_main_frame`: build the TFI grid exactly as now, then if `algorithm == 'elliptic'` run `GridElliptic.solve(rows, periodic=frame.periodic, iterations=..., relaxation=..., outer_orthogonal=(boundary_control.angle_mode == 'orthogonal'))`. With the ortho block, elliptic runs only on the outer (reduced-frame) rows — ortho rows stay exact. Wake strip stays TFI.
- GUI algorithm combo becomes: 'TFI (standard)'→`('tfi','standard')`, 'TFI (Hermite)'→`('tfi','hermite')`, 'Elliptic (Winslow + TM)'→`('elliptic','standard')` — store the pair via userData tuple or two userData strings; map into `algorithm` + `tfi_variant`. Add `structured_elliptic_iterations` QSpinBox (10–2000, default 150).

**Steps:** failing tests (engine matrix × `algorithm='elliptic'` incl. MW-166 both topologies + blunt wake strip untouched by elliptic; GUI roundtrip for the new combo entry and iterations) → red → implement → green → commit `Wire elliptic algorithm into structured engine and GUI`.

---

### Task 3: GridHyperbolic — layer marching with farfield blend

**Files:**
- Create: `src/GridHyperbolic.py`
- Test: `tests/test_grid_hyperbolic.py`

**Interfaces:**
- Consumes: `OrthoLayers.wall_normals` (exact spline normals + corner blend — the engine passes them in), `StructuredCore` distributions.
- Produces: `march(frame, *, normals, first_spacing, blend_fraction=0.2, smoothing=0.5) -> np.ndarray` — rows array; `rows[0] == frame.wall` verbatim, `rows[-1] == frame.outer` verbatim.

**Method (module docstring):** simplified Steger–Chan front marching:
1. Per-column target length `L_i = |outer_i − wall_i|`; global geometric height fractions from `geometric_distances(1.0-normalized, first_spacing/L_mean, nj)`, scaled per column by `L_i` — each column marches toward its own outer distance.
2. Per layer k: front normals = `_unit_normals` of current front (periodic-aware), smoothed with a few neighbor-averaging passes (the hyperbolic dissipation surrogate); predictor `r* = r_k + Δh_i · n_i`.
3. Implicit layer smoothing: `(I − ε·D²) r_{k+1} = r*` with D² the second difference along the layer — cyclic tridiagonal (Sherman–Morrison) for periodic O, natural ends for C; ε from `smoothing`, scaled by local Δh.
4. Boundary conditions: O — periodic wrap, column ni−1 copied from 0. C — front ends pinned to the outlet plane: after each step set `x_end = x_outlet` (from `frame.metadata['x_outlet']`), y from the solve.
5. **Farfield blend** (the spec's resolution of hyperbolic termination): the last `blend_fraction` of layers blend `r = (1−w)·r_marched + w·r_target` with `r_target` the straight-line interpolation between the blend-start front and `frame.outer` at the same height fractions, `w` a smoothstep 0→1 across the zone; final row = `frame.outer` exactly.

- [ ] **Step 1: failing tests** — wall verbatim; outer row `np.array_equal`; no inverted cells for all three airfoils × {C, O} × {sharp, blunt incl. wake-strip frame untouched}; O seam columns identical; C front ends on the outlet plane at every layer; no layer crossing (jacobians single sign) — same loader pattern as `test_grid_tfi.py`.
- [ ] **Step 2: red** → **Step 3: implement** → **Step 4: suite green** → **Step 5: commit** `Add GridHyperbolic: front marching with implicit smoothing and farfield blend`

---

### Task 4: Hyperbolic engine + GUI wiring

**Files:**
- Modify: `src/StructuredCore.py` (`hyperbolic_blend_fraction: float = 0.2`, `hyperbolic_smoothing: float = 0.5`), `src/StructuredEngine.py`, `src/ToolboxPagesMeshing.py`
- Test: extend `tests/test_structured_engine.py`, `tests/test_structured_gui.py`

**Wiring:** `algorithm == 'hyperbolic'` in `_fill_main_frame`: compute `normals = OrthoLayers.wall_normals(...)` (same corner indices as the ortho path) and call `GridHyperbolic.march`. With ortho block: march from the rim (reduced frame) with rim normals from finite differences of the rim polyline. GUI combo gains 'Hyperbolic (marching)' → `('hyperbolic','standard')` plus a blend-fraction QDoubleSpinBox (0.05–0.6, default 0.2). Tests: engine matrix × hyperbolic incl. MW-166; GUI roundtrip. Commit `Wire hyperbolic algorithm into structured engine and GUI`.

---

### Task 5: GridSmoothers — constrained post-smoothing stage

**Files:**
- Create: `src/GridSmoothers.py`
- Test: `tests/test_grid_smoothers.py`

**Interfaces:**
- `smooth(rows, *, method, iterations=10, periodic=False, frozen_rows=1, relaxation=0.5) -> tuple[np.ndarray, dict]` — `method in ('laplacian', 'elliptic', 'angle_based')`; `info = {'quality_before': float, 'quality_after': float}` where quality = min |cell jacobian|. Rows `0 .. frozen_rows−1` and the outer row are bit-identical after; side columns fixed unless `periodic`.
- Implementation: **laplacian** — under-relaxed 4-neighbor average of unfrozen interior, periodic roll for O. **elliptic** — delegate: `GridElliptic.solve(rows[frozen_rows−1:], periodic=periodic, iterations=iterations)` spliced back (the last frozen row acts as the Dirichlet wall). **angle_based** — Zhou–Shimada-style torsion relaxation: each unfrozen interior node moves under-relaxed toward the average of the four positions that would make its edges meet neighbors at right angles.
- Guard: if quality_after < quality_before, return the ORIGINAL rows with a logged warning (`smoothers never degrade` is enforced, not hoped for).

- [ ] Tests: wall + frozen ortho rows bit-identical for all three methods; laplacian moves interior (delta > 0); elliptic mode delegates (patch `GridElliptic.solve`, assert called with sliced rows); quality never degrades on naca0012 + MW166 C/O grids; degradation guard returns original rows on a crafted case. Red → implement → green → commit `Add GridSmoothers: constrained Laplacian, elliptic, and angle-based smoothing`

---

### Task 6: Smoother engine + GUI wiring

**Files:**
- Modify: `src/StructuredCore.py` (`smoother: str = 'none'`, `smoother_iterations: int = 10`), `src/StructuredEngine.py`, `src/ToolboxPagesMeshing.py`
- Test: extend `tests/test_structured_engine.py`, `tests/test_structured_gui.py`

**Wiring:** in `build_blocks`, after the volume fill and before the inverted-cell guard: if `smoother != 'none'`, `rows, info = GridSmoothers.smooth(rows, method=..., iterations=..., periodic=frame.periodic, frozen_rows=1 + settings.ortho_layers)` for main frames (`frozen_rows=1` for the wake strip) and log quality before/after. GUI: 'Smoother' combo (None/Laplacian/Elliptic/Angle-based, default None) + iterations spinbox; settings mapping. Tests: engine applies smoother with correct frozen_rows (patch and inspect), wall verbatim end-to-end with smoothing on, GUI roundtrip. Commit `Wire post-smoothing stage into structured engine and GUI`.

---

### Task 7: Spec/plan bookkeeping

Mark phases 2, 3, 5 as delivered in the spec's phasing section (one-line status notes), append execution notes to this plan, commit `Record phases 2, 3, 5 delivery in spec and plan`.

## Self-Review

- **Spec coverage:** phase 2 (Winslow/TTM + control functions + boundary angle/spacing) → Tasks 1–2; phase 3 (Steger–Chan-style marching, periodic O / matched-or-prescribed C, ~20% blend) → Tasks 3–4; phase 5 (three smoothers, constraints, quality reporting, never-run-implicitly GUI default) → Tasks 5–6. Phase 4 excluded by design.
- **Type consistency:** `solve` and `smooth` both return `(rows, info)`; `march` returns rows only (it cannot fail silently — the engine guard still runs). `frozen_rows` semantics identical in Tasks 5–6.
- **Honest simplifications, named in module docstrings:** Sorenson forcing via boundary-adjacent correction rather than full P,Q iteration; hyperbolic dissipation via normal smoothing + implicit layer solve rather than the full linearized Steger–Chan system. Both are validated by the same no-inverted-cells matrix as everything else.
