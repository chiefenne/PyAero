Menu *File Open*
""""""""""""""""

The :menuselection:`Open` submenu is used to load airfoil contour files or meshes.

At the moment file formats as used in `XFOIL <http://web.mit.edu/drela/Public/web/xfoil>`_ are supported. See Figure :ref:`figure_airfoil_file` for the layout/format for such a file. Only the first few lines of the file are printed here. Lines starting with a hash sign **"#"** at the beginning are interpreted as comment lines (those are not used inside PyAero).

.. _figure_airfoil_file:
.. figure::  images/airfoil_file.png
   :align:   center
   :target:  _images/airfoil_file.png
   :name: airfoil_file

   Typical format of an airfoil contour file
