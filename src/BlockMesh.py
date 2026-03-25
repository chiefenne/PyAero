from __future__ import annotations

import numpy as np
from scipy import interpolate

from MathUtils import VectorUtils


class BlockMesh:
    """Legacy structured block primitive used by the current mesh builders."""

    def __init__(self, name='block'):
        self.name = name
        self.ULines = []

    def addLine(self, line):
        self.ULines.append(line)

    def getULines(self):
        return self.ULines

    def setUlines(self, ulines):
        self.ULines = ulines

    def getVLines(self):
        vlines = []
        u_divisions, _ = self.getDivUV()

        for index in range(u_divisions + 1):
            vline = []
            for uline in self.getULines():
                vline.append(uline[index])
            vlines.append(vline)

        return vlines

    def getLine(self, number=0, direction='u'):
        direction = direction.lower()
        if direction == 'u':
            return self.getULines()[number]
        if direction == 'v':
            return self.getVLines()[number]
        raise ValueError(f'Unknown line direction: {direction}')

    def getDivUV(self):
        u = len(self.getULines()[0]) - 1
        v = len(self.getULines()) - 1
        return u, v

    def getNodeCoo(self, node):
        i_index, j_index = node
        point = self.getULines()[j_index][i_index]
        return np.asarray(point, dtype=float)

    def setNodeCoo(self, node, new_pos):
        i_index, j_index = node
        self.getULines()[j_index][i_index] = new_pos

    @staticmethod
    def makeLine(p1, p2, divisions=1, ratio=1.0):
        start = np.asarray(p1, dtype=float)
        end = np.asarray(p2, dtype=float)
        vector = end - start
        distance = np.linalg.norm(vector)
        spacing = BlockMesh.spacing(
            divisions=divisions,
            ratio=ratio,
            length=distance,
        )

        line = [(float(start[0]), float(start[1]))]
        direction = VectorUtils.unit_vector(vector)
        for index in range(1, len(spacing)):
            point = start + spacing[index] * direction
            line.append((float(point[0]), float(point[1])))
        line[-1] = (float(end[0]), float(end[1]))
        return line

    def extrudeLine_cell_thickness(self, line, cell_thickness=0.04,
                                   growth=1.05, divisions=1, direction=3):
        x_values, y_values = list(zip(*line))
        x_values = np.asarray(x_values, dtype=float)
        y_values = np.asarray(y_values, dtype=float)
        spacing, _ = self.spacing_cell_thickness(
            cell_thickness=cell_thickness,
            growth=growth,
            divisions=divisions,
        )

        if direction == 3:
            normals = self.curveNormals(x_values, y_values)
            for index in range(1, len(spacing)):
                x_offset = x_values + spacing[index] * normals[:, 0]
                y_offset = y_values + spacing[index] * normals[:, 1]
                self.addLine(list(zip(x_offset.tolist(), y_offset.tolist())))
        elif direction == 4:
            normals = self.curveNormals(x_values, y_values)
            normal_x = normals[:, 0].mean()
            normal_y = normals[:, 1].mean()
            for index in range(1, len(spacing)):
                x_offset = x_values + spacing[index] * normal_x
                y_offset = y_values + spacing[index] * normal_y
                self.addLine(list(zip(x_offset.tolist(), y_offset.tolist())))
        else:
            raise ValueError(f'Unsupported extrusion direction: {direction}')

    def extrudeLine(self, line, direction=0, length=0.1, divisions=1,
                    ratio=1.00001, constant=False):
        x_values, y_values = list(zip(*line))
        x_values = np.asarray(x_values, dtype=float)
        y_values = np.asarray(y_values, dtype=float)

        if constant and direction == 0:
            x_values.fill(length)
            self.addLine(list(zip(x_values.tolist(), y_values.tolist())))
            return
        if constant and direction == 1:
            y_values.fill(length)
            self.addLine(list(zip(x_values.tolist(), y_values.tolist())))
            return

        if direction not in (3, 4):
            raise ValueError(f'Unsupported extrusion direction: {direction}')

        spacing = self.spacing(divisions=divisions, ratio=ratio, length=length)
        normals = self.curveNormals(x_values, y_values)
        if direction == 3:
            for index in range(1, len(spacing)):
                x_offset = x_values + spacing[index] * normals[:, 0]
                y_offset = y_values + spacing[index] * normals[:, 1]
                self.addLine(list(zip(x_offset.tolist(), y_offset.tolist())))
        else:
            normal_x = normals[:, 0].mean()
            normal_y = normals[:, 1].mean()
            for index in range(1, len(spacing)):
                x_offset = x_values + spacing[index] * normal_x
                y_offset = y_values + spacing[index] * normal_y
                self.addLine(list(zip(x_offset.tolist(), y_offset.tolist())))

    def distribute(self, direction='u', number=0, type='constant'):
        if direction == 'u':
            line = np.asarray(self.getULines()[number], dtype=float)
        elif direction == 'v':
            line = np.asarray(self.getVLines()[number], dtype=float)
        else:
            raise ValueError(f'Unknown line direction: {direction}')

        tck, _ = interpolate.splprep(line.T, s=0, k=1)

        if type == 'constant':
            parameters = np.linspace(0.0, 1.0, num=len(line))
        elif type == 'transition':
            first = np.asarray(self.getULines()[0], dtype=float)
            last = np.asarray(self.getULines()[-1], dtype=float)
            _, first_parameters = interpolate.splprep(first.T, s=0, k=1)
            _, last_parameters = interpolate.splprep(last.T, s=0, k=1)
            if number < 0:
                number = len(self.getVLines())
            blend = float(number) / float(len(self.getVLines()))
            parameters = (1.0 - blend) * first_parameters + \
                blend * last_parameters
        else:
            raise ValueError(f'Unknown distribution type: {type}')

        redistributed = interpolate.splev(parameters, tck, der=0)
        redistributed = list(
            zip(redistributed[0].tolist(), redistributed[1].tolist())
        )

        if direction == 'u':
            self.getULines()[number] = redistributed
        else:
            for index, uline in enumerate(self.getULines()):
                uline[number] = redistributed[index]

    @staticmethod
    def spacing_cell_thickness(cell_thickness=0.04, growth=1.1, divisions=10):
        spacing = [cell_thickness]
        for _ in range(divisions - 1):
            spacing.append(spacing[0] + spacing[-1] * growth)
        spacing.insert(0, 0.0)
        return spacing, np.sum(spacing)

    @staticmethod
    def spacing(divisions=10, ratio=1.0, length=1.0):
        if divisions == 1:
            return np.array([0.0, 1.0])

        growth = ratio ** (1.0 / (float(divisions) - 1.0))
        if growth == 1.0:
            growth = 1.0 + 1.0e-10

        spacing = [1.0]
        for index in range(1, divisions + 1):
            spacing.append(growth ** index)

        spacing = np.asarray(spacing, dtype=float)
        spacing -= spacing[0]
        spacing /= spacing[-1]
        spacing *= length
        return spacing

    def mapLines(self, line_1, line_2):
        pass

    @staticmethod
    def curveNormals(x, y, closed=False):
        start_offset = 0
        end_offset = 0
        normals = []

        for index, _ in enumerate(x):
            if closed:
                if index == len(x) - 1:
                    end_offset = -index - 1
            else:
                if index == 0:
                    start_offset = 1
                if index == len(x) - 1:
                    end_offset = -1

            tangent = np.array(
                [
                    x[index + 1 + end_offset] - x[index - 1 + start_offset],
                    y[index + 1 + end_offset] - y[index - 1 + start_offset],
                ],
                dtype=float,
            )
            unit = VectorUtils.unit_vector(tangent)
            normals.append([unit[1], -unit[0]])
            start_offset = 0
            end_offset = 0

        return np.asarray(normals, dtype=float)

    def transfinite(self, boundary=None, ij=None):
        if boundary:
            lower, upper, left, right = boundary
        elif ij:
            lower = self.getULines()[ij[2]][ij[0]:ij[1] + 1]
            upper = self.getULines()[ij[3]][ij[0]:ij[1] + 1]
            left = self.getVLines()[ij[0]][ij[2]:ij[3] + 1]
            right = self.getVLines()[ij[1]][ij[2]:ij[3] + 1]
        else:
            lower = self.getULines()[0]
            upper = self.getULines()[-1]
            left = self.getVLines()[0]
            right = self.getVLines()[-1]

        lower = np.asarray(lower, dtype=float)
        upper = np.asarray(upper, dtype=float)
        left = np.asarray(left, dtype=float)
        right = np.asarray(right, dtype=float)

        _, u_lower = interpolate.splprep(lower.T, s=0, k=1)
        _, u_left = interpolate.splprep(left.T, s=0, k=1)

        nodes = np.zeros((len(left) * len(lower), 2), dtype=float)
        c1 = lower[0]
        c2 = upper[0]
        c3 = lower[-1]
        c4 = upper[-1]

        for i_index, xi in enumerate(u_lower):
            for j_index, eta in enumerate(u_left):
                node = i_index * len(u_left) + j_index
                point = (
                    (1.0 - xi) * left[j_index] + xi * right[j_index] +
                    (1.0 - eta) * lower[i_index] + eta * upper[i_index] -
                    (
                        (1.0 - xi) * (1.0 - eta) * c1 +
                        (1.0 - xi) * eta * c2 +
                        xi * (1.0 - eta) * c3 +
                        xi * eta * c4
                    )
                )
                nodes[node, 0] = point[0]
                nodes[node, 1] = point[1]

        vlines = []
        vline = []
        for index, node in enumerate(nodes, start=1):
            vline.append(node)
            if index % len(left) == 0:
                vlines.append(vline)
                vline = []

        vlines.reverse()

        if ij:
            ulines = self.makeUfromV(vlines)
            for offset, k_index in enumerate(range(ij[2], ij[3] + 1)):
                self.ULines[k_index][ij[0]:ij[1] + 1] = ulines[offset]
        else:
            self.ULines = self.makeUfromV(vlines)

    @staticmethod
    def makeUfromV(vlines):
        ulines = []
        for index in range(len(vlines[0])):
            uline = []
            for vline in vlines:
                x_value, y_value = vline[index][0], vline[index][1]
                uline.append((x_value, y_value))
            ulines.append(uline[::-1])
        return ulines


class Smooth:
    """Legacy block smoother used by the simple smoothing adapter."""

    def __init__(self, block):
        self.block = block

    def getNeighbours(self, node):
        i_index, j_index = node
        return {
            1: (i_index - 1, j_index - 1),
            2: (i_index, j_index - 1),
            3: (i_index + 1, j_index - 1),
            4: (i_index + 1, j_index),
            5: (i_index + 1, j_index + 1),
            6: (i_index, j_index + 1),
            7: (i_index - 1, j_index + 1),
            8: (i_index - 1, j_index),
        }

    def smooth(self, nodes, iterations=1, algorithm='laplace'):
        for _ in range(iterations):
            for node in nodes:
                neighbours = self.getNeighbours(node)

                if algorithm == 'laplace':
                    new_position = (
                        self.block.getNodeCoo(neighbours[2]) +
                        self.block.getNodeCoo(neighbours[4]) +
                        self.block.getNodeCoo(neighbours[6]) +
                        self.block.getNodeCoo(neighbours[8])
                    ) / 4.0
                elif algorithm == 'parallelogram':
                    new_position = (
                        self.block.getNodeCoo(neighbours[1]) +
                        self.block.getNodeCoo(neighbours[3]) +
                        self.block.getNodeCoo(neighbours[5]) +
                        self.block.getNodeCoo(neighbours[7])
                    ) / 4.0 - (
                        self.block.getNodeCoo(neighbours[2]) +
                        self.block.getNodeCoo(neighbours[4]) +
                        self.block.getNodeCoo(neighbours[6]) +
                        self.block.getNodeCoo(neighbours[8])
                    ) / 2.0
                else:
                    continue

                self.block.setNodeCoo(node, new_position.tolist())

        return self.block

    def selectNodes(self, domain='interior', ij=None):
        u_divisions, v_divisions = self.block.getDivUV()
        nodes = []

        if domain == 'interior':
            i_start, i_end = 1, u_divisions
            j_start, j_end = 1, v_divisions
        elif domain == 'ij' and ij is not None:
            i_start, i_end = ij[0], ij[1]
            j_start, j_end = ij[2], ij[3]
        else:
            raise ValueError(f'Unknown node selection domain: {domain}')

        for i_index in range(i_start, i_end):
            for j_index in range(j_start, j_end):
                nodes.append((i_index, j_index))

        return nodes
