"""Grab screenshots of the GeoDataFarm dock, the crop-simulation tabs and
the map canvas from a running QGIS session, for the paper's figures.

Run it inside QGIS, where the plugin is loaded and connected to the farm
with the credentials QGIS already holds (nothing is read from settings
here). Two ways:

1. QGIS Python console:
       exec(open(r'C:/dev/farm_proj/geodatafarm3/paper/scripts/take_screenshots.py').read())
2. From a shell, letting QGIS start and run it:
       C:\\OSGeo4W\\bin\\qgis-qt6.bat --code C:\\dev\\farm_proj\\geodatafarm3\\paper\\scripts\\take_screenshots.py

For the best figures, before running: select the study field, run one
crop simulation (so the date-slider map is populated), and calculate one
fertility index and show its layer. The script only captures what is on
screen; it does not click "Run".

Images land in paper/figures/screenshots/ at 2x device pixel ratio.
"""
import os
import re

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QApplication, QTabWidget
from qgis.utils import iface, plugins

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(
    __file__ if '__file__' in globals() else
    r'C:/dev/farm_proj/geodatafarm3/paper/scripts/x.py'))), 'figures', 'screenshots')


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_') or 'tab'


def _grab(widget, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    QApplication.processEvents()
    pixmap = widget.grab()
    path = os.path.join(OUT_DIR, name + '.png')
    pixmap.save(path, 'PNG')
    print('saved', path)


def _walk_tabs(tab_widget, prefix, depth=0):
    """Capture every tab of ``tab_widget`` and recurse into nested tab widgets."""
    for i in range(tab_widget.count()):
        tab_widget.setCurrentIndex(i)
        QApplication.processEvents()
        label = _slug(tab_widget.tabText(i)) or 'tab{}'.format(i)
        page = tab_widget.widget(i)
        _grab(tab_widget.window() if depth == 0 else page,
              '{}_{:02d}_{}'.format(prefix, i, label))
        for nested in page.findChildren(QTabWidget):
            if nested.parent() is not None and nested.isVisible():
                _walk_tabs(nested, '{}_{:02d}_{}'.format(prefix, i, label), depth + 1)


def shoot():
    plugin = plugins.get('geodatafarm') or plugins.get('geodatafarm3')
    if plugin is None:
        print('GeoDataFarm plugin not loaded; keys:', list(plugins))
        return
    if getattr(plugin, 'dock_widget', None) is None:
        plugin.run()
        QApplication.processEvents()
    dock = plugin.dock_widget
    dock.show()
    dock.raise_()
    QApplication.processEvents()
    _grab(dock, 'dock_current')
    _walk_tabs(dock.tabWidget, 'dock')
    sim = getattr(plugin, 'crop_simulation', None)
    if sim is not None and hasattr(sim.page, 'tabs'):
        for i in range(sim.page.tabs.count()):
            sim.page.tabs.setCurrentIndex(i)
            QApplication.processEvents()
            _grab(sim.page, 'cropsim_{:02d}_{}'.format(i, _slug(sim.page.tabs.tabText(i))))
    fert = getattr(plugin, 'fertility_index', None)
    if fert is not None:
        _grab(fert, 'fertility_index_page')
    _grab(iface.mapCanvas(), 'map_canvas')
    _grab(iface.mainWindow(), 'qgis_main_window')
    print('Screenshots written to', OUT_DIR)


# When started with --code the plugin may still be loading; wait a moment.
QTimer.singleShot(3000, shoot)
