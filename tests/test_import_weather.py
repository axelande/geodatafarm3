"""Tests for the free weather import (Weather dialog, opened from the
"Weather" card on the "Add data" page).

``test_cluster_by_location_*``, ``test_haversine_km_*`` and
``test_default_from_date_*`` are pure-function tests (no DB, no network) -
independent of the ordered/stateful part of the suite.

The rest use the shared ``gdf``/database fixture like tests/test_import_data.py,
so they must run as part of the full suite (`pytest tests`), not on their
own - see tests/conftest.py and the project's stateful/order-dependent test
setup. The Open-Meteo HTTP call is mocked (no network access needed), and
``QgsTask.fromFunction`` is patched to run synchronously so tests don't need
a real background task-manager event loop - see ``_run_task_sync`` below.
"""
import contextlib
from datetime import date
from unittest import mock

from qgis.PyQt.QtCore import QDate

from ..GeoDataFarm import GeoDataFarm
from ..import_data.handle_weather import WeatherData, _default_from_date
from . import gdf

_FAKE_DAILY = [
    {'date': '2024-05-01', 'precipitation_mm': 0.0, 'et0_mm': 3.1, 'temp_mean_c': 12.5},
    {'date': '2024-05-02', 'precipitation_mm': 12.4, 'et0_mm': 2.6, 'temp_mean_c': 13.0},
    {'date': '2024-05-03', 'precipitation_mm': None, 'et0_mm': None, 'temp_mean_c': None},
]


class _FakeQgsTask:
    """Stand-in for the ``task`` argument a real QgsTask passes to the
    wrapped function - just enough for setProgress()/isCanceled() calls."""

    def setProgress(self, pct):
        pass

    def isCanceled(self):
        return False


def _run_task_sync(description, func, *args, on_finished=None):
    """Stand-in for ``QgsTask.fromFunction`` that runs the task function
    (and its on_finished callback) synchronously and immediately, so tests
    don't need a real background task-manager loop."""
    task = _FakeQgsTask()
    try:
        result = func(task, *args)
        exception = None
    except Exception as e:  # pragma: no cover - only if the task itself errors
        result = None
        exception = e
    if on_finished is not None:
        on_finished(exception, result)
    return task


@contextlib.contextmanager
def _patch_task_manager(weather_data):
    """Patches QgsTask.fromFunction (synchronous) and tsk_mngr.addTask
    (no-op, since the task has already run by the time it's called - the
    real QgsTaskManager.addTask() rejects the fake task object
    _run_task_sync hands back, since it isn't a real QgsTask)."""
    with mock.patch(
            'geodatafarm.import_data.handle_weather.QgsTask.fromFunction',
            side_effect=_run_task_sync), \
        mock.patch.object(weather_data.tsk_mngr, 'addTask'):
        yield


def _set_range(dlg, date_from, date_to):
    dlg.DEWeatherFrom.setDate(QDate.fromString(date_from, 'yyyy-MM-dd'))
    dlg.DEWeatherTo.setDate(QDate.fromString(date_to, 'yyyy-MM-dd'))


# -- pure-function tests: clustering, distance, default dates --------------

def test_cluster_by_location_groups_nearby_fields():
    # roughly 1 km apart (Malmo area coordinates, like the real test fields)
    fields = [('a', 13.5529, 55.3966), ('b', 13.5405, 55.3945)]
    clusters = WeatherData._cluster_by_location(fields)
    assert len(clusters) == 1
    assert {f[0] for f in clusters[0]} == {'a', 'b'}


def test_cluster_by_location_separates_distant_fields():
    # ~55 km apart - well outside the 5 km sharing radius
    fields = [('a', 13.5529, 55.3966), ('b', 13.5529, 55.90)]
    clusters = WeatherData._cluster_by_location(fields)
    assert len(clusters) == 2


def test_haversine_km_is_zero_for_the_same_point():
    assert WeatherData._haversine_km(55.4, 13.5, 55.4, 13.5) == 0.0


def test_default_from_date_uses_this_year_on_or_after_march_1st():
    assert _default_from_date(date(2026, 3, 1)) == date(2026, 3, 1)
    assert _default_from_date(date(2026, 12, 31)) == date(2026, 3, 1)


def test_default_from_date_uses_last_year_before_march_1st():
    assert _default_from_date(date(2026, 1, 15)) == date(2025, 3, 1)
    assert _default_from_date(date(2026, 2, 28)) == date(2025, 3, 1)


# -- DB-backed tests --------------------------------------------------------

def test_open_dialog_defaults_to_1_march_through_today(gdf: GeoDataFarm):
    gdf.weather_data.open_dialog = gdf.weather_data.open_dialog  # (no-op; documents intent)
    with mock.patch.object(gdf.weather_data.dlg, 'exec'), \
        mock.patch.object(gdf.weather_data.dlg, 'show'):
        gdf.weather_data.open_dialog()

    today = date.today()
    expected_from = _default_from_date(today)
    assert gdf.weather_data.dlg.DEWeatherTo.date().toPyDate() == today
    assert gdf.weather_data.dlg.DEWeatherFrom.date().toPyDate() == expected_from


def test_fetch_weather_stores_precipitation_temperature_and_et0(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_weather_2024")
    dlg = gdf.weather_data.dlg
    dlg.CBWeatherAllFields.setChecked(False)
    gdf.weather_data.update_field_list()
    idx = dlg.CBWeatherField.findText('test_field')
    assert idx >= 0
    dlg.CBWeatherField.setCurrentIndex(idx)
    _set_range(dlg, '2024-05-01', '2024-05-03')

    with _patch_task_manager(gdf.weather_data), \
        mock.patch.object(gdf.weather_data.client, 'daily_weather',
                          return_value=_FAKE_DAILY) as m:
        dlg.PBFetchWeather.click()

    m.assert_called_once()
    assert 'test_field_weather_2024' in gdf.db.get_tables_in_db('weather')
    rows = gdf.db.execute_and_return(
        "SELECT date_, precipitation_mm, temp_mean_c, et0_mm, source"
        " FROM weather.test_field_weather_2024 ORDER BY date_")
    assert len(rows) == 3
    assert tuple(rows[0][1:]) == (0.0, 12.5, 3.1, 'open-meteo')
    assert tuple(rows[2][1:4]) == (None, None, None)  # last day has no data yet


def test_fetch_weather_asks_before_overwriting_existing_data(gdf: GeoDataFarm):
    # Depends on test_fetch_weather_stores_precipitation_temperature_and_et0
    # (above, in this same file) having already created the table.
    assert 'test_field_weather_2024' in gdf.db.get_tables_in_db('weather')
    dlg = gdf.weather_data.dlg
    dlg.CBWeatherAllFields.setChecked(False)
    idx = dlg.CBWeatherField.findText('test_field')
    dlg.CBWeatherField.setCurrentIndex(idx)
    _set_range(dlg, '2024-05-01', '2024-05-03')
    new_daily = [{'date': '2024-05-01', 'precipitation_mm': 99.0,
                 'et0_mm': 1.0, 'temp_mean_c': 1.0}]

    with _patch_task_manager(gdf.weather_data), \
        mock.patch.object(gdf.weather_data, '_confirm_overwrite_one', return_value=False), \
        mock.patch.object(gdf.weather_data.client, 'daily_weather',
                          return_value=new_daily) as m:
        dlg.PBFetchWeather.click()
    m.assert_not_called()
    rows = gdf.db.execute_and_return(
        "SELECT precipitation_mm FROM weather.test_field_weather_2024"
        " ORDER BY date_ LIMIT 1")
    assert rows[0][0] == 0.0  # unchanged - user declined to overwrite

    with _patch_task_manager(gdf.weather_data), \
        mock.patch.object(gdf.weather_data, '_confirm_overwrite_one', return_value=True), \
        mock.patch.object(gdf.weather_data.client, 'daily_weather',
                          return_value=new_daily) as m:
        dlg.PBFetchWeather.click()
    m.assert_called_once()
    rows = gdf.db.execute_and_return(
        "SELECT precipitation_mm FROM weather.test_field_weather_2024"
        " ORDER BY date_ LIMIT 1")
    assert rows[0][0] == 99.0  # replaced - user accepted the overwrite


def test_fetch_weather_without_field_warns(gdf: GeoDataFarm):
    dlg = gdf.weather_data.dlg
    dlg.CBWeatherAllFields.setChecked(False)
    dlg.CBWeatherField.clear()
    with _patch_task_manager(gdf.weather_data), \
        mock.patch.object(gdf.weather_data.client, 'daily_weather') as m:
        gdf.weather_data.fetch_weather()
        m.assert_not_called()


def test_fetch_all_fields_stores_data_for_every_field(gdf: GeoDataFarm):
    # test_field and test_iso_field (both created in tests/test_field.py) sit
    # about 1 km apart, so they're expected to share one Open-Meteo call -
    # see test_cluster_by_location_groups_nearby_fields above for that
    # behaviour in isolation. Other fields may also exist by this point in
    # the suite, so this only asserts on the two fields it knows about
    # rather than an exact call count.
    for name in ('test_field_weather_2024', 'test_iso_field_weather_2024'):
        gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(name))
    dlg = gdf.weather_data.dlg
    dlg.CBWeatherAllFields.setChecked(True)
    _set_range(dlg, '2024-05-01', '2024-05-03')

    with _patch_task_manager(gdf.weather_data), \
        mock.patch.object(gdf.weather_data.client, 'daily_weather',
                          return_value=_FAKE_DAILY) as m:
        dlg.PBFetchWeather.click()

    assert m.call_count >= 1
    tables = gdf.db.get_tables_in_db('weather')
    assert 'test_field_weather_2024' in tables
    assert 'test_iso_field_weather_2024' in tables
    dlg.CBWeatherAllFields.setChecked(False)
