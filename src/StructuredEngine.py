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
            self._reject_inverted(rows, name)
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

        contour_slice = frame.metadata.get('contour_slice')
        normals = OrthoLayers.wall_normals(
            frame.wall, corner_indices,
            spline_data=spline_data, contour_slice=contour_slice,
            closed=frame.periodic,
        )
        caps = OrthoLayers.max_offset_heights(
            frame.wall, normals,
            spline_data=spline_data, contour_slice=contour_slice,
        )
        ortho_rows = OrthoLayers.build_layers(
            frame.wall, normals, settings.ortho_layers,
            settings.first_layer_thickness, settings.ortho_growth, caps,
        )

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
    def _corner_indices(frame):
        if frame.kind == 'o':
            return [0, len(frame.wall) - 1]
        start, stop = frame.metadata['contour_slice']
        return [start, stop - 1]

    @staticmethod
    def _reject_inverted(rows: np.ndarray, name: str):
        jacobians = cell_jacobians(rows)
        positive = int(np.sum(jacobians > 0.0))
        negative = int(np.sum(jacobians < 0.0))
        inverted = min(positive, negative) + int(np.sum(jacobians == 0.0))
        if inverted:
            raise ValueError(
                f'Structured mesh block {name!r} has {inverted} inverted '
                'or degenerate cells; adjust layer heights or divisions.')

    @staticmethod
    def _emit_block(name: str, rows: np.ndarray) -> BlockMesh:
        block = BlockMesh(name=name)
        block.setUlines(BlockMesh.as_ulines(rows))
        return block
