import os
import json

import Airfoil
import Meshing
import MeshBuilders
import ToolboxServices

import logging
logger = logging.getLogger(__name__)


class Batch:

    def __init__(self, app, batch_controlfile, __version__):
        self.app = app
        self.app.mainwindow = self
        self.load_batch_control(batch_controlfile)
        self.workflow = ToolboxServices.WorkflowService(self)

        stars = 50
        message_stars = stars*'*'
        print('\n' + message_stars)
        message = '{:*^{stars}}'.format(' PYAERO batch meshing ', stars=stars)
        print(message)
        message = '{:*^{stars}}'.format('  v' + __version__ + '  ', stars=stars)
        print(message)
        logger.info(message)
        print(message_stars + '\n')

    def load_batch_control(self, batch_controlfile):
        with open(batch_controlfile, 'r') as f:
            self.batch_control = json.load(f)

    def run_batch(self):
        
        # loop all airfoils
        airfoil_path = self.batch_control['Airfoils']['path']
        mesh_path = self.batch_control['Output formats']['path']
        output_formats = self.batch_control['Output formats']['formats']

        print('Airfoil path is', airfoil_path)
        print('Mesh output path is', mesh_path, '\n')

        airfoils = self.batch_control['Airfoils']['names']
        trailing_edges = self.batch_control['Airfoils']['trailing_edges']

        message = 'Airfoils to mesh:'
        print(message)
        logger.info(message)
        for airfoil in airfoils:
            message = f'     --> {airfoil}'
            print(message)
            logger.info(message)
        
        print('\n')

        for i, airfoil in enumerate(airfoils):
            message = f'Starting batch processing for airfoil {airfoil}'
            print(message)
            logger.info(message)

            # load airfoil
            basename = os.path.splitext(airfoil)[0]
            self.airfoil = Airfoil.Airfoil.from_file(
                os.path.join(airfoil_path, airfoil),
                comment='#',
                mainwindow=self,
            )
            if self.airfoil is None:
                message = f'Failed to load airfoil {airfoil}'
                print(message)
                logger.error(message)
                continue

            try:
                # spline and refine
                refinement = self.batch_control['Airfoil contour refinement']
                refinement_settings = ToolboxServices.SplineRefineSettings(
                    tolerance=refinement['Refinement tolerance'],
                    points=refinement['Number of points on spline'],
                    ref_te=refinement['Refine trailing edge old'],
                    ref_te_n=refinement['Refine trailing edge new'],
                    ref_te_ratio=refinement['Refine trailing edge ratio'],
                )
                self.workflow.spline_and_refine(refinement_settings)

                # trailing edge
                if trailing_edges[i] == 'yes':
                    te = self.batch_control['Airfoil trailing edge']
                    trailing_edge_settings = ToolboxServices.TrailingEdgeSettings(
                        upper_blend=te['Upper side blending length'] / 100.0,
                        lower_blend=te['Lower side blending length'] / 100.0,
                        upper_exponent=te['Upper blending polynomial exponent'],
                        lower_exponent=te['Lower blending polynomial exponent'],
                        thickness=te['Trailing edge thickness relative to chord'],
                    )
                    self.workflow.add_trailing_edge(trailing_edge_settings)

                # mesh settings
                acm = self.batch_control['Airfoil contour mesh']
                tem = self.batch_control['Airfoil trailing edge mesh']
                tam = self.batch_control['Windtunnel mesh airfoil']
                twm = self.batch_control['Windtunnel mesh wake']
                mesh_settings = Meshing.WindtunnelMeshSettings(
                    airfoil=MeshBuilders.AirfoilBlockSettings(
                        name='block_airfoil',
                        divisions=acm['Divisions normal to airfoil'],
                        growth=acm['Cell growth rate'],
                        thickness=acm['1st cell layer thickness'],
                    ),
                    trailing_edge=MeshBuilders.TrailingEdgeBlockSettings(
                        name='block_TE',
                        trailing_edge_divisions=tem['Divisions at trailing edge'],
                        thickness=tem['1st cell layer thickness'],
                        divisions=tem['Divisions downstream'],
                        growth=tem['Cell growth rate'],
                    ),
                    tunnel=MeshBuilders.TunnelBlockSettings(
                        name='block_tunnel',
                        tunnel_height=tam['Windtunnel height'],
                        divisions_height=tam['Divisions of tunnel height'],
                        height_growth=tam['Cell thickness ratio'],
                        distribution=tam['Distribution biasing'],
                        smoothing_algorithm=tam['Smoothing algorithm'],
                        smoothing_iterations=tam['Smoothing iterations'],
                        smoothing_tolerance=tam['Smoothing tolerance'],
                        outer_boundary_slide=1.0,
                        elliptic_relaxation=1.0,
                        protected_guide_relaxation=0.25,
                        protected_guide_layers=8,
                        protected_guide_decay=0.20,
                        protected_guide_smoothing=15,
                    ),
                    wake=MeshBuilders.WakeBlockSettings(
                        name='block_tunnel_wake',
                        tunnel_wake=twm['Windtunnel wake'],
                        divisions=twm['Divisions in the wake'],
                        growth=twm['Cell thickness ratio'],
                        spread=twm['Equalize vertical wake line at'] / 100.0,
                    ),
                )
                wind_tunnel = self.workflow.generate_mesh(mesh_settings)
                if wind_tunnel is None:
                    raise ValueError('Mesh generation was canceled.')
            except ValueError as error:
                message = f'Failed to process airfoil {airfoil}: {error}'
                print(message)
                logger.error(message)
                continue

            message = f'Finished batch mesh generation for airfoil {airfoil}'
            print(message)
            logger.info(message)

            # export mesh
            message = f'Starting mesh export for airfoil {airfoil}'
            print(message)
            logger.info(message)

            export_settings = ToolboxServices.MeshExportSettings(
                formats=output_formats,
            )
            exported_files = self.workflow.export_mesh(
                wind_tunnel,
                os.path.join(mesh_path, basename),
                export_settings,
            )

            for mesh_name in exported_files:
                message = f'Finished mesh export for airfoil {airfoil} to {mesh_name}'
                print(message)
                logger.info(message)
