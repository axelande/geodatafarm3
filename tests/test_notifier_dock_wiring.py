"""Tests that plugin messages route into the GeoDataFarm dock's own message
bar (see GeoDataFarm_dockwidget.py's ``message_bar`` and
MessageBarNotifier.set_dock_message_bar), not just the main QGIS window's -
those were easy to miss while working inside the docked panel.

Uses the shared ``gdf`` fixture (already run() by the time any test sees it -
see tests/__init__.py) but doesn't touch 'test_field' or any other fixture
data, so there's no ordering dependency on tests/test_field.py.
"""
import threading

from qgis.PyQt.QtCore import QCoreApplication

from ..GeoDataFarm import GeoDataFarm
from ..support_scripts.notifier import report_warning
from ..support_scripts.notifier.exceptions import GeoDataFarmError
from . import gdf


def _settle(ms_loops=20):
    for _ in range(ms_loops):
        QCoreApplication.processEvents()


def test_run_wires_the_dock_message_bar_into_the_notifier(gdf: GeoDataFarm):
    assert gdf.notifier._dock_message_bar is gdf.dock_widget.message_bar


def test_report_warning_shows_up_on_the_dock_message_bar(gdf: GeoDataFarm):
    bar = gdf.dock_widget.message_bar
    before = len(bar.items())

    report_warning('pytest: dock message bar wiring check')

    assert len(bar.items()) == before + 1
    gdf.notifier.dismiss_all()


def test_display_message_from_a_background_thread_does_not_touch_widgets_there(
        gdf: GeoDataFarm):
    # Reproduces the real-world bug report: a DB call failing partway
    # through a background QgsTask (e.g. CropSimulation._compute_teach_scan,
    # run on a worker thread by _RunTeachScanTask) used to call straight
    # into display_message/display_exception, which build real QWidgets -
    # unsafe off the main thread and, in the field, hung the whole
    # application rather than just showing an error. run_teach_scan()'s own
    # test_mode path runs synchronously on the main thread, so this is the
    # only place that exercises a genuine cross-thread call - see
    # MessageBarNotifier._on_main_thread's docstring for the fix.
    bar = gdf.dock_widget.message_bar
    before = len(bar.items())
    touched_widgets_off_thread = []
    worker_thread = threading.Thread(
        target=lambda: touched_widgets_off_thread.append(
            gdf.notifier.display_message('pytest: off-thread message check')))
    worker_thread.start()
    worker_thread.join(timeout=5)

    assert not worker_thread.is_alive(), 'display_message hung the worker thread'
    assert len(touched_widgets_off_thread) == 1  # returned an id immediately
    # Not yet shown - the real widget creation is queued onto the main
    # thread's event loop, not done inline on the worker thread.
    assert len(bar.items()) == before

    _settle()

    assert len(bar.items()) == before + 1
    gdf.notifier.dismiss_all()


def test_display_exception_from_a_background_thread_does_not_touch_widgets_there(
        gdf: GeoDataFarm):
    bar = gdf.dock_widget.message_bar
    before = len(bar.items())
    worker_thread = threading.Thread(
        target=lambda: gdf.notifier.display_exception(
            GeoDataFarmError('pytest: off-thread exception check')))
    worker_thread.start()
    worker_thread.join(timeout=5)

    assert not worker_thread.is_alive(), 'display_exception hung the worker thread'
    assert len(bar.items()) == before

    _settle()

    assert len(bar.items()) == before + 1
    gdf.notifier.dismiss_all()
