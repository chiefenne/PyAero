# ****************
# PyAero settings
# ****************

import os


PYAEROPATH = os.getcwd()

# check if user has set the path via environment variable
if os.getenv('PYAEROPATH'):
    PYAEROPATH = os.getenv('PYAEROPATH')

# path to data
DATAPATH = os.path.join(PYAEROPATH, 'data')

# path to data (e.g. airfoil coordinate files)
# path can be absolute or relative (to position where starting PyAero)
AIRFOILDATA = os.path.join(PYAEROPATH, 'data/Airfoils')

# modified contours and mesh folder
OUTPUTDATA = os.path.join(DATAPATH, 'OUTPUT')

# path to menu data
MENUDATA = os.path.join(DATAPATH, 'Menus')

# path to log files
LOGDATA = os.path.join(DATAPATH, 'LOGS')

# set locale
# can be either 'C' or ''
# if string is empty then system default locale is used
# in case of 'C' decimal separator is a dot in spin boxes, etc.
LOCALE = 'C'

# application can be exited by pressing the escape key
EXITONESCAPE = True

# airfoil chord length
CHORDLENGTH = 1.

# path to icons
ICONS = os.path.join(PYAEROPATH, 'data/Icons')
ICONS_S = os.path.join(ICONS, '16x16')
ICONS_L = os.path.join(ICONS, '24x24')

# size of airfoil coordinate markers in pixels
MARKERSIZE = 3

# default airfoil for fast loading
DEFAULT_CONTOUR = os.path.join(AIRFOILDATA, 'F1K/hn1033a.dat')

# set the filter for files to be shown in dialogs
DIALOGFILTER = 'Airfoil contour files (*.dat *.txt)'
DIALOGFILTER_MESH = 'Mesh files FIRE(*.flma);;Mesh files SU2 (*.su2);;Mesh files GMSH (*.msh)'

# set the filter for files to be shown in the airfoil browser
FILEFILTER = ['*.dat', '*.txt', '*.su2']

# set anchor for zooming
# 'mouse' means zooming wrt to mouse pointer location
# 'center' means zooming wrt to the view center
ZOOMANCHOR = 'mouse'

# background of graphicsview ('solid', 'gradient')
VIEWSTYLE = 'solid'

# set zoom limits so that scene is always in meaningful size
MINZOOM = 10.0
MAXZOOM = 120000.

# set minimum relative rubberband size
# i.e. width of zoom rectangle wrt to viewer window width
# for smaller rectangles zoom is deactivated to avoid accidential zooms
# valid values between 0.05 and 1.0
RUBBERBANDSIZE = 0.08

# scale increment (must be >= 1.1)
SCALEINC = 1.1

 # zoom direction (can be inverted by changing the sign)
ZOOMDIRECTION = -1

# Color for emphasized log messages
LOGCOLOR = '#1763E7'
