# PyAero

![PyAero generated mesh](docs/images/SD7003_velocity_AOA6.png)

[![readthedocs](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](https://pyaero.readthedocs.io/en/latest/?badge=latest)
[![GitHub](https://img.shields.io/github/license/mashape/apistatus.svg)](https://en.wikipedia.org/wiki/MIT_License)

PyAero is an open-source desktop tool for airfoil contour preparation, contour analysis, and 2D block-structured CFD mesh generation. It focuses on the workflow that typically happens before a solver run: cleaning up geometry, refining point distributions, creating a practical trailing edge, building a structured wind-tunnel mesh, and exporting the result in solver-friendly formats.

The current application is built with Python and PySide6 and ships with a redesigned workflow-oriented user interface. PyAero does not solve the CFD case itself; it prepares geometry and meshes for downstream tools such as SU2, Gmsh, ParaView, or AVL FIRE workflows.

## Highlights

- Workflow sidebar with airfoil library, geometry prep, meshing, contour analysis, and CFD helper tools
- Bundled and local airfoil library with search, import, and quick loading
- Geometry preparation with CST and legacy B-spline modes
- Recursive leading-edge refinement plus dedicated trailing-edge segment refinement
- Optional finite-thickness trailing edge with independent upper and lower blending controls
- Derived geometry outputs including prepared contour, camber line, and CST parameters
- 2D block-structured C-type wind-tunnel mesh generation with dedicated airfoil, trailing-edge, tunnel, and wake blocks
- Simple, elliptic, and angle-based smoothing options, including protected tunnel guide controls
- Mesh export to `FLMA`, `SU2`, `Gmsh`, and `VTU`
- Batch mode for generating and exporting meshes without the GUI
- Registry-driven menus, toolbars, and keyboard shortcuts, including a shortcut editor

## Typical Workflow

1. Load an airfoil from the bundled library, local library, or an external `.dat` or `.txt` file.
2. Prepare the contour with CST or legacy B-spline refinement.
3. Optionally add a finite-thickness trailing edge.
4. Generate the structured tunnel mesh.
5. Export the mesh in one or more formats.

## Current Interface

[![PyAero interface overview](docs/images/ui_overview_main.png)](docs/images/ui_overview_main.png)

The application now centers around a workflow sidebar on the left and a workspace on the right. Geometry preparation, mesh generation, export, contour analysis, and CFD helper tools are grouped into dedicated pages so the main path from raw airfoil to exported mesh is easier to follow.

## Installation

PyAero currently runs from the source tree. Start it from the repository root so the application can resolve its bundled resources.

```bash
git clone https://github.com/chiefenne/PyAero.git
cd PyAero
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/PyAero.py
```

For batch mode:

```bash
python src/PyAero.py -no-gui data/Batch/batch_control.json
```

## Runtime Dependencies

- Python 3
- PySide6
- NumPy
- SciPy

`meshio` is no longer part of the active runtime dependency set.

## Documentation

The documentation lives in [docs/](docs) and is published at:

<https://pyaero.readthedocs.io>

The refreshed docs cover:

- the redesigned interface
- airfoil library usage
- geometry preparation and CST workflows
- meshing and export
- contour analysis
- CFD input helpers
- settings, shortcuts, and UI customization
- batch processing

## Project Scope

PyAero is currently focused on:

- 2D airfoil contour preparation
- 2D structured mesh generation
- mesh export for external CFD workflows

PyAero is not a full CFD solver, and mesh import remains future-facing compared with the export path.

## License

Distributed under the MIT license. See [LICENSE](LICENSE).

2026 Andreas Ennemoser - andreas.ennemoser@aon.at
