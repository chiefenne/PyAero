from __future__ import annotations

import numpy as np

import logging
logger = logging.getLogger(__name__)


class SmoothAngleBased:
    """Angle-based mesh smoothing for block-mesh vertex/connectivity data."""

    EPSILON = 1.0e-9
    DEFAULT_LOG_INTERVAL = 10

    def __init__(self, data, connectivity=None, data_source=None):
        self.block = None

        if connectivity is not None:
            vertices = data
        elif data_source == 'block':
            import Connect

            self.block = data
            connector = Connect.Connect()
            vertices = connector.getVertices(self.block)
            connectivity = connector.getConnectivity(self.block)
        elif data_source == 'mesh':
            vertices, connectivity = data
        else:
            raise ValueError(
                'SmoothAngleBased expects vertices/connectivity data or '
                'data_source="block"/"mesh".'
            )

        self.vertices = np.asarray(vertices, dtype=float)
        self.connectivity = np.asarray(connectivity, dtype=int)

        if self.vertices.ndim != 2 or self.vertices.shape[1] != 2:
            raise ValueError('SmoothAngleBased expects vertices as an N x 2 array.')
        if self.connectivity.ndim != 2:
            raise ValueError('SmoothAngleBased expects connectivity as a 2D array.')

        self.lvc = self.makeLVC()
        self.stencils = self.make_stencil(self.lvc)
        self._compile_stencils(self.stencils)

    @staticmethod
    def _should_log_iteration(iteration, iterations, log_interval):
        return (
            iteration == 1 or
            iteration == iterations or
            iteration % log_interval == 0
        )

    @staticmethod
    def _as_vertex_list(vertices):
        return [
            (float(vertex[0]), float(vertex[1]))
            for vertex in np.asarray(vertices, dtype=float)
        ]

    def makeLVC(self):
        lvc = {}
        for cell in self.connectivity:
            for node in cell:
                lvc.setdefault(int(node), []).append(cell)

        self.lvc = {
            node: np.asarray(cells, dtype=int)
            for node, cells in lvc.items()
        }
        return self.lvc

    def make_stencil(self, lvc, verbose=False):
        stencils = {}

        for idx in range(len(self.vertices)):
            if idx not in lvc:
                continue

            local_cells = np.asarray(lvc[idx], dtype=int)
            vertices, counts = np.unique(local_cells, return_counts=True)
            vertices_star = vertices[counts == 2]

            if len(vertices_star) != 4:
                continue

            cells_with_common_edges = []
            for vertex in vertices_star:
                mask = np.isin(local_cells, [vertex, idx])
                mask_edges = np.count_nonzero(mask, axis=1) == 2
                cells_with_common_edges.append(local_cells[mask_edges])

            if idx == 6 and verbose:
                for cells in cells_with_common_edges:
                    np.isin(cells, np.append(vertices_star.flatten(), idx))

            corresponding_corners = []
            stencil_vertices = np.append(vertices_star.flatten(), idx)
            for cells in cells_with_common_edges:
                mask_corners = np.isin(cells, stencil_vertices)
                corresponding_corners.append(cells[~mask_corners])

            stencils[idx] = corresponding_corners

        self.stencils = stencils
        return self.stencils

    def _compile_stencils(self, stencils):
        center_indices = []
        d_indices = []
        e_indices = []
        f_indices = []
        g_indices = []

        for center in sorted(stencils):
            stencil = stencils[center]
            center_indices.append(int(center))
            d_indices.append(int(stencil[2][0]))
            e_indices.append(int(stencil[0][0]))
            f_indices.append(int(stencil[1][1]))
            g_indices.append(int(stencil[0][1]))

        self.center_indices = np.asarray(center_indices, dtype=int)
        self.d_indices = np.asarray(d_indices, dtype=int)
        self.e_indices = np.asarray(e_indices, dtype=int)
        self.f_indices = np.asarray(f_indices, dtype=int)
        self.g_indices = np.asarray(g_indices, dtype=int)

    def _compute_cardinals(self, vertices):
        d_vertex = vertices[self.d_indices]
        e_vertex = vertices[self.e_indices]
        f_vertex = vertices[self.f_indices]
        g_vertex = vertices[self.g_indices]

        south = 0.5 * (d_vertex + e_vertex)
        west = 0.5 * (d_vertex + g_vertex)
        east = 0.5 * (e_vertex + f_vertex)
        north = 0.5 * (g_vertex + f_vertex)

        return south, west, east, north, d_vertex, e_vertex, f_vertex, g_vertex

    def make_cardinals(self, vertices):
        vertices = np.asarray(vertices, dtype=float)
        cardinals = {}

        if self.center_indices.size == 0:
            return cardinals

        south, west, east, north, d_vertex, e_vertex, f_vertex, g_vertex = (
            self._compute_cardinals(vertices)
        )

        for index, center in enumerate(self.center_indices):
            cardinals[int(center)] = (
                (float(south[index, 0]), float(south[index, 1])),
                (float(west[index, 0]), float(west[index, 1])),
                (float(east[index, 0]), float(east[index, 1])),
                (float(north[index, 0]), float(north[index, 1])),
                [float(d_vertex[index, 0]), float(d_vertex[index, 1])],
                [float(e_vertex[index, 0]), float(e_vertex[index, 1])],
                [float(f_vertex[index, 0]), float(f_vertex[index, 1])],
                [float(g_vertex[index, 0]), float(g_vertex[index, 1])],
            )

        return cardinals

    def smooth(self, iterations=20, tolerance=1.0e-4, verbose=False,
               log_interval=None):
        iterations = int(iterations)
        log_interval = (
            self.DEFAULT_LOG_INTERVAL if log_interval is None
            else max(1, int(log_interval))
        )

        if iterations <= 0 or self.center_indices.size == 0:
            return self._as_vertex_list(self.vertices)

        current_vertices = np.array(self.vertices, copy=True, dtype=float)
        previous_vertices = np.array(self.vertices, copy=True, dtype=float)
        omega = 1.0

        for iteration in range(1, iterations + 1):
            south, west, east, north, d_vertex, e_vertex, f_vertex, g_vertex = (
                self._compute_cardinals(current_vertices)
            )

            centers = current_vertices[self.center_indices]
            centers_old = previous_vertices[self.center_indices]
            x = centers[:, 0]
            y = centers[:, 1]
            xold = centers_old[:, 0]
            yold = centers_old[:, 1]

            ns = np.linalg.norm(south - north, axis=1)
            we = np.linalg.norm(east - west, axis=1)
            ns_safe = np.maximum(ns, self.EPSILON)
            we_safe = np.maximum(we, self.EPSILON)
            sigma = np.maximum(ns_safe / we_safe, we_safe / ns_safe)

            a1 = np.column_stack((south[:, 0], east[:, 0], north[:, 0], west[:, 0]))
            a2 = np.column_stack((east[:, 0], north[:, 0], west[:, 0], south[:, 0]))
            b1 = np.column_stack((south[:, 1], east[:, 1], north[:, 1], west[:, 1]))
            b2 = np.column_stack((east[:, 1], north[:, 1], west[:, 1], south[:, 1]))

            c1 = np.column_stack((
                south[:, 0], south[:, 0], east[:, 0], east[:, 0],
                north[:, 0], north[:, 0], west[:, 0], west[:, 0],
            ))
            c2 = np.column_stack((
                d_vertex[:, 0], e_vertex[:, 0], e_vertex[:, 0], f_vertex[:, 0],
                f_vertex[:, 0], g_vertex[:, 0], g_vertex[:, 0], d_vertex[:, 0],
            ))
            d1 = np.column_stack((
                south[:, 1], south[:, 1], east[:, 1], east[:, 1],
                north[:, 1], north[:, 1], west[:, 1], west[:, 1],
            ))
            d2 = np.column_stack((
                d_vertex[:, 1], e_vertex[:, 1], e_vertex[:, 1], f_vertex[:, 1],
                f_vertex[:, 1], g_vertex[:, 1], g_vertex[:, 1], d_vertex[:, 1],
            ))

            x4 = x[:, None]
            y4 = y[:, None]
            xold4 = xold[:, None]
            yold4 = yold[:, None]
            sigma4 = sigma[:, None]

            alpha_denominator_1 = (
                a1**2 + b1**2 - 2 * a1 * xold4 + xold4**2 -
                2 * b1 * yold4 + yold4**2
            )
            alpha_denominator_2 = (
                a2**2 + b2**2 - 2 * a2 * xold4 + xold4**2 -
                2 * b2 * yold4 + yold4**2
            )
            ca = np.sum(
                omega / (alpha_denominator_1 * alpha_denominator_2 + self.EPSILON),
                axis=1,
            )

            alpha_energy = (
                a1 * a2 + b1 * b2 - a1 * x4 - a2 * x4 + x4**2 -
                b1 * y4 - b2 * y4 + y4**2
            )
            dTdx_alpha = np.sum(
                -alpha_energy * (a1 + a2 - 2.0 * x4) -
                (4.0 * a1 - 4.0 * x4) * sigma4,
                axis=1,
            )
            dTdy_alpha = np.sum(
                -alpha_energy * (b1 + b2 - 2.0 * y4) -
                (4.0 * b1 - 4.0 * y4) * sigma4,
                axis=1,
            )
            d2Tdx2_alpha = np.sum(
                (a1 + a2 - 2.0 * x4) ** 2 + 2.0 * a1 * a2 + 2.0 * b1 * b2 -
                2.0 * a1 * x4 - 2.0 * a2 * x4 + 2.0 * x4**2 -
                2.0 * b1 * y4 - 2.0 * b2 * y4 + 2.0 * y4**2 + 4.0 * sigma4,
                axis=1,
            )
            d2Tdy2_alpha = np.sum(
                2.0 * a1 * a2 + (b1 + b2 - 2.0 * y4) ** 2 + 2.0 * b1 * b2 -
                2.0 * a1 * x4 - 2.0 * a2 * x4 + 2.0 * x4**2 -
                2.0 * b1 * y4 - 2.0 * b2 * y4 + 2.0 * y4**2 + 4.0 * sigma4,
                axis=1,
            )
            d2Tdxdy_alpha = np.sum((a1 + a2 - 2.0 * x4) * (b1 + b2 - 2.0 * y4), axis=1)

            x8 = x[:, None]
            y8 = y[:, None]
            xold8 = xold[:, None]
            yold8 = yold[:, None]

            beta_denominator_1 = (
                c1**2 - 2.0 * c1 * c2 + c2**2 + d1**2 - 2.0 * d1 * d2 + d2**2
            )
            beta_denominator_2 = (
                c1**2 + d1**2 - 2.0 * c1 * xold8 + xold8**2 -
                2.0 * d1 * yold8 + yold8**2
            )
            cb = np.sum(
                omega / (beta_denominator_1 * beta_denominator_2 + self.EPSILON),
                axis=1,
            )

            beta_energy = (
                c1**2 - c1 * c2 + d1**2 - d1 * d2 - c1 * x8 +
                c2 * x8 - d1 * y8 + d2 * y8
            )
            alpha_control = (np.sum(a1, axis=1) - 4.0 * x) * sigma
            beta_control = (np.sum(b1, axis=1) - 4.0 * y) * sigma
            dTdx_beta = np.sum(
                -beta_energy * (c1 - c2) - alpha_control[:, None],
                axis=1,
            )
            dTdy_beta = np.sum(
                -beta_energy * (d1 - d2) - beta_control[:, None],
                axis=1,
            )
            d2Tdx2_beta = np.sum((c1 - c2) ** 2 + 4.0 * sigma[:, None], axis=1)
            d2Tdy2_beta = np.sum((d1 - d2) ** 2 + 4.0 * sigma[:, None], axis=1)
            d2Tdxdy_beta = np.sum((c1 - c2) * (d1 - d2), axis=1)

            dTdx = ca * dTdx_alpha + cb * dTdx_beta
            dTdy = ca * dTdy_alpha + cb * dTdy_beta
            d2Tdx2 = ca * d2Tdx2_alpha + cb * d2Tdx2_beta
            d2Tdy2 = ca * d2Tdy2_alpha + cb * d2Tdy2_beta
            d2Tdxdy = ca * d2Tdxdy_alpha + cb * d2Tdxdy_beta

            hessian_determinant = d2Tdx2 * d2Tdy2 - d2Tdxdy**2
            safe_hessian_determinant = np.where(
                np.abs(hessian_determinant) < self.EPSILON,
                np.where(hessian_determinant < 0.0, -self.EPSILON, self.EPSILON),
                hessian_determinant,
            )

            xnew = x - (d2Tdy2 * dTdx - d2Tdxdy * dTdy) / safe_hessian_determinant
            ynew = y - (d2Tdx2 * dTdy - d2Tdxdy * dTdx) / safe_hessian_determinant

            residual = np.max(np.hypot(xnew - x, ynew - y))

            previous_vertices[:, :] = current_vertices
            current_vertices[self.center_indices, 0] = xnew
            current_vertices[self.center_indices, 1] = ynew

            if verbose and self._should_log_iteration(
                iteration,
                iterations,
                log_interval,
            ):
                logger.info(f'Iteration={iteration:3d}, residual={residual:.3e}')

            if residual < tolerance:
                break

        return self._as_vertex_list(current_vertices)

    def mapToUlines(self, smoothed_vertices):
        if self.block is None:
            raise ValueError(
                'mapToUlines() requires initialization with data_source="block".'
            )

        vertices = np.asarray(smoothed_vertices, dtype=float)
        ulines = []
        vertex_index = 0

        for uline in self.block.getULines():
            point_count = len(uline)
            new_uline = []
            for offset in range(point_count):
                x_value, y_value = vertices[vertex_index + offset]
                new_uline.append((float(x_value), float(y_value)))
            ulines.append(new_uline)
            vertex_index += point_count

        return ulines
