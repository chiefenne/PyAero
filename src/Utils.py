
from PySide6.QtCore import QCoreApplication

def get_main_window():
    """Return the application's main window instance."""
    return QCoreApplication.instance().mainwindow

def scalar_to_rgb(value, vmin, vmax, range='1'):
    """Convert scalar value to RGB color
        
        Args:
            value (float): scalar value
            vmin (float): minimum value
            vmax (float): maximum value
            range (str): color range (1 or 256)

        Returns:
            tuple: RGB color
    """
    v = np.clip(value, vmin, vmax)
    dv = vmax - vmin
    c = [1., 1., 1.]
    
    if v < (vmin + 0.25 * dv):
        c[0] = 0
        c[1] = 4 * (v - vmin) / dv
    elif v < (vmin + 0.5 * dv):
        c[0] = 0;
        c[2] = 1 + 4 * (vmin + 0.25 * dv - v) / dv;
    elif v < (vmin + 0.75 * dv):
        c[0] = 4 * (v - vmin - 0.5 * dv) / dv;
        c[2] = 0;
    else:
        c[1] = 1 + 4 * (vmin + 0.75 * dv - v) / dv;
        c[2] = 0;
    
    r, g, b = np.clip(c[0], 0., 1.), np.clip(c[1], 0., 1.), np.clip(c[2], 0., 1.)

    if range == '256':
        r *= 255
        g *= 255
        b *= 255

    return r, g, b