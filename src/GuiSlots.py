import sys
import copy
import webbrowser
import numpy as np
import scipy

import PySide6
from PySide6 import QtGui, QtCore, QtWidgets, QtPrintSupport

import PyAero
import Airfoil
import FileDialog
import GraphicsTest
from Settings import DIALOGFILTER, AIRFOILDATA, DEFAULT_CONTOUR
import logging
logger = logging.getLogger(__name__)


class Slots:
    """This class handles all callback routines for GUI actions

    PyQt uses signals and slots for GUI events and their respective
    handlers/callbacks.

    It is mandatory to decorate the callback functions with the
    @QtCore.Slot() decorator.
    """

    def __init__(self, parent):
        """Constructor for Slots class

        Args:
            parent (QMainWindow object): MainWindow instance
        """
        self.parent = parent

    @QtCore.Slot()
    def onOpen(self):
        """Summary

        Returns:
            TYPE: Description
        """
        file_dialog = FileDialog.Dialog()
        file_dialog.setFilter(DIALOGFILTER)
        filename, _ = file_dialog.openFilename(directory=AIRFOILDATA)

        if not filename:
            logger.info('No file selected. Nothing saved.')
            return

        if 'su2' in filename:
            self.loadSU2(filename)
            return

        self.loadAirfoil(filename)

    @QtCore.Slot()
    def onOpenPredefined(self):
        self.loadAirfoil(DEFAULT_CONTOUR)

    @QtCore.Slot(str, str)
    def loadAirfoil(self, filename, comment='#'):
        fileinfo = QtCore.QFileInfo(filename)
        name = fileinfo.fileName()

        airfoil = Airfoil.Airfoil(name)
        loaded = airfoil.readContour(filename, comment)

        if not loaded:
            logger.error(f'Failed to load airfoil from {filename}')
            return

        self._clearScene()
        self._addAirfoilToScene(airfoil)
        self._updateAirfoilList(name)
        self.fitAirfoilInView()
        logger.info(f'Airfoil {name} loaded')

    def _clearScene(self):
        self.parent.scene.clear()

    def _addAirfoilToScene(self, airfoil):
        airfoil.makeAirfoil()
        airfoil.addToScene(self.parent.scene)
        self.parent.airfoil = airfoil
        self.parent.airfoils.append(airfoil)

    def _updateAirfoilList(self, name):
        toolbox = self.parent.centralwidget.toolbox
        toolbox.header.setEnabled(True)
        toolbox.listwidget.setEnabled(True)
        toolbox.listwidget.addItem(name)

    @QtCore.Slot(str)
    def loadSU2(self, filename):
        comment = '%'

        try:
            with open(filename, mode='r') as f:
                lines = f.readlines()
        except IOError as error:
            # exc_info=True sends traceback to the logger
            logger.error('Failed to open file {} with error {}'.
                         format(filename, error), exc_info=True)
            return False

        # FIXME
        # FIXME complete code to read SU2 mesh files
        # FIXME
        data = [line for line in lines if comment not in line]

    @QtCore.Slot()
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

    @QtCore.Slot()
    def onViewAll(self):
        """Zoom view in order to fit all items of the scene"""

        # take all items except markers (as they are adjusted in size for view)

        rectf = self.parent.scene.itemsBoundingRect()
        self.parent.view.fitInView(rectf,
                                   aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # it is IMPORTANT that this is called after fitInView
        # adjust airfoil marker size to MARKERSIZE setting
        self.parent.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.parent.view.getSceneFromView()

    @QtCore.Slot()
    def toggleTestObjects(self):
        if self.parent.testitems:
            GraphicsTest.deleteTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView loaded')
        else:
            GraphicsTest.addTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView removed')
        self.parent.testitems = not self.parent.testitems

    @QtCore.Slot()
    def onSave(self):
        (fname, thefilter) = QtWidgets.QFileDialog. \
            getSaveFileNameAndFilter(self.parent,
                                     'Save file', '.', filter=DIALOGFILTER)
        if not fname:
            return

        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    @QtCore.Slot()
    def onSaveAs(self):
        (fname, thefilter) = QtGui. \
            QFileDialog.getSaveFileNameAndFilter(
            self.parent, 'Save file as ...', '.',
            filter=DIALOGFILTER)
        if not fname:
            return
        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    @QtCore.Slot()
    def onPrint(self):
        dialog = QtWidgets.QPrintDialog()
        if dialog.exec_() == QtGui.QDialog.Accepted:
            self.parent.editor.document().print_(dialog.printer())

    @QtCore.Slot()
    def onPreview(self):
        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        layout = QtGui.QPageLayout()
        layout.setOrientation(QtGui.QPageLayout.Landscape)
        layout.setPageSize(QtGui.QPageSize.A3)
        printer.setPageLayout(layout)

        preview = QtPrintSupport.QPrintPreviewDialog(printer, self.parent)
        preview.paintRequested.connect(self.handlePaintRequest)
        preview.exec()

    @QtCore.Slot()
    def handlePaintRequest(self, printer):
        # render QGraphicsView
        self.parent.view.render(QtGui.QPainter(printer))

    @QtCore.Slot(str)
    def toggleLogDock(self, _sender):
        """Switch message log window on/off"""

        visible = self.parent.messagedock.isVisible()
        self.parent.messagedock.setVisible(not visible)

        # update the checkbox if toggling is done via keyboard shortcut
        if _sender == 'shortcut':
            checkbox = self.parent.centralwidget.message_window_checkbox
            checkbox.setChecked(not checkbox.isChecked())

    @QtCore.Slot()
    def onBlockMesh(self):
        pass

    @QtCore.Slot(str)
    def getAirfoilByName(self, name):
        for airfoil in self.parent.airfoils:
            if airfoil.name == name:
                return airfoil
        return None

    @QtCore.Slot()
    def removeAirfoil(self, name=None):
        """Remove all selected airfoils from the scene"""

        # look also at toolbox listwidget
        centralwidget = self.parent.centralwidget
        listwidget = centralwidget.toolbox.listwidget

        # the name parameter is only set when coming from listwidget
        # and the deleting is done via DEL key
        if name:
            airfoil = self.getAirfoilByName(name)
        # FIXME:
        # FIXME: this does not work
        # FIXME: needs to delete the selected airfoil from the listwidget
        # FIXME:
        elif len(listwidget.selectedItems()) > 0:
            name = listwidget.selectedItems()[0].text()
            airfoil = self.getAirfoilByName(name)
        elif self.parent.airfoil:
            airfoil = self.parent.airfoil
        else:
            print('No airfoil selected for deletion')
            return

        # remove airfoil from the list in the list widget
        self.parent.airfoils.remove(airfoil)

        # remove from scene only if active airfoil was chosen
        if airfoil.name == self.parent.airfoil.name:
            # removes all items from the scene (polygon, chord, mesh, etc.)
            self.parent.scene.clear()

        # remove also listwidget entry
        itms = listwidget.findItems(
            self.parent.airfoil.name, QtCore.Qt.MatchExactly)
        for itm in itms:
            row = listwidget.row(itm)
            listwidget.takeItem(row)

        # fit all remaining scene items into the view
        self.onViewAll()

    @QtCore.Slot(str)
    def onMessage(self, msg):
        # move cursor to the end before writing new message
        # so in case text inside the log window was selected before
        # the new text is pastes correct
        self.parent.messages.moveCursor(QtGui.QTextCursor.End)
        self.parent.messages.append(msg)

    @QtCore.Slot()
    def onExit(self):
        sys.exit(QtWidgets.QApplication.exit())

    @QtCore.Slot()
    def onCalculator(self):
        pass

    @QtCore.Slot()
    def onBackground(self):
        if self.parent.view.viewstyle == 'gradient':
            self.parent.view.viewstyle = 'solid'
        else:
            self.parent.view.viewstyle = 'gradient'

        self.parent.view.setBackground(self.parent.view.viewstyle)

    @QtCore.Slot()
    def onLevelChanged(self):
        """Change size of message window when floating """
        if self.parent.messagedock.isFloating():
            self.parent.messagedock.resize(600, 300)

    @QtCore.Slot()
    def onTextChanged(self):
        """Move the scrollbar in the message log-window to the bottom.
        So latest messages are always in the view.
        """
        vbar = self.parent.messages.verticalScrollBar()
        if vbar:
            vbar.triggerAction(QtWidgets.QAbstractSlider.SliderToMaximum)

    @QtCore.Slot()
    def onTabChanged(self):
        """Sync tabs and toolboxes """
        tabs = self.parent.centralwidget.tabs
        tab_text = self.parent.centralwidget.tabs.tabText(tabs.currentIndex())
        toolbox = self.parent.centralwidget.toolbox

        if tab_text == 'Airfoil Viewer':
            toolbox.setCurrentIndex(toolbox.tb1)
        if tab_text == 'Contour Analysis':
            toolbox.setCurrentIndex(toolbox.tb3)

    @QtCore.Slot(str)
    def messageBox(self, message):
        QtWidgets.QMessageBox. \
            information(self.parent, 'Information',
                        message, QtWidgets.QMessageBox.Ok)

    @QtCore.Slot()
    def onKeyBd(self):
        # automatically populate shortcuts from PMenu.xml
        text = '<table> \
                '
        for eachMenu in self.parent.menudata:
            for pulldown in eachMenu[1]:
                if pulldown[2]:
                    if self.parent.platform == 'Darwin':
                        shortcut = pulldown[2].replace('CTRL', 'CMD')
                        # print(pulldown[2], '...', shortcut)
                    else:
                        shortcut = pulldown[2]
                    text += f' \
                        <tr> \
                            <td>{shortcut}</td> \
                            <hr> \
                            <td colspan=5></td> \
                            <td>{pulldown[1]}</td> \
                            <hr> \
                        </tr> \
                        '
        text += '</table>'
 
        textedit = QtWidgets.QTextEdit()
        textedit.setReadOnly(True)
        # textedit.setStyleSheet('font-family: Courier; font-size: 14px; ')
        textedit.setHtml(text)

        # buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        buttons = QtWidgets.QDialogButtonBox.Ok
        buttonBox = QtWidgets.QDialogButtonBox(buttons)
        
        # make a dialog to carry the textedit and button widget
        dlg = QtWidgets.QDialog(self.parent)
        dlg.setWindowTitle('Keyboard shortcuts')
        dlg.setFixedSize(800, 900)
        buttonBox.accepted.connect(dlg.accept)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(textedit)
        layout.addWidget(buttonBox)
        dlg.setLayout(layout)
        dlg.exec_()

    @QtCore.Slot()
    def runCommands(self):
        '''Automate different actions by simulation of button clicks
        Call directly a function or
        using click or animateClick on the respective widget
        # self.parent.centralwidget.toolbox.splineButton.click
        # self.parent.centralwidget.toolbox.splineButton.animateClick

        This feature is mainly used during tesing, as it runs the whole workflow
        automatically.
        
        '''        
        # load the predefined airfoil
        self.onOpenPredefined()
        # spline and refine the contour with defaults
        self.parent.centralwidget.toolbox.spline_and_refine()
        # add a blunt trailing edge with defaults
        self.parent.centralwidget.toolbox.makeTrailingEdge()
        # generate a mesh using defaults
        self.parent.centralwidget.toolbox.generateMesh()
        # export the mesh
        # self.parent.centralwidget.toolbox.exportMesh()

    @QtCore.Slot()
    def onHelpOnline(self):
        webbrowser.open('http://pyaero.readthedocs.io/en/latest/')

    @QtCore.Slot()
    def onHelpPDF(self):
        webbrowser.open('https://pyaero.readthedocs.io/_/downloads/en/latest/pdf/')

    @QtCore.Slot()
    def onAboutQt(self):
        QtWidgets.QApplication.aboutQt()

    @QtCore.Slot()
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
                  + "Numpy: %s" % (np.__version__) + "<br>"
                  + "Scipy: %s" % (scipy.__version__) + "<br>"
                  + "Qt for Python: %s" % (PySide6.__version__) + "<br>"
                  + "Qt: %s" % (PySide6.QtCore.__version__)
                  )
