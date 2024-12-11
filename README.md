
# PyAero
![](docs/images/SD7003_velocity_AOA6.png)
PyAero generated mesh (Solver: [SU2](https://su2code.github.io), Visualization: [ParaView](https://www.paraview.org/))
<br>

[![readthedocs](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](https://pyaero.readthedocs.io/en/latest/?badge=latest)
[![GitHub](https://img.shields.io/github/license/mashape/apistatus.svg)](https://en.wikipedia.org/wiki/MIT_License)


PyAero is an open-source airfoil contour analysis and CFD meshing tool written in Python. The graphical user interface is based on [Qt for Python](https://www.qt.io/qt-for-python) (Pyside6).

## Features

 - Load and display airfoil contour files
 - Airfoil splining and refining
   - Get a smooth contour and sufficient contour points
   - Refine leading edge and trailing edge
   - Prepare contour for meshing
   - Automatic calculation of leading edge radius
   - Point distribution on spline used as mesh distribution around airfoil
 - Automatic generation of block-strcuctured mesh
   - Single element C-type mesh
   - **Strictly orthogonal** mesh in the vicinity of the airfoil
   - Mesh resolution control for airfoil, leading edge, trailing edge and windtunnel
 - Sharp or blunt trailing edges
 - Mesh smoothing (to be improved)
 - Mesh export
   - [AVL FIRE](https://www.avl.com/fire) (.flma)
   - Some other file formats are exported as well (only listed formats)
     - [SU2](https://su2code.github.io) (.su2)
       - Including boundary markers
     - [GMSH](http://gmsh.info) (.msh)
     - [VTK](https://vtk.org) (.vtk)

   - Automatic definition of boundary elements (edges, faces)
     - Airfoil, inlet, outlet, symmetry
 - Run in batch mode (i.e. run PyAero from the command line)
   - Mesh multiple airfoils and export the meshes in multiple formats in one run without user interaction
   - Using the ``-no-gui`` option and a [control file](data/Batch/batch_control.json) in json format
   - Example command: ``python src/PyAero.py -no-gui data/Batch/batch_control.json``
 - Simple aerodynamic analysis using [AeroPython](http://nbviewer.ipython.org/github/barbagroup/AeroPython/blob/master/lessons/11_Lesson11_vortexSourcePanelMethod.ipynb)
 - Airfoil contour analysis (gradient, curvature and curvature circle)
 - NOT YET IMPLEMENTED:
   - Decent smoothing algorithm for the mesh regions outside the orthogonal blocks
   - Advanced aerodynamic analysis (i.e. linking to open source CFD software, e.g. SU2)

## Header image
 - Airfoil SD7003
 - Meshing with PyAero
 - Calculation with the CFD code [SU2](https://su2code.github.io)
 - Post-processing done in [ParaView](https://www.paraview.org/)

## Sample screenshots

![](docs/images/gui_airfoil1_new.png)
**PyAero GUI at a glance**
<br><br>

![](docs/images/mesh_RAE2822_MAC.png)
**Example mesh around RAE2822 airfoil**
<br><br>

![](docs/images/LE_mesh_RAE2822_MAC.png)
**Example mesh around RAE2822 airfoil - Leading Edge**
<br><br>

![](docs/images/TE_mesh_RAE2822_MAC.png)
**Example mesh around RAE2822 airfoil with a blunt Trailing Edge (with finite thickness)**
<br><br>

![](docs/images/TE_mesh_sharp_MAC.png)
**Example mesh with a sharp Trailing Edge**
<br><br>

![](docs/images/MAKAROV_KPS_mesh_MAC.png)
**Example mesh around MAKAROV KPS airfoil as used in the CFD code AVL-FIRE**
<br><br>

![](docs/images/MAKAROV_KPS_Veloyity.gif)
**Velocity field (RE=50000) around MAKAROV KPS airfoil using the CFD code AVL-FIRE**
<br><br>

![](docs/images/MAKAROV_KPS_TKE.gif)
**Turbulence kinetic energy field (RE=50000) around MAKAROV KPS airfoil using the CFD code AVL-FIRE**
<br><br>

![](docs/movies/RG14_3D_laminar_Iso-Q_pressure.gif)
**Unsteady 3D calculation of the RG14 airfoil using the CFD code AVL-FIRE**
<br>
**RE=330000, AOA=2°, 20 million cells.**
<br>
**Laminar calculation: CD=0.0079, CL=0.371**
<br>
**LES calculation (subgrid scale model: Kobayashi CSM): CD=0.0078, CL=0.362**
<br><br>

![](docs/images/SD7003_CP_RE200000_AOA3.png)
**Steady 2D calculation of the SD7003 airfoil using the CFD code SU2 (RE=200000, AOA=3), post-processing with ParaView**
<br><br>

## Documentation

The PyAero documentation can be found at the following link:

**[http://pyaero.readthedocs.io](http://pyaero.readthedocs.io)**

The documentation is automatically generated using the markdown files in the [docs](https://github.com/chiefenne/PyAero/tree/master/docs) folder via [Sphinx](http://www.sphinx-doc.org/en/stable/index.html).

## Dependencies

 - [Python 3.x](https://www.python.org/)
 - [Qt for Python (PySide6)](https://www.qt.io/qt-for-python)
 - [Numpy](http://www.numpy.org/)
 - [Scipy](https://www.scipy.org/)
 - [meshio](https://github.com/nschloe/meshio)

At the moment no binary is available for Windows.

## Download
The $ symbol at the beginning the following command examples represents the prompt at command shell. It is not part of the command.

### Option 1: Download source version using Git:

```bash
$ cd anywhere_on_your_computer
$ git clone https://github.com/chiefenne/PyAero.git
```
or if you want a specific branch (e.g. develop):

```bash
$ git clone https://github.com/chiefenne/PyAero.git -b develop
```


### Option 2: Download source version as a ZIP file:

From the [PyAero GitHub repository](https://github.com/chiefenne/PyAero). There is on the upper right side a green pull down menu ***Clone or download***. Click on it and then click ***Download ZIP***. You get a file ***PyAero-master.zip*** which you store anywhere on your computer.

```bash
$ cd anywhere_on_your_computer
$ unzip PyAero-master.zip
```

## Installation

After cloning from Git, or downloading and unzipping, set the environment variable for the PyAero installation path.

### Linux

If your shell is **bash**:
```bash
$ export PYAEROPATH=path_to_your_installation
```

And if you want to set it permanently across sessions (one of the following):
```bash
$ echo 'export PYAEROPATH=path_to_your_installation' >> ~/.bashrc
$ echo 'export PYAEROPATH=path_to_your_installation' >> ~/.bash_profile
```

For **csh** or **tcsh** use:
```bash
$ setenv PYAEROPATH path_to_your_installation
```

And if you want to set it permanently across sessions:
```bash
$ echo 'setenv PYAEROPATH path_to_your_installation' >> ~/.cshrc
```

Run PyAero using:

```bash
$ python $PYAEROPATH/src/PyAero.py
```

To simplify the command, set an *alias* (the upper beeing for bash and the lower for csh/tcsh).

```bash
$ alias pyaero="python $PYAEROPATH/src/PyAero.py"
$ alias pyaero "python $PYAEROPATH/src/PyAero.py"
```

To keep this across sessions, again append the *alias* command to the respective *.bashrc*, *.cshrc*, etc.

Then start PyAero using:

```bash
$ pyaero
```

## Qt for Python version

PyAero version based on the [Qt for Python](https://www.qt.io/qt-for-python) API (alias PySide2 for QT5 or PySide6 for QT6).

PyAero started based on the PyQt4 framework which for me was the API to go at the time when I started development.

After a small creative break I decided to upgrade to PyQt5 and continue development. I soon realized that the PyQt5 documentation lacks information, i.e. there were only links to the Qt C++ documentation and no Python related docs, I had the feeling that the PyQt5 development probably stagnates.

Short online research revealed to me that meanwhile Qt themselves are developing now **Qt for Python** which is based on the legacy Pyside API. This made me think that it is possibly best to go with Qt for Python as it is tightly coupled to Qt.

## License

Distributed under the MIT license. See [LICENSE](https://raw.githubusercontent.com/chiefenne/PyAero/master/LICENSE) for more information.

2024 Andreas Ennemoser – andreas.ennemoser@aon.at

## Stargazers over time

[![Stargazers over time](https://starchart.cc/chiefenne/PyAero.svg?variant=adaptive)](https://starchart.cc/chiefenne/PyAero)
