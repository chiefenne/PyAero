from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from BlockMesh import BlockMesh
from ExperimentalCGrid import (
    ExperimentalCGridGenerator,
    ExperimentalCGridSettings,
)
from ExperimentalOGrid import (
    ExperimentalOGridGenerator,
    ExperimentalOGridSettings,
)
from QuadLayout import QuadLayoutGenerator
from QuadMonitor import LineMetricField
from Smoother import SmootherFactory


MINIMUM_POINT_SIZE = 1.0e-9


def _as_points(points: Sequence[Sequence[float]]) -> np.ndarray:
    array = np.asarray(points, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError('Pipeline points must be an N x 2 array.')
    return array


def _point_sizes(line) -> np.ndarray:
    points = _as_points(line)
    point_count = len(points)
    if point_count == 0:
        return np.array([], dtype=float)
    if point_count == 1:
        return np.array([1.0], dtype=float)

    segments = np.linalg.norm(points[1:] - points[:-1], axis=1)
    sizes = np.empty(point_count, dtype=float)
    sizes[0] = segments[0]
    sizes[-1] = segments[-1]
    if point_count > 2:
        sizes[1:-1] = 0.5 * (segments[:-1] + segments[1:])
    return np.maximum(sizes, MINIMUM_POINT_SIZE)


@dataclass(slots=True)
class HybridStage2Settings:
    enabled: bool = True
    sweeps: int = 2
    redistribute_u: bool = True
    redistribute_v: bool = True
    monitor_kind: str = 'boundary_size'

    def __post_init__(self):
        self.enabled = bool(self.enabled)
        self.sweeps = max(0, int(self.sweeps))
        self.redistribute_u = bool(self.redistribute_u)
        self.redistribute_v = bool(self.redistribute_v)
        monitor_kind = str(self.monitor_kind).strip().lower() or 'boundary_size'
        if monitor_kind not in ('boundary_size',):
            monitor_kind = 'boundary_size'
        self.monitor_kind = monitor_kind


@dataclass(slots=True)
class HybridStage1Settings:
    enabled: bool = True
    algorithm: str = 'angle_based'
    iterations: int = 15
    tolerance: float = 1.0e-4
    relaxation: float = 0.6

    def __post_init__(self):
        self.enabled = bool(self.enabled)
        algorithm = str(self.algorithm).strip().lower() or 'angle_based'
        if algorithm in ('off', 'disabled'):
            algorithm = 'none'
        if algorithm not in ('none', 'simple', 'elliptic', 'angle_based'):
            algorithm = 'angle_based'
        self.algorithm = algorithm
        self.iterations = max(0, int(self.iterations))
        self.tolerance = max(1.0e-12, float(self.tolerance))
        self.relaxation = float(np.clip(self.relaxation, 0.01, 1.0))


@dataclass(slots=True)
class HybridQuadPipelineSettings:
    layout_strategy: str = 'metric_c_grid'
    protect_near_wall: bool = True
    singularity_template: str = 'auto_boundary_c'
    stage2: HybridStage2Settings = field(default_factory=HybridStage2Settings)
    stage1: HybridStage1Settings = field(default_factory=HybridStage1Settings)

    def __post_init__(self):
        strategy = (
            str(self.layout_strategy).strip().lower() or 'metric_c_grid'
        )
        if strategy in ('standard_stub',):
            strategy = 'multi_element_oc'
        if strategy in ('metric_wind_tunnel', 'metric_based'):
            strategy = 'metric_c_grid'
        if strategy not in ('metric_c_grid', 'multi_element_oc'):
            strategy = 'metric_c_grid'
        self.layout_strategy = strategy
        self.protect_near_wall = bool(self.protect_near_wall)
        template = str(self.singularity_template).strip().lower() or 'auto_boundary_c'
        if template not in ('auto_boundary_c',):
            template = 'auto_boundary_c'
        self.singularity_template = template
        if not isinstance(self.stage2, HybridStage2Settings):
            self.stage2 = HybridStage2Settings(**dict(self.stage2))
        if not isinstance(self.stage1, HybridStage1Settings):
            self.stage1 = HybridStage1Settings(**dict(self.stage1))


@dataclass(slots=True)
class HybridQuadPipelineResult:
    blocks: list[BlockMesh]
    layout_plan: object
    metadata: dict


class HybridQuadPipeline:
    """4 -> 2 -> 1 orchestration for layout-driven structured hybrid meshes."""

    @staticmethod
    def default_stage2_metadata(settings: HybridStage2Settings, *,
                                protect_near_wall: bool = True):
        return {
            'enabled': bool(settings.enabled),
            'monitor_kind': settings.monitor_kind,
            'sweeps': int(settings.sweeps),
            'redistribute_u': bool(settings.redistribute_u),
            'redistribute_v': bool(settings.redistribute_v),
            'protect_near_wall': bool(protect_near_wall),
            'blocks_processed': 0,
            'blocks_skipped': 0,
            'applied': False,
        }

    @staticmethod
    def default_stage1_metadata(settings: HybridStage1Settings, *,
                                protect_near_wall: bool = True):
        return {
            'enabled': bool(settings.enabled),
            'algorithm': settings.algorithm,
            'iterations': int(settings.iterations),
            'tolerance': float(settings.tolerance),
            'protect_near_wall': bool(protect_near_wall),
            'blocks_processed': 0,
            'blocks_skipped': 0,
            'applied': False,
        }

    @classmethod
    def build_metadata(cls, layout_plan, settings: HybridQuadPipelineSettings, *,
                       engine: str = 'hybrid', stage2_metadata=None,
                       stage1_metadata=None):
        stage2_metadata = dict(
            stage2_metadata or cls.default_stage2_metadata(
                settings.stage2,
                protect_near_wall=settings.protect_near_wall,
            )
        )
        stage1_metadata = dict(
            stage1_metadata or cls.default_stage1_metadata(
                settings.stage1,
                protect_near_wall=settings.protect_near_wall,
            )
        )
        return {
            'engine': str(engine).strip().lower() or 'hybrid',
            'layout_strategy': settings.layout_strategy,
            'protect_near_wall': bool(settings.protect_near_wall),
            'singularity_controls': {
                'template': settings.singularity_template,
            },
            'stages': {
                'stage4_ready': True,
                'stage2_applied': bool(stage2_metadata.get('applied', False)),
                'stage1_applied': bool(stage1_metadata.get('applied', False)),
            },
            'stage4': {
                'implemented': bool(layout_plan.metadata.get('implemented', False)),
                'strategy': settings.layout_strategy,
                'element_count': int(layout_plan.metadata.get('element_count', 0)),
                'block_count': int(layout_plan.metadata.get('block_count', 0)),
                'singularity_count': len(layout_plan.singularities),
                'applied': True,
            },
            'stage2': stage2_metadata,
            'stage1': stage1_metadata,
        }

    def run_stage4(self, blocks=None, contour=None, settings=None, *,
                   airfoil_settings=None, tunnel_settings=None,
                   wake_settings=None, trailing_edge_settings=None,
                   contour_metadata=None, boundary_loops=None,
                   engine: str = 'hybrid'):
        if settings is None:
            settings = HybridQuadPipelineSettings()
        if not isinstance(settings, HybridQuadPipelineSettings):
            settings = HybridQuadPipelineSettings(**dict(settings))

        layout_plan = self.build_layout_plan(
            contour,
            settings,
            airfoil_settings=airfoil_settings,
            tunnel_settings=tunnel_settings,
            wake_settings=wake_settings,
            trailing_edge_settings=trailing_edge_settings,
            contour_metadata=contour_metadata,
            boundary_loops=boundary_loops,
        )

        if blocks is None:
            blocks = self.build_blocks_from_layout(
                layout_plan,
                airfoil_settings=airfoil_settings,
                tunnel_settings=tunnel_settings,
            )
        else:
            blocks = list(blocks)

        return HybridQuadPipelineResult(
            blocks=blocks,
            layout_plan=layout_plan,
            metadata=self.build_metadata(
                layout_plan,
                settings,
                engine=engine,
            ),
        )

    def run(self, blocks=None, contour=None, settings=None, *,
            airfoil_settings=None, tunnel_settings=None, wake_settings=None,
            trailing_edge_settings=None, contour_metadata=None,
            boundary_loops=None):
        stage4_result = self.run_stage4(
            blocks=blocks,
            contour=contour,
            settings=settings,
            airfoil_settings=airfoil_settings,
            tunnel_settings=tunnel_settings,
            wake_settings=wake_settings,
            trailing_edge_settings=trailing_edge_settings,
            contour_metadata=contour_metadata,
            boundary_loops=boundary_loops,
            engine='hybrid',
        )
        if settings is None:
            settings = HybridQuadPipelineSettings()
        if not isinstance(settings, HybridQuadPipelineSettings):
            settings = HybridQuadPipelineSettings(**dict(settings))

        layout_plan = stage4_result.layout_plan
        blocks = list(stage4_result.blocks)

        stage2_metadata = self.apply_stage2(
            blocks,
            settings.stage2,
            protect_near_wall=settings.protect_near_wall,
        )
        stage1_metadata = self.apply_stage1(
            blocks,
            settings.stage1,
            protect_near_wall=settings.protect_near_wall,
        )

        return HybridQuadPipelineResult(
            blocks=blocks,
            layout_plan=layout_plan,
            metadata=self.build_metadata(
                layout_plan,
                settings,
                engine='hybrid',
                stage2_metadata=stage2_metadata,
                stage1_metadata=stage1_metadata,
            ),
        )

    @staticmethod
    def build_layout_plan(contour, settings: HybridQuadPipelineSettings, *,
                          airfoil_settings=None, tunnel_settings=None,
                          wake_settings=None, trailing_edge_settings=None,
                          contour_metadata=None, boundary_loops=None):
        if contour is None and boundary_loops is None:
            raise ValueError('The hybrid pipeline requires contour data or explicit boundary loops.')

        contour_metadata = dict(contour_metadata or {})
        explicit_loops = (
            boundary_loops is not None or
            any(
                key in contour_metadata
                for key in ('hybrid_boundary_loops', 'boundary_loops', 'element_loops')
            )
        )

        tunnel_height = float(
            getattr(tunnel_settings, 'tunnel_height', 3.5)
        )
        wake_length = float(
            getattr(wake_settings, 'tunnel_wake', 7.0)
        )
        surface_points = 0 if explicit_loops else (
            len(contour[0]) if contour is not None and len(contour) == 2 else 0
        )
        normal_divisions = int(getattr(airfoil_settings, 'divisions', 20))
        first_layer = float(getattr(airfoil_settings, 'thickness', 0.004))
        layer_growth = float(getattr(airfoil_settings, 'growth', 1.05))
        connector_layers = int(getattr(tunnel_settings, 'divisions_height', 80))
        trailing_edge_divisions = int(
            getattr(trailing_edge_settings, 'trailing_edge_divisions', 3)
        )

        if settings.layout_strategy == 'metric_c_grid':
            return QuadLayoutGenerator.generate_metric_c_grid(
                contour,
                boundary_loops=boundary_loops,
                metadata=contour_metadata,
                tunnel_height=tunnel_height,
                wake_length=wake_length,
                surface_points=surface_points,
                normal_divisions=normal_divisions,
                first_layer_thickness=first_layer,
                connector_layers=connector_layers,
                trailing_edge_divisions=trailing_edge_divisions,
                singularity_template=settings.singularity_template,
            )

        return QuadLayoutGenerator.generate(
            contour,
            boundary_loops=boundary_loops,
            metadata=contour_metadata,
            tunnel_height=tunnel_height,
            wake_length=wake_length,
            surface_points=surface_points,
            normal_divisions=normal_divisions,
            first_layer_thickness=first_layer,
            layer_growth=layer_growth,
            connector_layers=connector_layers,
            trailing_edge_divisions=trailing_edge_divisions,
        )

    @classmethod
    def build_blocks_from_layout(cls, layout_plan, *, airfoil_settings=None,
                                 tunnel_settings=None):
        ring_settings = ExperimentalOGridSettings(
            name='block_hybrid_element',
            normal_divisions=max(4, int(getattr(airfoil_settings, 'divisions', 20))),
            first_layer_thickness=max(
                1.0e-12,
                float(getattr(airfoil_settings, 'thickness', 0.004)),
            ),
            initial_smoothing_iterations=max(
                2,
                min(30, int(getattr(tunnel_settings, 'smoothing_iterations', 10))),
            ),
            final_smoothing_iterations=max(
                0,
                min(10, int(getattr(tunnel_settings, 'protected_guide_smoothing', 3))),
            ),
            smoothing_tolerance=max(
                1.0e-12,
                float(getattr(tunnel_settings, 'smoothing_tolerance', 1.0e-4)),
            ),
            relaxation=float(
                np.clip(
                    float(getattr(tunnel_settings, 'elliptic_relaxation', 0.4)),
                    0.01,
                    1.0,
                )
            ),
        )

        connector_iterations = max(
            0,
            min(20, int(getattr(tunnel_settings, 'smoothing_iterations', 10))),
        )
        connector_tolerance = max(
            1.0e-12,
            float(getattr(tunnel_settings, 'smoothing_tolerance', 1.0e-4)),
        )
        connector_relaxation = float(
            np.clip(float(getattr(tunnel_settings, 'elliptic_relaxation', 0.4)), 0.01, 1.0)
        )

        blocks = []
        for spec in layout_plan.block_specs:
            block = cls._build_block_from_spec(
                spec,
                ring_settings=ring_settings,
                connector_iterations=connector_iterations,
                connector_tolerance=connector_tolerance,
                connector_relaxation=connector_relaxation,
            )
            block.hybrid_role = spec.role
            block.hybrid_element_index = spec.element_index
            block.hybrid_protected = bool(spec.protected)
            block.hybrid_metadata = dict(spec.metadata)
            blocks.append(block)

        return blocks

    @staticmethod
    def _build_block_from_spec(spec, *, ring_settings, connector_iterations,
                               connector_tolerance, connector_relaxation):
        if spec.role == 'metric_patch':
            block = BlockMesh(name=spec.name)
            block.transfinite(
                boundary=[
                    spec.lower_boundary.tolist(),
                    spec.upper_boundary.tolist(),
                    spec.left_boundary.tolist(),
                    spec.right_boundary.tolist(),
                ]
            )

            x_grid, y_grid = ExperimentalOGridGenerator._ulines_to_grid(
                block.getULines()
            )
            x_grid, y_grid = ExperimentalOGridGenerator._refine_block(
                x_grid,
                y_grid,
                ring_settings,
            )
            block.setUlines(
                ExperimentalOGridGenerator._grid_to_ulines(x_grid, y_grid)
            )
            return block

        if spec.role == 'metric_c_grid':
            contour_points = np.asarray(
                spec.metadata.get('contour_points', spec.lower_boundary),
                dtype=float,
            )
            settings = ExperimentalCGridSettings(
                name=spec.name,
                surface_points=max(0, len(contour_points)),
                normal_divisions=max(
                    4,
                    int(spec.metadata.get(
                        'normal_divisions',
                        ring_settings.normal_divisions,
                    )),
                ),
                first_layer_thickness=max(
                    1.0e-12,
                    float(spec.metadata.get(
                        'first_layer_thickness',
                        ring_settings.first_layer_thickness,
                    )),
                ),
                wake_points=max(
                    4,
                    int(spec.metadata.get(
                        'wake_point_count',
                        ring_settings.normal_divisions,
                    )),
                ),
                initial_smoothing_iterations=max(
                    20,
                    4 * max(1, connector_iterations),
                ),
                final_smoothing_iterations=max(6, connector_iterations // 2),
                local_te_smoothing_iterations=max(4, connector_iterations // 3),
                smoothing_tolerance=connector_tolerance,
                relaxation=connector_relaxation,
            )
            generator = ExperimentalCGridGenerator()
            return generator.build_block(
                (contour_points[:, 0], contour_points[:, 1]),
                radius=float(spec.metadata['tunnel_height']),
                wake_length=float(spec.metadata['wake_length']),
                settings=settings,
            )

        if spec.role == 'element_ring':
            return ExperimentalOGridGenerator._build_block(
                spec.lower_boundary,
                spec.upper_boundary,
                settings=ring_settings,
                name=spec.name,
            )

        block = BlockMesh(name=spec.name)
        block.transfinite(
            boundary=[
                spec.lower_boundary.tolist(),
                spec.upper_boundary.tolist(),
                spec.left_boundary.tolist(),
                spec.right_boundary.tolist(),
            ]
        )

        if connector_iterations > 0:
            smoother = SmootherFactory.create_smoother('elliptic')
            smoother.smooth(
                block,
                iterations=connector_iterations,
                tolerance=connector_tolerance,
                relaxation=connector_relaxation,
            )
        return block

    @staticmethod
    def _eligible_blocks(blocks, *, protect_near_wall: bool):
        if not protect_near_wall:
            return list(blocks)
        return [
            block for block in blocks
            if not bool(getattr(block, 'hybrid_protected', False))
        ]

    def apply_stage2(self, blocks, settings: HybridStage2Settings, *,
                     protect_near_wall: bool = True):
        eligible_blocks = self._eligible_blocks(
            blocks,
            protect_near_wall=protect_near_wall,
        )
        metadata = {
            'enabled': bool(settings.enabled),
            'monitor_kind': settings.monitor_kind,
            'sweeps': int(settings.sweeps),
            'redistribute_u': bool(settings.redistribute_u),
            'redistribute_v': bool(settings.redistribute_v),
            'protect_near_wall': bool(protect_near_wall),
            'blocks_processed': 0,
            'blocks_skipped': len(blocks) - len(eligible_blocks),
            'applied': False,
        }

        if not settings.enabled or settings.sweeps <= 0:
            return metadata

        metadata['applied'] = True
        processed = 0
        for block in eligible_blocks:
            if self._redistribute_block(block, settings):
                processed += 1

        metadata['blocks_processed'] = processed
        return metadata

    def _redistribute_block(self, block, settings: HybridStage2Settings) -> bool:
        ulines = block.getULines()
        if not ulines or len(ulines) < 3 or len(ulines[0]) < 3:
            return False

        redistributed = False
        for _ in range(settings.sweeps):
            if settings.redistribute_u:
                bottom_sizes = _point_sizes(block.getULines()[0])
                top_sizes = _point_sizes(block.getULines()[-1])
                denominator = max(1, len(block.getULines()) - 1)
                for line_index in range(1, len(block.getULines()) - 1):
                    blend = float(line_index) / float(denominator)
                    point_sizes = (
                        (1.0 - blend) * bottom_sizes +
                        blend * top_sizes
                    )
                    block.redistributeLine(
                        direction='u',
                        number=line_index,
                        metric=LineMetricField.from_isotropic_sizes(point_sizes),
                    )
                    redistributed = True

            if settings.redistribute_v:
                vlines = block.getVLines()
                left_sizes = _point_sizes(vlines[0])
                right_sizes = _point_sizes(vlines[-1])
                denominator = max(1, len(vlines) - 1)
                for line_index in range(1, len(vlines) - 1):
                    blend = float(line_index) / float(denominator)
                    point_sizes = (
                        (1.0 - blend) * left_sizes +
                        blend * right_sizes
                    )
                    block.redistributeLine(
                        direction='v',
                        number=line_index,
                        metric=LineMetricField.from_isotropic_sizes(point_sizes),
                    )
                    redistributed = True

        return redistributed

    @classmethod
    def apply_stage1(cls, blocks, settings: HybridStage1Settings, *,
                     protect_near_wall: bool = True):
        eligible_blocks = cls._eligible_blocks(
            blocks,
            protect_near_wall=protect_near_wall,
        )
        metadata = {
            'enabled': bool(settings.enabled),
            'algorithm': settings.algorithm,
            'iterations': int(settings.iterations),
            'tolerance': float(settings.tolerance),
            'protect_near_wall': bool(protect_near_wall),
            'blocks_processed': 0,
            'blocks_skipped': len(blocks) - len(eligible_blocks),
            'applied': False,
        }

        if (
                not settings.enabled or
                settings.algorithm == 'none' or
                settings.iterations <= 0):
            return metadata

        metadata['applied'] = True
        smoother = SmootherFactory.create_smoother(settings.algorithm)
        for block in eligible_blocks:
            smoother.smooth(
                block,
                iterations=settings.iterations,
                tolerance=settings.tolerance,
                relaxation=settings.relaxation,
            )

        metadata['blocks_processed'] = len(eligible_blocks)
        return metadata
