Contour Analysis
================

The :guilabel:`Contour Analysis` page lets you inspect the geometry quality of the current airfoil. It is meant as a diagnostic tool for the contour-preparation stage and helps answer a simple question: is the current contour smooth enough for the mesh I want to build?

Available Inputs
================

The page allows you to choose:

- the contour source
- the quantity to plot

Contour source:

- :guilabel:`Raw`
- :guilabel:`Refined`

Plot quantity:

- :guilabel:`Gradient`
- :guilabel:`Curvature`
- :guilabel:`Radius`

Typical Use
===========

The most common sequence is:

1. load an airfoil
2. prepare and refine it
3. open :guilabel:`Contour Analysis`
4. click :guilabel:`Analyze Contour`
5. switch between gradient, curvature, and radius plots

This makes it easy to compare the raw geometry with the prepared one and to check whether the leading edge and trailing edge are being resolved the way you expect.

What to Look For
================

Useful signs during inspection include:

- smoother curvature behavior after preparation
- fewer abrupt spikes caused by sparse raw point distributions
- a cleaner radius profile around the leading edge

If the refined contour still shows undesirable spikes, go back to :ref:`spline_refine` and adjust the point count or refinement tolerance.

Workspace Integration
=====================

The contour analysis view lives in the same workspace as the graphics viewer, so switching between geometry inspection and mesh inspection stays fast.

.. figure:: images/tabbed_views_animated.gif
   :align: center
   :target: _images/tabbed_views_animated.gif

   Switching between the graphics view and the contour analysis view.
