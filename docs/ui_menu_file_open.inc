Submenu **Open**
""""""""""""""""

The :menuselection:`File --> Open` submenu is used to load airfoil contour files or meshes.

At the moment file formats as used in `XFOIL <http://web.mit.edu/drela/Public/web/xfoil>`_ are supported.
See figure below for the layout/format for such a file. 
Only the first few lines of the file are printed here. 
Lines starting with a hash sign **"#"** at the beginning are interpreted as comment lines (i.e. not used inside PyAero).

.. _figure_airfoil_file:
.. figure::  images/airfoil_file.png
   :align:   center
   :target:  _images/airfoil_file.png
   :name: airfoil_file

   Typical format of an airfoil contour file

The airfoil coordinates in those files are starting at the trailing edge, 
proceeding on the upper side of the airfoil towards the leading edge and then
are going back to the trailing edge on the lower side of the airfoil.
