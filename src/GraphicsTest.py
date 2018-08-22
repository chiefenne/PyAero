from PySide2 import QtGui, QtCore

import GraphicsItemsCollection as gc
import GraphicsItem


def addTestItems(scene):

    # add items to the scene
    circle1 = gc.GraphicsCollection()
    circle1.Circle(0., 0., 0.1)
    circle1.pen.setWidth(0.2)
    circle1.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    circle1.brush.setColor(QtGui.QColor(255, 255, 0, 255))

    circle2 = gc.GraphicsCollection()
    circle2.Circle(-0.3, -0.3, 0.3)
    circle2.pen.setWidth(0.02)
    circle2.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    circle2.brush.setColor(QtGui.QColor(255, 0, 0, 255))

    circle3 = gc.GraphicsCollection()
    circle3.Circle(0.5, 0.5, 0.2)
    circle3.pen.setWidth(0.02)
    circle3.pen.setColor(QtGui.QColor(0, 255, 0, 255))
    circle3.brush.setColor(QtGui.QColor(30, 30, 255, 100))

    circle4 = gc.GraphicsCollection()
    circle4.Circle(-0.1, 0.4, 0.2)
    circle4.pen.setWidth(0.02)
    circle4.pen.setColor(QtGui.QColor(0, 0, 255, 255))
    circle4.brush.setColor(QtGui.QColor(30, 30, 30, 255))

    rectangle1 = gc.GraphicsCollection()
    rectangle1.Rectangle(-0.20, 0.10, 0.70, 0.35)
    rectangle1.pen.setWidth(0.02)
    rectangle1.pen.setColor(QtGui.QColor(0, 0, 255, 255))
    rectangle1.brush.setColor(QtGui.QColor(0, 255, 0, 180))

    text1 = gc.GraphicsCollection()
    font = QtGui.QFont('Arial', 20)
    font.setBold(True)
    text1.Text(0, 0.90, 'This is a text', font)
    text1.pen.setColor(QtGui.QColor(50, 30, 200, 255))

    point1 = gc.GraphicsCollection()
    point1.Point(0, 0)
    point1.pen.setColor(QtGui.QColor(255, 0, 0, 255))
    point1.pen.setWidth(0.02)

    polygon1 = gc.GraphicsCollection()
    polygon = QtGui.QPolygonF()
    polygon.append(QtCore.QPointF(0.20, 0.10))
    polygon.append(QtCore.QPointF(0.45, 0.10))
    polygon.append(QtCore.QPointF(0.45, -0.40))
    polygon.append(QtCore.QPointF(0.15, -0.40))
    polygon.append(QtCore.QPointF(0.0, 0.0))
    polygon1.pen.setWidth(0.02)
    polygon1.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    polygon1.brush.setColor(QtGui.QColor(0, 0, 255, 150))
    polygon1.Polygon(polygon)

    scene.itemc1 = PGraphicsItem.GraphicsItem(circle1)
    scene.addItem(scene.itemc1)
    scene.itemc2 = PGraphicsItem.GraphicsItem(circle2)
    scene.addItem(scene.itemc2)
    scene.itemc3 = PGraphicsItem.GraphicsItem(circle3e)
    scene.addItem(scene.itemc3)
    scene.itemc4 = PGraphicsItem.GraphicsItem(circle4)
    scene.addItem(scene.itemc4)
    scene.itemr1 = PGraphicsItem.GraphicsItem(rectangle1)
    scene.addItem(scene.itemr1)


def deleteTestItems(scene):

    scene.removeItem(scene.itemc1)
    scene.removeItem(scene.itemc2)
    scene.removeItem(scene.itemc3)
    scene.removeItem(scene.itemc4)
    scene.removeItem(scene.itemr1)
