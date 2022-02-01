Submenu :guilabel:`Open`
""""""""""""""""""""""""

The :menuselection:`File --> Open` submenu is used to load airfoil contour files or meshes.

At the moment the standard file format as used in many applications is supported.

.. epigraph::

   "Coordinates in the standard format wrapping from upper surface trailing edge around 
   the leading edge to the lower surface trailing edge"
   
   -- `UIUC airofil data site <https://m-selig.ae.illinois.edu/ads/coord_database.html>`_

See figure below for the layout/format of such a file. Only the first and last few lines of the file 
are printed here. 

.. _figure_airfoil_file:
.. figure::  images/airfoil_file.png
   :align:   center
   :target:  _images/airfoil_file.png
   :name: airfoil_file

   Typical format of an airfoil contour file

This format is often used in software like `XFOIL <http://web.mit.edu/drela/Public/web/xfoil>`_ and similar.

In addition, lines starting with a hash sign :code:`#` at the beginning are interpreted as comment lines 
(i.e. not used inside PyAero). This can be used for documentation or to add additional information.
