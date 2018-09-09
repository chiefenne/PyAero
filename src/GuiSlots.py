import sys
import copy
import webbrowser

import PySide2
from PySide2 import QtGui, QtCore, QtWidgets

import PyAero
import Airfoil
import GraphicsTest
import IconProvider
from Settings import DIALOGFILTER, AIRFOILDATA, LOGCOLOR, DEFAULT_CONTOUR, \
                      DEFAULT_STL
import logging
logger = logging.getLogger(__name__)


class Slots:
    """This class handles all callback routines for GUI actions

    PyQt uses signals and slots for GUI events and their respective
    handlers/callbacks.
    """

    def __init__(self, parent):
        """Constructor for Slots class

        Args:
            parent (QMainWindow object): MainWindow instance
        """
        self.parent = parent

    # # @QtCore.pyqtSlot()
    def onOpen(self):

        dialog = QtWidgets.QFileDialog()

        provider = IconProvider.IconProvider()
        dialog.setIconProvider(provider)
        dialog.setNameFilter(DIALOGFILTER)
        dialog.setNameFilterDetailsVisible(True)
        dialog.setDirectory(AIRFOILDATA)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)

        # open custom file dialog using custom icons
        if dialog.exec_():
            filenames = dialog.selectedFiles()
            selfilter = dialog.selectedNameFilter()

        try:
            filenames
        # do nothing if CANCEL button was pressed
        except NameError as error:
            logger.info('Error during file load: {}'.format(error))
            return

        if 'stl' in selfilter.lower():  # method of QString object
            # currently limited to load only one STL file
            self.parent.postview.readStl(filenames[0])
        else:
            # load one or more airfoils
            for filename in filenames:
                self.loadAirfoil(filename)

    # # @QtCore.pyqtSlot()
    def onOpenPredefined(self):
        self.loadAirfoil(DEFAULT_CONTOUR)

    def loadAirfoil(self, filename, comment='#'):
        fileinfo = QtCore.QFileInfo(filename)
        name = fileinfo.fileName()

        airfoil = Airfoil.Airfoil(name)
        loaded = airfoil.readContour(filename, comment)

        # no error during loading
        if loaded:
            # clear all items from the scene when new airfoil is loaded
            self.parent.scene.clear()
            # make contour, markers, chord and add everything to the scene
            airfoil.makeAirfoil()
            # add all airfoil items (contour markers) to the scene
            Airfoil.Airfoil.addToScene(airfoil, self.parent.scene)
            # make loaded airfoil the currently active airfoil
            self.parent.airfoil = airfoil
            # add airfoil to list of loaded airfoils
            self.parent.airfoils.append(airfoil)
            # automatically zoom airfoil so that it fits into the view
            self.fitAirfoilInView()
            logger.info('Airfoil {} loaded'.format(name))

            self.parent.centralwidget.toolbox.header.setEnabled(True)
            self.parent.centralwidget.toolbox.listwidget.setEnabled(True)
            self.parent.centralwidget.toolbox.listwidget.addItem(name)

    # # @QtCore.pyqtSlot()
    def onPredefinedSTL(self):
        self.parent.postview.readStl(DEFAULT_STL)

    # # @QtCore.pyqtSlot()
    def fitAirfoilInView(self):

        if len(self.parent.airfoils) == 0:
            return

        # get bounding rect in scene coordinates
        item = self.parent.airfoil.contourPolygon
        rectf = item.boundingRect()
        rf = copy.deepcopy(rectf)

        center = rf.center()
        # make 4% smaller than width of graphicsview
        w = 1.04 * rf.width()
        h = 1.04 * rf.height()
        # do not use setWidhtF and setHeightF here!!!
        rf.setWidth(w)
        rf.setHeight(h)

        # shift center of rectf
        cx = center.x()
        cy = center.y()
        rf.moveCenter(QtCore.QPointF(cx, cy))

        self.parent.view.fitInView(rf,
                                   aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # it is IMPORTANT that this is called after fitInView
        # adjust airfoil marker size to MARKERSIZE setting
        self.parent.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.parent.view.getSceneFromView()

    # # @QtCore.pyqtSlot()
    def onViewAll(self):
        """zoom inorder to view all items in the scene"""

        # take all items except markers (as they are adjusted in size for view)

        rectf = self.parent.scene.itemsBoundingRect()
        self.parent.view.fitInView(rectf,
                                   aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # it is IMPORTANT that this is called after fitInView
        # adjust airfoil marker size to MARKERSIZE setting
        self.parent.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.parent.view.getSceneFromView()

    # @QtCore.pyqtSlot()
    def toggleTestObjects(self):
        if self.parent.testitems:
            GraphicsTest.deleteTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView loaded')
        else:
            GraphicsTest.addTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView removed')
        self.parent.testitems = not self.parent.testitems

    # @QtCore.pyqtSlot()
    def onSave(self):
        (fname, thefilter) = QtWidgets.QFileDialog. \
            getSaveFileNameAndFilter(self.parent,
                                     'Save file', '.', filter=DIALOGFILTER)
        if not fname:
            return

        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    # @QtCore.pyqtSlot()
    def onSaveAs(self):
        (fname, thefilter) = QtGui. \
            QFileDialog.getSaveFileNameAndFilter(
            self.parent, 'Save file as ...', '.',
            filter=DIALOGFILTER)
        if not fname:
            return
        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    # @QtCore.pyqtSlot()
    def onPrint(self):
        dialog = QtGui.QPrintDialog()
        if dialog.exec_() == QtGui.QDialog.Accepted:
            self.parent.editor.document().print_(dialog.printer())

    # @QtCore.pyqtSlot()
    def onPreview(self):
        printer = QtGui.QPrinter(QtGui.QPrinter.HighResolution)

        preview = QtGui.QPrintPreviewDialog(printer, self.parent)
        preview.paintRequested.connect(self.handlePaintRequest)
        preview.exec_()

    # setup printer for print preview
    def handlePaintRequest(self, printer):
        printer.setOrientation(QtGui.QPrinter.Landscape)
        self.parent.view.render(QtGui.QPainter(printer))

    def toggleLogDock(self, _sender):
        """Switch message log window on/off"""

        logger.debug('I am toggleLogDock')
        logger.debug('This is _sender: {}'.format(_sender))

        visible = self.parent.messagedock.isVisible()
        self.parent.messagedock.setVisible(not visible)

        # update the checkbox if toggling is done via keyboard shortcut
        if _sender == 'shortcut':
           checkbox = self.parent.centralwidget.cb1
           checkbox.setChecked(not checkbox.isChecked())

    # @QtCore.pyqtSlot()
    def onBlockMesh(self):
        pass

    def getAirfoilByName(self, name):
        for airfoil in self.parent.airfoils:
            if airfoil.name == name:
                return airfoil
        return None

    # @QtCore.pyqtSlot()
    def removeAirfoil(self, name=None):
        """Remove all selected airfoils from the scene"""

        # the name parameter is only set when coming from listwidget
        # and the deleting is done via DEL key
        if name:
            airfoil = self.getAirfoilByName(name)
        else:
            airfoil = self.parent.airfoil

        self.parent.airfoils.remove(airfoil)

        # remove from scene only if active airfoil was chosen
        if airfoil.name == self.parent.airfoil.name:
            self.parent.scene.removeItem(self.parent.airfoil.contourPolygon)
            self.parent.scene.removeItem(self.parent.airfoil.chord)
            self.parent.scene.removeItem(self.parent.airfoil.polygonMarkersGroup)

        # remove also listwidget entry
        centralwidget = self.parent.centralwidget
        listwidget = centralwidget.toolbox.listwidget
        itms = listwidget.findItems(self.parent.airfoil.name, QtCore.Qt.MatchExactly)
        for itm in itms:
            row = listwidget.row(itm)
            listwidget.takeItem(row)

        # fit all remaining scene items into the view
        self.onViewAll()

    def onMessage(self, msg):
        # move cursor to the end before writing new message
        # so in case text inside the log window was selected before
        # the new text is pastes correct
        self.parent.messages.moveCursor(QtGui.QTextCursor.End)
        self.parent.messages.append(msg)

    # @QtCore.pyqtSlot()
    def onExit(self):
        sys.exit(QtWidgets.qApp.quit())

    # @QtCore.pyqtSlot()
    def onCalculator(self):
        pass

    # @QtCore.pyqtSlot()
    def onBackground(self):
        if self.parent.view.viewstyle == 'gradient':
            self.parent.view.viewstyle = 'solid'
        else:
            self.parent.view.viewstyle = 'gradient'

        self.parent.view.setBackground(self.parent.view.viewstyle)

    # @QtCore.pyqtSlot()
    def onUndo(self):
        pass

    # @QtCore.pyqtSlot()
    def onLevelChanged(self):
        """Change size of message window when floating """
        if self.parent.messagedock.isFloating():
            self.parent.messagedock.resize(700, 300)

    # @QtCore.pyqtSlot()
    def onTextChanged(self):
        """Move the scrollbar in the message log-window to the bottom.
        So latest messages are always in the view.
        """
        vbar = self.parent.messages.verticalScrollBar()
        if vbar:
            vbar.triggerAction(QtWidgets.QAbstractSlider.SliderToMaximum)

    def onTabChanged(self):
        """Sync tabs and toolboxes """
        tabs = self.parent.centralwidget.tabs
        tab_text = self.parent.centralwidget.tabs.tabText(tabs.currentIndex())
        toolbox = self.parent.centralwidget.toolbox

        if tab_text == 'Airfoil Viewer':
            toolbox.setCurrentIndex(toolbox.tb1)
        if tab_text == 'Contour Analysis':
            toolbox.setCurrentIndex(toolbox.tb3)

    def messageBox(self, message):
        QtWidgets.QMessageBox. \
            information(self.parent, 'Information',
                        message, QtWidgets.QMessageBox.Ok)

    # @QtCore.pyqtSlot()
    def onRedo(self):
        pass

    # @QtCore.pyqtSlot()
    def onHelp(self):
        pass

    # @QtCore.pyqtSlot()
    def onHelpOnline(self):
        webbrowser.open('http://pyaero.readthedocs.io/en/latest/')

    # @QtCore.pyqtSlot()
    def onAbout(self):
        QtWidgets.QMessageBox. \
            about(self.parent, "About " + PyAero.__appname__,
                  "<b>" + PyAero.__appname__ +
                  "</b> is used for "
                  "2D airfoil contour analysis and CFD mesh generation.\
                  <br><br>"
                  "<b>" + PyAero.__appname__ + "</b> code under " +
                  PyAero.__license__ +
                  " license. (c) " +
                  PyAero.__copyright__ + "<br><br>"
                  "email to: " + PyAero.__email__ + "<br><br>"
                  "Embedded <b>Aeropython</b> code under MIT license. <br> \
                  (c) 2014 Lorena A. Barba, Olivier Mesnard<br>"
                  "Link to " +
                  "<a href='http://nbviewer.ipython.org/github/" +
                  "barbagroup/AeroPython/blob/master/lessons/" +
                  "11_Lesson11_vortexSourcePanelMethod.ipynb'> \
                  <b>Aeropython</b></a> (iPython notebook)." + "<br><br>"
                  + "<b>VERSIONS:</b>" + "<br>"
                  + PyAero.__appname__ + ": " + PyAero.__version__ +
                  "<br>"
                  + "Python: %s" % (sys.version.split()[0]) + "<br>"
                  + "Qt for Python: %s" % (PySide2.__version__) + "<br>"
                  + "Qt: %s" % (PySide2.QtCore.__version__)
                  )
