.. make a label for this file
.. _batchmode:

Batch mode (run from command line)
==================================

In order to be able to automate the mesh generation process, a batch utility is available. This allows to run the mesh generation on a large number of airfoils. A batch control file is used to specify the airfoils to be processed. The batch control file is a text file (:file:`data/Batch/batch_control.json`) which contains the following information:

   * Airfoils which should be meshed
   * Settings to be used for the mesher
   * Output formats in which the mesh(es) should be written

The command used to launch the batch processing is:

:code:`python src/PyAero.py -no-gui data/Batch/batch_control.json`



