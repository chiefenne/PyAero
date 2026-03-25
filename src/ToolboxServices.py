from __future__ import annotations

from dataclasses import dataclass, field

from PySide6 import QtCore, QtGui

import ContourAnalysis as ca
import Meshing
import PyAero
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


class ToolboxWorkflowController:
    mesh_export_extensions = {
        'flma': '.flma',
        'su2': '.su2',
        'gmsh': '.msh',
        'vtu': '.vtu',
    }

    def __init__(self, toolbox, mainwindow=None):
        self.toolbox = toolbox
        self.mw = mainwindow or get_main_window()

    def spline_and_refine(self, settings: SplineRefineSettings):
        airfoil = self._require_airfoil()
        if airfoil is None:
            return None

        airfoil.has_TE = False

        refine = SplineRefine.SplineRefine()
        refine.doSplineRefine(
            tolerance=settings.tolerance,
            points=settings.points,
            ref_te=settings.ref_te,
            ref_te_n=settings.ref_te_n,
            ref_te_ratio=settings.ref_te_ratio,
        )

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
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        airfoil.has_TE = True

        trailing = TrailingEdge.TrailingEdge()
        trailing.trailingEdge(
            blend=settings.upper_blend,
            ex=settings.upper_exponent,
            thickness=settings.thickness,
            side='upper',
        )
        trailing.trailingEdge(
            blend=settings.lower_blend,
            ex=settings.lower_exponent,
            thickness=settings.thickness,
            side='lower',
        )
        self.refresh_modified_contour_scene()
        self._update_derived_contour_geometry(airfoil)
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
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        wind_tunnel = Meshing.Windtunnel()
        try:
            completed = wind_tunnel.makeMesh(settings=settings, airfoil=airfoil)
        except ValueError as error:
            self._show_message(str(error))
            return None

        if not completed:
            return None

        self.toolbox.box_meshexport.setEnabled(True)
        self.toolbox.refreshWorkflowState()
        return wind_tunnel

    def prepare_contour_analysis(self):
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        self.mw.mainArea.tabs.setCurrentIndex(1)
        self.toolbox.setCurrentIndex(self.toolbox.tb3)
        self.toolbox.cgb.setEnabled(True)
        self.mw.contourview.analyze()
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
        if wind_tunnel is None:
            self._show_message('Please generate a mesh first.')
            return []
        if not settings.formats:
            self._show_message('Please select at least one export format.')
            return []

        wind_tunnel.setBoundaryDefinitions(settings.boundary_definitions)
        exported_files = []
        for mesh_format in settings.formats:
            output_name = filename + self.mesh_export_extensions[mesh_format]
            wind_tunnel.export_mesh(mesh_format, name=output_name)
            exported_files.append(output_name)
        return exported_files

    def export_contour(self, filename: str):
        airfoil = self._require_airfoil(require_spline=True)
        if airfoil is None:
            return None

        x_values, y_values = airfoil.spline_data[0]
        try:
            with open(filename, 'w') as handle:
                handle.write('#\n')
                handle.write('# File created with ' + PyAero.__appname__ + '\n')
                handle.write('# Version: ' + PyAero.__version__ + '\n')
                handle.write('# Author: ' + PyAero.__author__ + '\n')
                handle.write('#\n')
                handle.write('# Derived from: %s\n' % str(airfoil.name).strip())
                handle.write('# Number of points: %s\n' % len(x_values))
                handle.write('#\n')
                for index, _ in enumerate(x_values):
                    handle.write(
                        '{:10.6f} {:10.6f}\n'.format(
                            x_values[index],
                            y_values[index],
                        )
                    )
        except IOError as error:
            logger.info('IO error: {}'.format(error))
            return None

        logger.info('Contour saved as {}'.format(filename))
        return filename

    def _require_airfoil(self, require_spline: bool = False):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            self._show_message('No airfoil loaded.')
            return None

        if require_spline and not airfoil.has_spline:
            self._show_message('Splining needs to be done first.')
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

        camber = refine.getCamberThickness(spline_data, le_id)
        airfoil.drawCamber(camber)
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
