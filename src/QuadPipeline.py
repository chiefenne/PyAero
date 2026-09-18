from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from BlockMesh import BlockMesh
from ExperimentalCGrid import (
    ExperimentalCGridGenerator,
    ExperimentalCGridSettings,
)
from QuadLayout import QuadLayoutGenerator


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
        self.layout_strategy = 'metric_c_grid'
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

    @staticmethod
    def build_layout_plan(contour, settings: HybridQuadPipelineSettings, *,
                          airfoil_settings=None, tunnel_settings=None,
                          wake_settings=None, trailing_edge_settings=None,
                          contour_metadata=None, boundary_loops=None):
        if contour is None and boundary_loops is None:
            raise ValueError('The pipeline requires contour data or explicit boundary loops.')

        contour_metadata = dict(contour_metadata or {})
        explicit_loops = (
            boundary_loops is not None or
            any(
                key in contour_metadata
                for key in ('boundary_loops', 'element_loops')
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
        connector_layers = int(getattr(tunnel_settings, 'divisions_height', 80))
        trailing_edge_divisions = int(
            getattr(trailing_edge_settings, 'trailing_edge_divisions', 3)
        )

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

    @classmethod
    def build_blocks_from_layout(cls, layout_plan, *, airfoil_settings=None,
                                 tunnel_settings=None):
        default_normal_divisions = max(4, int(getattr(airfoil_settings, 'divisions', 20)))
        default_first_layer_thickness = max(
            1.0e-12,
            float(getattr(airfoil_settings, 'thickness', 0.004)),
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

        return [
            cls._build_block_from_spec(
                spec,
                default_normal_divisions=default_normal_divisions,
                default_first_layer_thickness=default_first_layer_thickness,
                connector_iterations=connector_iterations,
                connector_tolerance=connector_tolerance,
                connector_relaxation=connector_relaxation,
            )
            for spec in layout_plan.block_specs
        ]

    @staticmethod
    def _build_block_from_spec(spec, *, default_normal_divisions,
                               default_first_layer_thickness,
                               connector_iterations, connector_tolerance,
                               connector_relaxation):
        contour_points = np.asarray(
            spec.metadata.get('contour_points', spec.lower_boundary),
            dtype=float,
        )
        settings = ExperimentalCGridSettings(
            name=spec.name,
            surface_points=max(0, len(contour_points)),
            normal_divisions=max(
                4,
                int(spec.metadata.get('normal_divisions', default_normal_divisions)),
            ),
            first_layer_thickness=max(
                1.0e-12,
                float(spec.metadata.get(
                    'first_layer_thickness',
                    default_first_layer_thickness,
                )),
            ),
            wake_points=max(
                4,
                int(spec.metadata.get('wake_point_count', default_normal_divisions)),
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
