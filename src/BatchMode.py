import os
import json

import Airfoil
import SplineRefine
import TrailingEdge
import Meshing
from Settings import DATAPATH


class Batch:

    def __init__(self, app):
        self.app = app
        self.app.mainwindow = self
        self.load_batch_control()
        self.run_batch()

    def load_batch_control(self):
        batch_controlfile = os.path.join(DATAPATH, 'Batch', 'batch_control.json')
        with open(batch_controlfile, 'r') as f:
            self.batch_control = json.load(f)

        print(self.batch_control.keys())

    def run_batch(self):
        
        # loop all airfoils
        airfoils = self.batch_control['Airfoils']
        for name in airfoils:
            print(name)

            # load airfoil
            basename = os.path.splitext(name)[0]
            self.airfoil = Airfoil.Airfoil(basename)
            loaded = self.airfoil.readContour(name, '#')

            # spline and refine
            refinement = self.batch_control['Airfoil contour refinement']
            refine = SplineRefine.SplineRefine()
            refine.doSplineRefine(tolerance=refinement['Refinement tolerance'],
                                  points=refinement['Number of points on spline'],
                                  ref_te=refinement['Refine trailing edge old'],
                                  ref_te_n=refinement['Refine trailing edge new'],
                                  ref_te_ratio=refinement['Refine trailing edge ratio'])

            # trailing edge
            te = self.batch_control['Airfoil trailing edge']
            trailing = TrailingEdge.TrailingEdge()
            trailing.trailingEdge(blend=te['Upper side blending length'] / 100.0,
                                  ex=te['Upper blending polynomial exponent'],
                                  thickness=te['Trailing edge thickness relative to chord'],
                                  side='upper')
            trailing.trailingEdge(blend=te['Lower side blending length'] / 100.0,
                                  ex=te['Upper blending polynomial exponent'],
                                  thickness=te['Trailing edge thickness relative to chord'],
                                  side='lower')
            
            # make mesh
            wind_tunnel = Meshing.Windtunnel()
            contour = self.app.mainwindow.airfoil.spline_data

            # mesh around airfoil
            acm = self.batch_control['Airfoil contour mesh']
            wind_tunnel.AirfoilMesh(name='block_airfoil',
                                    contour=contour,
                                    divisions=acm['Divisions normal to airfoil'],
                                    ratio=acm['Cell growth rate'],
                                    thickness=acm['1st cell layer thickness'])

            # mesh at trailing edge
            tem = self.batch_control['Airfoil trailing edge mesh']
            wind_tunnel.TrailingEdgeMesh(name='block_TE',
                                         te_divisions=tem['Divisions at trailing edge'],
                                         thickness=tem['1st cell layer thickness'],
                                         divisions=tem['Divisions downstream'],
                                         ratio=tem['Cell growth rate'])

            # mesh tunnel airfoil
            tam = self.batch_control['Windtunnel mesh airfoil']
            wind_tunnel.TunnelMesh(name='block_tunnel',
                                   tunnel_height=tam['Windtunnel height'],
                                   divisions_height=tam['Divisions of tunnel height'],
                                   ratio_height=tam['Cell thickness ratio'],
                                   dist=tam['Distribution biasing'])

            # mesh tunnel wake
            twm = self.batch_control['Windtunnel mesh wake']
            wind_tunnel.TunnelMeshWake(name='block_tunnel_wake',
                                       tunnel_wake=twm['Windtunnel wake'],
                                       divisions=twm['Divisions in the wake'],
                                       ratio=twm['Cell thickness ratio'],
                                       spread=twm['Equalize vertical wake line at'] / 100.0)
 
