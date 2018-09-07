import vtk

from PySide2 import QtGui, QtWidgets
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

import PyAero
from Settings import LOGCOLOR

import logging
logger = logging.getLogger(__name__)


class VtkWindow(QtWidgets.QFrame):
    """
    VtkWindow integrates a QVTKRenderWindowInteractor for Python and Qt. Uses a
    vtkGenericRenderWindowInteractor to handle the interactions.  Use
    GetRenderWindow() to get the vtkRenderWindow.  Create with the
    keyword stereo=1 in order to generate a stereo-capable window.

    The user interface is summarized in vtkInteractorStyle.h:

    - Keypress j / Keypress t: toggle between joystick (position
    sensitive) and trackball (motion sensitive) styles. In joystick
    style, motion occurs continuously as long as a mouse button is
    pressed. In trackball style, motion occurs when the mouse button
    is pressed and the mouse pointer moves.

    - Keypress c / Keypress o: toggle between camera and object
    (actor) modes. In camera mode, mouse events affect the camera
    position and focal point. In object mode, mouse events affect
    the actor that is under the mouse pointer.

    - Button 1: rotate the camera around its focal point (if camera
    mode) or rotate the actor around its origin (if actor mode). The
    rotation is in the direction defined from the center of the
    renderer's viewport towards the mouse position. In joystick mode,
    the magnitude of the rotation is determined by the distance the
    mouse is from the center of the render window.

    - Button 2: pan the camera (if camera mode) or translate the actor
    (if object mode). In joystick mode, the direction of pan or
    translation is from the center of the viewport towards the mouse
    position. In trackball mode, the direction of motion is the
    direction the mouse moves. (Note: with 2-button mice, pan is
    defined as <Shift>-Button 1.)

    - Button 3: zoom the camera (if camera mode) or scale the actor
    (if object mode). Zoom in/increase scale if the mouse position is
    in the top half of the viewport; zoom out/decrease scale if the
    mouse position is in the bottom half. In joystick mode, the amount
    of zoom is controlled by the distance of the mouse pointer from
    the horizontal centerline of the window.

    - Keypress 3: toggle the render window into and out of stereo
    mode.  By default, red-blue stereo pairs are created. Some systems
    support Crystal Eyes LCD stereo glasses; you have to invoke
    SetStereoTypeToCrystalEyes() on the rendering window.  Note: to
    use stereo you also need to pass a stereo=1 keyword argument to
    the constructor.

    - Keypress e: exit the application.

    - Keypress f: fly to the picked point

    - Keypress p: perform a pick operation. The render window interactor
    has an internal instance of vtkCellPicker that it uses to pick.

    - Keypress r: reset the camera view along the current view
    direction. Centers the actors and moves the camera so that all actors
    are visible.

    - Keypress s: modify the representation of all actors so that they
    are surfaces.

    - Keypress u: invoke the user-defined function. Typically, this
    keypress will bring up an interactor that you can type commands in.

    - Keypress w: modify the representation of all actors so that they
    are wireframe.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        self.outline = False

        self.vl = QtWidgets.QVBoxLayout()
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        self.vl.addWidget(self.vtkWidget)
        self.setLayout(self.vl)

        self.renderer = vtk.vtkRenderer()

        self.vtkwindow = self.vtkWidget.GetRenderWindow()
        self.vtkwindow.AddRenderer(self.renderer)

        self.interactor = self.vtkWidget.GetRenderWindow().GetInteractor()

        self.renderer.GradientBackgroundOn()
        self.renderer.SetBackground(1, 1, 1)
        self.renderer.SetBackground2(0, 0, 1)

        self.interactor.Initialize()

        self.vtkWidget.AddObserver('KeyPressEvent', self.onKeyPress)

    def onKeyPress(self, obj, event):
        """"Define hotkeys. Partially overwriting base functionality of
        QVTKRenderWindowInteractor.
        """
        key = obj.GetKeyCode()
        logger.debug('Key code returned is {}'.format(key))

        if key == 'o':
            self.toggleOutline()
        elif key == 'p':
            self.setDisplay('points')
        elif key == 'w':
            self.setDisplay('wireframe')
        elif key == 's':
            self.setDisplay('shaded')
        elif key == 'f':
            self.setShading('flat')
        elif key == 'g':
            self.setShading('gouraud')
        elif key == 'W':
            # FIXME
            # FIXME add dialog for filename
            # FIXME
            self.writeStl('test_writing_STL.stl')
        elif key == 'h':
            self.makeScreenshot()

    def readStl(self, name):
        self.reader = vtk.vtkSTLReader()
        self.reader.SetFileName(str(name))

        logger.log.info('STL file <b><font color=%s>' % (LOGCOLOR) +
                        str(name) + '</b> loaded')

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputConnection(self.reader.GetOutputPort())

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetColor(0, 1, 0.2)  # (R,G,B)
        self.actor.GetProperty().SetLineWidth(2.0)

        # create outline mapper
        self.outl = vtk.vtkOutlineFilter()
        self.outl.SetInputConnection(self.reader.GetOutputPort())
        self.outlineMapper = vtk.vtkPolyDataMapper()
        self.outlineMapper.SetInputConnection(self.outl.GetOutputPort())

        # create outline actor
        self.outlineActor = vtk.vtkActor()
        self.outlineActor.SetMapper(self.outlineMapper)

        self.renderer.AddActor(self.actor)
        self.renderer.ResetCamera()

        self.setDisplay('shaded')
        self.setShading('gouraud')

        # set tab to VTK window after loading an STL file
        ntabs = self.parent.centralwidget.tabs.count()
        self.parent.centralwidget.tabs.setCurrentIndex(ntabs-1)

    def writeStl(self, name):
        # Write the stl file to disk
        self.writer = vtk.vtkSTLWriter()
        self.writer.SetFileName(name)
        # self.writer.SetFileTypeToASCII()
        self.writer.SetFileTypeToBinary()
        self.writer.SetInputConnection(self.reader.GetOutputPort())
        self.writer.Write()

    def setShading(self, style):
        if style.lower() == 'flat':
            self.actor.GetProperty().SetInterpolationToFlat()
        if style.lower() == 'gouraud':
            self.actor.GetProperty().SetInterpolationToGouraud()
        if style.lower() == 'phong':
            self.actor.GetProperty().SetInterpolationToPhong()

    def setDisplay(self, style):
        if style.lower() == 'points':
            self.actor.GetProperty().SetRepresentationToPoints()
        if style.lower() == 'wireframe':
            self.actor.GetProperty().SetRepresentationToWireframe()
        if style.lower() == 'shaded':
            self.actor.GetProperty().SetRepresentationToSurface()

    def edgesOn(self):
        self.actor.GetProperty().EdgeVisibilityOn()

    def toggleOutline(self):
        self.outline = not self.outline
        if self.outline:
            self.renderer.AddActor(self.outlineActor)
        else:
            self.renderer.RemoveActor(self.outlineActor)

        # redraw everything
        self.vtkWidget.Render()

    def makeScreenshot(self):
        w2if = vtk.vtkWindowToImageFilter()
        w2if.SetInput(self.vtkwindow)
        w2if.Update()

        title = PyAero.__appname__+' - Message'
        dlg = QtGui.QInputDialog(self)
        dlg.resize(400, 200)
        dlg.setWindowTitle(title)
        dlg.setInputMode(QtGui.QInputDialog.TextInput)
        dlg.setLabelText('Enter screenshot name (*.png):')
        dlg.exec_()
        if not dlg.result():
            return

        fname = str(dlg.textValue())
        if not fname.endswith('.png'):
            fname = fname + '.png'

        writer = vtk.vtkPNGWriter()
        writer.SetFileName(fname)
        writer.SetInputData(w2if.GetOutput())
        writer.Write()

        text = 'Screenshot <b>%s</b> generated in current folder.' % (fname)
        msgbox = QtWidgets.QMessageBox()
        msgbox.setWindowTitle(title)
        msgbox.setText(text)
        msgbox.exec_()

        logger.log.info(text)
