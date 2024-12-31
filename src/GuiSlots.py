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
from Utils import get_main_window
import logging
logger = logging.getLogger(__name__)


class Slots:
    """This class handles all callback routines for GUI actions

    PyQt uses signals and slots for GUI events and their respective
    handlers/callbacks.

    It is mandatory to decorate the callback functions with the
    @QtCore.Slot() decorator.
    """

    def __init__(self):
        """Constructor for Slots class"""

        # MainWindow instance
        self.mw = get_main_window()

    @QtCore.Slot()
    def onOpen(self):
        """Summary

        Returns:
            TYPE: Description
        """
        file_dialog = FileDialog.Dialog()
        file_dialog.setFilter(self.mw.DIALOG_FILTER)
        filename, _ = file_dialog.open_filename()

        if not filename:
            logger.info('No file selected. Nothing saved.')
            return

        if 'su2' in filename:
            self.loadSU2(filename)
            return

        self.loadAirfoil(filename)

    @QtCore.Slot()
    def onOpenPredefined(self):
        self.loadAirfoil(self.mw.DEFAULT_AIRFOIL)

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
        self.mw.scene.clear()

    def _addAirfoilToScene(self, airfoil):
        airfoil.makeAirfoil()
        airfoil.addToScene(self.mw.scene)
        self.mw.airfoil = airfoil
        self.mw.airfoils.append(airfoil)

    def _updateAirfoilList(self, name):
        toolbox = self.mw.mainArea.toolbox
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

        if len(self.mw.airfoils) == 0:
            return

        # get bounding rect in scene coordinates
        item = self.mw.airfoil.contourPolygon
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

        self.mw.view.fitInView(rf,
                                   aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # it is IMPORTANT that this is called after fitInView
        # adjust airfoil marker size to MARKER_SIZE setting
        self.mw.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.mw.view.getSceneFromView()

    @QtCore.Slot()
    def onViewAll(self):
        """Zoom view in order to fit all items of the scene"""

        # take all items except markers (as they are adjusted in size for view)

        rectf = self.mw.scene.itemsBoundingRect()
        self.mw.view.fitInView(rectf,
                                   aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # it is IMPORTANT that this is called after fitInView
        # adjust airfoil marker size to MARKER_SIZE setting
        self.mw.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.mw.view.getSceneFromView()


    @QtCore.Slot()
    def onSave(self):
        (fname, thefilter) = QtWidgets.QFileDialog. \
            getSaveFileNameAndFilter(self.mw,
                                     'Save file', '.', filter=self.mw.DIALOG_FILTER)
        if not fname:
            return

        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    @QtCore.Slot()
    def onSaveAs(self):
        (fname, thefilter) = QtGui. \
            QFileDialog.getSaveFileNameAndFilter(
            self.mw, 'Save file as ...', '.',
            filter=self.mw.DIALOG_FILTER)
        if not fname:
            return
        with open(fname, 'w') as f:
            f.write('This test worked for me ...')

    @QtCore.Slot()
    def onPrint(self):
        dialog = QtWidgets.QPrintDialog()
        if dialog.exec_() == QtGui.QDialog.Accepted:
            self.mw.editor.document().print_(dialog.printer())

    @QtCore.Slot()
    def onPreview(self):
        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        layout = QtGui.QPageLayout()
        layout.setOrientation(QtGui.QPageLayout.Landscape)
        layout.setPageSize(QtGui.QPageSize.A3)
        printer.setPageLayout(layout)

        preview = QtPrintSupport.QPrintPreviewDialog(printer, self.mw)
        preview.paintRequested.connect(self.handlePaintRequest)
        preview.exec()

    @QtCore.Slot()
    def handlePaintRequest(self, printer):
        # render QGraphicsView
        self.mw.view.render(QtGui.QPainter(printer))

    @QtCore.Slot(str)
    def toggleLogDock(self, _sender):
        """Switch message log window on/off"""

        # check if self.mw.messagedock exists
        if not hasattr(self.mw, 'messagedock'):
            return
        visible = self.mw.messagedock.isVisible()
        self.mw.messagedock.setVisible(not visible)

        # update the checkbox if toggling is done via keyboard shortcut
        if _sender == 'shortcut':
            # variable message_window_checkbox is defined in viewingOptions()
            checkbox = self.mw.mainArea.message_window_checkbox
            checkbox.setChecked(not checkbox.isChecked())

    @QtCore.Slot(str)
    def getAirfoilByName(self, name):
        for airfoil in self.mw.airfoils:
            if airfoil.name == name:
                return airfoil
        return None

    @QtCore.Slot()
    def removeAirfoil(self, name=None):
        """Remove all selected airfoils from the scene"""

        # look also at toolbox listwidget
        mainArea = self.mw.mainArea
        listwidget = mainArea.toolbox.listwidget

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
        elif self.mw.airfoil:
            airfoil = self.mw.airfoil
        else:
            print('No airfoil selected for deletion')
            return

        # remove airfoil from the list in the list widget
        self.mw.airfoils.remove(airfoil)

        # remove from scene only if active airfoil was chosen
        if airfoil.name == self.mw.airfoil.name:
            # removes all items from the scene (polygon, chord, mesh, etc.)
            self.mw.scene.clear()

        # remove also listwidget entry
        itms = listwidget.findItems(
            self.mw.airfoil.name, QtCore.Qt.MatchExactly)
        for itm in itms:
            row = listwidget.row(itm)
            listwidget.takeItem(row)

        # fit all remaining scene items into the view
        self.onViewAll()

    @QtCore.Slot(str)
    def onMessage(self, msg):
        # Move cursor to the end before writing the new message
        # so in case text inside the log window was selected before
        # the new text is pasted correctly
        self.mw.messages.moveCursor(QtGui.QTextCursor.End)
        self.mw.messages.append(msg)

    @QtCore.Slot()
    def onExit(self):
        sys.exit(QtWidgets.QApplication.exit())

    @QtCore.Slot()
    def onCalculator(self):
        pass

    @QtCore.Slot()
    def onBackground(self):
        if self.mw.view.viewstyle == 'gradient':
            self.mw.view.viewstyle = 'solid'
        else:
            self.mw.view.viewstyle = 'gradient'

        self.mw.view.setBackground(self.mw.view.viewstyle)

    @QtCore.Slot()
    def onLevelChanged(self):
        """Change size of message window when floating """
        if self.mw.messagedock.isFloating():
            self.mw.messagedock.resize(600, 300)

    @QtCore.Slot()
    def onTextChanged(self):
        """Move the scrollbar in the message log-window to the bottom.
        So latest messages are always in the view.
        """
        vbar = self.mw.messages.verticalScrollBar()
        if vbar:
            vbar.triggerAction(QtWidgets.QAbstractSlider.SliderToMaximum)

    @QtCore.Slot()
    def onTabChanged(self):
        """Sync tabs and toolboxes """
        tabs = self.mw.mainArea.tabs
        tab_text = self.mw.mainArea.tabs.tabText(tabs.currentIndex())
        toolbox = self.mw.mainArea.toolbox

        if tab_text == 'Airfoil Viewer':
            toolbox.setCurrentIndex(toolbox.tb1)
        if tab_text == 'Contour Analysis':
            toolbox.setCurrentIndex(toolbox.tb3)

    @QtCore.Slot(str)
    def messageBox(self, message):
        QtWidgets.QMessageBox. \
            information(self.mw, 'Information',
                        message, QtWidgets.QMessageBox.Ok)

    @QtCore.Slot()
    def onKeyBd(self):
        # automatically populate shortcuts from PMenu.xml
        text = '<table> \
                '
        for eachMenu in self.mw.menudata:
            for pulldown in eachMenu[1]:
                if pulldown[2]:
                    if self.mw.platform == 'Darwin':
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
        dlg = QtWidgets.QDialog(self.mw)
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
        # self.mw.mainArea.toolbox.splineButton.click
        # self.mw.mainArea.toolbox.splineButton.animateClick

        This feature is mainly used during tesing, as it runs the whole workflow
        automatically.
        
        '''        
        # load the predefined airfoil
        self.onOpenPredefined()
        # spline and refine the contour with defaults
        self.mw.mainArea.toolbox.spline_and_refine()
        # add a blunt trailing edge with defaults
        self.mw.mainArea.toolbox.makeTrailingEdge()
        # generate a mesh using defaults
        self.mw.mainArea.toolbox.generateMesh()
        # export the mesh
        # self.mw.mainArea.toolbox.exportMesh()

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
            about(self.mw, "About " + PyAero.__appname__,
                  "<b>" + PyAero.__appname__ +
                  "</b> is used for "
                  "2D CFD mesh generation for airfoils.\
                  <br><br>"
                  "<b>" + PyAero.__appname__ + "</b> code under " +
                  PyAero.__license__ +
                  " license. (c) " +
                  PyAero.__copyright__ + "<br><br>"
                  "email to: " + PyAero.__email__ + "<br><br>"
                  + "<b>VERSIONS:</b>" + "<br>"
                  + PyAero.__appname__ + ": " + PyAero.__version__ +
                  "<br>"
                  + "Python: %s" % (sys.version.split()[0]) + "<br>"
                  + "Numpy: %s" % (np.__version__) + "<br>"
                  + "Scipy: %s" % (scipy.__version__) + "<br>"
                  + "Qt for Python: %s" % (PySide6.__version__) + "<br>"
                  + "Qt: %s" % (PySide6.QtCore.__version__)
                  )
