from PySide6 import QtGui, QtCore

import GraphicsItemsCollection as gic
import GraphicsItem


def addTestItems(scene):

    # add items to the scene
    circle1 = gic.GraphicsCollection()
    circle1.Circle(0., 0., 0.1)
    circle1.pen.setWidthF(0.2)
    circle1.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    circle1.brush.setColor(QtGui.QColor(255, 255, 0, 255))

    circle2 = gic.GraphicsCollection()
    circle2.Circle(-0.3, -0.3, 0.3)
    circle2.pen.setWidthF(0.02)
    circle2.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    circle2.brush.setColor(QtGui.QColor(255, 0, 0, 255))

    circle3 = gic.GraphicsCollection()
    circle3.Circle(0.5, 0.5, 0.2)
    circle3.pen.setWidthF(0.02)
    circle3.pen.setColor(QtGui.QColor(0, 255, 0, 255))
    circle3.brush.setColor(QtGui.QColor(30, 30, 255, 100))

    circle4 = gic.GraphicsCollection()
    circle4.Circle(-0.1, 0.4, 0.2)
    circle4.pen.setWidthF(0.02)
    circle4.pen.setColor(QtGui.QColor(0, 0, 255, 255))
    circle4.brush.setColor(QtGui.QColor(30, 30, 30, 255))

    rectangle1 = gic.GraphicsCollection()
    rectangle1.Rectangle(-0.20, 0.10, 0.70, 0.35)
    rectangle1.pen.setWidthF(0.02)
    rectangle1.pen.setColor(QtGui.QColor(0, 0, 255, 255))
    rectangle1.brush.setColor(QtGui.QColor(0, 255, 0, 180))

    text1 = gic.GraphicsCollection()
    font = QtGui.QFont('Arial', 20)
    font.setBold(True)
    text1.Text(0, 0.90, 'This is a text', font)
    text1.pen.setColor(QtGui.QColor(50, 30, 200, 255))

    point1 = gic.GraphicsCollection()
    point1.Point(0, 0)
    point1.pen.setColor(QtGui.QColor(255, 0, 0, 255))
    point1.pen.setWidthF(0.02)

    polygon1 = gic.GraphicsCollection()
    polygon = QtGui.QPolygonF()
    polygon.append(QtCore.QPointF(0.20, 0.10))
    polygon.append(QtCore.QPointF(0.45, 0.10))
    polygon.append(QtCore.QPointF(0.45, -0.40))
    polygon.append(QtCore.QPointF(0.15, -0.40))
    polygon.append(QtCore.QPointF(0.0, 0.0))
    polygon1.pen.setWidthF(0.02)
    polygon1.pen.setColor(QtGui.QColor(0, 0, 0, 255))
    polygon1.brush.setColor(QtGui.QColor(0, 0, 255, 150))
    polygon1.Polygon(polygon)

    # create on the fly scene attributes which can be accessed deleteTestItems
    scene.itemc1 = GraphicsItem.GraphicsItem(circle1)
    scene.itemc2 = GraphicsItem.GraphicsItem(circle2)
    scene.itemc3 = GraphicsItem.GraphicsItem(circle3)
    scene.itemc4 = GraphicsItem.GraphicsItem(circle4)
    scene.itemr1 = GraphicsItem.GraphicsItem(rectangle1)
    
    # add test items to the scene
    scene.addItem(scene.itemc1)
    scene.addItem(scene.itemc2)
    scene.addItem(scene.itemc3)
    scene.addItem(scene.itemc4)
    scene.addItem(scene.itemr1)


def deleteTestItems(scene):

    scene.removeItem(scene.itemc1)
    scene.removeItem(scene.itemc2)
    scene.removeItem(scene.itemc3)
    scene.removeItem(scene.itemc4)
    scene.removeItem(scene.itemr1)
