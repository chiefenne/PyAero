import sys
import copy
import logging
import webbrowser

import PySide2
from PySide2 import QtGui, QtCore, QtWidgets

import PyAero
import Airfoil
import GraphicsTest as gt
import IconProvider
from Settings import DIALOGFILTER, AIRFOILDATA, LOGCOLOR, DEFAULT_CONTOUR, \
                      DEFAULT_STL

logger = logging.getLogger(__name__)

getframe_expr = 'sys._getframe({}).f_code.co_name'


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
            logger.info('Error during file load: %s' % (error))
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
            # make contour, markers, chord and add everything to the scene
            airfoil.makeAirfoil()
            self.parent.airfoils.append(airfoil)
            # shift the airfoils (vertical stack) if more than one loaded
            self.shiftContours()
            # fit all airfoils into the view
            self.onViewAll()
            logger.info('Test ABCDEFG')
            logger.info('Airfoil <b><font color=%s>' % (LOGCOLOR) + name +
                            '</b> loaded')

            self.parent.centralwidget.tools.header.setEnabled(True)
            self.parent.centralwidget.tools.listwidget.setEnabled(True)
            self.parent.centralwidget.tools.listwidget.addItem(name)

    def shiftContours(self, shift=True):
        """Shifts airfoils vertically from eachother. This is done when
        more than one airfoil is loaded.

        Slots.fitAirfoilInView() takes care of this shift when fitting
        automatically the last loaded airfoil to the view.

        Args:
            shift (bool, optional): Can be used to re-align all airfoils
        """

        offset = 0.0
        for i, airfoil in enumerate(self.parent.airfoils):
            # don't shift the first airfoil
            if i == 0:
                continue
            if shift:
                delta = 0.006
                offset += self.parent.airfoils[i-1].offset[1] + \
                    abs(self.parent.airfoils[i].offset[0]) + delta

            # do the actual shift
            airfoil.contourPolygon.setPos(QtCore.QPointF(0.0, offset))

            if airfoil.contourSpline:
                # with zero shift item gets same position as parent
                airfoil.contourSpline.setPos(QtCore.QPointF(0.0, 0.0))

    # # @QtCore.pyqtSlot()
    def onPredefinedSTL(self):
        self.parent.postview.readStl(DEFAULT_STL)

    # # @QtCore.pyqtSlot()
    def fitAirfoilInView(self):

        if len(self.parent.airfoils) == 0:
            return

        nothing_selected = True
        for id, airfoil in enumerate(self.parent.airfoils):
            if airfoil.contourPolygon.isSelected():
                nothing_selected = False
                break

        if nothing_selected:
            id = 0

        # get bounding rect in scene coordinates
        item = self.parent.airfoils[id].contourPolygon
        rectf = item.boundingRect()
        rf = copy.deepcopy(rectf)

        # scale by 2% (seems to be done also by scene.itemsBoundingRect())
        # after loading a single airfoil this leads to the same zoom as
        # if onViewAll was called
        center = rf.center()

        w = 1.02 * rf.width()
        h = 1.02 * rf.height()
        rf.setWidth(w)
        rf.setHeight(h)

        # shift center of rectf
        cx = center.x()
        # not easy to understand (at least for me)
        # this is needed due to the Airfoil.shiftContours() function
        cy = center.y() + item.pos().y()
        rf.moveCenter(QtCore.QPointF(cx, cy))

        self.parent.view.fitInView(rf, aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # adjust airfoil marker size to MARKERSIZE setting
        self.parent.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.parent.view.getSceneFromView()

    # # @QtCore.pyqtSlot()
    def onViewAll(self):
        # calculates and returns the bounding rect of all items on the scene
        rectf = self.parent.scene.itemsBoundingRect()
        self.parent.view.fitInView(rectf, aspectRadioMode=QtCore.Qt.KeepAspectRatio)

        # adjust airfoil marker size to MARKERSIZE setting
        self.parent.view.adjustMarkerSize()

        # cache view to be able to keep it during resize
        self.parent.view.getSceneFromView()

    # @QtCore.pyqtSlot()
    def toggleTestObjects(self):
        if self.parent.testitems:
            gt.deleteTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView loaded')
        else:
            gt.addTestItems(self.parent.scene)
            logger.info('Test items for GraphicsView removed')
        self.parent.testitems = not self.parent.testitems

    # @QtCore.pyqtSlot()
    def onSave(self):
        (fname, thefilter) = QtGui.QFileDialog. \
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

        print('I am toggleLogDock:')
        print('This is _sender:', _sender)
        
        visible = self.parent.messagedock.isVisible()
        self.parent.messagedock.setVisible(not visible)

        # update the checkbox if toggling is done via keyboard shortcut
        if _sender == 'shortcut':
           checkbox = self.parent.centralwidget.tools.cb1
           checkbox.setChecked(not checkbox.isChecked())

    # @QtCore.pyqtSlot()
    def onBlockMesh(self):
        pass

    # @QtCore.pyqtSlot()
    def removeAirfoil(self):
        """Remove all selected airfoils from the scene"""
        removed = list()
        for airfoil in self.parent.airfoils:
            if airfoil.contourPolygon.isSelected():
                removed.append(airfoil)
                # remove from scene
                self.parent.scene.removeItem(airfoil.contourPolygon)
                logger.info('Airfoil <b><font color=%s>' % (LOGCOLOR) +
                                airfoil.name + '</b> removed')

                # remove from listwidget
                centralwidget = self.parent.centralwidget
                lw = centralwidget.tools.listwidget
                itms = lw.findItems(airfoil.name, QtCore.Qt.MatchExactly)
                for itm in itms:
                    row = lw.row(itm)
                    lw.takeItem(row)

        # remove from list of airfoils
        for r in removed:
            self.parent.airfoils.remove(r)

        # re-shift everything
        self.shiftContours(shift=True)

        # fit all airfoils into the view
        self.onViewAll()

    def onMessage(self, msg):
        # move cursor to the end before writing new message
        # so in case text inside the log window was selected before
        # the new text is pastes correct
        self.parent.messages.moveCursor(QtGui.QTextCursor.End)
        self.parent.messages.insertHtml(msg)

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
        tab = self.parent.centralwidget.tabs.currentIndex()
        self.parent.centralwidget.tools.setCurrentIndex(tab)

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
        QtGui.QMessageBox. \
            about(self.parent, "About " + PyAero.__appname__,
                  "<b>" + PyAero.__appname__ +
                  "</b> is used for "
                  "2D airfoil contour analysis and CFD mesh generation.\
                  <br><br>"
                  "<b>" + PyAero.__appname__ + "</b> code under " +
                  PyAero.__license__ +
                  " license. (c) " +
                  PyAero.__copyright__ + "<br><br>"
                  "email to: " + PyAero.__email__ + "<br>"
                  "Twitter: <a href='http://twitter.com/chiefenne'>\
                  @chiefenne</a><br><br>"
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
