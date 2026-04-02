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
import PrintLayout
import UiExport
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
        self._current_print_layout_options = None
        self._current_print_airfoil = None

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
        airfoil = self._activeAirfoilForPrint()
        if airfoil is None:
            return

        options = self._promptPrintLayout(airfoil)
        if options is None:
            return

        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        PrintLayout.configure_printer_for_layout(printer, options)

        dialog = QtPrintSupport.QPrintDialog(printer, self.mw)
        dialog.setWindowTitle('Print Airfoil Drawing')
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        self._current_print_airfoil = airfoil
        self._current_print_layout_options = options
        self.handlePaintRequest(printer)

    @QtCore.Slot()
    def onPreview(self):
        airfoil = self._activeAirfoilForPrint()
        if airfoil is None:
            return

        options = self._promptPrintLayout(airfoil)
        if options is None:
            return

        printer = QtPrintSupport.QPrinter(QtPrintSupport.QPrinter.HighResolution)
        PrintLayout.configure_printer_for_layout(printer, options)

        self._current_print_airfoil = airfoil
        self._current_print_layout_options = options
        preview = QtPrintSupport.QPrintPreviewDialog(printer, self.mw)
        preview.paintRequested.connect(self.handlePaintRequest)
        preview.exec()

    @QtCore.Slot()
    def handlePaintRequest(self, printer):
        airfoil = self._current_print_airfoil or getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            return

        options = PrintLayout.default_print_layout_options(
            airfoil,
            previous=self._current_print_layout_options,
        )
        renderer = PrintLayout.AirfoilPrintRenderer()

        painter = QtGui.QPainter(printer)
        try:
            renderer.render(painter, printer, airfoil, self.mw.view, options)
        except ValueError as error:
            logger.error(
                'Failed to render print layout for %s: %s',
                getattr(airfoil, 'name', 'airfoil'),
                error,
                exc_info=True,
            )
            self.messageBox(str(error))
        finally:
            painter.end()

    def _activeAirfoilForPrint(self):
        airfoil = getattr(self.mw, 'airfoil', None)
        if airfoil is None:
            self.messageBox('No airfoil loaded.')
        return airfoil

    def _promptPrintLayout(self, airfoil):
        options = self._current_print_layout_options
        if options is not None:
            options = PrintLayout.clone_print_layout_options(options)

        dialog = PrintLayout.PrintLayoutDialog(
            airfoil,
            options=options,
            parent=self.mw,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        return dialog.selected_options()

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

        checkbox = getattr(self.mw.mainArea, 'message_window_checkbox', None)
        if checkbox is not None:
            blocker = QtCore.QSignalBlocker(checkbox)
            checkbox.setChecked(not visible)
            del blocker

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
            self.mw.mainArea.resetAirfoilViewControls()
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
    def onSettings(self):
        dialog = self._buildSettingsDialog()
        dialog.exec()

    @QtCore.Slot()
    def onBackground(self):
        if self.mw.view.viewstyle == 'gradient':
            self.mw.view.viewstyle = 'solid'
        else:
            self.mw.view.viewstyle = 'gradient'

        self.mw.view.setBackground(self.mw.view.viewstyle)

    @QtCore.Slot()
    def onCycleWindowSize(self):
        self.mw.cycleWindowSizePreset()

    @QtCore.Slot()
    def onWindowPreset1(self):
        self.mw.applyWindowSizePreset(1)

    @QtCore.Slot()
    def onWindowPreset2(self):
        self.mw.applyWindowSizePreset(2)

    @QtCore.Slot()
    def onWindowPreset3(self):
        self.mw.applyWindowSizePreset(3)

    @QtCore.Slot()
    def onExportUiCaptureSet(self):
        dialog = FileDialog.Dialog(self.mw)
        directory = dialog.choose_directory(
            title='Select Folder For Complete UI Export'
        )
        if not directory:
            logger.info('No folder selected. Complete UI export canceled.')
            return

        output_dir = Path(directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = []
        skipped = []
        self._exportUiCaptureSet(output_dir, exported, skipped)

        summary = f'Exported {len(exported)} UI capture(s) to:\n{output_dir}'
        if skipped:
            summary += '\n\nSkipped:\n' + '\n'.join(skipped)
        self.messageBox(summary)

    @QtCore.Slot()
    def onExportCurrentWorkflowPanel(self):
        toolbox = getattr(self.mw.mainArea, 'toolbox', None)
        if toolbox is None or toolbox.currentIndex() < 0:
            self.messageBox('No workflow panel is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=toolbox.page_card,
            default_name=self._workflowPanelExportFilename(toolbox),
            dialog_title='Export Workflow Panel As',
            rounded_radius=12.0,
            success_label='Workflow panel',
        )

    @QtCore.Slot()
    def onExportActiveAirfoilCard(self):
        toolbox = getattr(self.mw.mainArea, 'toolbox', None)
        if toolbox is None:
            self.messageBox('No active airfoil card is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=toolbox.summary_card,
            default_name='active_airfoil_card.png',
            dialog_title='Export Active Airfoil Card As',
            rounded_radius=12.0,
            success_label='Active airfoil card',
        )

    @QtCore.Slot()
    def onExportWorkflowNavigation(self):
        toolbox = getattr(self.mw.mainArea, 'toolbox', None)
        if toolbox is None:
            self.messageBox('No workflow navigation card is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=toolbox.workflow_card,
            default_name='workflow_navigation.png',
            dialog_title='Export Workflow Navigation As',
            rounded_radius=12.0,
            success_label='Workflow navigation',
        )

    @QtCore.Slot()
    def onExportMessagePanel(self):
        panel = getattr(self.mw.mainArea, 'message_panel', None)
        if panel is None:
            self.messageBox('No message panel is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=panel,
            default_name='message_panel.png',
            dialog_title='Export Message Panel As',
            rounded_radius=8.0,
            success_label='Message panel',
        )

    @QtCore.Slot()
    def onExportViewerControlsPanel(self):
        panel = getattr(self.mw.mainArea, 'viewer_controls_panel', None)
        if panel is None:
            self.messageBox('No viewer controls panel is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=panel,
            default_name='viewer_controls_panel.png',
            dialog_title='Export Viewer Controls Panel As',
            rounded_radius=8.0,
            success_label='Viewer controls panel',
        )

    @QtCore.Slot()
    def onExportCanvasScreenshot(self):
        widget, default_name, label = self._currentCanvasExportTarget()
        if widget is None:
            self.messageBox('No canvas is available yet.')
            return

        UiExport.export_widget_as_png(
            mainwindow=self.mw,
            widget=widget,
            default_name=default_name,
            dialog_title='Export Canvas Screenshot As',
            success_label=label,
        )

    def _workflowPanelExportFilename(self, toolbox):
        title = toolbox.currentPageTitle() or 'workflow-panel'
        slug = UiExport.slugify_text(title, fallback='workflow_panel')
        return f'{slug}_panel.png'

    def _currentCanvasExportTarget(self):
        workspace_index = self.mw.mainArea.tabs.currentIndex()
        if workspace_index == self.mw.mainArea.WORKSPACE_ANALYSIS_INDEX:
            return (
                self.mw.contourview.chart_view,
                'contour_analysis_canvas.png',
                'Contour analysis canvas',
            )
        return (
            self.mw.view,
            'viewer_canvas.png',
            'Viewer canvas',
        )

    def _exportUiCaptureSet(self, output_dir, exported, skipped):
        toolbox = getattr(self.mw.mainArea, 'toolbox', None)
        if toolbox is None:
            skipped.append('Toolbox panels (toolbox unavailable)')
            return

        original_page_index = toolbox.currentIndex()
        original_workspace_index = self.mw.mainArea.tabs.currentIndex()

        try:
            self._saveCapture(
                self.mw,
                output_dir / 'ui_overview_main.png',
                'Main window overview',
                exported,
                skipped,
            )
            self._saveCapture(
                toolbox.summary_card,
                output_dir / 'active_airfoil_card.png',
                'Active airfoil card',
                exported,
                skipped,
                rounded_radius=12.0,
            )
            self._saveCapture(
                toolbox.workflow_card,
                output_dir / 'workflow_navigation.png',
                'Workflow navigation',
                exported,
                skipped,
                rounded_radius=12.0,
            )
            self._saveCapture(
                self.mw.mainArea.message_panel,
                output_dir / 'message_panel.png',
                'Message panel',
                exported,
                skipped,
                rounded_radius=8.0,
            )
            self._saveCapture(
                self.mw.mainArea.viewer_controls_panel,
                output_dir / 'viewer_controls_panel.png',
                'Viewer controls panel',
                exported,
                skipped,
                rounded_radius=8.0,
            )

            for index in range(toolbox.pageCount()):
                toolbox.setCurrentIndex(index)
                QtWidgets.QApplication.processEvents()
                title = toolbox.pageTitle(index)
                filename = (
                    f'{UiExport.slugify_text(title, fallback="workflow")}_panel.png'
                )
                self._saveCapture(
                    toolbox.page_card,
                    output_dir / filename,
                    f'{title} panel',
                    exported,
                    skipped,
                    rounded_radius=12.0,
                )

            self.mw.mainArea.tabs.setCurrentIndex(
                self.mw.mainArea.WORKSPACE_VIEWER_INDEX
            )
            QtWidgets.QApplication.processEvents()
            self._saveCapture(
                self.mw.view,
                output_dir / 'viewer_canvas.png',
                'Viewer canvas',
                exported,
                skipped,
            )

            self.mw.mainArea.tabs.setCurrentIndex(
                self.mw.mainArea.WORKSPACE_ANALYSIS_INDEX
            )
            QtWidgets.QApplication.processEvents()
            self._saveCapture(
                self.mw.contourview.chart_view,
                output_dir / 'contour_analysis_canvas.png',
                'Contour analysis canvas',
                exported,
                skipped,
            )

            self._exportDialogCapture(
                output_dir / 'settings_dialog.png',
                'Settings dialog',
                exported,
                skipped,
                self._buildSettingsDialog,
            )
            self._exportDialogCapture(
                output_dir / 'keyboard_shortcuts_dialog.png',
                'Keyboard shortcuts dialog',
                exported,
                skipped,
                self._buildShortcutDialog,
            )
            self._exportDialogCapture(
                output_dir / 'icon_preview_dialog.png',
                'Icon preview dialog',
                exported,
                skipped,
                self._buildIconPreviewDialog,
            )
            self._exportDialogCapture(
                output_dir / 'about_dialog.png',
                'About dialog',
                exported,
                skipped,
                self._buildAboutDialog,
            )

            cst_dialog, cst_error = toolbox.createCstParametersDialog()
            if cst_dialog is None:
                skipped.append(f'CST parameters dialog ({cst_error})')
            else:
                self._exportDialogCapture(
                    output_dir / 'cst_parameters_dialog.png',
                    'CST parameters dialog',
                    exported,
                    skipped,
                    lambda dialog=cst_dialog: dialog,
                )
        finally:
            if original_page_index >= 0:
                toolbox.setCurrentIndex(original_page_index)
            self.mw.mainArea.tabs.setCurrentIndex(original_workspace_index)
            QtWidgets.QApplication.processEvents()

    def _exportDialogCapture(
        self,
        output_path,
        label,
        exported,
        skipped,
        factory,
        rounded_radius=18.0,
    ):
        dialog = None
        try:
            dialog = factory()
            self._saveCapture(
                dialog,
                output_path,
                label,
                exported,
                skipped,
                rounded_radius=rounded_radius,
            )
        finally:
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()

    def _saveCapture(
        self,
        widget,
        output_path,
        label,
        exported,
        skipped,
        rounded_radius=None,
    ):
        try:
            UiExport.save_widget_png(
                widget=widget,
                filename=str(output_path),
                rounded_radius=rounded_radius,
                fallback_widget=self.mw,
            )
        except OSError as error:
            logger.warning(
                'Skipping %s during UI export: %s',
                label,
                error,
            )
            skipped.append(f'{label} ({error})')
            return False

        exported.append(str(output_path))
        return True

    def _buildSettingsDialog(self):
        import SettingsEditor

        return SettingsEditor.SettingsEditorDialog(self.mw)

    def _buildShortcutDialog(self):
        import ShortcutEditor

        return ShortcutEditor.ShortcutEditorDialog(self.mw)

    def _buildIconPreviewDialog(self):
        import IconPreview

        return IconPreview.IconPreviewDialog(self.mw)

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
        dialog = self._buildShortcutDialog()
        dialog.exec()

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
        dialog = self._buildIconPreviewDialog()
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
        dialog = self._buildAboutDialog()
        dialog.exec()

    def _buildAboutDialog(self):
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
        UiExport.install_dialog_export_button(
            buttons,
            mainwindow=self.mw,
            widget=dialog,
            default_name='about_dialog.png',
            dialog_title='Export About Dialog As',
            success_label='About dialog',
        )
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        return dialog
