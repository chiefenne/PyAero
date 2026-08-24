import os
from dataclasses import dataclass, field, replace

import numpy as np

from PySide6 import QtCore, QtWidgets

from BlockMesh import BlockMesh as LegacyBlockMesh
from BlockMesh import Smooth as LegacySmooth
import Domain
import Mesh as MeshModel
import MeshGraphics
import MeshBuilders
import Connect
from Elliptic import BoundaryGuide, SlidingBoundary, EllipticSolver
from ExperimentalCGrid import (
    ExperimentalCGridGenerator,
    ExperimentalCGridSettings,
)
from ExperimentalOGrid import (
    ExperimentalOGridGenerator,
    ExperimentalOGridSettings,
)
from QuadPipeline import (
    HybridQuadPipeline,
    HybridQuadPipelineSettings,
    HybridStage1Settings,
    HybridStage2Settings,
)
from QuadQuality import QuadQualityEvaluator
from Smoother import SmootherFactory
from StructuredCore import StructuredMeshSettings, TunnelBoundaryControl
from StructuredEngine import StructuredEngine
from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)

OUTPUT = os.path.join(os.path.dirname(__file__), 'output')


def _default_metric_pipeline_settings():
    return HybridQuadPipelineSettings(
        layout_strategy='metric_c_grid',
        protect_near_wall=False,
        stage2=HybridStage2Settings(enabled=False, sweeps=0),
        stage1=HybridStage1Settings(
            enabled=False,
            algorithm='none',
            iterations=0,
        ),
    )


@dataclass(slots=True)
class WindtunnelMeshSettings:
    airfoil: MeshBuilders.AirfoilBlockSettings
    trailing_edge: MeshBuilders.TrailingEdgeBlockSettings
    tunnel: MeshBuilders.TunnelBlockSettings
    wake: MeshBuilders.WakeBlockSettings
    engine: str = 'metric_based'
    metric_based: HybridQuadPipelineSettings = field(
        default_factory=_default_metric_pipeline_settings
    )
    hybrid: HybridQuadPipelineSettings = field(
        default_factory=HybridQuadPipelineSettings
    )
    hybrid_staged: HybridQuadPipelineSettings = field(
        default_factory=HybridQuadPipelineSettings
    )
    experimental: ExperimentalCGridSettings = field(
        default_factory=ExperimentalCGridSettings
    )
    experimental_o: ExperimentalOGridSettings = field(
        default_factory=ExperimentalOGridSettings
    )
    structured: StructuredMeshSettings = field(
        default_factory=StructuredMeshSettings
    )


class NullProgressDialog:
    def setFixedWidth(self, _width):
        return None

    def setMinimumDuration(self, _duration):
        return None

    def setWindowTitle(self, _title):
        return None

    def setWindowModality(self, _modality):
        return None

    def setCancelButtonText(self, _text):
        return None

    def show(self):
        return None

    def setValue(self, _value):
        return None

    def wasCanceled(self):
        return False


class Windtunnel:
    """
    The Windtunnel class is responsible for generating a computational fluid dynamics (CFD) mesh 
    around an airfoil within a wind tunnel. It includes methods for creating different parts of 
    the mesh, such as the airfoil mesh, trailing edge mesh, tunnel mesh, and tunnel wake mesh. 
    Additionally, it provides functionality for mesh quality assessment, drawing the mesh, and 
    exporting the mesh in various formats.
    """

    def __init__(self):

        # contains list of BlockMesh objects
        self.blocks = []
        self.block_airfoil = None
        self.block_te = None
        self.block_tunnel = None
        self.block_tunnel_wake = None
        self.tunnel_height = None
        self._block_builder = None
        self._experimental_c_grid_generator = None
        self._experimental_o_grid_generator = None
        self._structured_engine = None
        self._hybrid_pipeline = None
        self._scene_renderer = None
        self.topology = None
        self.mesh_model = None
        self.domain_model = None
        self.quality = None
        self.quality_report = None
        self.layout_plan = None
        self.pipeline_metadata = {}
        self.hybrid_pipeline_settings = None
        self.hybrid_stage_state = {
            'stage4': False,
            'stage2': False,
            'stage1': False,
        }
        self.boundary_definitions = MeshModel.BoundaryDefinitions()
        self.mesh_engine = 'metric_based'

        # MainWindow instance
        self.mw = get_main_window()

    def getBlockBuilder(self):
        if self._block_builder is None:
            self._block_builder = MeshBuilders.LegacyBlockMeshBuilder(
                block_mesh_cls=LegacyBlockMesh,
                create_smoother=SmootherFactory.create_smoother,
            )
        return self._block_builder

    def getExperimentalCGridGenerator(self):
        if self._experimental_c_grid_generator is None:
            self._experimental_c_grid_generator = ExperimentalCGridGenerator()
        return self._experimental_c_grid_generator

    def getExperimentalOGridGenerator(self):
        if self._experimental_o_grid_generator is None:
            self._experimental_o_grid_generator = ExperimentalOGridGenerator()
        return self._experimental_o_grid_generator

    def getStructuredEngine(self):
        if self._structured_engine is None:
            self._structured_engine = StructuredEngine()
        return self._structured_engine

    def getHybridPipeline(self):
        if self._hybrid_pipeline is None:
            self._hybrid_pipeline = HybridQuadPipeline()
        return self._hybrid_pipeline

    def registerBlock(self, attribute_name, block):
        setattr(self, attribute_name, block)
        self.blocks.append(block)
        return block

    def getSceneRenderer(self):
        if not hasattr(self.mw, 'scene') or not hasattr(self.mw, 'mainArea'):
            return None
        if self._scene_renderer is None:
            self._scene_renderer = MeshGraphics.MeshSceneRenderer(self.mw)
        return self._scene_renderer

    def _resetHybridPipelineState(self):
        self.hybrid_pipeline_settings = None
        self.hybrid_stage_state = {
            'stage4': False,
            'stage2': False,
            'stage1': False,
        }

    def _createProgressDialog(self, label_text='Meshing in progress',
                              window_title='Generating the CFD mesh'):
        if isinstance(self.mw, QtWidgets.QWidget) and \
                QtWidgets.QApplication.instance() is not None:
            progdialog = QtWidgets.QProgressDialog(
                label_text,
                'Cancel',
                0,
                100,
                self.mw,
            )
            progdialog.setFixedWidth(300)
            progdialog.setMinimumDuration(0)
            progdialog.setWindowTitle(window_title)
            progdialog.setWindowModality(QtCore.Qt.WindowModal)
            progdialog.setCancelButtonText('Abort meshing ...')
            progdialog.show()
            return progdialog
        return NullProgressDialog()

    def buildMeshModel(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        name = airfoil.name if airfoil else 'wind_tunnel_mesh'
        if hasattr(self, 'mesh'):
            self.ensureTopology()
        return MeshModel.BlockStructuredMesh.from_windtunnel(
            self,
            name=name,
            boundary_conditions=self.getBoundaryDefinitions().as_dict(),
        )

    def setBoundaryDefinitions(self, boundary_definitions=None, **names):
        current = self.getBoundaryDefinitions().as_dict()
        if boundary_definitions is not None:
            current.update(
                MeshModel.BoundaryDefinitions.from_mapping(
                    boundary_definitions
                ).as_dict()
            )

        for key, value in names.items():
            if value is not None:
                current[key] = value

        self.boundary_definitions = MeshModel.BoundaryDefinitions.from_mapping(
            current
        )
        if self.mesh_model is not None:
            self.mesh_model.boundary_conditions = (
                self.boundary_definitions.as_dict()
            )
        return self.boundary_definitions

    def getBoundaryDefinitions(self):
        if isinstance(
            getattr(self, 'boundary_definitions', None),
            MeshModel.BoundaryDefinitions,
        ):
            return self.boundary_definitions
        self.boundary_definitions = MeshModel.BoundaryDefinitions()
        return self.boundary_definitions

    def export_mesh(self, mesh_format, name='', boundary_definitions=None,
                    **kwargs):
        definitions = self.getBoundaryDefinitions()
        if boundary_definitions is not None:
            definitions = self.setBoundaryDefinitions(boundary_definitions)

        if self.mesh_model is None:
            self.mesh_model = self.buildMeshModel(
                airfoil=getattr(self.mw, 'airfoil', None)
            )
        else:
            self.mesh_model.boundary_conditions = definitions.as_dict()

        MeshModel.MeshExportRegistry.export(
            self.mesh_model,
            mesh_format=mesh_format,
            name=name,
            boundary_definitions=definitions,
            **kwargs,
        )
        return name

    def buildDomainModel(self, airfoil=None, mesh_model=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        mesh_model = mesh_model or self.mesh_model or self.buildMeshModel(
            airfoil=airfoil
        )
        return Domain.DomainBuilder.from_mesh(
            mesh_model,
            airfoil=airfoil,
            name=f'{airfoil.name if airfoil else "wind_tunnel"}_domain',
            metadata={'source': self.__class__.__name__},
        )

    def setMesh(self, vertices, connectivity):
        self.mesh = vertices, connectivity
        self.topology = None
        self.mesh_model = None
        self.domain_model = None

    def rebuildTopology(self):
        vertices, connectivity = self.mesh
        self.topology = MeshModel.MeshTopology.from_mesh(vertices, connectivity)
        self.LCV = self.topology.cell_to_vertices
        self.LCE = self.topology.cell_to_edges
        self.edges = list(self.topology.edges)
        self.boundary_edges = list(self.topology.boundary_edges)
        self.boundary_tags = {
            tag: list(edges)
            for tag, edges in self.topology.boundary_tags.items()
        }

        if self.mesh_model is not None and self.mesh_model.data is not None:
            self.mesh_model.data.cell_to_vertices = self.LCV
            self.mesh_model.data.cell_to_edges = self.LCE
            self.mesh_model.data.boundary_tags = self.boundary_tags
            self.mesh_model.data.metadata['boundary_edges'] = (
                list(self.boundary_edges)
            )
        return self.topology

    def ensureTopology(self):
        if self.topology is None:
            return self.rebuildTopology()
        return self.topology

    def publishMeshArtifacts(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        self.rebuildTopology()
        self.mesh_model = self.buildMeshModel(airfoil=airfoil)
        self.domain_model = self.buildDomainModel(
            airfoil=airfoil,
            mesh_model=self.mesh_model,
        )
        if airfoil is not None:
            airfoil.mesh_model = self.mesh_model
            airfoil.domain_model = self.domain_model
        return self.mesh_model, self.domain_model

    def AirfoilMesh(self, name='', contour=None, divisions=15, ratio=3.0,
                    thickness=0.04):
        settings = MeshBuilders.AirfoilBlockSettings(
            name=name,
            divisions=divisions,
            growth=ratio,
            thickness=thickness,
        )
        block = self.getBlockBuilder().build_airfoil_block(contour, settings)
        return self.registerBlock('block_airfoil', block)

    def TrailingEdgeMesh(self, name='', te_divisions=3,
                         thickness=0.04, divisions=10, ratio=1.05):
        settings = MeshBuilders.TrailingEdgeBlockSettings(
            name=name,
            trailing_edge_divisions=te_divisions,
            thickness=thickness,
            divisions=divisions,
            growth=ratio,
        )
        block = self.getBlockBuilder().build_trailing_edge_block(
            self.block_airfoil,
            has_trailing_edge=getattr(self.mw.airfoil, 'has_TE', False),
            settings=settings,
        )
        return self.registerBlock('block_te', block)

    def TunnelMesh(self, name='', tunnel_height=2.0, divisions_height=100,
                   ratio_height=10.0, dist='symmetric',
                   smoothing_algorithm='simple',
                   smoothing_iterations=10,
                   smoothing_tolerance=1e-3,
                   outer_boundary_slide=0.0,
                   elliptic_relaxation=0.2,
                   protected_guide_relaxation=0.25,
                   protected_guide_layers=5,
                   protected_guide_decay=0.8,
                   protected_guide_smoothing=3):
        settings = MeshBuilders.TunnelBlockSettings(
            name=name,
            tunnel_height=tunnel_height,
            divisions_height=divisions_height,
            height_growth=ratio_height,
            distribution=dist,
            smoothing_algorithm=smoothing_algorithm,
            smoothing_iterations=smoothing_iterations,
            smoothing_tolerance=smoothing_tolerance,
            outer_boundary_slide=outer_boundary_slide,
            elliptic_relaxation=elliptic_relaxation,
            protected_guide_relaxation=protected_guide_relaxation,
            protected_guide_layers=protected_guide_layers,
            protected_guide_decay=protected_guide_decay,
            protected_guide_smoothing=protected_guide_smoothing,
        )
        block = self.getBlockBuilder().build_tunnel_block(
            self.block_airfoil,
            self.block_te,
            settings,
        )
        if settings.smoothing_algorithm.strip().lower() == 'elliptic':
            block = self._smoothProtectedTunnelBlock(block, settings)
        self.tunnel_height = settings.tunnel_height
        return self.registerBlock('block_tunnel', block)

    @staticmethod
    def _concatenateInterfaceSegments(*segments):
        arrays = []
        for index, segment in enumerate(segments):
            coordinates = np.asarray(segment, dtype=float)
            if coordinates.ndim != 2 or coordinates.shape[1] != 2:
                raise ValueError('Expected interface segments with 2D coordinates.')
            if index < len(segments) - 1:
                coordinates = coordinates[:-1]
            if len(coordinates):
                arrays.append(coordinates)

        if not arrays:
            return np.empty((0, 2), dtype=float)
        return np.vstack(arrays)

    def _protectedTunnelBoundaryGuide(self):
        if self.block_airfoil is None or self.block_te is None:
            raise ValueError('Protected tunnel smoothing requires airfoil and trailing edge blocks.')

        airfoil_ulines = self.block_airfoil.getULines()
        trailing_edge_vlines = self.block_te.getVLines()

        if len(airfoil_ulines) < 2:
            raise ValueError('Airfoil block must contain at least two u-lines for protected tunnel smoothing.')
        if len(trailing_edge_vlines) < 3:
            raise ValueError('Trailing edge block must contain at least three v-lines for protected tunnel smoothing.')

        boundary_line = self._concatenateInterfaceSegments(
            trailing_edge_vlines[-1][::-1],
            airfoil_ulines[-1],
            trailing_edge_vlines[0],
        )
        adjacent_line = self._concatenateInterfaceSegments(
            trailing_edge_vlines[-2][::-1],
            airfoil_ulines[-2],
            trailing_edge_vlines[1],
        )

        if boundary_line.shape != adjacent_line.shape:
            raise ValueError(
                'Protected tunnel interface lines must have matching shapes.'
            )

        return boundary_line, boundary_line - adjacent_line

    @staticmethod
    def _smoothInterfaceProfile(values, passes):
        profile = np.asarray(values, dtype=float)
        passes = max(0, int(passes))
        if profile.ndim != 1 or profile.size < 3 or passes == 0:
            return np.array(profile, copy=True, dtype=float)

        smoothed = np.array(profile, copy=True, dtype=float)
        for _ in range(passes):
            updated = np.array(smoothed, copy=True, dtype=float)
            updated[1:-1] = (
                0.25 * smoothed[:-2] +
                0.50 * smoothed[1:-1] +
                0.25 * smoothed[2:]
            )
            smoothed = updated

        return smoothed

    def _protectedTunnelGuideProfile(self, tunnel_block, boundary_line, guide_vectors,
                                     settings):
        normals = EllipticSolver.curveNormals(boundary_line[:, 0], boundary_line[:, 1])
        normal_strength = np.sum(guide_vectors * normals, axis=1)
        normal_strength = self._smoothInterfaceProfile(
            normal_strength,
            settings.protected_guide_smoothing,
        )
        projected_vectors = normal_strength[:, None] * normals

        tunnel_ulines = tunnel_block.getULines()
        interior_layers = max(0, len(tunnel_ulines) - 2)
        layer_count = min(
            max(1, int(settings.protected_guide_layers)),
            interior_layers,
        )
        if layer_count <= 0:
            return projected_vectors, None

        first_offsets = np.asarray(tunnel_ulines[1], dtype=float) - boundary_line
        first_normal_strength = np.sum(first_offsets * normals, axis=1)
        fallback_scale = np.ones_like(first_normal_strength)

        scale_factors = []
        for layer_index in range(1, layer_count + 1):
            offsets = np.asarray(tunnel_ulines[layer_index], dtype=float) - boundary_line
            layer_normal_strength = np.sum(offsets * normals, axis=1)
            scale = np.divide(
                layer_normal_strength,
                first_normal_strength,
                out=np.array(fallback_scale * float(layer_index), copy=True),
                where=np.abs(first_normal_strength) > 1.0e-10,
            )
            scale = np.maximum(scale, 0.0)
            scale = self._smoothInterfaceProfile(
                scale,
                max(0, settings.protected_guide_smoothing - 1),
            )
            scale_factors.append(scale)

        return projected_vectors, np.asarray(scale_factors, dtype=float)

    def _smoothProtectedTunnelBlock(self, tunnel_block, settings):
        boundary_line, guide_vectors = self._protectedTunnelBoundaryGuide()
        tunnel_inner_line = np.asarray(tunnel_block.getULines()[0], dtype=float)

        if tunnel_inner_line.shape != boundary_line.shape:
            raise ValueError(
                'Tunnel block inner boundary does not match the protected interface layout.'
            )
        if not np.allclose(tunnel_inner_line, boundary_line):
            raise ValueError(
                'Tunnel block inner boundary coordinates do not match the protected interface coordinates.'
            )
        projected_vectors, layer_scale_factors = self._protectedTunnelGuideProfile(
            tunnel_block,
            boundary_line,
            guide_vectors,
            settings,
        )

        boundary_guides = {
            'bottom': BoundaryGuide(
                target_vectors=projected_vectors,
                relaxation=settings.protected_guide_relaxation,
                layers=settings.protected_guide_layers,
                decay=settings.protected_guide_decay,
                layer_scale_factors=layer_scale_factors,
            ),
        }
        sliding_boundaries = None
        if settings.outer_boundary_slide > 0.0:
            outer_geometry = np.asarray(tunnel_block.getULines()[-1], dtype=float)
            sliding_boundaries = {
                'top': SlidingBoundary(
                    geometry=outer_geometry,
                    relaxation=float(np.clip(settings.outer_boundary_slide, 0.0, 1.0)),
                    control_origins=boundary_line,
                    control_directions=projected_vectors,
                    control_segment='c_arc',
                ),
            }

        smoother = SmootherFactory.create_smoother('elliptic')
        return smoother.smooth(
            tunnel_block,
            iterations=settings.smoothing_iterations,
            tolerance=settings.smoothing_tolerance,
            boundary_guides=boundary_guides,
            sliding_boundaries=sliding_boundaries,
            relaxation=settings.elliptic_relaxation,
        )

    def TunnelMeshWake(self, name='', tunnel_wake=2.0,
                       divisions=100, ratio=0.1, spread=0.4):
        settings = MeshBuilders.WakeBlockSettings(
            name=name,
            tunnel_wake=tunnel_wake,
            divisions=divisions,
            growth=ratio,
            spread=spread,
        )
        block = self.getBlockBuilder().build_wake_block(
            self.block_tunnel,
            self.block_te,
            tunnel_height=self.tunnel_height,
            settings=settings,
        )
        return self.registerBlock('block_tunnel_wake', block)

    def _finalizeMeshGeneration(self, airfoil, progdialog):
        connect = Connect.Connect(progdialog)
        vertices, connectivity = connect.connectAllBlocks(self.blocks)

        self.setMesh(vertices, connectivity)
        self.publishMeshArtifacts(airfoil=airfoil)

        logger.info('Mesh around {} created'.format(airfoil.name))
        logger.info('Mesh has {} vertices and {} elements'.format(
            len(vertices),
            len(connectivity),
        ))

        self.drawMesh(airfoil)
        self.drawBlockOutline(airfoil)

        progdialog.setValue(100)
        return True

    def _publishPipelineMetadata(self):
        if self.mesh_model is None or self.mesh_model.data is None:
            return

        metadata = self.mesh_model.data.metadata
        if self.layout_plan is not None:
            metadata['layout_plan'] = {
                'boundary_point_count': int(len(self.layout_plan.boundary_points)),
                'singularity_count': int(len(self.layout_plan.singularities)),
                'metadata': dict(self.layout_plan.metadata),
            }
        if self.pipeline_metadata:
            metadata['quad_pipeline'] = dict(self.pipeline_metadata)

    def _hybridStageRequirement(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            raise ValueError('No airfoil loaded.')
        if not airfoil.has_spline:
            raise ValueError('The contour needs to be prepared first.')
        if self.layout_plan is None or not self.blocks:
            raise ValueError('Please run Stage 4 first.')
        if self.mesh_engine != 'hybrid_staged':
            raise ValueError('Please run Stage 4 with the staged hybrid engine first.')
        return airfoil

    def _finalizeHybridPipelineStep(self, airfoil, progdialog, settings, *,
                                    stage2_metadata=None,
                                    stage1_metadata=None):
        self.pipeline_metadata = self.getHybridPipeline().build_metadata(
            self.layout_plan,
            settings,
            engine='hybrid_staged',
            stage2_metadata=stage2_metadata,
            stage1_metadata=stage1_metadata,
        )
        if not self._finalizeMeshGeneration(airfoil, progdialog):
            return False
        self.MeshQuality(crit='k2inf')
        self._publishPipelineMetadata()
        return True

    def _buildStandardBlocks(self, settings: WindtunnelMeshSettings, contour,
                             progdialog):
        self.AirfoilMesh(
            name=settings.airfoil.name,
            contour=contour,
            divisions=settings.airfoil.divisions,
            ratio=settings.airfoil.growth,
            thickness=settings.airfoil.thickness,
        )
        progdialog.setValue(20)

        if progdialog.wasCanceled():
            return False

        self.TrailingEdgeMesh(
            name=settings.trailing_edge.name,
            te_divisions=settings.trailing_edge.trailing_edge_divisions,
            thickness=settings.trailing_edge.thickness,
            divisions=settings.trailing_edge.divisions,
            ratio=settings.trailing_edge.growth,
        )
        progdialog.setValue(30)

        if progdialog.wasCanceled():
            return False

        self.TunnelMesh(
            name=settings.tunnel.name,
            tunnel_height=settings.tunnel.tunnel_height,
            divisions_height=settings.tunnel.divisions_height,
            ratio_height=settings.tunnel.height_growth,
            dist=settings.tunnel.distribution,
            smoothing_algorithm=settings.tunnel.smoothing_algorithm,
            smoothing_iterations=settings.tunnel.smoothing_iterations,
            smoothing_tolerance=settings.tunnel.smoothing_tolerance,
            outer_boundary_slide=settings.tunnel.outer_boundary_slide,
            elliptic_relaxation=settings.tunnel.elliptic_relaxation,
            protected_guide_relaxation=settings.tunnel.protected_guide_relaxation,
            protected_guide_layers=settings.tunnel.protected_guide_layers,
            protected_guide_decay=settings.tunnel.protected_guide_decay,
            protected_guide_smoothing=settings.tunnel.protected_guide_smoothing,
        )
        progdialog.setValue(50)

        if progdialog.wasCanceled():
            return False

        self.TunnelMeshWake(
            name=settings.wake.name,
            tunnel_wake=settings.wake.tunnel_wake,
            divisions=settings.wake.divisions,
            ratio=settings.wake.growth,
            spread=settings.wake.spread,
        )
        progdialog.setValue(70)

        if progdialog.wasCanceled():
            return False

        return True

    def _makeHybridMesh(self, settings: WindtunnelMeshSettings, airfoil,
                        progdialog):
        contour = airfoil.spline_data.coordinates
        result = self.getHybridPipeline().run(
            contour=contour,
            settings=settings.hybrid,
            airfoil_settings=settings.airfoil,
            tunnel_settings=settings.tunnel,
            wake_settings=settings.wake,
            trailing_edge_settings=settings.trailing_edge,
            contour_metadata=getattr(airfoil.spline_data, 'metadata', None),
        )
        self.blocks = result.blocks
        self.layout_plan = result.layout_plan
        self.pipeline_metadata = result.metadata
        progdialog.setValue(70)

        if progdialog.wasCanceled():
            return False

        if not self._finalizeMeshGeneration(airfoil, progdialog):
            return False

        self.MeshQuality(crit='k2inf')
        self._publishPipelineMetadata()
        return True

    def _makeMetricMesh(self, settings: WindtunnelMeshSettings, airfoil,
                        progdialog):
        contour = airfoil.spline_data.coordinates
        metric_settings = settings.metric_based
        result = self.getHybridPipeline().run_stage4(
            contour=contour,
            settings=metric_settings,
            airfoil_settings=settings.airfoil,
            tunnel_settings=settings.tunnel,
            wake_settings=settings.wake,
            trailing_edge_settings=settings.trailing_edge,
            contour_metadata=getattr(airfoil.spline_data, 'metadata', None),
            engine='metric_based',
        )
        self.blocks = result.blocks
        self.layout_plan = result.layout_plan
        self.pipeline_metadata = result.metadata
        self.hybrid_pipeline_settings = metric_settings
        self.hybrid_stage_state = {
            'stage4': True,
            'stage2': False,
            'stage1': False,
        }
        progdialog.setValue(70)

        if progdialog.wasCanceled():
            return False

        if not self._finalizeMeshGeneration(airfoil, progdialog):
            return False

        self.MeshQuality(crit='k2inf')
        self._publishPipelineMetadata()
        return True

    def _makeHybridStage4Mesh(self, settings: WindtunnelMeshSettings, airfoil,
                              progdialog):
        contour = airfoil.spline_data.coordinates
        staged_settings = settings.hybrid_staged
        result = self.getHybridPipeline().run_stage4(
            contour=contour,
            settings=staged_settings,
            airfoil_settings=settings.airfoil,
            tunnel_settings=settings.tunnel,
            wake_settings=settings.wake,
            trailing_edge_settings=settings.trailing_edge,
            contour_metadata=getattr(airfoil.spline_data, 'metadata', None),
            engine='hybrid_staged',
        )
        self.blocks = result.blocks
        self.layout_plan = result.layout_plan
        self.pipeline_metadata = result.metadata
        self.hybrid_pipeline_settings = staged_settings
        self.hybrid_stage_state = {
            'stage4': True,
            'stage2': False,
            'stage1': False,
        }
        progdialog.setValue(70)

        if progdialog.wasCanceled():
            return False

        if not self._finalizeMeshGeneration(airfoil, progdialog):
            return False

        self.MeshQuality(crit='k2inf')
        self._publishPipelineMetadata()
        return True

    def _makeExperimentalMesh(self, settings: WindtunnelMeshSettings,
                              airfoil, progdialog):
        if self.mesh_engine == 'experimental_o':
            generator = self.getExperimentalOGridGenerator()
            blocks = generator.build_blocks(
                contour=airfoil.spline_data.coordinates,
                radius=settings.tunnel.tunnel_height,
                wake_length=settings.wake.tunnel_wake,
                settings=settings.experimental_o,
                trailing_edge_settings=settings.trailing_edge,
            )
            for attribute_name, block in zip(
                    (
                        'block_experimental_o_grid_top',
                        'block_experimental_o_grid_left',
                        'block_experimental_o_grid_bottom',
                        'block_experimental_o_grid_right',
                    ),
                    blocks):
                self.registerBlock(attribute_name, block)
        else:
            generator = self.getExperimentalCGridGenerator()
            if getattr(airfoil, 'has_TE', False):
                blocks = generator.build_blunt_blocks(
                    contour=airfoil.spline_data.coordinates,
                    radius=settings.tunnel.tunnel_height,
                    wake_length=settings.wake.tunnel_wake,
                    settings=settings.experimental,
                    trailing_edge_settings=settings.trailing_edge,
                )
                for attribute_name, block in zip(
                        (
                            'block_experimental_te_patch',
                            'block_experimental_wake_bridge',
                            'block_experimental_c_grid',
                        ),
                        blocks):
                    self.registerBlock(attribute_name, block)
            else:
                block = generator.build_block(
                    contour=airfoil.spline_data.coordinates,
                    radius=settings.tunnel.tunnel_height,
                    wake_length=settings.wake.tunnel_wake,
                    settings=settings.experimental,
                )
                self.registerBlock('block_experimental_c_grid', block)
        self.tunnel_height = settings.tunnel.tunnel_height

        progdialog.setValue(70)
        if progdialog.wasCanceled():
            return False

        return self._finalizeMeshGeneration(airfoil, progdialog)

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

    def makeMesh(self, settings: WindtunnelMeshSettings, airfoil=None):

        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            raise ValueError('No airfoil loaded.')
        if not airfoil.has_spline:
            raise ValueError('The contour needs to be prepared first.')

        self.blocks = []
        self.block_airfoil = None
        self.block_te = None
        self.block_tunnel = None
        self.block_tunnel_wake = None
        self.tunnel_height = None
        self.layout_plan = None
        self.pipeline_metadata = {}
        self._resetHybridPipelineState()
        self.quality = None
        self.quality_report = None
        self.mesh_engine = str(settings.engine).strip().lower() or 'metric_based'
        if self.mesh_engine == 'experimental':
            self.mesh_engine = 'experimental_c'

        contour = airfoil.spline_data.coordinates

        # delete blocks outline if existing
        # because a new one will be generated
        if getattr(airfoil, 'mesh_blocks', None) is not None and \
                hasattr(self.mw, 'scene'):
            self.mw.scene.removeItem(airfoil.mesh_blocks)
            airfoil.mesh_blocks = None

        progdialog = self._createProgressDialog()

        progdialog.setValue(10)
        # progdialog.setLabelText('making blocks')

        if self.mesh_engine in ('experimental_c', 'experimental_o'):
            return self._makeExperimentalMesh(settings, airfoil, progdialog)
        if self.mesh_engine == 'structured':
            return self._makeStructuredMesh(settings, airfoil, progdialog)
        if self.mesh_engine == 'metric_based':
            return self._makeMetricMesh(settings, airfoil, progdialog)
        if self.mesh_engine == 'hybrid':
            return self._makeHybridMesh(settings, airfoil, progdialog)
        if self.mesh_engine == 'hybrid_staged':
            return self._makeHybridStage4Mesh(settings, airfoil, progdialog)

        if not self._buildStandardBlocks(settings, contour, progdialog):
            return False

        return self._finalizeMeshGeneration(airfoil, progdialog)

    def makeHybridStage4Mesh(self, settings: WindtunnelMeshSettings,
                             airfoil=None):
        return self.makeMesh(
            replace(settings, engine='hybrid_staged'),
            airfoil=airfoil,
        )

    def applyHybridStage2(self, settings: WindtunnelMeshSettings, airfoil=None):
        airfoil = self._hybridStageRequirement(airfoil=airfoil)
        staged_settings = settings.hybrid_staged
        self.hybrid_pipeline_settings = staged_settings
        self.mesh_engine = 'hybrid_staged'

        progdialog = self._createProgressDialog(
            label_text='Applying Stage 2 redistribution',
            window_title='Applying Hybrid Stage 2',
        )
        progdialog.setValue(20)

        pipeline = self.getHybridPipeline()
        stage2_metadata = pipeline.apply_stage2(
            self.blocks,
            staged_settings.stage2,
            protect_near_wall=staged_settings.protect_near_wall,
        )
        stage1_metadata = pipeline.default_stage1_metadata(
            staged_settings.stage1,
            protect_near_wall=staged_settings.protect_near_wall,
        )
        self.hybrid_stage_state = {
            'stage4': True,
            'stage2': bool(stage2_metadata.get('applied', False)),
            'stage1': False,
        }

        progdialog.setValue(70)
        if progdialog.wasCanceled():
            return False

        return self._finalizeHybridPipelineStep(
            airfoil,
            progdialog,
            staged_settings,
            stage2_metadata=stage2_metadata,
            stage1_metadata=stage1_metadata,
        )

    def applyHybridStage1(self, settings: WindtunnelMeshSettings, airfoil=None):
        airfoil = self._hybridStageRequirement(airfoil=airfoil)
        staged_settings = settings.hybrid_staged
        self.hybrid_pipeline_settings = staged_settings
        self.mesh_engine = 'hybrid_staged'

        progdialog = self._createProgressDialog(
            label_text='Applying Stage 1 cleanup',
            window_title='Applying Hybrid Stage 1',
        )
        progdialog.setValue(20)

        pipeline = self.getHybridPipeline()
        existing_stage2_metadata = dict(
            self.pipeline_metadata.get(
                'stage2',
                pipeline.default_stage2_metadata(
                    staged_settings.stage2,
                    protect_near_wall=staged_settings.protect_near_wall,
                ),
            )
        )
        stage1_metadata = pipeline.apply_stage1(
            self.blocks,
            staged_settings.stage1,
            protect_near_wall=staged_settings.protect_near_wall,
        )
        self.hybrid_stage_state = {
            'stage4': True,
            'stage2': bool(existing_stage2_metadata.get('applied', False)),
            'stage1': bool(stage1_metadata.get('applied', False)),
        }

        progdialog.setValue(70)
        if progdialog.wasCanceled():
            return False

        return self._finalizeHybridPipelineStep(
            airfoil,
            progdialog,
            staged_settings,
            stage2_metadata=existing_stage2_metadata,
            stage1_metadata=stage1_metadata,
        )
    
    def makeLCV(self):
        """Make cell to vertex connectivity for the mesh
           LCV is identical to connectivity
        """
        self.ensureTopology()
        return self.LCV

    def makeLVC(self):
        _, connectivity = self.mesh
        nodes = list(set([node for cell in connectivity for node in cell]))
        self.lvc = dict()
        for node in nodes:
            for cell in connectivity:
                if node in cell:
                    self.lvc.setdefault(node, []).append(cell.tolist())

    def makeLCE(self):
        """Make cell to edge connectivity for the mesh"""
        self.ensureTopology()
        return self.LCE

    def makeLCC(self):
        """Make cell to cell connectivity for the mesh"""
        pass

    def makeBoundaries(self):
        """A boundary edge is an edge that belongs only to one cell"""
        self.ensureTopology()
        return self.boundary_tags

    def drawMesh(self, airfoil):
        renderer = self.getSceneRenderer()
        if renderer is None:
            return None
        return renderer.render_mesh(airfoil, self.blocks)

    def drawMeshQuality(self, quality):
        renderer = self.getSceneRenderer()
        if renderer is None:
            return None
        vertices, connectivity = self.mesh
        airfoil = getattr(self.mw, 'airfoil', None)
        return renderer.render_mesh_quality(
            vertices,
            connectivity,
            quality,
            airfoil=airfoil,
        )

    def drawBlockOutline(self, airfoil):
        renderer = self.getSceneRenderer()
        if renderer is None:
            return None
        return renderer.render_block_outline(
            airfoil,
            self.blocks,
            layout_plan=self.layout_plan,
        )

    def MeshQuality(self, crit='k2inf'):
        vertices, connectivity = self.mesh
        self.quality_report = QuadQualityEvaluator.evaluate(
            vertices,
            connectivity,
            criterion=crit,
        )
        self.quality = self.quality_report.values
        if self.mesh_model is not None and self.mesh_model.data is not None:
            self.mesh_model.data.quality = self.quality
        return self.quality


class BlockMesh(LegacyBlockMesh):
    """Backward-compatible export shim for legacy callers."""

    @staticmethod
    def writeFLMA(wind_tunnel, name='', depth=0.3):
        return wind_tunnel.export_mesh('flma', name=name, depth=depth)

    @staticmethod
    def writeSU2(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('su2', name=name)

    @staticmethod
    def writeVTU(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('vtu', name=name)

    @staticmethod
    def writeGMSH(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('gmsh', name=name)

    writeVTK = writeVTU


Smooth = LegacySmooth
