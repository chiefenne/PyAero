from __future__ import annotations

from dataclasses import dataclass, field

import Camber
import ContourAnalysis as ca
from CSTAirfoil import METHOD_CST_MODIFIED
import FileOperations
import MetricTriangulation
import Mesh as MeshModel
import Meshing
import SplineRefine
import TrailingEdge
from Utils import get_main_window

import logging
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SplineRefineSettings:
    tolerance: float
    points: int
    ref_te: int
    ref_te_n: int
    ref_te_ratio: float
    method: str = METHOD_CST_MODIFIED
    cst_order: int = 8


@dataclass(slots=True)
class TrailingEdgeSettings:
    upper_blend: float
    lower_blend: float
    upper_exponent: float
    lower_exponent: float
    thickness: float


@dataclass(slots=True)
class MeshExportSettings:
    boundary_definitions: dict[str, str] = field(default_factory=dict)
    formats: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.boundary_definitions = (
            MeshModel.BoundaryDefinitions.from_mapping(
                self.boundary_definitions
            ).as_dict()
        )

        normalized_formats = []
        seen_formats = set()
        for mesh_format in self.formats:
            normalized = MeshModel.MeshExportRegistry.normalize_format(
                mesh_format
            )
            if normalized in seen_formats:
                continue
            normalized_formats.append(normalized)
            seen_formats.add(normalized)
        self.formats = normalized_formats


@dataclass(slots=True)
class MetricTestSettings:
    example: str
    width: float
    height: float
    hole_radius: float
    hole_spacing: float
    outer_resolution: int
    hole_resolution: int
    interior_x: int
    interior_y: int
    airfoil_path: str | None = None

    def to_triangulation_settings(self):
        return MetricTriangulation.MetricTriangulationSettings(
            example=self.example,
            width=self.width,
            height=self.height,
            hole_radius=self.hole_radius,
            hole_spacing=self.hole_spacing,
            outer_resolution=self.outer_resolution,
            hole_resolution=self.hole_resolution,
            interior_x=self.interior_x,
            interior_y=self.interior_y,
            airfoil_path=self.airfoil_path,
        )


class WorkflowService:
    def __init__(self, mainwindow=None):
        self.mw = mainwindow or get_main_window()

    def require_airfoil(self, require_spline: bool = False):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            raise ValueError('No airfoil loaded.')

        if require_spline and not airfoil.has_spline:
            raise ValueError('Please prepare the contour first.')

        return airfoil

    def spline_and_refine(self, settings: SplineRefineSettings):
        airfoil = self.require_airfoil()
        airfoil.has_TE = False

        refine = SplineRefine.SplineRefine()
        refine.doSplineRefine(
            tolerance=settings.tolerance,
            points=settings.points,
            ref_te=settings.ref_te,
            ref_te_n=settings.ref_te_n,
            ref_te_ratio=settings.ref_te_ratio,
            method=settings.method,
            cst_order=settings.cst_order,
        )
        return airfoil, refine

    def add_trailing_edge(self, settings: TrailingEdgeSettings):
        airfoil = self.require_airfoil(require_spline=True)
        airfoil.has_TE = True

        trailing = TrailingEdge.TrailingEdge()
        trailing.trailingEdge(
            blend=settings.upper_blend,
            ex=settings.upper_exponent,
            thickness=settings.thickness,
            side='both',
            lower_blend=settings.lower_blend,
            lower_exponent=settings.lower_exponent,
        )
        refine = SplineRefine.SplineRefine()
        rebuilt = refine.rebuildSplineData(airfoil.spline_data.coordinates)
        if rebuilt is not None:
            airfoil.spline_data = rebuilt
        return airfoil, refine

    def generate_mesh(self, settings):
        airfoil = self.require_airfoil(require_spline=True)

        wind_tunnel = Meshing.Windtunnel()
        completed = wind_tunnel.makeMesh(settings=settings, airfoil=airfoil)
        if not completed:
            return None
        return wind_tunnel

    def generate_hybrid_stage4(self, settings):
        airfoil = self.require_airfoil(require_spline=True)

        wind_tunnel = Meshing.Windtunnel()
        completed = wind_tunnel.makeHybridStage4Mesh(
            settings=settings,
            airfoil=airfoil,
        )
        if not completed:
            return None
        return wind_tunnel

    def apply_hybrid_stage2(self, wind_tunnel, settings):
        if wind_tunnel is None:
            raise ValueError('Please run Stage 4 first.')

        airfoil = self.require_airfoil(require_spline=True)
        completed = wind_tunnel.applyHybridStage2(
            settings=settings,
            airfoil=airfoil,
        )
        if not completed:
            return None
        return wind_tunnel

    def apply_hybrid_stage1(self, wind_tunnel, settings):
        if wind_tunnel is None:
            raise ValueError('Please run Stage 4 first.')

        airfoil = self.require_airfoil(require_spline=True)
        completed = wind_tunnel.applyHybridStage1(
            settings=settings,
            airfoil=airfoil,
        )
        if not completed:
            return None
        return wind_tunnel

    def export_mesh(self, wind_tunnel, filename: str,
                    settings: MeshExportSettings):
        if wind_tunnel is None:
            raise ValueError('Please generate a mesh first.')
        if not settings.formats:
            raise ValueError('Please select at least one export format.')

        wind_tunnel.setBoundaryDefinitions(settings.boundary_definitions)
        exported_files = []
        for mesh_format in settings.formats:
            output_name = (
                filename + MeshModel.MeshExportRegistry.extension_for(mesh_format)
            )
            try:
                wind_tunnel.export_mesh(mesh_format, name=output_name)
            except (OSError, ValueError) as error:
                FileOperations.report_io_error(
                    'export mesh',
                    output_name,
                    error,
                    mainwindow=self.mw,
                )
                return exported_files
            exported_files.append(output_name)
        return exported_files

    def export_contour(self, filename: str):
        airfoil = self.require_airfoil()
        return FileOperations.write_contour(
            airfoil,
            filename,
            prefer_spline=True,
            mainwindow=self.mw,
        )

    def export_camber(self, filename: str):
        airfoil = self.require_airfoil(require_spline=True)
        return FileOperations.write_camber(
            airfoil,
            filename,
            mainwindow=self.mw,
        )

    def export_cst(self, filename: str):
        airfoil = self.require_airfoil(require_spline=True)
        return FileOperations.write_cst_parameters(
            airfoil,
            filename,
            mainwindow=self.mw,
        )

    def generate_metric_test(self, settings: MetricTestSettings):
        return MetricTriangulation.MetricTriangulator.generate(
            settings.to_triangulation_settings()
        )


class ToolboxWorkflowController:
    def __init__(self, toolbox, mainwindow=None):
        self.toolbox = toolbox
        self.mw = mainwindow or get_main_window()
        self.service = WorkflowService(self.mw)

    def spline_and_refine(self, settings: SplineRefineSettings):
        try:
            airfoil, refine = self.service.spline_and_refine(settings)
        except ValueError as error:
            self._show_message(str(error))
            return None

        airfoil.makeContourSpline()
        rc, le_id = self._update_derived_contour_geometry(airfoil, refine=refine)
        self.invalidate_contour_analysis(airfoil)
        self.invalidate_mesh_state(airfoil)

        logger.info('Leading edge radius: {:11.8f}'.format(rc))
        logger.info('Leading edge circle tangent at point: {}'.format(le_id))

        self.toolbox.trailingButton.setEnabled(True)
        self.toolbox.exportContourButton.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return airfoil

    def add_trailing_edge(self, settings: TrailingEdgeSettings):
        try:
            airfoil, refine = self.service.add_trailing_edge(settings)
        except ValueError as error:
            self._show_message(str(error))
            return None
        self.refresh_modified_contour_scene()
        self._update_derived_contour_geometry(airfoil, refine=refine)
        self.invalidate_contour_analysis(airfoil)
        self.invalidate_mesh_state(airfoil)
        self.toolbox.refreshWorkflowState()
        return airfoil

    def refresh_modified_contour_scene(self):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            return None

        airfoil.makeContourSpline()
        airfoil.setSplineFillEnabled(self.toolbox.splineFillEnabled())
        airfoil.polygonMarkersGroup.setZValue(120)
        if airfoil.splineMarkersGroup is not None:
            airfoil.splineMarkersGroup.setZValue(140)

        if airfoil.chord is not None:
            airfoil.chord.setZValue(30)
        if airfoil.camberline is not None:
            airfoil.camberline.setZValue(35)
        if airfoil.camber_circles is not None:
            airfoil.camber_circles.setZValue(34)

        self.mw.view.adjustMarkerSize()
        return airfoil

    def invalidate_contour_analysis(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is not None:
            airfoil.curvature_data = None
        self.toolbox.cgb.setEnabled(False)

    def invalidate_mesh_state(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is not None:
            for attribute_name in ('mesh', 'mesh_blocks', 'mesh_quality'):
                item = getattr(airfoil, attribute_name, None)
                self._remove_scene_item(item)
                setattr(airfoil, attribute_name, None)
            airfoil.mesh_model = None
            airfoil.domain_model = None

        self.toolbox.wind_tunnel = None
        self.toolbox.box_meshexport.setEnabled(False)
        self._set_checkbox_state('mesh_checkbox', checked=False, enabled=False)
        self._set_checkbox_state(
            'mesh_blocks_checkbox',
            checked=False,
            enabled=False,
        )
        self.toolbox.refreshWorkflowState()

    def generate_mesh(self, settings):
        try:
            wind_tunnel = self.service.generate_mesh(settings)
        except ValueError as error:
            self._show_message(str(error))
            return None
        if wind_tunnel is None:
            return None

        self.toolbox.box_meshexport.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return wind_tunnel

    def generate_hybrid_stage4(self, settings):
        try:
            wind_tunnel = self.service.generate_hybrid_stage4(settings)
        except ValueError as error:
            self._show_message(str(error))
            return None
        if wind_tunnel is None:
            return None

        self.toolbox.box_meshexport.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return wind_tunnel

    def apply_hybrid_stage2(self, wind_tunnel, settings):
        try:
            updated = self.service.apply_hybrid_stage2(wind_tunnel, settings)
        except ValueError as error:
            self._show_message(str(error))
            return None
        if updated is None:
            return None

        self.toolbox.box_meshexport.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return updated

    def apply_hybrid_stage1(self, wind_tunnel, settings):
        try:
            updated = self.service.apply_hybrid_stage1(wind_tunnel, settings)
        except ValueError as error:
            self._show_message(str(error))
            return None
        if updated is None:
            return None

        self.toolbox.box_meshexport.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return updated

    def prepare_contour_analysis(self):
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        self.mw.mainArea.tabs.setCurrentIndex(1)
        self.toolbox.setCurrentIndex(self.toolbox.tb3)
        self.toolbox.cgb.setEnabled(True)
        self.mw.contourview.analyze()
        return airfoil

    def refresh_camber_geometry(self, airfoil=None):
        airfoil = airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is None or not getattr(airfoil, 'has_spline', False):
            return None
        self._update_derived_contour_geometry(airfoil)
        return airfoil

    def draw_contour_analysis(self, quantity: str):
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        if not hasattr(airfoil, 'curvature_data'):
            return None
        if getattr(airfoil, 'curvature_data', None) is None:
            return None

        self.mw.contourview.drawContour(quantity)
        return quantity

    def export_mesh(self, wind_tunnel, filename: str,
                    settings: MeshExportSettings):
        try:
            return self.service.export_mesh(wind_tunnel, filename, settings)
        except ValueError as error:
            self._show_message(str(error))
            return []

    def export_contour(self, filename: str):
        try:
            return self.service.export_contour(filename)
        except ValueError as error:
            self._show_message(str(error))
            return None

    def export_camber(self, filename: str):
        try:
            return self.service.export_camber(filename)
        except ValueError as error:
            self._show_message(str(error))
            return None

    def export_cst(self, filename: str):
        try:
            return self.service.export_cst(filename)
        except ValueError as error:
            self._show_message(str(error))
            return None

    def generate_metric_test(self, settings: MetricTestSettings):
        try:
            return self.service.generate_metric_test(settings)
        except ValueError as error:
            self._show_message(str(error))
            return None

    def _require_airfoil(self, require_spline: bool = False):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            self._show_message('No airfoil loaded.')
            return None

        if require_spline and not airfoil.has_spline:
            self._show_message('Please prepare the contour first.')
            return None

        return airfoil

    def _show_message(self, message: str):
        self.mw.slots.messageBox(message)

    def _update_derived_contour_geometry(self, airfoil, refine=None):
        spline_data = airfoil.spline_data
        curvature_data = ca.ContourAnalysis.getCurvature(spline_data)
        rc, xc, yc, xle, yle, le_id = ca.ContourAnalysis.getLeRadius(
            spline_data,
            curvature_data,
        )

        refine = refine or SplineRefine.SplineRefine()
        refine.makeLeCircle(rc, xc, yc, xle, yle)

        camber_builder = Camber.CamberBuilder()
        camber_data = camber_builder.build(
            spline_data,
            rc,
            xc,
            yc,
            xle,
            yle,
        )
        airfoil.camber_data = camber_data
        airfoil.drawCamber(camber_data)
        airfoil.drawCamberCircles(camber_data)
        airfoil.drawCamberMaximumMarkers(camber_data)
        return rc, le_id

    def _remove_scene_item(self, item):
        if item is None:
            return
        scene = item.scene()
        if scene is not None:
            scene.removeItem(item)

    def _set_checkbox_state(self, name, checked=None, enabled=None):
        checkbox = getattr(self.mw.mainArea, name, None)
        if checkbox is None:
            return
        if checked is not None:
            checkbox.setChecked(checked)
        if enabled is not None:
            checkbox.setEnabled(enabled)
