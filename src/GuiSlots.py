import sys
import webbrowser
import html
from pathlib import Path
import numpy as np
import scipy

import PySide6
from PySide6 import QtGui, QtCore, QtWidgets, QtPrintSupport

import PyAero
import Airfoil
import FileDialog
import FileOperations
import Icons
import Mesh as MeshModel
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

    def __init__(self, mainwindow=None):
        """Constructor for Slots class"""

        # MainWindow instance
        self.mw = mainwindow or get_main_window()

    @QtCore.Slot()
    def onOpen(self):
        """Open an airfoil contour or a future mesh import target."""
        file_dialog = FileDialog.Dialog()
        filename, _ = file_dialog.open_filename(
            title='Open File',
            filter=self.openFileDialogFilter(),
        )

        if not filename:
            logger.info('No file selected. Nothing opened.')
            return

        self.openFile(filename)

    def openFileDialogFilter(self):
        contour_filter = FileOperations.CONTOUR_FILTER
        mesh_filter = MeshModel.MeshImportRegistry.qt_file_dialog_filter()
        if not mesh_filter:
            return contour_filter
        return f'{contour_filter};;{mesh_filter}'

    @QtCore.Slot(str)
    def openFile(self, filename):
        if MeshModel.MeshImportRegistry.can_import(filename):
            return self.loadMesh(filename)
        if Path(filename).suffix.lower() not in FileOperations.SUPPORTED_AIRFOIL_EXTENSIONS:
            message = f'Unsupported file type: {Path(filename).name}'
            logger.warning('%s (%s)', message, filename)
            self.messageBox(message)
            return None
        return self.loadAirfoil(filename)

    @QtCore.Slot()
    def onOpenPredefined(self):
        self.loadAirfoil(self.mw.DEFAULT_AIRFOIL)

    @QtCore.Slot(str, str)
    def loadAirfoil(self, filename, comment='#'):
        airfoil = Airfoil.Airfoil.from_file(
            filename,
            comment=comment,
            mainwindow=self.mw,
        )
        if airfoil is None:
            logger.error(f'Failed to load airfoil from {filename}')
            self.messageBox(f'Failed to load airfoil:\n{filename}')
            return

        self._registerAirfoil(airfoil)
        self.activateAirfoil(airfoil)
        logger.info(f'Airfoil {airfoil.name} loaded')

    def _clearScene(self):
        self.mw.scene.clear()

    def _addAirfoilToScene(self, airfoil):
        airfoil.makeAirfoil()
        airfoil.addToScene(self.mw.scene)
        self.mw.airfoil = airfoil

    def _registerAirfoil(self, airfoil):
        self.mw.airfoils = [airfoil]
        toolbox = self.mw.mainArea.toolbox
        toolbox.refreshAirfoilLibrary()
        toolbox.selectAirfoilLibraryPath(getattr(airfoil, 'source_path', None))
        toolbox.refreshWorkflowState()

    def _removeAirfoilListEntry(self, name):
        toolbox = self.mw.mainArea.toolbox
        toolbox.refreshAirfoilLibrary()
        toolbox.selectAirfoilLibraryPath(None)
        toolbox.refreshWorkflowState()

    def _selectAirfoilInList(self, airfoil):
        self.mw.mainArea.toolbox.selectAirfoilLibraryPath(
            getattr(airfoil, 'source_path', None)
        )

    def activateAirfoil(self, airfoil):
        if airfoil is None:
            return

        self._clearScene()
        self._addAirfoilToScene(airfoil)
        self._selectAirfoilInList(airfoil)
        self.mw.mainArea.toolbox.refreshWorkflowState()
        self.fitAirfoilInView()

    def _expandedRect(self, rectf, padding_factor=1.0):
        rect = QtCore.QRectF(rectf)
        if rect.isNull() or padding_factor == 1.0:
            return rect

        center = rect.center()
        rect.setWidth(rect.width() * padding_factor)
        rect.setHeight(rect.height() * padding_factor)
        rect.moveCenter(center)
        return rect

    def _fitViewToRect(self, rectf, padding_factor=1.0):
        rect = self._expandedRect(rectf, padding_factor=padding_factor)
        if rect.isNull():
            return

        self.mw.view.fitInView(rect, QtCore.Qt.KeepAspectRatio)
        self.mw.view.adjustMarkerSize()
        self.mw.view.getSceneFromView()

    def _airfoilContourRect(self, airfoil):
        contour = airfoil.current_contour(prefer_spline=True)
        if contour is None:
            return QtCore.QRectF()

        x_values, y_values = contour
        min_x = float(min(x_values))
        max_x = float(max(x_values))
        min_y = float(min(y_values))
        max_y = float(max(y_values))
        return QtCore.QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    @QtCore.Slot(str)
    def loadMesh(self, filename):
        try:
            return MeshModel.MeshData.from_file(filename)
        except NotImplementedError as error:
            logger.info(str(error))
            self.messageBox(str(error))
            return None
        except (OSError, ValueError) as error:
            logger.error(
                'Failed to load mesh file %s with error %s',
                filename,
                error,
                exc_info=True,
            )
            self.messageBox(f'Failed to load mesh file:\n{filename}\n\n{error}')
            return None

    @QtCore.Slot(str)
    def loadSU2(self, filename):
        return self.loadMesh(filename)

    @QtCore.Slot()
    def fitAirfoilInView(self):

        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            return

        rect = self._airfoilContourRect(airfoil)
        if rect.isNull():
            return
        self._fitViewToRect(rect, padding_factor=1.04)

    @QtCore.Slot()
    def onViewAll(self):
        """Zoom view in order to fit all items of the scene"""

        # take all items except markers (as they are adjusted in size for view)
        self._fitViewToRect(self.mw.scene.itemsBoundingRect())


    @QtCore.Slot()
    def onSave(self):
        self.saveCurrentAirfoilContour(title='Save Contour')

    @QtCore.Slot()
    def onSaveAs(self):
        self.saveCurrentAirfoilContour(title='Save Contour As')

    def saveCurrentAirfoilContour(self, title='Save Contour As'):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            self.messageBox('No airfoil loaded.')
            return None

        filename = FileOperations.choose_contour_save_filename(
            airfoil,
            title=title,
            mainwindow=self.mw,
        )
        if not filename:
            logger.info('No file selected. Nothing saved.')
            return None

        return FileOperations.write_contour(
            airfoil,
            filename,
            prefer_spline=True,
            mainwindow=self.mw,
        )

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

    def toggleLogDock(self, _sender=None):
        """Switch message log window on/off"""

        # check if self.mw.messagedock exists
        if not hasattr(self.mw, 'messagedock'):
            return
        visible = self.mw.messagedock.isVisible()
        if hasattr(self.mw.mainArea, 'setMessagePanelVisible'):
            self.mw.mainArea.setMessagePanelVisible(not visible)
        else:
            self.mw.messagedock.setVisible(not visible)

        # update the checkbox if toggling is done via keyboard shortcut
        if _sender == 'shortcut':
            # variable message_window_checkbox is defined in the viewer controls panel
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
        """Remove the current working airfoil."""

        if name:
            airfoil = self.getAirfoilByName(name)
        elif self.mw.airfoil:
            airfoil = self.mw.airfoil
        else:
            logger.info('No airfoil selected for deletion')
            return

        if airfoil is None:
            logger.info('No matching airfoil found for deletion')
            return

        is_active_airfoil = airfoil == self.mw.airfoil

        if airfoil in self.mw.airfoils:
            self.mw.airfoils.remove(airfoil)

        if is_active_airfoil:
            self.mw.scene.clear()
            self.mw.airfoil = None
        self._removeAirfoilListEntry(airfoil.name)

        if is_active_airfoil:
            return

        # keep the current scene and view unchanged when removing
        # a non-active airfoil entry
        self.mw.mainArea.toolbox.refreshWorkflowState()

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
        if hasattr(self.mw.messagedock, 'isFloating') and self.mw.messagedock.isFloating():
            self.mw.messagedock.resize(600, 300)

    @QtCore.Slot()
    def onTextChanged(self):
        """Move the scrollbar in the message log-window to the bottom.
        So latest messages are always in the view.
        """
        vbar = self.mw.messages.verticalScrollBar()
        if vbar:
            vbar.triggerAction(QtWidgets.QAbstractSlider.SliderToMaximum)

    @QtCore.Slot(int)
    def onTabChanged(self, _index=None):
        """Sync tabs and toolboxes """
        tabs = self.mw.mainArea.tabs
        self.mw.mainArea.updateWorkspaceChrome(tabs.currentIndex())
        toolbox = self.mw.mainArea.toolbox

        if tabs.currentIndex() == self.mw.mainArea.WORKSPACE_ANALYSIS_INDEX:
            toolbox.setCurrentIndex(toolbox.tb3)
        elif toolbox.currentIndex() == toolbox.tb3:
            toolbox.setCurrentIndex(toolbox.lastWorkflowIndex())

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
    def onIconPreview(self):
        import IconPreview

        dialog = IconPreview.IconPreviewDialog(self.mw)
        dialog.exec()

    def _readBundledText(self, relative_path, fallback=''):
        root = Path(__file__).resolve().parent.parent
        try:
            return (root / relative_path).read_text(encoding='utf-8').strip()
        except OSError:
            return fallback

    def _addAboutStat(self, layout, row, label, value):
        key = QtWidgets.QLabel(label)
        key.setObjectName('aboutStatKey')
        layout.addWidget(key, row, 0)

        val = QtWidgets.QLabel(value)
        val.setObjectName('aboutStatValue')
        val.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(val, row, 1)

    def _aboutDetailsHtml(self):
        mit_license = self._readBundledText(
            'LICENSE',
            'PyAero is distributed under the MIT License.',
        )
        lucide_license = self._readBundledText(
            'resources/Icons/lucide/LICENSE',
            'Lucide icons are distributed under the ISC License.',
        )

        return f"""
            <html>
                <head>
                    <style>
                        body {{
                            color: #243447;
                            font-family: "SF Pro Text", "Segoe UI", sans-serif;
                            font-size: 13px;
                            line-height: 1.5;
                        }}
                        h2 {{
                            color: #1b3148;
                            font-size: 17px;
                            margin: 0 0 8px 0;
                        }}
                        p {{
                            margin: 0 0 12px 0;
                        }}
                        a {{
                            color: #2f5f93;
                            text-decoration: none;
                        }}
                        .section {{
                            margin-top: 14px;
                        }}
                        .license-card {{
                            margin-top: 14px;
                            padding: 14px;
                            border: 1px solid #d7e1ec;
                            border-radius: 12px;
                            background: #f8fbfd;
                        }}
                        .license-title {{
                            color: #17324a;
                            font-size: 14px;
                            font-weight: 700;
                            margin-bottom: 4px;
                        }}
                        .license-subtitle {{
                            color: #66788c;
                            font-size: 12px;
                            font-weight: 600;
                            text-transform: uppercase;
                            letter-spacing: 0.06em;
                            margin-bottom: 10px;
                        }}
                        pre {{
                            margin: 0;
                            white-space: pre-wrap;
                            font-family: "SF Mono", "Menlo", "Monaco", monospace;
                            font-size: 12px;
                            color: #324558;
                        }}
                    </style>
                </head>
                <body>
                    <h2>What PyAero Does</h2>
                    <p><b>{html.escape(PyAero.__appname__)}</b> is used for 2D CFD mesh generation and contour analysis for airfoils.</p>
                    <p>Questions or feedback: <a href="mailto:{html.escape(PyAero.__email__)}">{html.escape(PyAero.__email__)}</a></p>

                    <div class="section">
                        <h2>Licenses</h2>
                        <p>The following bundled license texts apply to this build.</p>
                    </div>

                    <div class="license-card">
                        <div class="license-title">PyAero</div>
                        <div class="license-subtitle">MIT License</div>
                        <pre>{html.escape(mit_license)}</pre>
                    </div>

                    <div class="license-card">
                        <div class="license-title">Lucide Icons</div>
                        <div class="license-subtitle">ISC License and Bundled Notices</div>
                        <pre>{html.escape(lucide_license)}</pre>
                    </div>
                </body>
            </html>
        """

    @QtCore.Slot()
    def onAbout(self):
        dialog = QtWidgets.QDialog(self.mw)
        dialog.setWindowTitle('About ' + PyAero.__appname__)
        dialog.setWindowIcon(self.mw.windowIcon())
        dialog.setModal(True)
        dialog.resize(760, 720)
        dialog.setMinimumSize(700, 620)
        dialog.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        dialog.setStyleSheet(
            """
            QDialog {
                background: #eef3f8;
            }
            QFrame#aboutHero {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #edf5fb
                );
                border: 1px solid #d6e3ef;
                border-radius: 18px;
            }
            QLabel#aboutEyebrow {
                color: #6b7f92;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel#aboutTitle {
                color: #182c41;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#aboutSubtitle {
                color: #4d6072;
                font-size: 14px;
                line-height: 1.4em;
            }
            QLabel#aboutBadge {
                background: #ffffff;
                border: 1px solid #d6e3ef;
                border-radius: 999px;
                color: #24415e;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            }
            QFrame#aboutCard {
                background: #ffffff;
                border: 1px solid #d6e0ea;
                border-radius: 16px;
            }
            QLabel#aboutSectionTitle {
                color: #5d7287;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QLabel#aboutStatKey {
                color: #627789;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#aboutStatValue {
                color: #1d3148;
                font-size: 12px;
                font-weight: 600;
            }
            QTextBrowser#aboutDetails {
                background: #ffffff;
                border: 1px solid #d6e0ea;
                border-radius: 16px;
                padding: 10px;
            }
            QDialogButtonBox QPushButton {
                background: #ffffff;
                border: 1px solid #c7d5e3;
                border-radius: 10px;
                color: #1e334b;
                font-weight: 600;
                min-width: 96px;
                padding: 8px 14px;
            }
            QDialogButtonBox QPushButton:hover {
                background: #f4f8fb;
                border-color: #9eb8d4;
            }
            """
        )

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        hero = QtWidgets.QFrame()
        hero.setObjectName('aboutHero')
        hero_layout = QtWidgets.QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setSpacing(18)

        logo = QtWidgets.QLabel()
        logo.setFixedSize(84, 84)
        logo.setAlignment(QtCore.Qt.AlignCenter)
        logo_pixmap = Icons.app_icon().pixmap(72, 72)
        if not logo_pixmap.isNull():
            logo.setPixmap(
                logo_pixmap.scaled(
                    72,
                    72,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        hero_layout.addWidget(logo, 0, QtCore.Qt.AlignTop)

        hero_text = QtWidgets.QVBoxLayout()
        hero_text.setSpacing(8)

        eyebrow = QtWidgets.QLabel('2D Airfoil CFD Meshes')
        eyebrow.setObjectName('aboutEyebrow')
        hero_text.addWidget(eyebrow)

        title = QtWidgets.QLabel(PyAero.__appname__)
        title.setObjectName('aboutTitle')
        hero_text.addWidget(title)

        subtitle = QtWidgets.QLabel(
            'Modern airfoil contour analysis and 2D CFD meshing in a focused desktop workspace.'
        )
        subtitle.setObjectName('aboutSubtitle')
        subtitle.setWordWrap(True)
        hero_text.addWidget(subtitle)

        badge_row = QtWidgets.QHBoxLayout()
        badge_row.setSpacing(8)
        for text in (
            f'Version {PyAero.__version__}',
            'PyAero MIT',
            'Lucide ISC',
        ):
            badge = QtWidgets.QLabel(text)
            badge.setObjectName('aboutBadge')
            badge_row.addWidget(badge)
        badge_row.addStretch(1)
        hero_text.addLayout(badge_row)

        hero_layout.addLayout(hero_text, 1)
        layout.addWidget(hero)

        stats_card = QtWidgets.QFrame()
        stats_card.setObjectName('aboutCard')
        stats_layout = QtWidgets.QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(18, 18, 18, 18)
        stats_layout.setSpacing(12)

        stats_title = QtWidgets.QLabel('Runtime')
        stats_title.setObjectName('aboutSectionTitle')
        stats_layout.addWidget(stats_title)

        stats_grid = QtWidgets.QGridLayout()
        stats_grid.setHorizontalSpacing(20)
        stats_grid.setVerticalSpacing(10)
        self._addAboutStat(stats_grid, 0, 'Contact', PyAero.__email__)
        self._addAboutStat(stats_grid, 1, PyAero.__appname__, PyAero.__version__)
        self._addAboutStat(stats_grid, 2, 'Python', sys.version.split()[0])
        self._addAboutStat(stats_grid, 3, 'NumPy', np.__version__)
        self._addAboutStat(stats_grid, 4, 'SciPy', scipy.__version__)
        self._addAboutStat(stats_grid, 5, 'Qt for Python', PySide6.__version__)
        self._addAboutStat(stats_grid, 6, 'Qt', PySide6.QtCore.__version__)
        stats_grid.setColumnStretch(1, 1)
        stats_layout.addLayout(stats_grid)
        layout.addWidget(stats_card)

        details = QtWidgets.QTextBrowser()
        details.setObjectName('aboutDetails')
        details.setOpenExternalLinks(True)
        details.setReadOnly(True)
        details.setHtml(self._aboutDetailsHtml())
        layout.addWidget(details, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()
