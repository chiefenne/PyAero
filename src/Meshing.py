import os
from dataclasses import dataclass

import numpy as np

from PySide6 import QtCore, QtWidgets

from BlockMesh import BlockMesh as LegacyBlockMesh
from BlockMesh import Smooth as LegacySmooth
import Domain
import Mesh as MeshModel
import MeshGraphics
import MeshBuilders
import Connect
from Smoother import SmootherFactory
from Utils import get_main_window
from MathUtils import VectorUtils
import logging
logger = logging.getLogger(__name__)

OUTPUT = os.path.join(os.path.dirname(__file__), 'output')


@dataclass(slots=True)
class WindtunnelMeshSettings:
    airfoil: MeshBuilders.AirfoilBlockSettings
    trailing_edge: MeshBuilders.TrailingEdgeBlockSettings
    tunnel: MeshBuilders.TunnelBlockSettings
    wake: MeshBuilders.WakeBlockSettings


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
        self._scene_renderer = None
        self.topology = None
        self.mesh_model = None
        self.domain_model = None
        self.quality = None
        self.boundary_definitions = MeshModel.BoundaryDefinitions()

        # MainWindow instance
        self.mw = get_main_window()

    def getBlockBuilder(self):
        if self._block_builder is None:
            self._block_builder = MeshBuilders.LegacyBlockMeshBuilder(
                block_mesh_cls=LegacyBlockMesh,
                create_smoother=SmootherFactory.create_smoother,
            )
        return self._block_builder

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
                   smoothing_tolerance=1e-3):
        settings = MeshBuilders.TunnelBlockSettings(
            name=name,
            tunnel_height=tunnel_height,
            divisions_height=divisions_height,
            height_growth=ratio_height,
            distribution=dist,
            smoothing_algorithm=smoothing_algorithm,
            smoothing_iterations=smoothing_iterations,
            smoothing_tolerance=smoothing_tolerance,
        )
        block = self.getBlockBuilder().build_tunnel_block(
            self.block_airfoil,
            self.block_te,
            settings,
        )
        self.tunnel_height = settings.tunnel_height
        return self.registerBlock('block_tunnel', block)

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

    def makeMesh(self, settings: WindtunnelMeshSettings, airfoil=None):

        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            raise ValueError('No airfoil loaded.')
        if not airfoil.has_spline:
            raise ValueError('Splining needs to be done first.')

        self.blocks = []
        self.block_airfoil = None
        self.block_te = None
        self.block_tunnel = None
        self.block_tunnel_wake = None
        self.tunnel_height = None

        contour = airfoil.spline_data[0]

        # delete blocks outline if existing
        # because a new one will be generated
        if getattr(airfoil, 'mesh_blocks', None) is not None and \
                hasattr(self.mw, 'scene'):
            self.mw.scene.removeItem(airfoil.mesh_blocks)
            airfoil.mesh_blocks = None

        progdialog = QtWidgets.QProgressDialog(
            "Meshing in progress", "Cancel", 0, 100, self.mw)
        progdialog.setFixedWidth(300)
        progdialog.setMinimumDuration(0)
        progdialog.setWindowTitle('Generating the CFD mesh')
        progdialog.setWindowModality(QtCore.Qt.WindowModal)
        progdialog.setCancelButtonText('Abort meshing ...')
        progdialog.show()

        progdialog.setValue(10)
        # progdialog.setLabelText('making blocks')

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

        # connect mesh blocks
        connect = Connect.Connect(progdialog)
        vertices, connectivity, progdialog = \
            connect.connectAllBlocks(self.blocks)

        self.setMesh(vertices, connectivity)
        self.publishMeshArtifacts(airfoil=airfoil)

        logger.info('Mesh around {} created'.
                    format(airfoil.name))
        logger.info('Mesh has {} vertices and {} elements'.
                    format(len(vertices), len(connectivity)))

        self.drawMesh(airfoil)
        self.drawBlockOutline(airfoil)

        # mesh quality
        # quality = self.MeshQuality(crit='k2inf')
        # self.drawMeshQuality(quality)

        progdialog.setValue(100)
        return True
    
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
        return renderer.render_block_outline(airfoil, self.blocks)

    def MeshQuality(self, crit='k2inf'):
        vertices, connectivity = self.mesh
        vertices = np.asarray(vertices, dtype=float)
        connectivity = np.asarray(connectivity, dtype=int)

        if crit == 'k2inf':
            v12 = vertices[connectivity[:, 1]] - vertices[connectivity[:, 0]]
            v23 = vertices[connectivity[:, 2]] - vertices[connectivity[:, 1]]
            v34 = vertices[connectivity[:, 3]] - vertices[connectivity[:, 2]]
            v41 = vertices[connectivity[:, 0]] - vertices[connectivity[:, 3]]
            a = np.linalg.norm(v12)
            b = np.linalg.norm(v23)
            c = np.linalg.norm(v34)
            d = np.linalg.norm(v41)
            p = 0.5 * (a + b + c + d)
            q2 = np.sqrt(a**2 + b**2 + c**2 + d**2)

            alpha = VectorUtils.angle_between(v12, -v41)
            beta =  VectorUtils.angle_between(v23, -v12)
            gamma = VectorUtils.angle_between(v34, -v23)
            delta = VectorUtils.angle_between(v41, -v12)
            theta = 0.5 * (alpha + gamma)

            # quad area using Bretschneider’s formula
            A = np.sqrt((p -a)*(p-b)*(p-c)*(p-d) - a*b*c*d*np.cos(theta))

            ka = (a**2 + d**2) / (a*d*np.sin(alpha))
            kb = (a**2 + b**2) / (a*b*np.sin(beta))
            kc = (b**2 + c**2) / (b*c*np.sin(gamma))
            kd = (c**2 + d**2) / (c*d*np.sin(delta))
            k = np.stack((ka, kb, kc, kd))

            quality = np.max(k, axis=0) / 2.

        self.quality = quality
        if self.mesh_model is not None and self.mesh_model.data is not None:
            self.mesh_model.data.quality = quality
        return self.quality


class BlockMesh(LegacyBlockMesh):
    """Backward-compatible export shim for legacy callers."""

    @staticmethod
    def writeFLMA(wind_tunnel, name='', depth=0.3):
        return wind_tunnel.export_mesh('flma', name=name, depth=depth)

    @staticmethod
    def writeSU2_nolib(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('su2', name=name)

    @staticmethod
    def writeVTK_nolib(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('vtu', name=name)

    @staticmethod
    def writeGMSH_nolib(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('gmsh', name=name)

    @staticmethod
    def writeSU2(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('su2', name=name)

    @staticmethod
    def writeVTK(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('vtu', name=name)

    @staticmethod
    def writeGMSH(wind_tunnel, name=''):
        return wind_tunnel.export_mesh('gmsh', name=name)


Smooth = LegacySmooth
