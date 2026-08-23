"""Tests for dated irrigation logging (import_data/handle_irrigation.py):
Raindancer operations logged with their own real date/geometry
(IrrigationHandler._store_dated_operation/get_grid_data). There is no
manual whole-field entry - no real irrigation pass covers a whole field at
once, so dated irrigation only ever comes from Raindancer.

Uses the shared ``gdf``/database fixture like tests/test_import_data.py, so
it must run as part of the full suite (`pytest tests`), not on its own -
see tests/conftest.py and the project's stateful/order-dependent test setup.
No network access needed - these mock MyRainDancer.get_operation_data
rather than hitting the real API.
"""
from datetime import datetime
from unittest import mock

from qgis.PyQt.QtCore import QDate

from ..GeoDataFarm import GeoDataFarm
from ..import_data.handle_irrigation import IrrigationHandler
from . import gdf

_TABLE = 'test_field_irrigation_events_2024'
# Well inside test_field's own boundary (see tests/test_field.py's
# coordinates: roughly lat 55.394-55.397, lng 13.552-13.560).
_LINE_INSIDE_TEST_FIELD = "LINESTRING(13.557 55.396, 13.555 55.395)"


def test_store_dated_operation_logs_the_real_date_and_flight_path(gdf: GeoDataFarm):
    # A Raindancer operation's own flight-path geometry (buffered, then
    # clipped to the field) is what lets
    # database_scripts/crop_simulation.py's per-cell stress map actually
    # vary by where the irrigation landed.
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))
    handler = IrrigationHandler(gdf)

    handler._store_dated_operation(_LINE_INSIDE_TEST_FIELD, datetime(2024, 6, 15), 18.5)

    assert _TABLE in gdf.db.get_tables_in_db('weather')
    rows = gdf.db.execute_and_return(
        "SELECT date_, irrigation_mm, source, st_area(polygon) FROM weather.{}".format(_TABLE))
    assert len(rows) == 1
    assert rows[0][0].isoformat() == '2024-06-15'
    assert rows[0][1] == 18.5
    assert rows[0][2] == 'raindancer'
    assert rows[0][3] > 0  # a real clipped flight-path polygon, not empty

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))


def test_store_dated_operation_touches_no_table_far_from_any_field(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))
    handler = IrrigationHandler(gdf)

    handler._store_dated_operation(
        "LINESTRING(0.0 0.0, 0.001 0.001)", datetime(2024, 6, 15), 18.5)

    assert _TABLE not in gdf.db.get_tables_in_db('weather')


def test_get_grid_data_logs_each_operation_into_the_dated_table(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))
    handler = IrrigationHandler(gdf)
    handler.IIR.CWFrom.setSelectedDate(QDate.fromString('2024-01-01', 'yyyy-MM-dd'))
    handler.IIR.CWTo.setSelectedDate(QDate.fromString('2024-12-31', 'yyyy-MM-dd'))
    operation = {
        'finished': {'year': 2024, 'month': 6, 'day': 15},
        'origin': {'lng': 13.555, 'lat': 55.395},
        'destination': {'lng': 13.557, 'lat': 55.396},
        'precipitation': 18.5,
    }
    handler.dancer = mock.Mock()
    handler.dancer.get_operation_data.return_value = [operation]

    handler.get_grid_data()

    rows = gdf.db.execute_and_return(
        "SELECT date_, irrigation_mm, source FROM weather.{}".format(_TABLE))
    assert len(rows) == 1
    assert rows[0][0].isoformat() == '2024-06-15'
    assert rows[0][1] == 18.5
    assert rows[0][2] == 'raindancer'

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))


def test_get_grid_data_skips_operations_outside_the_selected_range(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(_TABLE))
    handler = IrrigationHandler(gdf)
    handler.IIR.CWFrom.setSelectedDate(QDate.fromString('2024-01-01', 'yyyy-MM-dd'))
    handler.IIR.CWTo.setSelectedDate(QDate.fromString('2024-03-01', 'yyyy-MM-dd'))
    operation = {
        'finished': {'year': 2024, 'month': 6, 'day': 15},  # outside the range above
        'origin': {'lng': 13.555, 'lat': 55.395},
        'destination': {'lng': 13.557, 'lat': 55.396},
        'precipitation': 18.5,
    }
    handler.dancer = mock.Mock()
    handler.dancer.get_operation_data.return_value = [operation]

    handler.get_grid_data()

    assert _TABLE not in gdf.db.get_tables_in_db('weather')
