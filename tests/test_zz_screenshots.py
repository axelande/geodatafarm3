"""Capture screenshots of the current UI for the documentation.

Run with:  pytest tests/test_zz_screenshots.py  (under the QGIS python).
Writes PNGs into homepage/images/.
"""
import os

from qgis.PyQt.QtWidgets import QApplication, QScrollArea, QFrame
from qgis.PyQt.QtCore import QCoreApplication

from ..GeoDataFarm import GeoDataFarm
from . import gdf

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                   'homepage', 'images'))


def _settle(ms_loops=12):
    for _ in range(ms_loops):
        QCoreApplication.processEvents()


def _nav_row(nav, keyword):
    """Row number of the sidebar item whose label contains `keyword`."""
    for row in range(nav.count()):
        if keyword in nav.item(row).text():
            return row
    raise AssertionError(f'no sidebar row labelled {keyword!r}')


def _grab(widget, name):
    path = os.path.join(OUT, name)
    pm = widget.grab()
    ok = pm.save(path)
    print(f'{"OK " if ok else "FAIL"} {name}  ({pm.width()}x{pm.height()})')
    return ok


def _ensure_guide_embedded(g: GeoDataFarm):
    """Make sure the guide-file widget is embedded in its dock tab (normally
    done in set_buttons; do it here too in case the DB path skipped it)."""
    dw = g.dock_widget
    if getattr(g, 'guide', None) is None:
        g.create_guide()
    if dw.layoutGuideFile.count() == 0:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame if hasattr(QFrame, 'Shape')
                             else QFrame.NoFrame)
        scroll.setWidget(g.guide.CGF)
        dw.layoutGuideFile.addWidget(scroll)


def test_capture_screenshots(gdf: GeoDataFarm):
    os.makedirs(OUT, exist_ok=True)
    dw = gdf.dock_widget
    assert dw is not None, 'dock widget not created'
    _ensure_guide_embedded(gdf)

    dw.resize(1230, 900)
    dw.show()
    _settle()

    nav = dw.navSidebar

    # Whole-dock shots per sidebar page. Looked up by label rather than by row
    # number - rows shift whenever a page is added (Fertility index is even
    # inserted at runtime), and a stale number silently shoots the wrong page.
    pages = {
        'Farm': 'ui_farm_fields.png',
        'Crop simulation': 'ui_crop_simulation.png',
        'Add data': 'ui_add_data.png',
        'Data sets': 'ui_data_sets.png',
        'Visualization': 'ui_visualization.png',
        'Data tools': 'ui_data_tools.png',
        'Satellite': 'ui_satellite.png',
        'Reports': 'ui_reports.png',
        'Plan ahead': 'ui_plan_ahead.png',
        'ISO-XML': 'ui_isoxml_generator.png',
    }
    for keyword, name in pages.items():
        nav.setCurrentRow(_nav_row(nav, keyword))
        _settle()
        _grab(dw, name)

    # Add-data unified form (opened from a picker card): file + manual views.
    nav.setCurrentRow(_nav_row(nav, 'Add data'))
    _settle()
    form = getattr(gdf, 'add_data_form', None)
    if form is not None:
        try:
            form._open('opPlanting')
            _settle()
            _grab(form, 'add_data_form_file.png')
            form.segManual.setChecked(True)
            form.inputStack.setCurrentIndex(1)
            _settle()
            _grab(form, 'add_data_form_manual.png')
            form.show_picker()
        except Exception as e:
            print('add-data form capture skipped:', e)

    # Guide file page: capture both sub-tabs (and a close-up of just the wizard).
    nav.setCurrentRow(_nav_row(nav, 'Guide file'))
    _settle()
    cgf = gdf.guide.CGF
    tabf = cgf.tabFormat
    tabf.setCurrentIndex(0)   # Shapefile
    _settle()
    _grab(dw, 'ui_guide_shapefile.png')
    _grab(cgf, 'guide_shapefile_panel.png')
    tabf.setCurrentIndex(1)   # ISO-XML
    _settle()
    _grab(dw, 'ui_guide_isoxml.png')
    _grab(cgf, 'guide_isoxml_panel.png')

    # Crop simulation documentation shots. These use a small deterministic
    # map fixture so the screenshots show the real Premium controls and map
    # legend without requiring a live weather request during capture.
    crop_simulation = gdf.crop_simulation
    crop_page = crop_simulation.page
    crop_page.resize(1100, 900)
    crop_page.show()
    saved_license_key = crop_simulation.qsettings.value(
        'geodatafarm/pro_license_key', '')
    saved_license_instance = crop_simulation.qsettings.value(
        'geodatafarm/pro_license_instance_id', '')
    crop_simulation.qsettings.remove('geodatafarm/pro_license_key')
    crop_simulation.qsettings.remove('geodatafarm/pro_license_instance_id')
    crop_simulation._refresh_license_status()
    _settle()
    _grab(crop_page, 'crop_simulation_locked.png')
    if saved_license_key:
        crop_simulation.qsettings.setValue('geodatafarm/pro_license_key', saved_license_key)
    if saved_license_instance:
        crop_simulation.qsettings.setValue(
            'geodatafarm/pro_license_instance_id', saved_license_instance)
    crop_simulation._cell_polygons = {
        1: 'POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))',
        2: 'POLYGON((1 0, 1 1, 2 1, 2 0, 1 0))',
    }
    crop_simulation._trace_dates = ['2026-05-01', '2026-07-15', '2026-09-15']
    crop_simulation._cell_yields = {1: 7.2, 2: 5.8}
    crop_simulation._cell_yields_by_date = {
        1: {'2026-05-01': 0.0, '2026-07-15': 2.8, '2026-09-15': 7.2},
        2: {'2026-05-01': 0.0, '2026-07-15': 2.1, '2026-09-15': 5.8},
    }
    crop_simulation._cell_traces = {}
    crop_simulation._cell_water_totals = {}
    crop_page.CBMapMode.setCurrentIndex(crop_page.CBMapMode.findData('yield'))
    crop_simulation._render_heatmap('2026-07-15')
    _settle()
    _grab(crop_page, 'crop_simulation_yield_map.png')
    crop_simulation._render_heatmap('2026-07-15')
    crop_page.CBMapMode.setCurrentIndex(crop_page.CBMapMode.findData('stress'))
    _settle()
    _grab(crop_page, 'crop_simulation_stress_map.png')
    crop_page.hide()

    # at least the guide shots must exist
    assert os.path.isfile(os.path.join(OUT, 'ui_guide_isoxml.png'))
