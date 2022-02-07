.. make a label for this file
.. _loading_airfoils:

.. |right_Arrow| unicode:: U+025BA .. BLACK RIGHT-POINTING POINTER
.. |right_medium_Arrow| unicode:: U+023F5 .. BLACK MEDIUM RIGHT-POINTING TRIANGLE
.. |down_right_Arrow| unicode:: U+021B3 .. DOWNWARDS ARROW WITH TIP RIGHTWARDS

Loading Airfoils
================

Loading airfoils can be done in different ways.

Load via menu :guilabel:`Open`
------------------------------

The :menuselection:`File --> Open` menu is the standard way to load airfoil contour data. 
The shortcut assigned to this menu is :kbd:`CTRL-o`. When clicking this menu or applying the 
respective shortcut, a file dialog pops up. It allows to select files or browse directories.

.. _figure_menu_open:
.. figure::  images/menu_open.png
   :align:   center
   :target:  _images/menu_open.png
   :name: MenuOpen

   *Open* menu to load an airfoil contour via the file browser

Load via the inline file browser
--------------------------------

As outlined above there are more ways to load airfoils. A very handy way to browse airfoils is to use the 
implemented file browser. This browser is restricted in terms of navigation. Only files and folders below a 
predefined root path are visible. The default root is the :file:`data/Airfoils` subfolder from the 
standard installation. The root path for airfoils can be changed by the user in the file :file:`src/Settings.py` 
by changing the value of the variable :code:`AIRFOILDATA`.

The file browser is located in the *toolbox* on the left side of the application. It is the uppermost tab in 
the toolbox area.

.. _figure_toolbox_area:
.. figure::  images/toolbox_area_1_NEW.png
   :align:   center
   :target:  _images/toolbox_area_1_NEW.png
   :name: Toolbar_Open

   File browser integrated in the *Toolbox*.

.. seealso:: For more information on configuring the root path to airfoil data see :ref:`tutorial_settings`.

Load via the *Toolbar*
----------------------

Another way to open the file dialog is to click on the :menuselection:`Open` icon in the toolbar. 
The toolbar consists of a row of icons just below the menu bar. The toolbar and its icons can be customized by 
editing the file :file:`data/PToolBar.xml`.

.. _figure_toolbar_open:
.. figure::  images/toolbar_open.png
   :align:   center
   :target:  _images/toolbar_open.png
   :name: Toolbar_Open

   Toolbar icon to load an airfoil contour via the file browser

.. seealso:: For more information on configuring the menubar and the toolbar see :ref:`tutorial_settings`.

Load a predefined airfoil
-------------------------

For testing purposes a predefined airfoil can be loaded without the need of a file dialog. The airfoil which is predefined can be configured.

.. _figure_toolbar_open_predefined:
.. figure::  images/toolbar_open_predefined.png
   :align:   center
   :target:  _images/toolbar_open_predefined.png
   :name: Toolbar_Open

   Toolbar icon to load a predefined airfoil contour

.. seealso:: See tutorial :ref:`tutorial_settings` on how to change the default airfoil.

Load via drag and drop
----------------------

Last but not least, one or more airfoil(s) can be loaded via drag and drop. Just drag a couple of files, e.g. from the 
Explorer (Windows) or Finder (MacOS), to the graphics window. All files will be loaded, but only one file will 
be displayed. All the other files are shown (and can be activated by clicking on the name) in the toolbox area.

.. _figure_drag_and_drop:
.. figure::  images/Drag_and_drop.gif
   :align:   center
   :target:  _images/Drag_and_drop.gif
   :name: Load_drag_and_drop

   Load multiple contours via drag and drop

