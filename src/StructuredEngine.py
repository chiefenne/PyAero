"""Orchestrator for the Structured engine.

Composes topology frames, the optional exact-normal ortho block, and the
selected volume algorithm (phase 1: TFI standard/Hermite) into ordinary
BlockMesh objects. A blunt-TE C-mesh yields two blocks: the main C block
and the wake strip behind the base.
"""
from __future__ import annotations

import logging

import numpy as np

import GridElliptic
import GridHyperbolic
import GridSmoothers
import GridTFI
import OrthoLayers
from BlockMesh import BlockMesh
from StructuredCore import (
    StructuredMeshSettings,
    cell_jacobians,
    contour_array,
)
from StructuredTopologies import build_frames, side_segment

MAIN_BLOCK_NAME = 'block_structured'
WAKE_STRIP_BLOCK_NAME = 'block_structured_wake_strip'
# The ortho rim may reach at most this share of each column's wall-to-
# farfield distance, so the remaining normal divisions keep room to grow.
ORTHO_MAX_REACH = 0.5

logger = logging.getLogger(__name__)


class StructuredEngine:

    def build_blocks(self, *, spline_data,
                     settings: StructuredMeshSettings):
        contour = contour_array(spline_data)
        frames = build_frames(contour, settings)

        named_blocks = []
        for frame in frames:
            if frame.kind == 'wake_strip':
                rows = GridTFI.fill(frame, 'standard')
                name = WAKE_STRIP_BLOCK_NAME
                frozen_rows = 1
            else:
                rows = self._fill_main_frame(frame, spline_data, settings)
                name = MAIN_BLOCK_NAME
                frozen_rows = 1 + settings.ortho_layers
            rows = self._apply_smoother(rows, frame, settings, frozen_rows,
                                        name)
            self._reject_inverted(rows, name, frozen_rows)
            named_blocks.append((name, self._emit_block(name, rows)))
        return named_blocks

    @staticmethod
    def _apply_smoother(rows, frame, settings: StructuredMeshSettings,
                        frozen_rows: int, name: str) -> np.ndarray:
        if settings.smoother == 'none':
            return rows
        rows, info = GridSmoothers.smooth(
            rows, method=settings.smoother,
            iterations=settings.smoother_iterations,
            periodic=frame.periodic, frozen_rows=frozen_rows,
        )
        logger.info(
            'Structured block %r: %s smoother quality %.3e -> %.3e',
            name, settings.smoother, info['quality_before'],
            info['quality_after'])
        return rows

    def _volume_fill(self, frame, settings: StructuredMeshSettings, *,
                     spline_data=None, corner_indices=None) -> np.ndarray:
        if settings.algorithm == 'hyperbolic':
            contour_slice = (frame.metadata.get('contour_slice')
                            if spline_data is not None else None)
            normals = OrthoLayers.wall_normals(
                frame.wall, corner_indices or [],
                spline_data=spline_data, contour_slice=contour_slice,
                closed=frame.periodic,
            )
            return GridHyperbolic.march(
                frame, normals=normals,
                first_spacing=settings.first_layer_thickness,
                fraction_cap=settings.hyperbolic_fraction_cap,
                smoothing=settings.hyperbolic_smoothing,
            )

        rows = GridTFI.fill(frame, settings.tfi_variant,
                            settings.boundary_control)
        if settings.algorithm == 'elliptic':
            rows, _info = GridElliptic.solve(
                rows,
                periodic=frame.periodic,
                iterations=settings.elliptic_iterations,
                relaxation=settings.elliptic_relaxation,
                outer_orthogonal=(
                    settings.boundary_control.angle_mode == 'orthogonal'),
            )
        return rows

    def _fill_main_frame(self, frame, spline_data,
                         settings: StructuredMeshSettings) -> np.ndarray:
        if settings.algorithm not in ('tfi', 'elliptic', 'hyperbolic'):
            raise ValueError(
                f'Unknown structured algorithm: {settings.algorithm!r}.')
        corner_indices = self._corner_indices(frame)
        if settings.ortho_layers <= 0:
            return self._volume_fill(
                frame, settings, spline_data=spline_data,
                corner_indices=corner_indices)

        if settings.ortho_layers >= settings.normal_divisions:
            raise ValueError(
                'Ortho layers must be fewer than total normal divisions.')

        ortho_rows = self._build_ortho_rows(
            frame, spline_data, settings, corner_indices,
            settings.first_layer_thickness)
        if not self._ortho_rows_usable(ortho_rows, frame):
            raise ValueError(self._ortho_too_thick_message(
                frame, spline_data, settings, corner_indices))

        rim = ortho_rows[-1]
        next_spacing = (settings.first_layer_thickness *
                        settings.ortho_growth ** settings.ortho_layers)
        remaining_count = (settings.normal_divisions -
                           settings.ortho_layers + 1)
        side_start = side_segment(rim[0], frame.outer[0],
                                  next_spacing, remaining_count)
        if frame.periodic:
            side_end = side_start.copy()
        else:
            side_end = side_segment(rim[-1], frame.outer[-1],
                                    next_spacing, remaining_count)
        reduced = type(frame)(
            wall=rim, outer=frame.outer,
            side_start=side_start, side_end=side_end,
            kind=frame.kind, te_type=frame.te_type,
            periodic=frame.periodic, metadata=dict(frame.metadata),
        )
        # The rim is no longer the exact contour, so the reduced-frame
        # fill never uses spline_data/contour_slice for its normals
        # (hyperbolic) — only finite differences on the rim polyline,
        # per the design spec's "rim normals from finite differences".
        outer_rows = self._volume_fill(
            reduced, settings, spline_data=None,
            corner_indices=corner_indices)
        return np.vstack((ortho_rows, outer_rows[1:]))

    @staticmethod
    def _build_ortho_rows(frame, spline_data,
                          settings: StructuredMeshSettings, corner_indices,
                          first_height: float,
                          warn: bool = True) -> np.ndarray:
        contour_slice = frame.metadata.get('contour_slice')
        block_height = OrthoLayers.layer_heights(
            settings.ortho_layers, first_height, settings.ortho_growth)[-1]
        normals = OrthoLayers.wall_normals(
            frame.wall, corner_indices,
            spline_data=spline_data, contour_slice=contour_slice,
            closed=frame.periodic,
            blend_length=OrthoLayers.CORNER_BLEND_FACTOR * block_height,
        )
        caps = OrthoLayers.max_offset_heights(
            frame.wall, normals,
            spline_data=spline_data, contour_slice=contour_slice,
            corner_indices=corner_indices,
        )
        return OrthoLayers.build_layers(
            frame.wall, normals, settings.ortho_layers,
            first_height, settings.ortho_growth, caps,
            closed=frame.periodic, warn=warn,
        )

    @staticmethod
    def _ortho_rows_usable(ortho_rows: np.ndarray, frame) -> bool:
        """No folded/degenerate ortho cell, and the rim keeps clear of the
        farfield (ORTHO_MAX_REACH of each column's distance)."""
        jacobians = cell_jacobians(ortho_rows)
        if not (np.all(jacobians > 0.0) or np.all(jacobians < 0.0)):
            return False
        reach = np.linalg.norm(ortho_rows[-1] - frame.wall, axis=1)
        room = np.linalg.norm(frame.outer - frame.wall, axis=1)
        return bool(np.all(reach <= ORTHO_MAX_REACH * room))

    def _ortho_too_thick_message(self, frame, spline_data,
                                 settings: StructuredMeshSettings,
                                 corner_indices) -> str:
        layers = settings.ortho_layers
        growth = settings.ortho_growth
        first = settings.first_layer_thickness
        height = OrthoLayers.layer_heights(layers, first, growth)[-1]

        # Largest uniform scale of the layer heights that still works.
        low, high = 0.0, 1.0
        for _ in range(30):
            mid = 0.5 * (low + high)
            rows = self._build_ortho_rows(
                frame, spline_data, settings, corner_indices, first * mid,
                warn=False)
            if self._ortho_rows_usable(rows, frame):
                low = mid
            else:
                high = mid
        safe_height = low * height

        message = (
            f'Ortho block too thick: {layers} layers at growth {growth:g} '
            f'reach {height:.3g} (chord = 1), but on this contour the '
            f'block folds or crowds the farfield above about '
            f'{safe_height:.3g}.')
        max_layers = 0
        while (max_layers < layers and OrthoLayers.layer_heights(
                max_layers + 1, first, growth)[-1] <= safe_height):
            max_layers += 1
        hints = []
        if max_layers >= 1:
            hints.append(f'use at most {max_layers} layers at growth '
                         f'{growth:g}')
        if layers * first <= safe_height:
            low_growth, high_growth = 1.0, growth
            for _ in range(40):
                mid = 0.5 * (low_growth + high_growth)
                if OrthoLayers.layer_heights(layers, first, mid)[-1] \
                        <= safe_height:
                    low_growth = mid
                else:
                    high_growth = mid
            low_growth = np.floor(low_growth * 1000.0) / 1000.0
            hints.append(f'or growth <= {low_growth:.3f} with {layers} '
                         'layers')
        if not hints:
            hints.append('reduce the first layer thickness')
        return message + ' ' + ' '.join(hints).capitalize() + '.'

    @staticmethod
    def _corner_indices(frame):
        if frame.kind == 'o':
            return [0, len(frame.wall) - 1]
        start, stop = frame.metadata['contour_slice']
        return [start, stop - 1]

    @staticmethod
    def _reject_inverted(rows: np.ndarray, name: str,
                         frozen_rows: int = 1):
        jacobians = cell_jacobians(rows)
        positive = int(np.sum(jacobians > 0.0))
        negative = int(np.sum(jacobians < 0.0))
        majority = 1.0 if positive >= negative else -1.0
        bad = np.argwhere(jacobians * majority <= 0.0)
        if not len(bad):
            return
        j, i = bad[np.argmin(bad[:, 0])]
        center = rows[j:j + 2, i:i + 2].reshape(-1, 2).mean(axis=0)
        rows_hit = f'rows {bad[:, 0].min()}-{bad[:, 0].max()}'
        if frozen_rows > 1:
            region = ('inside the ortho block' if j < frozen_rows - 1
                      else 'in the fill above the ortho block')
        else:
            region = 'in the volume fill'
        raise ValueError(
            f'Structured mesh block {name!r} has {len(bad)} inverted or '
            f'degenerate cells, {region} ({rows_hit}), first near '
            f'x={center[0]:.3f}, y={center[1]:.3f}. Try fewer ortho layers '
            'or a smaller growth, more normal divisions, or the Elliptic '
            'algorithm.')

    @staticmethod
    def _emit_block(name: str, rows: np.ndarray) -> BlockMesh:
        block = BlockMesh(name=name)
        block.setUlines(BlockMesh.as_ulines(rows))
        return block
