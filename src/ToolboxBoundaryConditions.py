from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class BoundaryConditionInputs:
    reynolds: float
    chord: float
    aoa_from: float
    aoa_to: float
    aoa_step: float
    turbulence: float
    length_scale: float
    pressure: float
    temperature_c: float
    yplus: float


@dataclass(slots=True)
class BoundaryConditionResults:
    density: float
    dynamic_viscosity: float
    kinematic_viscosity: float
    aoa: np.ndarray
    u_velocity: np.ndarray
    v_velocity: np.ndarray
    wall_distance: float
    tke: float
    temperature_k: float


def calculate_boundary_conditions(inputs: BoundaryConditionInputs):
    gas_constant = 287.14
    temperature_k = inputs.temperature_c + 273.15
    density = inputs.pressure / gas_constant / temperature_k
    num = int((inputs.aoa_to - inputs.aoa_from) / inputs.aoa_step + 1)
    aoa = np.linspace(inputs.aoa_from, inputs.aoa_to, num=num, endpoint=True)

    dynamic_viscosity = _dynamic_viscosity(temperature_k)
    kinematic_viscosity = dynamic_viscosity / density
    velocity = inputs.reynolds / inputs.chord * kinematic_viscosity
    uprime = velocity * inputs.turbulence / 100.0
    tke = 3.0 / 2.0 * uprime**2
    u_velocity = velocity * np.cos(aoa * np.pi / 180.0)
    v_velocity = velocity * np.sin(aoa * np.pi / 180.0)

    reynolds_number = inputs.reynolds
    log_re = np.power(np.log10(reynolds_number), 2.58)
    if reynolds_number < 5.1e6:
        friction_coefficient = 0.455 / log_re
    else:
        friction_coefficient = 0.455 / log_re - 1700.0 / reynolds_number

    wall_shear_stress = friction_coefficient * 0.5 * density * velocity**2
    friction_velocity = np.sqrt(wall_shear_stress / density)
    wall_distance = (
        inputs.yplus * dynamic_viscosity / density / friction_velocity
    )

    return BoundaryConditionResults(
        density=density,
        dynamic_viscosity=dynamic_viscosity,
        kinematic_viscosity=kinematic_viscosity,
        aoa=aoa,
        u_velocity=u_velocity,
        v_velocity=v_velocity,
        wall_distance=wall_distance,
        tke=tke,
        temperature_k=temperature_k,
    )


def format_boundary_conditions_html(inputs, results):
    newline = '<br>'
    html = '<b>CFD Boundary Conditions</b>' + newline
    html += f'Reynolds (-): {inputs.reynolds}' + newline
    html += f'Pressure (Pa): {inputs.pressure}' + newline
    html += f'Temperature (C): {inputs.temperature_c}' + newline
    html += f'Temperature (K): {results.temperature_k}' + newline
    html += f'Density (kg/(m<sup>3</sup>)): {results.density}' + newline
    html += (
        f'Dynamic viscosity (kg/(m.s)): {results.dynamic_viscosity}' + newline
    )
    html += (
        f'Kinematic viscosity (m/s) {results.kinematic_viscosity}:'
        + newline
    )
    html += (
        f'<b>1st cell layer thickness (m)</b>, for y<sup>+</sup>={inputs.yplus}'
        + newline
    )
    html += '{:16.8f}'.format(results.wall_distance) + newline
    html += '<b>TKE (m<sup>2</sup>/s<sup>2</sup>), Length-scale (m)</b>'
    html += newline
    html += '{:16.8f} {:16.8f}'.format(results.tke, inputs.length_scale)
    html += newline
    html += '<b>AOA (°)   u-velocity (m/s)   v-velocity (m/s)</b>' + newline
    for index, _ in enumerate(results.u_velocity):
        html += '{: >5.2f} {: >16.8f} {: >16.8f}{}'.format(
            results.aoa[index],
            results.u_velocity[index],
            results.v_velocity[index],
            newline,
        )
    return html


def _dynamic_viscosity(temperature_k):
    # Sutherland formula for air
    c_const = 120.0
    lamb = 1.512041288e-6
    return lamb * temperature_k**1.5 / (temperature_k + c_const)
