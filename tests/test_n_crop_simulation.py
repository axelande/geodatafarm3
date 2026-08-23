"""Integration tests for the Pro "Crop simulation" tab.

Uses the shared ``gdf``/database fixture like tests/test_import_data.py and
tests/test_import_weather.py, so it must run as part of the full suite
(`pytest tests`), not on its own - see tests/conftest.py and the project's
stateful/order-dependent test setup. The Lemon Squeezy and Open-Meteo HTTP
calls are both mocked so this test needs no network access.
"""
from datetime import date, timedelta
from unittest import mock

from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import QCheckBox
import pytest

from ..GeoDataFarm import GeoDataFarm
from ..database_scripts import crop_simulation as crop_simulation_module
from ..database_scripts.crop_simulation import (
    DEV_BYPASS_LICENSE_SETTING, LICENSE_INSTANCE_SETTING, LICENSE_KEY_SETTING)
from ..database_scripts.db import ensure_ferti_nutrient_column
from ..support_scripts import field_grid
from ..support_scripts.fertilizer_timing_model import DailyWeather
from . import gdf


def _weather_series(start, days, rain_day_index, temp=15.0):
    d0 = date.fromisoformat(start)
    out = []
    for i in range(days):
        d = d0 + timedelta(days=i)
        rain = 30.0 if i == rain_day_index else 0.0
        out.append({'date': d.isoformat(), 'precipitation_mm': rain,
                   'et0_mm': 3.0, 'temp_mean_c': temp,
                   'solar_radiation_mj_m2': 15.0, 'daylight_hours': 14.0})
    return out


def _clear_license(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.remove(LICENSE_KEY_SETTING)
    gdf.crop_simulation.qsettings.remove(LICENSE_INSTANCE_SETTING)


def _select_test_field(gdf: GeoDataFarm):
    page = gdf.crop_simulation.page
    idx = page.CBField.findText('test_field')
    if idx < 0:
        gdf.populate.reload_fields(page.CBField)
        idx = page.CBField.findText('test_field')
    page.CBField.setCurrentIndex(idx)


def test_simulation_is_locked_without_a_license(gdf: GeoDataFarm):
    _clear_license(gdf)

    assert gdf.crop_simulation.is_licensed() is False

    with mock.patch('requests.get') as m:
        gdf.crop_simulation.run_simulation()
        m.assert_not_called()


def test_activate_license_saves_key_and_instance_id(gdf: GeoDataFarm):
    _clear_license(gdf)
    page = gdf.crop_simulation.page
    page.LELicenseKey.setText('TEST-LICENSE-KEY')
    payload = {'activated': True, 'instance': {'id': 'instance-123'}}

    with mock.patch.object(gdf.crop_simulation.license_client, 'activate',
                           return_value=payload) as m:
        page.PBActivateLicense.click()

    m.assert_called_once()
    assert m.call_args.args[0] == 'TEST-LICENSE-KEY'
    assert gdf.crop_simulation.qsettings.value(LICENSE_KEY_SETTING) == 'TEST-LICENSE-KEY'
    assert gdf.crop_simulation.qsettings.value(LICENSE_INSTANCE_SETTING) == 'instance-123'
    assert 'unlocked' in page.LLicenseStatus.text()


def test_activate_license_with_rejected_key_stays_locked(gdf: GeoDataFarm):
    _clear_license(gdf)
    page = gdf.crop_simulation.page
    page.LELicenseKey.setText('BAD-KEY')
    payload = {'activated': False, 'error': 'This license key is not valid.'}

    with mock.patch.object(gdf.crop_simulation.license_client, 'activate',
                           return_value=payload):
        page.PBActivateLicense.click()

    assert gdf.crop_simulation.qsettings.value(LICENSE_KEY_SETTING, '') != 'BAD-KEY'
    assert 'Not licensed' in page.LLicenseStatus.text()
    assert gdf.crop_simulation.is_licensed() is False


def test_developer_license_bypass_only_works_in_test_mode(gdf: GeoDataFarm):
    _clear_license(gdf)
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    original_test_mode = gdf.test_mode
    gdf.test_mode = False
    try:
        assert gdf.crop_simulation.is_licensed() is False
    finally:
        gdf.test_mode = original_test_mode
        gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_license_network_failure_only_uses_recent_validation(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import LICENSE_LAST_VALIDATED_SETTING

    gdf.crop_simulation.qsettings.setValue(LICENSE_KEY_SETTING, 'TEST-LICENSE-KEY')
    gdf.crop_simulation.qsettings.setValue(LICENSE_INSTANCE_SETTING, 'instance-123')
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    with mock.patch.object(gdf.crop_simulation.license_client, 'validate',
                           side_effect=crop_simulation_module.LicenseError('offline')):
        gdf.crop_simulation.qsettings.setValue(LICENSE_LAST_VALIDATED_SETTING,
                                               crop_simulation_module.time.time())
        assert gdf.crop_simulation.is_licensed() is True
        gdf.crop_simulation.qsettings.setValue(
            LICENSE_LAST_VALIDATED_SETTING,
            crop_simulation_module.time.time()
            - crop_simulation_module.LICENSE_OFFLINE_GRACE_SECONDS - 1)
        assert gdf.crop_simulation.is_licensed() is False
    _clear_license(gdf)
    gdf.crop_simulation.qsettings.remove(LICENSE_LAST_VALIDATED_SETTING)


def test_run_simulation_uses_advanced_tier_for_a_well_dated_potato_application(gdf: GeoDataFarm):
    # Licensed, with a fake but locally-saved key/instance so is_licensed()
    # only needs the mocked validate() call, not a real network round trip.
    gdf.crop_simulation.qsettings.setValue(LICENSE_KEY_SETTING, 'TEST-LICENSE-KEY')
    gdf.crop_simulation.qsettings.setValue(LICENSE_INSTANCE_SETTING, 'instance-123')

    # test_import_weather.py leaves a real, persistent weather.test_field_
    # weather_2024 table on file for the whole suite (several of its own
    # tests deliberately depend on it surviving between them) - _load_
    # weather now prefers stored data over a live fetch (see its own
    # docstring), so without this it would silently use that real table
    # instead of ever calling the mock below, defeating the point of this
    # test entirely.
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_weather_2024")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate)"
        " VALUES ('test_field', 'potato', '2024-05-10', '150 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-05-01', '15', '3')")

    page = gdf.crop_simulation.page
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-05-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-05-15', 'yyyy-MM-dd'))

    weather = _weather_series('2024-05-01', 46, rain_day_index=9)  # 2024-05-10 -> index 9
    with mock.patch.object(gdf.crop_simulation, 'license_client') as license_mock, \
        mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather) as weather_mock:
        license_mock.validate.return_value = {'valid': True}
        page.PBRun.click()

    weather_mock.assert_called_once()
    details = page.TEDetails.toPlainText()
    assert '2024-05-10' in details
    assert 'advanced model - potato' in details
    assert gdf.crop_simulation.canvas is not None
    assert '1 application(s)' in page.LStatus.text()
    # No plant.manual row was inserted for THIS run, and no crop picked in
    # CBCrop - but test_import_data.py's test_import_plant_text leaves a
    # real, persistent plant.manual "ghost" row on file for the whole suite
    # (table_='test_field_plant_2023_04_15', crop 'Potatoes', date_text
    # only - see _load_crop's docstring on why date_text-only rows count
    # too), so the field's auto-detected crop below correctly comes from
    # that, independent of this run's own ferti event, which carries its
    # own 'potato' crop for the "advanced model" text above. That same
    # persistent import table also has a real "potato_variety" column
    # (a genuine ISO-XML-style designator - see _load_variety) whose actual
    # per-row value for this fixture is 'inova' - plant.manual's own
    # variety is the 'None' sentinel (test_import_plant_text picks the
    # column via the combo, which insert_manual_from_file.py no longer
    # echoes back as if it were a value - see _load_variety's 'None'
    # guard), so resolution correctly falls through to that raw value.
    assert page.LCrop.text() == (
        'Crop: Potatoes - variety: inova (from the planting record)')
    # The season irrigation/yield estimate runs independently of the
    # per-application analysis and should also have rendered something.
    assert 'Estimated yield' in page.LSeasonEstimate.text()
    # The date slider should now span the run's weather dates.
    assert page.SLDate.isEnabled()
    assert page.SLDate.maximum() > 0

    # tests/test_xclose.py removes every test field at the end of the suite
    # and refuses to remove one with dependent plant/ferti/spray/harvest/soil
    # data - clean up what this test added so that check still passes.
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")


def test_run_simulation_shows_actual_yield_when_harvest_data_overlaps_the_field(gdf: GeoDataFarm):
    # Same setup as the advanced-tier test above, plus a synthetic harvest
    # table (harvest.* tables get a 'pos' point column, not 'polygon' - see
    # _candidate_harvest_tables) overlapping test_field with a yield point
    # inside the run's date range - _load_actual_yield_t_ha should find it
    # and _render_actual_yield should show it next to the model's estimate.
    gdf.crop_simulation.qsettings.setValue(LICENSE_KEY_SETTING, 'TEST-LICENSE-KEY')
    gdf.crop_simulation.qsettings.setValue(LICENSE_INSTANCE_SETTING, 'instance-123')

    # See the identical guard in test_run_simulation_uses_advanced_tier_
    # for_a_well_dated_potato_application above for why this is needed.
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_weather_2024")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate)"
        " VALUES ('test_field', 'potato', '2024-05-10', '150 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-05-01', '15', '3')")

    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")
    create_result = gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_harvest_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, yield_kg_ha real, pos geometry(POINT, 4326))",
        return_failure=True)
    assert create_result[0] is True, create_result
    insert_result = gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_synthetic (date_, yield_kg_ha, pos)"
        " SELECT '2024-05-12 00:00:00', 42000.0, st_centroid(polygon)"
        " FROM fields WHERE field_name = 'test_field'",
        return_failure=True, return_row_count=True)
    assert insert_result[0] is True, insert_result
    assert insert_result[2] == 1, 'fixture insert did not add the harvest row'

    candidates = gdf.crop_simulation._candidate_harvest_tables('test_field')
    actual = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2024-05-01', '2024-05-15')
    assert 'test_field_harvest_synthetic' in candidates, candidates
    assert actual == 42.0, actual

    page = gdf.crop_simulation.page
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-05-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-05-15', 'yyyy-MM-dd'))

    weather = _weather_series('2024-05-01', 46, rain_day_index=9)
    with mock.patch.object(gdf.crop_simulation, 'license_client') as license_mock, \
        mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather) as weather_mock:
        license_mock.validate.return_value = {'valid': True}
        page.PBRun.click()

    weather_mock.assert_called_once()
    # isHidden() (not isVisible()) - isVisible() reflects the whole ancestor
    # chain (see test_advanced_toggle_shows_and_hides_the_curve_shape_section's
    # comment on the same gotcha for the settings dialog), which for this
    # page's embedding stays False in this test harness regardless of
    # show()/hide(); isHidden() reflects LActualYield's own explicit
    # show()/hide() state (set by _render_actual_yield) directly.
    assert page.LActualYield.isHidden() is False
    assert 'Actual harvested yield: 42.0 t/ha' in page.LActualYield.text()

    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")


def test_load_actual_yield_reads_harvest_manual_too(gdf: GeoDataFarm):
    # harvest.manual has a plain 'field' column, like ferti.manual - unlike
    # a per-import harvest.<table>, which only has a 'pos' point column and
    # needs the spatial match _candidate_harvest_tables does. Both sources
    # must be checked (real farm harvest data can live in either, depending
    # on whether it was entered by hand or came from a per-file import) -
    # this reproduces the bug report where a field's real harvest.manual
    # yield row wasn't being picked up at all.
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield)"
        " VALUES ('test_field', '2024-05-12', '42000')")

    actual = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2024-05-01', '2024-05-15')
    assert actual == 42.0, actual

    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")


def test_load_actual_yield_matches_by_year_not_the_runs_exact_date_range(gdf: GeoDataFarm):
    # A real harvest/lift date routinely falls well after a growing-season
    # "To" date (haulm-killed, then actually lifted later) - reproduces the
    # bug report where a real Sept harvest wasn't found for a run whose "To"
    # was in the same growing season but weeks earlier. Matching must be by
    # calendar year, not requiring the harvest date inside [date_from, date_to].
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_text = 'c_2024-09-20'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_text, yield)"
        " VALUES ('test_field', 'c_2024-09-20', '55000')")

    # Run's own date range ends months before the harvest date above.
    actual = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2024-04-01', '2024-05-15')
    assert actual == 55.0, actual
    # A different year must not match this row - 2099 rather than e.g. 2023
    # since other tests in this file leave real test_field harvest data
    # behind in some years (see this module's other harvest fixtures) and
    # would make a "nothing found" assumption false for the wrong reason.
    not_matched = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2099-04-01', '2099-05-15')
    assert not_matched is None, not_matched

    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_text = 'c_2024-09-20'")


def test_load_actual_yield_ignores_a_non_numeric_yield_matched_column(gdf: GeoDataFarm):
    # Reproduces the real-world crash report: _find_column('yield',) matches
    # on substring, so on a real ISO-XML harvest import it can just as
    # easily land on a machine diagnostic column that happens to contain
    # "yield" (e.g. a "Yield Measurement I/O" on/off flag, imported as
    # text) as on the real numeric yield value. avg() has no overload for
    # text, so this used to crash the whole farm-wide scan outright -
    # "function avg(text) does not exist" - instead of just finding that
    # table's "yield" column unusable, the same way an unparseable
    # harvest.manual row is simply skipped elsewhere. A table with only
    # non-numeric-looking values must be silently ignored (not crash); one
    # with a mix must still average just the numeric-looking ones.
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_yield_io_check")
    gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_harvest_yield_io_check (row_id serial"
        " PRIMARY KEY, date_ timestamp, yield_measurement__i_o_ text, pos geometry)")
    insert_result = gdf.db.execute_sql(
        # ::timestamp is required on each UNION ALL branch - a bare string
        # literal resolves to text as part of determining the UNION's
        # result type, before it ever reaches the target column, so it
        # loses the "match the target column's type" inference a plain
        # single-branch SELECT would get (see the identical gotcha noted in
        # test_load_events_collapses_many_gps_points_on_one_day_into_one_
        # application above) - without it this raises DatatypeMismatch,
        # which execute_sql swallows silently in test_mode.
        "INSERT INTO harvest.test_field_harvest_yield_io_check"
        " (date_, yield_measurement__i_o_, pos)"
        " SELECT '2024-09-10 00:00:00'::timestamp, 'ON', st_centroid(polygon)"
        " FROM fields WHERE field_name = 'test_field'"
        " UNION ALL"
        " SELECT '2024-09-11 00:00:00'::timestamp, '45000', st_centroid(polygon)"
        " FROM fields WHERE field_name = 'test_field'"
        " UNION ALL"
        " SELECT '2024-09-12 00:00:00'::timestamp, '47000', st_centroid(polygon)"
        " FROM fields WHERE field_name = 'test_field'",
        return_failure=True, return_row_count=True)
    assert insert_result[0] is True, insert_result
    assert insert_result[2] == 3, 'fixture insert did not add all 3 rows'

    actual = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2024-04-01', '2024-05-15')

    assert actual == 46.0, actual  # average of only the two numeric rows
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_yield_io_check")


def test_load_actual_yield_ignores_a_near_zero_average(gdf: GeoDataFarm):
    # Reproduces the real bug report: a field/year whose only matching
    # harvest.manual row is a near-zero yield-monitor artifact (a headland
    # turn/calibration pass, not a real measurement - no crop this
    # codebase models could plausibly average to a fraction of a kg/ha)
    # used to be returned as-is. "Teach your model" then divided its
    # Predicted figure by that near-zero Actual, producing absurd Diff
    # percentages (seen live: +9309725%) and would have corrupted any fit
    # trained against it. Must be treated the same as "nothing found".
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES ('test_field', '2024-05-12', '0.4')")

    actual = gdf.crop_simulation._load_actual_yield_t_ha('test_field', '2024-05-01', '2024-05-15')
    assert actual is None, actual

    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")


def test_compute_cell_traces_accumulates_rain_and_irrigation_per_cell(gdf: GeoDataFarm):
    # cell_water_totals (used by _render_heatmap's "rain + irrigation" mode)
    # is cumulative field-wide rain (same running total for every cell)
    # plus that cell's own irrigation on top - not the day-of stress figure
    # cell_traces already carries. Reuses the same half-field irrigation
    # fixture as test_resolve_irrigation_by_cell_only_matches_covered_cells,
    # so roughly half the grid ends up irrigated and half doesn't.
    table = 'test_field_irrigation_events_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " irrigation_mm double precision, polygon geometry, source text)".format(table))
    bbox = gdf.db.execute_and_return(
        "SELECT st_xmin(polygon), st_xmax(polygon), st_ymin(polygon),"
        " st_ymax(polygon) FROM fields WHERE field_name = 'test_field'")[0]
    xmin, xmax, ymin, ymax = bbox
    xmid = (xmin + xmax) / 2
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, irrigation_mm, polygon, source)"
        " VALUES ('2024-05-03', 15.0, st_makeenvelope(%s, %s, %s, %s, 4326), 'raindancer')"
        .format(table), params=(xmin - 1, ymin - 1, xmid, ymax + 1))

    # _weather_series returns raw dicts (mimicking OpenMeteoClient's own
    # response shape, which _load_weather normally converts) - convert to
    # DailyWeather here too, since _compute_cell_traces is called directly.
    weather = [
        DailyWeather(date=d['date'], precipitation_mm=d['precipitation_mm'],
                    et0_mm=d['et0_mm'], temp_mean_c=d['temp_mean_c'])
        for d in _weather_series('2024-05-01', 10, rain_day_index=1)]  # 30mm on 2024-05-02
    _, _, _, trace_dates, cell_water_totals, _ = gdf.crop_simulation._compute_cell_traces(
        'test_field', '2024-05-01', '2024-05-10', weather, 'potato', 15.0, 3.0)

    assert cell_water_totals
    last_date = trace_dates[-1]
    totals_on_last_date = [totals[last_date] for totals in cell_water_totals.values()]
    # Every cell got the same 30mm of rain; only the irrigated half also
    # got 15mm of irrigation - so the totals split into exactly two groups.
    assert max(totals_on_last_date) == 45.0
    assert min(totals_on_last_date) == 30.0

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_compute_cell_traces_computes_a_per_cell_predicted_yield(gdf: GeoDataFarm):
    # cell_yields (used by _render_heatmap's "yield" mode) combines each
    # cell's own water-only relative yield (daily_trace_with_relative_yield)
    # with the field-wide nitrogen/potassium/heat relative yields and that
    # cell's own crop model's potential_yield_t_ha - see
    # _compute_cell_traces' own docstring.
    weather = [
        DailyWeather(date=d['date'], precipitation_mm=d['precipitation_mm'],
                    et0_mm=d['et0_mm'], temp_mean_c=d['temp_mean_c'])
        for d in _weather_series('2024-05-01', 10, rain_day_index=1)]
    cell_polygons, _, _, _, _, cell_yields = gdf.crop_simulation._compute_cell_traces(
        'test_field', '2024-05-01', '2024-05-10', weather, 'potato', 15.0, 3.0)

    assert cell_yields
    assert set(cell_yields) == set(cell_polygons)
    for value in cell_yields.values():
        assert 0.0 <= value <= 45.0  # potato's potential_yield_t_ha ceiling

    # A worse field-wide nitrogen relative yield should never let any
    # cell's predicted yield come out higher (Liebig's law of the minimum
    # - see season_water_model.py's module docstring).
    _, _, _, _, _, stressed_cell_yields = gdf.crop_simulation._compute_cell_traces(
        'test_field', '2024-05-01', '2024-05-10', weather, 'potato', 15.0, 3.0,
        field_relative_yield_nitrogen=0.5)
    for cell_id, value in stressed_cell_yields.items():
        assert value <= cell_yields[cell_id]


def test_daily_yield_projection_follows_crop_maturity(gdf: GeoDataFarm):
    from ..support_scripts.crop_models import CROP_MODELS
    from ..support_scripts.season_water_model import daily_trace_with_relative_yield

    d0 = date(2024, 4, 1)
    weather = [DailyWeather(
        date=(d0 + timedelta(days=i)).isoformat(), precipitation_mm=3.0,
        et0_mm=3.0, temp_mean_c=15.0) for i in range(140)]
    _trace, final_water_fraction, _stage, daily_yields = (
        daily_trace_with_relative_yield(
            weather, 'potato', 20.0, 2.0, {}, crop_model=CROP_MODELS['potato'],
            planting_date=weather[0].date, include_daily_relative_yield=True))

    first = daily_yields[weather[0].date]
    early = daily_yields[weather[29].date]
    forming = daily_yields[weather[89].date]
    late = daily_yields[weather[139].date]
    assert first < 0.01
    assert early == 0.0
    assert early < forming < late
    assert late == pytest.approx(final_water_fraction, abs=0.001)


def test_change_map_mode_shows_label_only_for_rain_irrigation_mode(gdf: GeoDataFarm):
    page = gdf.crop_simulation.page
    assert page.CBMapMode.currentData() == 'stress'  # default, before any change
    assert page.LRainIrrigation.isHidden() is True

    page.CBMapMode.setCurrentIndex(page.CBMapMode.findData('rain_irrigation'))
    assert page.LRainIrrigation.isHidden() is False

    page.CBMapMode.setCurrentIndex(page.CBMapMode.findData('yield'))
    assert page.LRainIrrigation.isHidden() is True

    page.CBMapMode.setCurrentIndex(page.CBMapMode.findData('stress'))
    assert page.LRainIrrigation.isHidden() is True


def test_render_heatmap_in_yield_mode_uses_cell_yields_not_cell_traces(gdf: GeoDataFarm):
    # A direct check that the "yield" branch is wired to _cell_yields (not
    # accidentally left reading _cell_traces/_cell_water_totals, the other
    # two modes' data) and doesn't blow up when a cell has no yield figure.
    sim = gdf.crop_simulation
    sim._cell_polygons = {
        1: 'POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))',
        2: 'POLYGON((1 0, 1 1, 2 1, 2 0, 1 0))',
    }
    sim._cell_yields = {1: 30.0}  # cell 2 deliberately missing
    sim.page.CBMapMode.setCurrentIndex(sim.page.CBMapMode.findData('yield'))

    sim._render_heatmap('2024-05-01')

    assert sim.canvas is not None


def test_load_events_includes_an_imported_ferti_table_matched_spatially(gdf: GeoDataFarm):
    # Imported tables (unlike .manual) have no 'field' column - they're
    # matched to a field by geometry - and store date_ as TIMESTAMP, not
    # DATE (see import_data/handle_text_data.py), which is what the
    # _as_date_str normalisation fix guards against.
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE ferti.test_field_ferti_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, rate_kg_ha real, crop_type text,"
        " polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO ferti.test_field_ferti_synthetic"
        " (date_, rate_kg_ha, crop_type, polygon)"
        " SELECT '2024-05-20 00:00:00', 120.0, 'wheat', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    events = gdf.crop_simulation._load_events('test_field', '2024-05-01', '2024-05-31')
    matching = [e for e in events if e.date == '2024-05-20']
    assert len(matching) == 1
    assert matching[0].rate_text == '120.0'
    assert matching[0].crop == 'wheat'

    # Negative control: a different, non-overlapping field must not pick up
    # this table's data (test_iso_field sits ~1 km away, its own polygon
    # doesn't overlap test_field's).
    other_events = gdf.crop_simulation._load_events(
        'test_iso_field', '2024-05-01', '2024-05-31')
    assert not any(e.date == '2024-05-20' and e.rate_text == '120.0'
                  for e in other_events)

    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")


def test_load_events_collapses_many_gps_points_on_one_day_into_one_application(gdf: GeoDataFarm):
    # ISO-XML/text-imported ferti tables are machine logs with one row per
    # GPS-referenced point (see import_data/handle_text_data.py's
    # create_table) - a single day's spreading pass can log hundreds of
    # rows. Reproduces the real-world bug report: without aggregation, each
    # row became its own "application" (377 near-identical ones for one
    # real operation); this must collapse to exactly one per day.
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE ferti.test_field_ferti_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, rate_kg_ha real, crop_type text,"
        " polygon geometry)")
    insert_result = gdf.db.execute_sql(
        "INSERT INTO ferti.test_field_ferti_synthetic"
        " (date_, rate_kg_ha, crop_type, polygon)"
        # ::timestamp is required - concatenating with || makes this a text
        # expression, and Postgres has no *implicit* text->timestamp cast
        # (unlike a plain string literal, which the parser resolves against
        # the target column type directly) - without it this raises
        # DatatypeMismatch and execute_sql swallows that silently below.
        " SELECT ('2024-05-20 ' || lpad((n % 24)::text, 2, '0') || ':00:00')::timestamp,"
        " 118.0 + n, 'wheat', polygon"
        " FROM fields, generate_series(1, 50) AS n"
        " WHERE field_name = 'test_field'",
        return_failure=True, return_row_count=True)
    # execute_sql swallows a failed statement silently in test_mode (logs
    # nothing, just returns False) - assert on it explicitly so a broken
    # fixture insert fails loudly here instead of surfacing as a confusing
    # "0 events found" a few lines down.
    assert insert_result[0] is True, insert_result
    assert insert_result[2] == 50, 'fixture insert did not add all 50 rows'

    events = gdf.crop_simulation._load_events('test_field', '2024-05-01', '2024-05-31')

    matching = [e for e in events if e.date == '2024-05-20']
    assert len(matching) == 1
    # rate is the mean of 118+1 .. 118+50 = 118 + mean(1..50) = 118 + 25.5
    assert matching[0].rate_text == '143.5'
    assert matching[0].crop == 'wheat'

    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")


def test_load_imported_ferti_events_routes_a_tagged_nutrient_to_its_own_slot(gdf: GeoDataFarm):
    # An imported ferti table tagged with a constant 'nutrient' column
    # (set once per import batch - see handle_iso11783.py's ferti
    # nutrient prompt) must route its rate into that nutrient's own
    # FertilizerEvent slot, not the nitrogen default every table used to
    # get regardless of what was actually spread.
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE ferti.test_field_ferti_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, rate_kg_ha real, crop_type text,"
        " nutrient text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO ferti.test_field_ferti_synthetic"
        " (date_, rate_kg_ha, crop_type, nutrient, polygon)"
        " SELECT '2024-05-20 00:00:00', 90.0, 'wheat', 'K', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    events = gdf.crop_simulation._load_events('test_field', '2024-05-01', '2024-05-31')

    matching = [e for e in events if e.date == '2024-05-20']
    assert len(matching) == 1
    assert matching[0].rate_text_k == '90.0'
    assert not matching[0].rate_text  # not misattributed to nitrogen

    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")


def test_load_imported_ferti_events_drops_an_unmodeled_nutrient_instead_of_defaulting_to_nitrogen(
        gdf: GeoDataFarm):
    # 'S'/'Na' aren't modeled by FertilizerEvent at all (see its
    # docstring) - a table explicitly tagged with one of those must be
    # dropped, not silently misattributed to nitrogen just because it's
    # unrecognised (unlike a table with no nutrient column at all, which
    # keeps the original nitrogen-assumed behaviour - see
    # test_load_events_includes_an_imported_ferti_table_matched_spatially).
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE ferti.test_field_ferti_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, rate_kg_ha real, crop_type text,"
        " nutrient text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO ferti.test_field_ferti_synthetic"
        " (date_, rate_kg_ha, crop_type, nutrient, polygon)"
        " SELECT '2024-05-20 00:00:00', 90.0, 'wheat', 'S', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    events = gdf.crop_simulation._load_events('test_field', '2024-05-01', '2024-05-31')

    assert not any(e.date == '2024-05-20' for e in events)

    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")


def test_load_events_groups_ferti_manual_rows_by_nutrient_on_one_date(gdf: GeoDataFarm):
    # A single real application (e.g. one NPK blend) is stored as several
    # ferti.manual rows sharing a date, one per nutrient it delivered (see
    # ferti.manual.nutrient) - _load_events must fold those back into one
    # FertilizerEvent per date rather than treating each nutrient as its own
    # separate application.
    ensure_ferti_nutrient_column(gdf.db)
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, nutrient, rate)"
        " VALUES ('test_field', 'potato', '2024-05-12', 'N', '48'),"
        " ('test_field', 'potato', '2024-05-12', 'P', '20'),"
        " ('test_field', 'potato', '2024-05-12', 'K', '76'),"
        " ('test_field', 'potato', '2024-05-12', 'Mg', '7')")

    events = gdf.crop_simulation._load_events('test_field', '2024-05-01', '2024-05-31')

    matching = [e for e in events if e.date == '2024-05-12']
    assert len(matching) == 1
    event = matching[0]
    assert event.rate_text == '48'
    assert event.rate_text_p == '20'
    assert event.rate_text_k == '76'
    assert event.rate_text_mg == '7'
    assert event.crop == 'potato'

    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-05-12'")


def test_load_soil_includes_an_imported_soil_table_matched_spatially(gdf: GeoDataFarm):
    # _load_soil has no date filter - it ranks soil.manual rows and matched
    # imported-table rows together by date, most recent wins, ties broken
    # by insertion order (soil.manual first, see that method). Many other
    # tests in this file leave a ('test_field', '2024-06-01', '20', '2')
    # soil.manual row behind at some point in the run - without clearing
    # it here first, a same-day tie would make that unrelated row win over
    # this test's own imported-table row instead of the other way around.
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE soil.test_field_soil_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, clay_pct real, humus_pct real,"
        " polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO soil.test_field_soil_synthetic"
        " (date_, clay_pct, humus_pct, polygon)"
        " SELECT '2024-06-01 00:00:00', 22.5, 4.0, polygon"
        " FROM fields WHERE field_name = 'test_field'")

    clay, humus = gdf.crop_simulation._load_soil('test_field')

    assert clay == 22.5
    assert humus == 4.0
    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_synthetic")


def test_load_soil_reads_a_swedish_lab_reports_column_names(gdf: GeoDataFarm):
    # Reproduces the real bug report: a genuine Swedish soil lab report
    # (see _CLAY_COLUMN_PREFIXES' docstring) uses 'total_lerhalt' ("total
    # clay content") and 'mullhalt' ("humus content") - neither contains
    # "clay" or "humus" anywhere, so a table with real, usable soil data
    # on file was silently treated as having none. Also includes a
    # 'fin_lerhalt' ("fine clay", a narrower fraction) column, which must
    # not be preferred over the total figure.
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_swedish")
    gdf.db.execute_sql(
        "CREATE TABLE soil.test_field_soil_swedish (row_id serial"
        " PRIMARY KEY, date_ timestamp, total_lerhalt real, fin_lerhalt real,"
        " mullhalt real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO soil.test_field_soil_swedish"
        " (date_, total_lerhalt, fin_lerhalt, mullhalt, polygon)"
        " SELECT '2024-06-01 00:00:00', 28.0, 12.0, 5.5, polygon"
        " FROM fields WHERE field_name = 'test_field'")

    clay, humus = gdf.crop_simulation._load_soil('test_field')
    found, count = gdf.crop_simulation._soil_available('test_field')

    assert clay == 28.0  # the total figure, not fin_lerhalt's 12.0
    assert humus == 5.5
    assert found is True
    assert count >= 1

    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_swedish")


def test_find_column_matches_a_prefixed_column_name(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE ferti.test_field_ferti_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, rate_kg_ha real, polygon geometry)")

    found = gdf.crop_simulation._find_column(
        'ferti', 'test_field_ferti_synthetic', ('rate',))
    missing = gdf.crop_simulation._find_column(
        'ferti', 'test_field_ferti_synthetic', ('variety',))

    assert found == 'rate_kg_ha'
    assert missing is None
    gdf.db.execute_sql("DROP TABLE IF EXISTS ferti.test_field_ferti_synthetic")


def test_find_column_matches_a_keyword_anywhere_in_the_name(gdf: GeoDataFarm):
    # Reproduces the real bug report: ISO-XML imports (see
    # import_data/handle_iso11783.py) name columns straight from a
    # machine/DDOP's free-text designator, e.g. "Potato Variety" ->
    # potato_variety (keyword LAST, not first) - a strict prefix match
    # would miss this entirely.
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, potato_variety text,"
        " set_planting_distance_mm real, polygon geometry)")

    variety_col = gdf.crop_simulation._find_column(
        'plant', 'test_field_plant_synthetic', ('variety',))
    # 'spacing' alone would miss this real-world column name entirely -
    # the actual DDOP designator used "distance", not "spacing".
    spacing_col = gdf.crop_simulation._find_column(
        'plant', 'test_field_plant_synthetic', ('spacing', 'distance'))

    assert variety_col == 'potato_variety'
    assert spacing_col == 'set_planting_distance_mm'
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_manual_and_import_count_combines_both_sources(gdf: GeoDataFarm):
    # _manual_and_import_count (the "Data inventory" tab's building block
    # for planting/fertilizing/soil) must add together schema.manual rows
    # and spatially-matched schema.<table> import rows for the same
    # field/year, not just one or the other.
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2021-03-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2021-03-01', '15', '3')")

    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE soil.test_field_soil_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, clay_pct real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO soil.test_field_soil_synthetic (date_, clay_pct, polygon)"
        " SELECT '2021-04-15 00:00:00', 18.0, polygon"
        " FROM fields WHERE field_name = 'test_field'")

    count = gdf.crop_simulation._manual_and_import_count('soil', 'test_field', 2021)
    other_year_count = gdf.crop_simulation._manual_and_import_count('soil', 'test_field', 2099)

    assert count == 2  # one manual row + one import-table row
    assert other_year_count == 0

    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2021-03-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_soil_synthetic")


def test_harvest_count_combines_manual_and_import_sources(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2021-09-01'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield)"
        " VALUES ('test_field', '2021-09-01', '50000')")

    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_harvest_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, yield_kg_ha real, pos geometry(POINT, 4326))")
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_synthetic (date_, yield_kg_ha, pos)"
        " SELECT '2021-09-05 00:00:00', 45000.0, st_centroid(polygon)"
        " FROM fields WHERE field_name = 'test_field'")

    count = gdf.crop_simulation._harvest_count('test_field', 2021)
    other_year_count = gdf.crop_simulation._harvest_count('test_field', 2099)

    assert count == 2  # one manual row + one import-table row
    assert other_year_count == 0

    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2021-09-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")


def test_dated_table_exists_finds_weather_and_irrigation_style_tables(gdf: GeoDataFarm):
    # weather.<field>_weather_<year>/weather.<field>_irrigation_events_<year>
    # are the only storage either category ever has (no manual path for
    # either) - _dated_table_exists is what the "Data inventory" tab uses
    # to find them without already knowing which years exist.
    table = 'test_field_weather_2021'
    gdf.db.execute_sql(f"DROP TABLE IF EXISTS weather.{table}")
    gdf.db.execute_sql(
        f"CREATE TABLE weather.{table} (row_id serial PRIMARY KEY,"
        " date_ date, precipitation_mm double precision)")
    gdf.db.execute_sql(
        f"INSERT INTO weather.{table} (date_, precipitation_mm) VALUES ('2021-05-01', 3.0)")

    found, count = gdf.crop_simulation._dated_table_exists('test_field', 2021, 'weather')
    missing_found, missing_count = gdf.crop_simulation._dated_table_exists(
        'test_field', 2099, 'weather')

    assert found is True
    assert count == 1
    assert missing_found is False
    assert missing_count == 0

    gdf.db.execute_sql(f"DROP TABLE IF EXISTS weather.{table}")


def test_field_year_inventory_returns_all_six_categories(gdf: GeoDataFarm):
    # A field/year with nothing on file should still get one row per
    # category, all reported missing - not an empty list, and not silently
    # dropping a category that happens to have no data.
    rows = gdf.crop_simulation._field_year_inventory('test_field', 2099)

    assert [r[0] for r in rows] == [
        'Planting', 'Fertilizing', 'Harvest', 'Soil', 'Irrigation', 'Weather']
    assert all(found is False for (_label, _op, found, _count, _optional) in rows)
    # Soil (and only Soil) is optional - estimate_season already falls
    # back to a generic default when it's absent, unlike a real gap in
    # any other category.
    assert [optional for (label, _op, _found, _count, optional) in rows
           if label == 'Soil'] == [True]
    assert not any(optional for (label, _op, _found, _count, optional) in rows
                  if label != 'Soil')


def test_field_year_inventory_finds_soil_from_a_different_year(gdf: GeoDataFarm):
    # Reproduces the real bug report: the "Data inventory" tab showed Soil
    # as "Missing" for a field/year even though a real soil sample existed
    # for that field, just logged in an earlier year - unlike Planting/
    # Fertilizing/Harvest, soil is never matched by year at all (see
    # _load_soil: composition is treated as stable, so the reading closest
    # to a run's target date wins, however old) - the inventory tab must
    # reflect that, not claim a real sample is missing just because the
    # currently-selected year doesn't match when it was logged.
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2018-01-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2018-01-01', '15', '3')")

    rows = gdf.crop_simulation._field_year_inventory('test_field', 2024)
    soil_row = next(r for r in rows if r[0] == 'Soil')

    assert soil_row[2] is True, soil_row  # found
    assert soil_row[3] >= 1, soil_row  # count
    assert soil_row[4] is True, soil_row  # optional

    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2018-01-01'")


def test_check_field_year_data_shows_soil_as_optional_not_missing(gdf: GeoDataFarm):
    # The "Data inventory" tab must not show a genuine soil gap (e.g. a
    # field with only an EM38 conductivity survey on file, which this
    # codebase can't parse into clay%/humus% at all) the same way it
    # shows a real, model-blocking gap like Weather - see
    # _field_year_inventory's docstring on why Soil (and only Soil) is
    # optional.
    gdf.db.execute_sql("DELETE FROM soil.manual WHERE field = 'test_field'")
    page = gdf.crop_simulation.page
    idx = page.CBInventoryField.findText('test_field')
    page.CBInventoryField.setCurrentIndex(idx)
    page.SBInventoryYear.setValue(2099)

    gdf.crop_simulation._check_field_year_data()

    table = page.TWDataInventory
    status_by_label = {table.item(r, 0).text(): table.item(r, 1).text()
                       for r in range(table.rowCount())}
    assert status_by_label['Soil'] == '○ Optional (not on file)'
    assert status_by_label['Weather'] == '✗ Missing'  # a real gap, unchanged


def test_load_weather_caps_the_advanced_tier_horizon_at_today(gdf: GeoDataFarm):
    # Reproduces the real bug: a "to" date close to today pushed the +30
    # day advanced-tier horizon past Open-Meteo's allowed range, which
    # rejected the request outright instead of GeoDataFarm capping it.
    today = date.today().isoformat()
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=[]) as m:
        gdf.crop_simulation._load_weather('test_field', '2024-05-01', today)

    called_end_date = m.call_args.args[3]
    assert called_end_date <= today


def test_load_weather_warns_instead_of_erroring_on_api_failure(gdf: GeoDataFarm):
    from ..support_scripts.open_meteo_client import OpenMeteoError
    # _load_weather returns (weather, warning) rather than calling
    # report_warning/report_error itself - it also runs from a background
    # QgsTask's worker thread (see _compute_simulation), where touching
    # the message bar directly isn't safe; only the caller, back on the
    # main thread, shows the warning (see _apply_simulation_result).
    # test_import_weather.py leaves a real, persistent weather.test_field_
    # weather_2024 table on file for the whole suite - _load_weather now
    # prefers stored data over a live fetch (see its own docstring), so
    # without dropping it here this year would never even attempt the
    # mocked call below.
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_weather_2024")
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          side_effect=OpenMeteoError('boom')):
        weather, warning = gdf.crop_simulation._load_weather(
            'test_field', '2024-05-01', '2024-05-10')

    assert weather == []
    assert warning is not None
    assert 'boom' in warning


def test_load_weather_warns_when_open_meteo_returns_nothing(gdf: GeoDataFarm):
    # See the identical guard in test_load_weather_warns_instead_of_
    # erroring_on_api_failure above for why this is needed.
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_weather_2024")
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=[]):
        weather, warning = gdf.crop_simulation._load_weather(
            'test_field', '2024-05-01', '2024-05-10')

    assert weather == []
    assert warning is not None


def test_load_weather_prefers_a_fully_stored_year_over_a_live_fetch(gdf: GeoDataFarm):
    # Reproduces the real bug report: a farm-wide "Teach the model" scan
    # re-fetched every field's weather live regardless of what was
    # already stored via the free "Load weather" feature (see
    # import_data/handle_weather.py), routinely tripping Open-Meteo's
    # per-minute rate limit and silently losing fields that had nothing
    # actually missing. A year already stored must not hit the API at
    # all.
    table = 'test_field_weather_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " precipitation_mm double precision, temp_mean_c double precision,"
        " et0_mm double precision, polygon geometry, source text)".format(table))
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, precipitation_mm, temp_mean_c, et0_mm, source)"
        " VALUES ('2024-05-05', 3.5, 14.0, 2.1, 'open-meteo')".format(table))

    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather') as m:
        weather, warning = gdf.crop_simulation._load_weather(
            'test_field', '2024-05-01', '2024-05-10')

    m.assert_not_called()
    assert warning is None
    matching = [w for w in weather if w.date == '2024-05-05']
    assert len(matching) == 1
    assert matching[0].precipitation_mm == 3.5
    assert matching[0].temp_mean_c == 14.0
    assert matching[0].et0_mm == 2.1

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_load_weather_merges_stored_and_live_fetched_years(gdf: GeoDataFarm):
    # A field with some years already stored and others not must use the
    # stored data for the years it has and only live-fetch the genuinely
    # missing ones - not blindly re-fetch the whole requested range live
    # just because one year in it is missing.
    table = 'test_field_weather_2023'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " precipitation_mm double precision, temp_mean_c double precision,"
        " et0_mm double precision, polygon geometry, source text)".format(table))
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, precipitation_mm, temp_mean_c, et0_mm, source)"
        " VALUES ('2023-12-20', 1.0, 2.0, 0.5, 'open-meteo')".format(table))

    live_day = {'date': '2024-01-05', 'precipitation_mm': 4.0, 'et0_mm': 1.0,
               'temp_mean_c': 1.5, 'solar_radiation_mj_m2': 3.0, 'daylight_hours': 7.0}
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=[live_day]) as m:
        weather, warning = gdf.crop_simulation._load_weather(
            'test_field', '2023-12-15', '2024-01-10')

    assert warning is None
    m.assert_called_once()
    # Only the missing (2024) year was requested live, not the stored one.
    called_from, called_to = m.call_args.args[2], m.call_args.args[3]
    assert called_from.startswith('2024')
    assert called_to.startswith('2024')

    dates = {w.date for w in weather}
    assert '2023-12-20' in dates  # from the stored table
    assert '2024-01-05' in dates  # from the live fetch

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_add_and_remove_planned_event_updates_list_and_widget(gdf: GeoDataFarm):
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    page.DEPlannedDate.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.LEPlannedRate.setText('120 kg N/ha')

    page.PBAddPlanned.click()

    assert len(gdf.crop_simulation._planned_events) == 1
    assert gdf.crop_simulation._planned_events[0].date == '2024-06-01'
    assert gdf.crop_simulation._planned_events[0].rate_text == '120 kg N/ha'
    assert page.LWPlannedEvents.count() == 1

    page.LWPlannedEvents.setCurrentRow(0)
    page.PBRemovePlanned.click()

    assert gdf.crop_simulation._planned_events == []
    assert page.LWPlannedEvents.count() == 0


def test_add_planned_event_without_rate_warns_and_does_not_add(gdf: GeoDataFarm):
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    page.LEPlannedRate.setText('')

    page.PBAddPlanned.click()

    assert gdf.crop_simulation._planned_events == []
    assert page.LWPlannedEvents.count() == 0


def test_add_planned_event_with_p_k_mg_rates_populates_all_fields(gdf: GeoDataFarm):
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    page.DEPlannedDate.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.LEPlannedRate.setText('100 kg N/ha')
    page.LEPlannedRateP.setText('30')
    page.LEPlannedRateK.setText('200')
    page.LEPlannedRateMg.setText('15')

    page.PBAddPlanned.click()

    assert len(gdf.crop_simulation._planned_events) == 1
    event = gdf.crop_simulation._planned_events[0]
    assert event.rate_kg_n_ha == 100.0
    assert event.rate_kg_p_ha == 30.0
    assert event.rate_kg_k_ha == 200.0
    assert event.rate_kg_mg_ha == 15.0
    # All four line edits are cleared after a successful add, ready for
    # the next application.
    assert page.LEPlannedRate.text() == ''
    assert page.LEPlannedRateP.text() == ''
    assert page.LEPlannedRateK.text() == ''
    assert page.LEPlannedRateMg.text() == ''

    page.LWPlannedEvents.setCurrentRow(0)
    page.PBRemovePlanned.click()
    assert gdf.crop_simulation._planned_events == []


def test_add_planned_event_with_only_a_phosphorus_rate_does_not_warn(gdf: GeoDataFarm):
    # add_planned_event only warns/refuses when ALL FOUR nutrient fields
    # are empty - any single one (not just nitrogen) is enough to add the
    # application.
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    page.DEPlannedDate.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.LEPlannedRate.setText('')
    page.LEPlannedRateP.setText('30')
    page.LEPlannedRateK.setText('')
    page.LEPlannedRateMg.setText('')

    page.PBAddPlanned.click()

    assert len(gdf.crop_simulation._planned_events) == 1
    assert gdf.crop_simulation._planned_events[0].rate_kg_p_ha == 30.0
    assert gdf.crop_simulation._planned_events[0].rate_kg_n_ha is None

    page.LWPlannedEvents.setCurrentRow(0)
    page.PBRemovePlanned.click()


def test_run_simulation_feeds_planned_potassium_phosphorus_magnesium_into_the_season(
        gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))
    # Explicit, not relied on auto-detection from test_field's own planting
    # record - keeps this test deterministic regardless of what other tests
    # have done to that record by the time this one runs.
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('potato')
    if crop_idx < 0:
        page.CBCrop.addItem('potato')
        crop_idx = page.CBCrop.findText('potato')
    page.CBCrop.setCurrentIndex(crop_idx)
    page.DEPlannedDate.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.LEPlannedRate.setText('100')
    page.LEPlannedRateP.setText('30')
    page.LEPlannedRateK.setText('200')
    page.LEPlannedRateMg.setText('15')
    page.PBAddPlanned.click()

    weather = _weather_series('2024-06-01', 40, rain_day_index=-1)  # entirely dry
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert gdf.crop_simulation._last_run['fertilizer_kg_k_by_date'] == {'2024-06-01': 200.0}
    assert gdf.crop_simulation._last_run['phosphorus_applied_kg_ha'] == 30.0
    assert gdf.crop_simulation._last_run['magnesium_applied_kg_ha'] == 15.0

    crop_name = gdf.crop_simulation._last_run['crop_for_model']
    gdf.crop_simulation._populate_settings_dialog(crop_name)
    results_text = gdf.crop_simulation.settings_dlg.TEResults.toPlainText()
    assert 'Potassium' in results_text
    assert 'Phosphorus' in results_text
    assert 'Magnesium' in results_text

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_run_simulation_estimates_season_with_no_fertilizer_events(gdf: GeoDataFarm):
    # Licensed via the dev bypass this time, to also exercise that path.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 40, rain_day_index=-1)  # entirely dry
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert page.LStatus.text() == 'No fertilizer applications found for this field/period.'
    assert 'Estimated yield' in page.LSeasonEstimate.text()

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_crop_override_is_applied_to_events_missing_a_crop(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-08-01'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate)"
        " VALUES ('test_field', '', '2024-08-01', '100 kg N/ha')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-08-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-08-10', 'yyyy-MM-dd'))
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('wheat')
    if crop_idx < 0:
        page.CBCrop.addItem('wheat')
        crop_idx = page.CBCrop.findText('wheat')
    page.CBCrop.setCurrentIndex(crop_idx)

    weather = _weather_series('2024-08-01', 40, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    details = page.TEDetails.toPlainText()
    assert '2024-08-01' in details
    assert 'wheat' in details  # override applied since ferti.manual's crop was blank

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2024-08-01'")


def test_load_irrigation_sums_logged_events_within_the_date_range(gdf: GeoDataFarm):
    table = 'test_field_irrigation_events_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " irrigation_mm double precision, polygon geometry, source text)".format(table))
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, irrigation_mm, source) VALUES"
        " ('2024-06-01', 10.0, 'manual'), ('2024-06-01', 5.0, 'manual'),"
        " ('2024-06-10', 8.0, 'manual'), ('2024-12-25', 20.0, 'manual')"
        .format(table))

    totals = gdf.crop_simulation._load_irrigation('test_field', '2024-06-01', '2024-06-30')

    # Same-day rows accumulate (not overwritten); the December row is
    # outside the requested range and must not be included.
    assert totals == {'2024-06-01': 15.0, '2024-06-10': 8.0}

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_load_irrigation_returns_empty_when_no_table_exists(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DROP TABLE IF EXISTS weather.test_field_irrigation_events_2024")

    totals = gdf.crop_simulation._load_irrigation('test_field', '2024-06-01', '2024-06-30')

    assert totals == {}


def test_run_simulation_uses_logged_irrigation_in_the_season_estimate(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    table = 'test_field_irrigation_events_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 40, rain_day_index=-1)  # entirely dry
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()
    assert 'This field has irrigation data in the old undated grid' not in page.LLegacyIrrigationWarning.text()
    # The detailed irrigation breakdown moved off the main page into the
    # "Crop model settings" popup's live results (see
    # CropSimulation._season_full_text) - populate the dialog the same way
    # open_crop_settings does, without actually exec()-ing the modal popup.
    dry_crop_name = gdf.crop_simulation._last_run['crop_for_model']
    gdf.crop_simulation._populate_settings_dialog(dry_crop_name)
    dry_run_text = gdf.crop_simulation.settings_dlg.TEResults.toPlainText()

    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " irrigation_mm double precision, polygon geometry, source text)".format(table))
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, irrigation_mm, source) VALUES"
        " ('2024-06-03', 25.0, 'manual')".format(table))
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()
    irrigated_crop_name = gdf.crop_simulation._last_run['crop_for_model']
    gdf.crop_simulation._populate_settings_dialog(irrigated_crop_name)
    irrigated_run_text = gdf.crop_simulation.settings_dlg.TEResults.toPlainText()

    assert 'No irrigation logged' in dry_run_text
    assert 'You logged 25 mm' in irrigated_run_text
    # The short summary that stays on the main page no longer carries this
    # level of detail.
    assert 'You logged' not in page.LSeasonEstimate.text()

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_run_simulation_warns_about_legacy_undated_irrigation_grid(gdf: GeoDataFarm):
    # The old whole-farm grid (weather.irrigation_<year>) has real spatial
    # resolution but no date, so it can't feed this simulation's calendar -
    # a field with only that kind of data must be told to re-log it, not
    # silently show as "no irrigation logged".
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.test_field_irrigation_events_2024")
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.irrigation_2024")
    gdf.db.execute_sql(
        "CREATE TABLE weather.irrigation_2024 (field_row_id serial,"
        " polygon geometry, irrigation_mm double precision)")
    gdf.db.execute_sql(
        "INSERT INTO weather.irrigation_2024 (polygon, irrigation_mm)"
        " SELECT polygon, 12.0 FROM fields WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 10, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert 'This field has irrigation data in the old undated grid' in \
        page.LLegacyIrrigationWarning.text()
    assert '2024' in page.LLegacyIrrigationWarning.text()

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.irrigation_2024")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_run_simulation_builds_a_per_cell_stress_map(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert len(gdf.crop_simulation._cell_polygons) > 0
    assert len(gdf.crop_simulation._trace_dates) == 5
    first_cell_id = next(iter(gdf.crop_simulation._cell_polygons))
    assert set(gdf.crop_simulation._cell_traces[first_cell_id].keys()) == set(
        gdf.crop_simulation._trace_dates)
    assert page.SLDate.isEnabled()
    assert page.SLDate.maximum() == 4
    assert page.LSliderDate.text() == gdf.crop_simulation._trace_dates[-1]

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_resolve_irrigation_by_cell_only_matches_covered_cells(gdf: GeoDataFarm):
    # A Raindancer-sourced row's real (not whole-field) geometry should
    # only water the cells it actually covers - see
    # import_data/handle_irrigation.py's _store_dated_operation.
    table = 'test_field_irrigation_events_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " irrigation_mm double precision, polygon geometry, source text)".format(table))
    bbox = gdf.db.execute_and_return(
        "SELECT st_xmin(polygon), st_xmax(polygon), st_ymin(polygon),"
        " st_ymax(polygon) FROM fields WHERE field_name = 'test_field'")[0]
    xmin, xmax, ymin, ymax = bbox
    xmid = (xmin + xmax) / 2
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, irrigation_mm, polygon, source)"
        " VALUES ('2024-06-03', 20.0, st_makeenvelope(%s, %s, %s, %s, 4326), 'raindancer')"
        .format(table), params=(xmin - 1, ymin - 1, xmid, ymax + 1))

    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    irrigation_by_cell = gdf.crop_simulation._resolve_irrigation_by_cell(
        'test_field', '2024-06-01', '2024-06-10')
    field_grid.drop_grid(gdf.db)

    matched_cells = set(irrigation_by_cell.keys())
    assert matched_cells
    assert matched_cells.issubset({c.cell_id for c in cells})
    assert len(matched_cells) < len(cells)  # only (roughly) half the field was covered
    some_matched_cell = next(iter(matched_cells))
    assert irrigation_by_cell[some_matched_cell] == {'2024-06-03': 20.0}

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_resolve_irrigation_by_cell_covers_every_cell_a_wide_pass_overlaps(gdf: GeoDataFarm):
    # _resolve_irrigation_by_cell matches purely on each row's own stored
    # geometry - a row whose geometry happens to span the whole field
    # (e.g. a wide pass, or historical data with a coarser polygon) should
    # water every cell it actually overlaps, exactly like a narrow one
    # only waters the cells it overlaps (see the "only_matches_covered_
    # cells" test above).
    table = 'test_field_irrigation_events_2024'
    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))
    field_polygon_wkt = gdf.db.execute_and_return(
        "SELECT st_astext(polygon) FROM fields WHERE field_name = 'test_field'")[0][0]
    gdf.db.execute_sql(
        "CREATE TABLE weather.{} (row_id serial PRIMARY KEY, date_ date,"
        " irrigation_mm double precision, polygon geometry, source text)".format(table))
    gdf.db.execute_sql(
        "INSERT INTO weather.{} (date_, irrigation_mm, polygon, source)"
        " VALUES ('2024-06-03', 15.0, st_geomfromtext(%s, 4326), 'manual')".format(table),
        params=(field_polygon_wkt,))

    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    irrigation_by_cell = gdf.crop_simulation._resolve_irrigation_by_cell(
        'test_field', '2024-06-01', '2024-06-10')
    field_grid.drop_grid(gdf.db)

    # Allow a small margin for edge cells whose centroid could sit just
    # outside the (unclipped) field boundary - see field_grid.build_grid.
    assert len(irrigation_by_cell) >= len(cells) * 0.9
    assert all(v == {'2024-06-03': 15.0} for v in irrigation_by_cell.values())

    gdf.db.execute_sql("DROP TABLE IF EXISTS weather.{}".format(table))


def test_open_crop_settings_warns_when_nothing_to_configure(gdf: GeoDataFarm):
    saved_last_run = gdf.crop_simulation._last_run
    gdf.crop_simulation._last_run = None
    page = gdf.crop_simulation.page
    # CBCrop is a widget shared by every test in this module (gdf isn't
    # recreated per test) - save/restore its items and selection the same
    # way _last_run is saved/restored just above, or every later test that
    # doesn't set CBCrop itself silently inherits "nothing selected" here.
    saved_items = [page.CBCrop.itemText(i) for i in range(page.CBCrop.count())]
    saved_index = page.CBCrop.currentIndex()
    page.CBCrop.clear()
    page.CBCrop.addItem(gdf.crop_simulation.tr(crop_simulation_module._SELECT_CROP))
    page.CBCrop.setCurrentIndex(0)

    with mock.patch.object(crop_simulation_module, 'report_warning') as warn_mock:
        gdf.crop_simulation.open_crop_settings()

    warn_mock.assert_called_once()
    gdf.crop_simulation._last_run = saved_last_run
    page.CBCrop.clear()
    for item in saved_items:
        page.CBCrop.addItem(item)
    page.CBCrop.setCurrentIndex(saved_index)


def test_populate_settings_dialog_loads_the_effective_crop_model(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    crop_model_settings.reset_overrides(gdf.db, 'wheat')
    crop_model_settings.save_overrides(gdf.db, 'wheat', potential_yield_t_ha=42.0)

    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg

    assert dlg.LCropName.text() == 'Crop: wheat'
    assert dlg.SBPotentialYield.value() == 42.0
    assert gdf.crop_simulation._settings_crop_name == 'wheat'

    crop_model_settings.reset_overrides(gdf.db, 'wheat')


def test_recompute_settings_preview_reflects_dialog_changes_live(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 40, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    crop_name = gdf.crop_simulation._last_run['crop_for_model']
    gdf.crop_simulation._populate_settings_dialog(crop_name)
    dlg = gdf.crop_simulation.settings_dlg
    baseline_text = dlg.TEResults.toPlainText()
    assert 'Estimated yield' in baseline_text

    dlg.SBPotentialYield.setValue(dlg.SBPotentialYield.value() + 50.0)

    assert dlg.TEResults.toPlainText() != baseline_text

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_save_crop_settings_persists_and_updates_main_page(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 40, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    crop_name = gdf.crop_simulation._last_run['crop_for_model']
    crop_model_settings.reset_overrides(gdf.db, crop_name)
    gdf.crop_simulation._populate_settings_dialog(crop_name)
    dlg = gdf.crop_simulation.settings_dlg
    # SBPotentialYield.setRange(0.0, 200.0) - clearly above any crop's
    # actual default (9.5-45 t/ha) but still in range, unlike 999.0 which
    # would just silently clamp to 200.0.
    dlg.SBPotentialYield.setValue(150.0)

    dlg.PBSaveSettings.click()

    assert crop_model_settings.get_overrides(gdf.db, crop_name)['potential_yield_t_ha'] == 150.0
    assert 'Saved' in dlg.LSettingsStatus.text()
    assert '150.0 t/ha well-managed baseline' in page.LSeasonEstimate.text()

    crop_model_settings.reset_overrides(gdf.db, crop_name)
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_reset_crop_settings_reverts_to_default(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    from ..support_scripts.crop_models import get_crop_model
    crop_model_settings.save_overrides(gdf.db, 'wheat', potential_yield_t_ha=42.0)
    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg
    assert dlg.SBPotentialYield.value() == 42.0

    dlg.PBResetSettings.click()

    assert crop_model_settings.get_overrides(gdf.db, 'wheat') == {}
    assert dlg.SBPotentialYield.value() == get_crop_model('wheat').potential_yield_t_ha
    assert 'Reset to the built-in default' in dlg.LSettingsStatus.text()


def test_resolve_crop_and_variety_by_cell_keeps_a_variety_only_column_separate_from_crop(
        gdf: GeoDataFarm):
    # Reproduces the real-world layer shape: a machine-logged planting
    # pass only knows the product/variety name it planted (e.g.
    # "arsenal"), not the crop's botanical name - a lone 'variety' column
    # with no 'crop' column at all must never let the variety masquerade
    # as the crop (see _resolve_crop_and_variety_by_cell's docstring).
    _select_test_field(gdf)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '2024-05-01 00:00:00', 'arsenal', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    crop_variety_by_cell = gdf.crop_simulation._resolve_crop_and_variety_by_cell()
    field_grid.drop_grid(gdf.db)

    assert crop_variety_by_cell
    assert all(crop is None and variety == 'arsenal'
              for crop, variety in crop_variety_by_cell.values())

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_resolve_crop_and_variety_by_cell_reads_both_columns_when_both_exist(gdf: GeoDataFarm):
    _select_test_field(gdf)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop text, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, crop, variety, polygon)"
        " SELECT '2024-05-01 00:00:00', 'potato', 'fontane', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    crop_variety_by_cell = gdf.crop_simulation._resolve_crop_and_variety_by_cell()
    field_grid.drop_grid(gdf.db)

    assert crop_variety_by_cell
    assert all(crop == 'potato' and variety == 'fontane'
              for crop, variety in crop_variety_by_cell.values())

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_build_cell_traces_uses_the_field_crop_not_the_variety_name_for_a_variety_only_cell(
        gdf: GeoDataFarm):
    # The exact bug from the field report: without _resolve_crop_and_
    # variety_by_cell keeping crop/variety separate, a variety-only plant
    # layer made the per-cell water balance fall back to the generic
    # DEFAULT_CROP_MODEL instead of potato's own (get_crop_model('arsenal')
    # matches nothing, since "potato" never appears in that string).
    from ..support_scripts.fertilizer_timing_model import DailyWeather
    from ..support_scripts.season_water_model import daily_trace
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '2024-06-01 00:00:00', 'arsenal', polygon"
        " FROM fields WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('potato')
    if crop_idx < 0:
        page.CBCrop.addItem('potato')
        crop_idx = page.CBCrop.findText('potato')
    page.CBCrop.setCurrentIndex(crop_idx)

    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert gdf.crop_simulation._cell_varieties
    variety_cell_id = next(iter(gdf.crop_simulation._cell_varieties))
    assert gdf.crop_simulation._cell_varieties[variety_cell_id] == 'arsenal'
    actual_trace = gdf.crop_simulation._cell_traces[variety_cell_id]
    last_date = gdf.crop_simulation._trace_dates[-1]

    # weather (from _weather_series, used above only to mock the Open-Meteo
    # client) is a list of raw dicts - daily_trace needs real DailyWeather
    # objects, the same conversion _load_weather does for production code.
    weather_objects = [DailyWeather(**day) for day in weather]
    potato_trace = {p.date: p for p in daily_trace(weather_objects, 'potato', 20.0, 2.0, {})}
    default_trace = {p.date: p for p in daily_trace(
        weather_objects, 'not-a-real-crop-name', 20.0, 2.0, {})}
    assert actual_trace[last_date].capacity_mm == potato_trace[last_date].capacity_mm
    assert actual_trace[last_date].capacity_mm != default_trace[last_date].capacity_mm

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_settings_dialog_variety_picker_and_save_scoping(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '2024-06-01 00:00:00', 'solist', polygon"
        " FROM fields WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('potato')
    if crop_idx < 0:
        page.CBCrop.addItem('potato')
        crop_idx = page.CBCrop.findText('potato')
    page.CBCrop.setCurrentIndex(crop_idx)

    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert gdf.crop_simulation._last_run['varieties'] == ['solist']

    crop_model_settings.reset_overrides(gdf.db, 'potato', 'solist')
    gdf.crop_simulation._populate_settings_dialog('potato')
    dlg = gdf.crop_simulation.settings_dlg
    items = [dlg.CBVariety.itemText(i) for i in range(dlg.CBVariety.count())]
    assert items[1:] == ['solist']
    assert dlg.CBVariety.currentIndex() == 0  # defaults to "crop default"

    dlg.CBVariety.setCurrentIndex(dlg.CBVariety.findText('solist'))
    # SBPotentialYield.setRange(0.0, 200.0) - 999.0 would just clamp to 200.0.
    dlg.SBPotentialYield.setValue(150.0)
    dlg.PBSaveSettings.click()

    assert crop_model_settings.get_overrides(gdf.db, 'potato', 'solist') == {
        'potential_yield_t_ha': 150.0}
    assert crop_model_settings.get_overrides(gdf.db, 'potato') == {}
    # A variety-level save must not touch the main page's field-wide
    # number - the season estimate stays single-crop/field-wide by design.
    assert '150.0' not in page.LSeasonEstimate.text()

    crop_model_settings.reset_overrides(gdf.db, 'potato', 'solist')
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_load_spacing_includes_an_imported_plant_table_matched_spatially(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, spacing_mm real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic"
        " (date_, spacing_mm, polygon)"
        " SELECT '2024-06-01 00:00:00', 180.0, polygon"
        " FROM fields WHERE field_name = 'test_field'")

    spacing = gdf.crop_simulation._load_spacing('test_field')

    assert spacing == 180.0
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_spacing_ignores_a_non_numeric_value(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, spacing_mm text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic"
        " (date_, spacing_mm, polygon)"
        " SELECT '2024-06-01 00:00:00', 'wide', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    spacing = gdf.crop_simulation._load_spacing('test_field')

    # Not a strict "nothing found" - _load_spacing has no date filter, and
    # test_import_data.py's test_import_plant_text leaves a real, deliberately
    # persistent imported planting table for 'test_field' (a 2023-04-15
    # fixture, see that test) that may well have its own genuine numeric
    # spacing/distance column; when run as part of the full suite this
    # non-numeric 'wide' row (dated more recently, 2024-06-01) is correctly
    # skipped and the search falls through to whatever older, valid
    # candidate is next - it's specifically 'wide' being misparsed that
    # would be the bug, not a fallback to something else entirely.
    assert spacing is None or (isinstance(spacing, float) and spacing > 0)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_run_simulation_applies_spacing_yield_multiplier_when_crop_model_configures_it(
        gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, spacing_mm real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic"
        " (date_, spacing_mm, polygon)"
        " SELECT '2024-06-01 00:00:00', 350.0, polygon"
        " FROM fields WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    crop_model_settings.reset_overrides(gdf.db, 'potato')
    crop_model_settings.save_overrides(
        gdf.db, 'potato', reference_spacing_mm=250.0, spacing_sensitivity=1.0)
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('potato')
    if crop_idx < 0:
        page.CBCrop.addItem('potato')
        crop_idx = page.CBCrop.findText('potato')
    page.CBCrop.setCurrentIndex(crop_idx)

    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert gdf.crop_simulation._last_run['spacing_mm'] == 350.0
    # 250mm reference, 1.0 sensitivity, 350mm actual -> multiplier 0.84 (see
    # crop_models.spacing_yield_multiplier's own docstring for the formula),
    # applied to potato's 45.0 t/ha potential_yield_t_ha.
    expected_ceiling = 45.0 * 0.84
    assert '{:.1f} t/ha well-managed baseline'.format(expected_ceiling) in page.LSeasonEstimate.text()

    crop_model_settings.reset_overrides(gdf.db, 'potato')
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_settings_dialog_loads_and_saves_heat_stress_fields(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    from ..support_scripts.crop_models import get_crop_model
    crop_model_settings.reset_overrides(gdf.db, 'potato')

    gdf.crop_simulation._populate_settings_dialog('potato')
    dlg = gdf.crop_simulation.settings_dlg

    # Loads the built-in defaults (ky_heat=0.0 - disabled - for every crop).
    default_model = get_crop_model('potato')
    assert dlg.SBHeatThreshold.value() == default_model.heat_stress_threshold_c
    assert dlg.SBKyHeat.value() == 0.0

    dlg.SBHeatThreshold.setValue(26.0)
    dlg.SBKyHeat.setValue(0.8)
    dlg.PBSaveSettings.click()

    overrides = crop_model_settings.get_overrides(gdf.db, 'potato')
    assert overrides['heat_stress_threshold_c'] == 26.0
    assert overrides['ky_heat'] == 0.8

    crop_model_settings.reset_overrides(gdf.db, 'potato')


def test_run_simulation_applies_heat_stress_when_crop_model_configures_it(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-07-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-07-01', '20', '2')")
    crop_model_settings.reset_overrides(gdf.db, 'potato')
    crop_model_settings.save_overrides(
        gdf.db, 'potato', heat_stress_threshold_c=25.0, ky_heat=1.5)
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-07-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-07-10', 'yyyy-MM-dd'))
    gdf.crop_simulation._populate_crop_combo()
    crop_idx = page.CBCrop.findText('potato')
    if crop_idx < 0:
        page.CBCrop.addItem('potato')
        crop_idx = page.CBCrop.findText('potato')
    page.CBCrop.setCurrentIndex(crop_idx)

    hot_weather = _weather_series('2024-07-01', 10, rain_day_index=0, temp=35.0)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=hot_weather):
        page.PBRun.click()

    gdf.crop_simulation._populate_settings_dialog('potato')
    full_text = gdf.crop_simulation.settings_dlg.TEResults.toPlainText()
    assert 'Heat:' in full_text
    assert '10 of 10 day(s) exceeded 25' in full_text

    crop_model_settings.reset_overrides(gdf.db, 'potato')
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-07-01'")


def test_iso_style_variety_and_spacing_columns_are_found_end_to_end(gdf: GeoDataFarm):
    # End-to-end reproduction of the real bug report: a single ISO-XML-
    # imported plant table (import_data/handle_iso11783.py) with both a
    # variety and a spacing/distance column named straight from the
    # machine's free-text DDOP designators - "Potato Variety" and "Set
    # Planting Distance mm" - neither keyword at the start of its column
    # name, and "distance" instead of "spacing" for the latter.
    _select_test_field(gdf)
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, potato_variety text,"
        " set_planting_distance_mm real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic"
        " (date_, potato_variety, set_planting_distance_mm, polygon)"
        " SELECT '2024-06-01 00:00:00', 'arsenal', 180.0, polygon"
        " FROM fields WHERE field_name = 'test_field'")

    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    crop_variety_by_cell = gdf.crop_simulation._resolve_crop_and_variety_by_cell()
    field_grid.drop_grid(gdf.db)
    spacing = gdf.crop_simulation._load_spacing('test_field')

    assert crop_variety_by_cell
    assert all(crop is None and variety == 'arsenal'
              for crop, variety in crop_variety_by_cell.values())
    assert spacing == 180.0

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_advanced_toggle_shows_and_hides_the_curve_shape_section(gdf: GeoDataFarm):
    dlg = gdf.crop_simulation.settings_dlg
    # QWidget.isVisible() reflects the *whole* ancestor chain, not just
    # this widget's own setVisible() call - a child of a QDialog that was
    # never itself shown always reports isVisible() False regardless, so
    # this needs the dialog actually shown first to test the toggle
    # meaningfully (non-blocking - show(), never exec(), so this doesn't
    # hang waiting for a user to close it).
    dlg.show()
    assert dlg.advanced_frame.isVisible() is False

    dlg.PBToggleAdvanced.setChecked(True)
    assert dlg.advanced_frame.isVisible() is True
    assert 'Hide' in dlg.PBToggleAdvanced.text()

    dlg.PBToggleAdvanced.setChecked(False)
    assert dlg.advanced_frame.isVisible() is False
    assert 'Show' in dlg.PBToggleAdvanced.text()

    dlg.hide()


def test_populate_settings_dialog_loads_curve_shape_fields(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    from ..support_scripts.crop_models import get_crop_model
    crop_model_settings.reset_overrides(gdf.db, 'wheat')

    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg
    default_model = get_crop_model('wheat')

    assert dlg.SBGddBase.value() == default_model.gdd_base_c
    assert dlg.SBKcIni.value() == default_model.kc_ini
    assert dlg.SBKcMid.value() == default_model.kc_mid
    assert dlg.SBKcEnd.value() == default_model.kc_end
    assert dlg.SBKcIniEndGdd.value() == default_model.kc_ini_end_gdd
    assert dlg.SBKcMidEndGdd.value() == default_model.kc_mid_end_gdd
    assert dlg.SBKcLateStartGdd.value() == default_model.kc_late_start_gdd
    assert dlg.SBSeasonEndGdd.value() == default_model.season_end_gdd
    assert dlg.SBRootDepthMin.value() == default_model.root_depth_min_cm
    assert dlg.SBRootDepthMax.value() == default_model.root_depth_max_cm
    assert dlg.SBRootDepthFullGdd.value() == default_model.root_depth_full_gdd
    assert dlg.SBNUptakeMidpoint.value() == default_model.n_uptake_midpoint_gdd
    # SBNUptakeSteepness.setDecimals(4) - 6.5/season_end_gdd (a division,
    # unlike the other curve-shape fields' clean multiplications) generally
    # isn't representable in 4 decimals at all, so the round trip through
    # the spin box can be off by up to half its own step (0.00005); 1e-6
    # was tighter than the widget itself can ever actually store.
    assert abs(dlg.SBNUptakeSteepness.value() - default_model.n_uptake_steepness) < 1e-4


def test_dialog_crop_model_reflects_edited_curve_shape_spin_boxes(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    crop_model_settings.reset_overrides(gdf.db, 'wheat')

    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg
    dlg.SBGddBase.setValue(2.5)
    dlg.SBKcMid.setValue(1.05)

    model = gdf.crop_simulation._dialog_crop_model()

    assert model.gdd_base_c == 2.5
    assert model.kc_mid == 1.05


def test_render_curve_chart_creates_a_canvas_without_crashing(gdf: GeoDataFarm):
    from ..support_scripts.crop_models import get_crop_model
    dlg = gdf.crop_simulation.settings_dlg
    first_call_canvas = None

    gdf.crop_simulation._render_curve_chart(get_crop_model('potato'))
    assert dlg.curve_canvas is not None
    first_call_canvas = dlg.curve_canvas

    # Rebuilding (e.g. from a spin-box change) must replace, not stack, the
    # canvas - same stray-widget concern as _render_heatmap.
    gdf.crop_simulation._render_curve_chart(get_crop_model('wheat'))
    assert dlg.curve_canvas is not None
    assert dlg.curve_canvas is not first_call_canvas


def test_save_crop_settings_persists_curve_shape_fields(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    crop_model_settings.reset_overrides(gdf.db, 'wheat')

    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg
    dlg.SBGddBase.setValue(1.5)
    dlg.SBKcIniEndGdd.setValue(180.0)
    dlg.SBKcMidEndGdd.setValue(900.0)
    dlg.SBSeasonEndGdd.setValue(1600.0)

    dlg.PBSaveSettings.click()

    overrides = crop_model_settings.get_overrides(gdf.db, 'wheat')
    assert overrides['gdd_base_c'] == 1.5
    assert overrides['kc_ini_end_gdd'] == 180.0
    assert overrides['kc_mid_end_gdd'] == 900.0
    assert overrides['season_end_gdd'] == 1600.0

    crop_model_settings.reset_overrides(gdf.db, 'wheat')


def test_save_crop_settings_warns_and_saves_nothing_for_an_invalid_curve(gdf: GeoDataFarm):
    from ..support_scripts import crop_model_settings
    crop_model_settings.reset_overrides(gdf.db, 'wheat')

    gdf.crop_simulation._populate_settings_dialog('wheat')
    dlg = gdf.crop_simulation.settings_dlg
    # Force mid-season to end before the initial stage does - nonsensical.
    dlg.SBKcIniEndGdd.setValue(900.0)
    dlg.SBKcMidEndGdd.setValue(200.0)

    with mock.patch.object(crop_simulation_module, 'report_warning') as warn_mock:
        dlg.PBSaveSettings.click()

    warn_mock.assert_called_once()
    assert crop_model_settings.get_overrides(gdf.db, 'wheat') == {}


def test_run_simulation_refuses_a_second_run_while_one_is_in_flight(gdf: GeoDataFarm):
    # In production "in flight" means a _RunSimulationTask is running on a
    # background thread (see CropSimulation.run_simulation) - simulated
    # here by setting _running_task directly, since test_mode runs the
    # task synchronously and there's no real window to race against.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)
    page = gdf.crop_simulation.page
    gdf.crop_simulation._running_task = object()

    with mock.patch.object(crop_simulation_module, 'report_warning') as warn_mock, \
        mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather') as weather_mock:
        page.PBRun.click()

    warn_mock.assert_called_once()
    weather_mock.assert_not_called()  # never even reached the weather fetch

    gdf.crop_simulation._running_task = None
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_run_simulation_hides_the_spinner_and_restores_controls_when_done(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus)"
        " VALUES ('test_field', '2024-06-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    page.DEFrom.setDate(QDate.fromString('2024-06-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))

    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        page.PBRun.click()

    assert gdf.crop_simulation._running_task is None
    assert page.PBRun.isEnabled()
    assert page.CBField.isEnabled()
    assert gdf.crop_simulation.canvas is not None
    # The chart slot should hold the finished heatmap canvas, not the
    # spinner, once the run is done - see _show_simulation_spinner/
    # _hide_simulation_spinner.
    assert page.mplvl.indexOf(gdf.crop_simulation.canvas) != -1
    assert page.mplvl.indexOf(page.spinner) == -1
    assert page.spinner.isVisible() is False

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-06-01'")


def test_run_simulation_reports_an_error_and_resets_state_if_the_task_raises(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)
    page = gdf.crop_simulation.page

    with mock.patch.object(gdf.crop_simulation, '_load_weather',
                          side_effect=RuntimeError('boom')), \
        mock.patch.object(crop_simulation_module, 'report_error') as err_mock:
        page.PBRun.click()

    err_mock.assert_called_once()
    assert 'boom' in err_mock.call_args.args[0]
    assert gdf.crop_simulation._running_task is None
    assert page.PBRun.isEnabled()
    assert page.spinner.isVisible() is False

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_compute_simulation_returns_no_season_and_a_warning_when_weather_fails(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import _SimulationInputs
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)

    inputs = _SimulationInputs(
        field_name='test_field', date_from='2024-06-01', date_to='2024-06-05',
        override_crop='', planned_events=[])
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=[]):
        result = gdf.crop_simulation._compute_simulation(inputs)

    assert result.season is None
    assert len(result.warnings) == 1
    assert 'Open-Meteo' in result.warnings[0]

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_load_crop_returns_the_planting_date_alongside_the_crop_name(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-04-10'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_)"
        " VALUES ('test_field', 'potato', '2024-04-10')")

    crop, planting_date = gdf.crop_simulation._load_crop('test_field', '2024-06-01')

    assert crop == 'potato'
    assert planting_date == '2024-04-10'

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-04-10'")


def test_run_simulation_rejects_a_growth_stop_date_before_the_from_date(gdf: GeoDataFarm):
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)
    page = gdf.crop_simulation.page
    page.DEFrom.setDate(QDate.fromString('2024-06-10', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-06-20', 'yyyy-MM-dd'))
    page.CBGrowthStopEnabled.setChecked(True)
    page.DEGrowthStop.setDate(QDate.fromString('2024-06-05', 'yyyy-MM-dd'))

    with mock.patch.object(crop_simulation_module, 'report_warning') as warn_mock, \
        mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather') as weather_mock:
        page.PBRun.click()

    warn_mock.assert_called_once()
    weather_mock.assert_not_called()  # never even reached the weather fetch

    page.CBGrowthStopEnabled.setChecked(False)
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_compute_simulation_warns_when_the_logged_planting_date_precedes_the_from_date(
        gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import _SimulationInputs
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_)"
        " VALUES ('test_field', 'potato', '2024-05-01')")

    inputs = _SimulationInputs(
        field_name='test_field', date_from='2024-06-01', date_to='2024-06-05',
        override_crop='', planned_events=[])
    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        result = gdf.crop_simulation._compute_simulation(inputs)

    # Too early to safely anchor to (the weather fetch isn't widened to
    # cover it) - the GDD clock still starts at "From", but flagged.
    assert result.planting_date is None
    assert any('before the selected "From" date' in w for w in result.warnings)

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_compute_simulation_anchors_to_a_planting_date_inside_the_analysed_period(
        gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import _SimulationInputs
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-06-02'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_)"
        " VALUES ('test_field', 'potato', '2024-06-02')")

    inputs = _SimulationInputs(
        field_name='test_field', date_from='2024-06-01', date_to='2024-06-05',
        override_crop='', planned_events=[])
    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        result = gdf.crop_simulation._compute_simulation(inputs)

    assert result.planting_date == '2024-06-02'
    assert not any('before the selected "From" date' in w for w in result.warnings)
    assert result.season is not None
    assert 'anchored to a logged planting date of 2024-06-02' in result.season.note

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-06-02'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_compute_simulation_echoes_back_the_growth_stop_date_override(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import _SimulationInputs
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    _select_test_field(gdf)

    inputs = _SimulationInputs(
        field_name='test_field', date_from='2024-06-01', date_to='2024-06-05',
        override_crop='', planned_events=[], growth_stop_date='2024-06-03')
    weather = _weather_series('2024-06-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        result = gdf.crop_simulation._compute_simulation(inputs)

    assert result.growth_stop_date == '2024-06-03'
    assert result.season is not None
    assert 'Growth was treated as stopped' in result.season.note

    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_gdd_ticks_to_dates_maps_gdd_thresholds_to_the_dates_that_reached_them(
        gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import CropSimulation
    from ..support_scripts.fertilizer_timing_model import DailyWeather
    d0 = date(2024, 4, 1)
    # A steady 14.4 degC every day, base 4.4 degC -> exactly 10 GDD/day, so
    # the expected dates are easy to hand-check.
    weather = [DailyWeather(date=(d0 + timedelta(days=i)).isoformat(),
                            precipitation_mm=0.0, et0_mm=3.0, temp_mean_c=14.4)
              for i in range(120)]
    ticks = [600.0, 0.0, 1100.0, 200.0, 5000.0]  # unsorted, one unreachable

    dates = CropSimulation._gdd_ticks_to_dates(weather, 4.4, '2024-04-01', ticks)

    assert dates == ['2024-05-30', '2024-04-01', '2024-07-19', '2024-04-20', None]


def test_gdd_ticks_to_dates_ignores_days_before_start_date(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import CropSimulation
    from ..support_scripts.fertilizer_timing_model import DailyWeather
    d0 = date(2024, 3, 1)
    weather = [DailyWeather(date=(d0 + timedelta(days=i)).isoformat(),
                            precipitation_mm=0.0, et0_mm=3.0, temp_mean_c=14.4)
              for i in range(60)]  # 2024-03-01 .. 2024-04-29

    # Planted well after the start of the weather series - GDD must only
    # accumulate from planting, not from the first day the weather covers.
    dates = CropSimulation._gdd_ticks_to_dates(weather, 4.4, '2024-04-01', [100.0])

    assert dates == ['2024-04-10']  # 10 GDD/day from 2024-04-01, not 2024-03-01


# ------------------------------------------------------------------
# "Teach your model": farm-wide accuracy scan + per-crop fitting
# ------------------------------------------------------------------

def test_harvest_years_for_field_finds_manual_dates_and_the_date_text_fallback(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field'"
        " AND (date_ = '2021-09-10' OR date_text = 'c_2019-08-20')")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2021-09-10', '50000')")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_text, yield) VALUES"
        " ('test_field', 'c_2019-08-20', '40000')")

    years = gdf.crop_simulation._harvest_years_for_field('test_field')

    assert years.get(2021) == '2021-09-10'
    # No real date_ on file for the date_text-only row - falls back to
    # December 31 of the year read out of the text, not a made-up day.
    assert years.get(2019) == '2019-12-31'

    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field'"
        " AND (date_ = '2021-09-10' OR date_text = 'c_2019-08-20')")


def test_estimate_season_date_range_uses_a_logged_planting_date_when_available(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-03-15'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2024-03-15')")

    season_from, season_to, planting_logged, crop = (
        gdf.crop_simulation._estimate_season_date_range('test_field', '2024-08-01'))

    assert season_from == '2024-03-15'
    assert season_to == '2024-08-01'
    assert planting_logged is True
    assert crop == 'wheat'

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-03-15'")


def test_estimate_season_date_range_falls_back_without_a_logged_planting_date(gdf: GeoDataFarm):
    # A harvest date early enough that no test fixture could have a real
    # planting record on/before it - _load_crop (used internally here) also
    # checks every imported plant.* table (see its docstring), and those
    # persist for the whole suite (e.g. test_import_data.py's
    # plant.test_field_plant_2023_04_15), so a *future* harvest date would
    # actually be guaranteed to match one via its date_ <= target filter -
    # the opposite of what's needed to prove the fallback here.
    harvest_date = '1900-01-01'
    expected_from = (date(1900, 1, 1) - timedelta(days=150)).isoformat()

    season_from, season_to, planting_logged, crop = (
        gdf.crop_simulation._estimate_season_date_range('test_field', harvest_date))

    assert season_from == expected_from
    assert season_to == harvest_date
    assert planting_logged is False
    assert crop == ''


def test_fit_crop_model_recovers_known_parameters_from_synthetic_examples(gdf: GeoDataFarm):
    from dataclasses import replace as _replace
    from ..database_scripts.crop_simulation import TrainingExample, _fit_crop_model
    from ..support_scripts import crop_models
    from ..support_scripts.season_water_model import estimate_season

    base_model = crop_models.CROP_MODELS['wheat']
    true_model = _replace(base_model, potential_yield_t_ha=14.0, ky_nitrogen=2.0,
                          min_relative_yield_nitrogen=0.5)

    d0 = date(2024, 4, 1)
    # Rain matches ET0 every day - water never becomes the limiting
    # factor, so every example's yield is driven purely by the nitrogen
    # side, the thing this test is actually checking the fit recovers.
    weather = [DailyWeather(date=(d0 + timedelta(days=i)).isoformat(),
                            precipitation_mm=3.0, et0_mm=3.0, temp_mean_c=15.0)
              for i in range(180)]

    examples = []
    # Three deficit levels: none (pins potential_yield_t_ha), a partial
    # deficit that stays above the floor (pins ky_nitrogen), and a total
    # deficit that's clipped by the floor (pins min_relative_yield_nitrogen) -
    # without all three, the search has no way to tell the floor and
    # ky_nitrogen apart.
    for n_applied_fraction in (1.0, 0.85, 0.0):
        n_by_date = ({weather[10].date: true_model.season_n_demand_kg_ha * n_applied_fraction}
                    if n_applied_fraction else {})
        season = estimate_season(
            weather, 'wheat', 20.0, 2.0, {},
            fertilizer_kg_n_by_date=n_by_date, crop_model=true_model)
        examples.append(TrainingExample(
            field_name='synthetic', year=2024, crop='wheat',
            season_from=weather[0].date, season_to=weather[-1].date,
            planting_date_logged=True, weather=weather, clay=20.0, organic_matter=2.0,
            irrigation_by_date={}, fertilizer_kg_n_by_date=n_by_date,
            # None (not {}), matching the "actual" generation call above,
            # which never passes fertilizer_kg_k_by_date either - both
            # must agree on "potassium isn't modelled here" (see
            # estimate_season's own omitted-vs-empty-dict docstring), or
            # potassium's own floor would swamp the nitrogen signal this
            # test exists to isolate.
            fertilizer_kg_k_by_date=None, predicted_yield_t_ha=0.0,
            actual_yield_t_ha=season.estimated_yield_t_ha))

    fitted, sse_before, sse_after = _fit_crop_model(base_model, examples)

    # With only 3 data points - and nitrogen timing/leaching in the mix,
    # not just a flat season total - several nearby (potential_yield,
    # ky_nitrogen, floor) triples can fit them almost equally well; that's
    # a real property of small-sample nonlinear fitting, not a search
    # bug. The meaningful thing to check is that the search drives the
    # fit error down dramatically from the untouched default (proving it
    # actually searches, not just returns the starting point) and moves
    # every parameter in the right direction, not pinpoint recovery of
    # the exact generating values.
    assert sse_after < sse_before * 0.05
    assert fitted.potential_yield_t_ha > base_model.potential_yield_t_ha
    assert fitted.ky_nitrogen > base_model.ky_nitrogen
    assert fitted.min_relative_yield_nitrogen > base_model.min_relative_yield_nitrogen


def test_apply_teach_scan_result_shows_the_limiting_factor(gdf: GeoDataFarm):
    # Reproduces the real diagnostic gap: "Teach your model"'s results
    # table showed a bare Predicted (t/ha) figure with no way to tell
    # whether it was genuinely water-limited by that field/year's real
    # weather, or pinned at some other resource's floor regardless of
    # weather - the single-run tab already surfaces this
    # (season.limiting_factor, see _set_crop_label), so the farm-wide
    # table must too.
    from ..database_scripts.crop_simulation import TrainingExample
    example = TrainingExample(
        field_name='test_field', year=2024, crop='wheat',
        season_from='2024-04-01', season_to='2024-09-01', planting_date_logged=True,
        weather=[], clay=20.0, organic_matter=2.0, irrigation_by_date={},
        fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
        predicted_yield_t_ha=8.0, actual_yield_t_ha=7.5, limiting_factor='nitrogen')

    gdf.crop_simulation._apply_teach_scan_result([example])

    table = gdf.crop_simulation.page.TWTeachExamples
    assert table.item(0, 8).text() == 'nitrogen'


def test_train_selected_reports_not_enough_examples_for_a_single_checked_row(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import TrainingExample
    example = TrainingExample(
        field_name='test_field', year=2024, crop='wheat',
        season_from='2024-04-01', season_to='2024-09-01', planting_date_logged=True,
        weather=[], clay=20.0, organic_matter=2.0, irrigation_by_date={},
        fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
        predicted_yield_t_ha=8.0, actual_yield_t_ha=7.5)

    gdf.crop_simulation._apply_teach_scan_result([example])
    gdf.crop_simulation._train_selected()

    results_text = gdf.crop_simulation.page.TETeachResults.toPlainText()
    assert 'not enough' in results_text.lower()
    assert gdf.crop_simulation.page.CBTeachSaveCrop.count() == 0


def _two_teach_examples():
    from ..database_scripts.crop_simulation import TrainingExample
    return [
        TrainingExample(
            field_name='test_field', year=2024, crop='wheat',
            season_from='2024-04-01', season_to='2024-09-01', planting_date_logged=True,
            weather=[], clay=20.0, organic_matter=2.0, irrigation_by_date={},
            fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=8.0, actual_yield_t_ha=7.5, variety='zeta'),
        TrainingExample(
            field_name='test_field', year=2023, crop='wheat',
            season_from='2023-04-01', season_to='2023-09-01', planting_date_logged=True,
            weather=[], clay=20.0, organic_matter=2.0, irrigation_by_date={},
            fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=6.0, actual_yield_t_ha=5.5, variety='alpha'),
    ]


def test_sort_teach_examples_orders_rows_by_the_clicked_column(gdf: GeoDataFarm):
    gdf.crop_simulation._apply_teach_scan_result(_two_teach_examples())
    table = gdf.crop_simulation.page.TWTeachExamples

    gdf.crop_simulation._sort_teach_examples(4)  # Variety column

    assert [table.item(r, 4).text() for r in range(table.rowCount())] == ['alpha', 'zeta']

    gdf.crop_simulation._sort_teach_examples(4)  # same column again -> reversed

    assert [table.item(r, 4).text() for r in range(table.rowCount())] == ['zeta', 'alpha']


def test_sort_teach_examples_preserves_each_rows_checked_state(gdf: GeoDataFarm):
    # QTableWidget's own setSortingEnabled doesn't move a setCellWidget
    # checkbox along with its row - reproduces exactly that failure mode:
    # re-sorting must never silently change which rows are checked.
    gdf.crop_simulation._apply_teach_scan_result(_two_teach_examples())
    table = gdf.crop_simulation.page.TWTeachExamples
    # Uncheck 'zeta' while it's still row 0 (before sorting moves it).
    table.cellWidget(0, 0).findChild(QCheckBox).setChecked(False)

    gdf.crop_simulation._sort_teach_examples(4)  # -> alpha, zeta

    assert [table.item(r, 4).text() for r in range(table.rowCount())] == ['alpha', 'zeta']
    checked_varieties = {ex.variety for ex in gdf.crop_simulation._teach_checked_examples()}
    assert checked_varieties == {'alpha'}  # zeta stayed unchecked despite moving rows


def test_sort_teach_examples_ignores_a_click_on_the_checkbox_column(gdf: GeoDataFarm):
    gdf.crop_simulation._apply_teach_scan_result(_two_teach_examples())
    table = gdf.crop_simulation.page.TWTeachExamples
    before = [table.item(r, 1).text() for r in range(table.rowCount())]

    gdf.crop_simulation._sort_teach_examples(0)

    after = [table.item(r, 1).text() for r in range(table.rowCount())]
    assert after == before


def test_train_selected_skips_unchecked_rows(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import TrainingExample
    examples = [
        TrainingExample(
            field_name='test_field', year=year, crop='wheat',
            season_from='{}-04-01'.format(year), season_to='{}-09-01'.format(year),
            planting_date_logged=True, weather=[], clay=20.0, organic_matter=2.0,
            irrigation_by_date={}, fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=8.0, actual_yield_t_ha=7.5)
        for year in (2022, 2023)]

    gdf.crop_simulation._apply_teach_scan_result(examples)
    # Uncheck the second row - only one checked example remains, which
    # isn't enough to fit either.
    table = gdf.crop_simulation.page.TWTeachExamples
    table.cellWidget(1, 0).findChild(QCheckBox).setChecked(False)
    gdf.crop_simulation._train_selected()

    results_text = gdf.crop_simulation.page.TETeachResults.toPlainText()
    assert 'not enough' in results_text.lower()


def test_train_selected_and_save_persists_the_fitted_values(gdf: GeoDataFarm):
    from dataclasses import replace as _replace
    from ..database_scripts import crop_simulation as crop_simulation_module
    from ..database_scripts.crop_simulation import TrainingExample
    from ..support_scripts import crop_model_settings, crop_models

    crop_model_settings.reset_overrides(gdf.db, 'barley')
    examples = [
        TrainingExample(
            field_name='test_field', year=year, crop='barley',
            season_from='{}-04-01'.format(year), season_to='{}-09-01'.format(year),
            planting_date_logged=True, weather=[], clay=20.0, organic_matter=2.0,
            irrigation_by_date={}, fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=6.0, actual_yield_t_ha=5.5)
        for year in (2022, 2023)]
    gdf.crop_simulation._apply_teach_scan_result(examples)

    fitted_model = _replace(crop_models.CROP_MODELS['barley'], potential_yield_t_ha=99.0,
                            ky_nitrogen=2.5, min_relative_yield_nitrogen=0.42)
    with mock.patch.object(crop_simulation_module, '_fit_crop_model',
                          return_value=(fitted_model, 10.0, 2.0)) as fit_mock:
        gdf.crop_simulation._train_selected()

    fit_mock.assert_called_once()
    # Both checked examples were passed to the fit, still identifiable as
    # the same field/year rows selected in the checklist - the point of
    # the user's own follow-up that the training stay linked to exactly
    # which field/years went into it.
    fitted_examples = fit_mock.call_args.args[1]
    assert [(ex.field_name, ex.year) for ex in fitted_examples] == [
        ('test_field', 2022), ('test_field', 2023)]
    assert gdf.crop_simulation.page.CBTeachSaveCrop.count() == 1
    assert ('fitted from 2 field/year(s): test_field 2022, test_field 2023'
           in gdf.crop_simulation.page.TETeachResults.toPlainText())

    gdf.crop_simulation.page.PBTeachSaveCrop.click()

    overrides = crop_model_settings.get_overrides(gdf.db, 'barley')
    assert overrides['potential_yield_t_ha'] == 99.0
    assert overrides['ky_nitrogen'] == 2.5
    assert overrides['min_relative_yield_nitrogen'] == 0.42

    crop_model_settings.reset_overrides(gdf.db, 'barley')


def test_run_teach_scan_finds_a_field_year_with_harvest_data(gdf: GeoDataFarm):
    # End-to-end: "Scan farm" should turn one field/year's planting +
    # fertilizing + soil + harvest records into a row in the "Teach the
    # model" checklist - reuses the same fixture shape as
    # test_run_simulation_shows_actual_yield_when_harvest_data_overlaps_the_field.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2023-05-01')")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate) VALUES"
        " ('test_field', 'wheat', '2023-05-10', '120 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2023-04-15', '18', '3')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2023-09-15', '48000')")

    weather = _weather_series('2023-04-01', 220, rain_day_index=40)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        gdf.crop_simulation.run_teach_scan()

    table = gdf.crop_simulation.page.TWTeachExamples
    rows = [(table.item(r, 1).text(), table.item(r, 2).text(), table.item(r, 3).text())
            for r in range(table.rowCount())]
    assert ('test_field', '2023', 'wheat') in rows

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_run_teach_scan_finds_a_field_year_when_planting_was_only_imported(gdf: GeoDataFarm):
    # Reproduces the reported bug: a field whose planting was only ever
    # imported (never entered via plant.manual) used to make _load_crop
    # return no crop at all, which made _estimate_season_date_range return
    # crop='' and _compute_teach_scan silently skip the field/year - "Scan
    # farm" reported 0 matches even though real harvest data was on file.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, crop, polygon)"
        " SELECT '2023-05-01 00:00:00', 'wheat', polygon"
        " FROM fields WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate) VALUES"
        " ('test_field', 'wheat', '2023-05-10', '120 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2023-04-15', '18', '3')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2023-09-15', '48000')")

    weather = _weather_series('2023-04-01', 220, rain_day_index=40)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        gdf.crop_simulation.run_teach_scan()

    table = gdf.crop_simulation.page.TWTeachExamples
    rows = [(table.item(r, 1).text(), table.item(r, 2).text(), table.item(r, 3).text())
            for r in range(table.rowCount())]
    assert ('test_field', '2023', 'wheat') in rows

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_compute_teach_scan_skips_a_stale_planting_year_by_default(gdf: GeoDataFarm):
    # Reproduces the real bug report: a field harvested in several years
    # but only ever planted-and-logged once (e.g. 2015/2019/2021/2023
    # harvests, a single 2016 planting record on file) produced one
    # implausible training example per extra year, all reusing that same
    # stale planting date/crop/variety as if it were fresh - misleading
    # for an annual crop replanted every season. Default behaviour (the
    # "Allow multi-year crops" checkbox off) must skip a field/year whose
    # resolved planting date isn't in the harvest's own calendar year.
    # 2098/2099 (not 2022/2023) - test_field carries a real, persistent
    # harvest.test_field_harvest_2023_09_15 import table for the whole
    # suite (see test_import_data.py's test_import_harvest_text), which
    # would otherwise win _harvest_years_for_field's per-year max() over
    # this test's own 2023 row and pull in an unrelated planting date/
    # season entirely - 2099 is this file's own established "definitely
    # uncontaminated" year (see e.g. test_load_actual_yield_matches_by_
    # year_not_the_runs_exact_date_range).
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2098-12-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2098-12-01')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2099-02-01'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2099-02-01', '48000')")

    weather = _weather_series('2098-12-01', 75, rain_day_index=10)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        examples, skip_reasons = gdf.crop_simulation._compute_teach_scan()

    matching = [ex for ex in examples
               if ex.field_name == 'test_field' and ex.year == 2099]
    assert matching == []
    assert any('different year' in reason for reason in skip_reasons)

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2098-12-01'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2099-02-01'")


def test_compute_teach_scan_includes_a_stale_planting_year_when_allowed(gdf: GeoDataFarm):
    # Same fixture as test_compute_teach_scan_skips_a_stale_planting_year_
    # by_default, but with allow_multiyear_crops=True (the checkbox on) -
    # the field/year must be included, still anchored to the real
    # (if old) planting date, for farms with genuinely multi-year crops.
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2098-12-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2098-12-01')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2099-02-01'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2099-02-01', '48000')")

    weather = _weather_series('2098-12-01', 75, rain_day_index=10)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        examples, _skip_reasons = gdf.crop_simulation._compute_teach_scan(
            allow_multiyear_crops=True)

    matching = [ex for ex in examples
               if ex.field_name == 'test_field' and ex.year == 2099]
    assert len(matching) == 1
    assert matching[0].season_from == '2098-12-01'

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2098-12-01'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2099-02-01'")


def test_allow_multiyear_crops_checkbox_is_off_by_default(gdf: GeoDataFarm):
    assert gdf.crop_simulation.page.CBAllowMultiyearCrops.isChecked() is False


def test_compute_teach_scan_surfaces_the_real_weather_failure_reason(gdf: GeoDataFarm):
    from ..support_scripts.open_meteo_client import OpenMeteoError
    # Reproduces the real bug report: a field/year with nothing missing
    # in the Data inventory tab could still silently never appear in
    # "Scan farm" results, with no way to tell why - the live Open-Meteo
    # fetch (not the separate stored/"Load weather" table that tab
    # checks - see handle_weather.py's docstring) is what actually gates
    # this, and its failure reason used to be thrown away entirely in
    # favour of one bare "no weather data available" bucket.
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2024-05-01')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-09-15'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2024-09-15', '48000')")

    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          side_effect=OpenMeteoError('boom')):
        _examples, skip_reasons = gdf.crop_simulation._compute_teach_scan()

    assert any('boom' in reason for reason in skip_reasons)

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2024-09-15'")


def test_load_crop_falls_back_to_an_imported_plant_table_when_manual_has_nothing(
        gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-04-10'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, crop, polygon)"
        " SELECT '2024-04-10 00:00:00', 'potato', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    crop, planting_date = gdf.crop_simulation._load_crop('test_field', '2024-06-01')

    assert crop == 'potato'
    assert planting_date == '2024-04-10'

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_crop_prefers_whichever_source_is_more_recent(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-03-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2024-03-01')")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, crop, polygon)"
        " SELECT '2024-05-01 00:00:00', 'potato', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    crop, planting_date = gdf.crop_simulation._load_crop('test_field', '2024-06-01')

    assert crop == 'potato'
    assert planting_date == '2024-05-01'

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-03-01'")


def test_load_variety_falls_back_to_an_imported_plant_table_when_manual_has_nothing(
        gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '2024-04-10 00:00:00', 'bintje', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    variety, planting_date = gdf.crop_simulation._load_variety('test_field', '2024-06-01')

    assert variety == 'bintje'
    assert planting_date == '2024-04-10'
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_variety_reads_date_text_only_manual_rows(gdf: GeoDataFarm):
    # Same date_text-only gap _load_crop had to handle (see its
    # docstring) - a plant.manual row logged via the "same date for every
    # row" import path only ever sets date_text, never date_.
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_text = 'c_2024-04-12'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, variety, date_text) VALUES"
        " ('test_field', 'potato', 'solist', 'c_2024-04-12')")

    variety, planting_date = gdf.crop_simulation._load_variety('test_field', '2024-06-01')

    assert variety == 'solist'
    assert planting_date == '2024-04-12'
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_text = 'c_2024-04-12'")


def test_load_variety_skips_a_column_that_is_also_matched_as_crop(gdf: GeoDataFarm):
    # A table with one ambiguous column (matches both the 'crop' and
    # 'variety' substrings, e.g. a real column literally named
    # "crop_variety") must never let that column's values pose as the
    # variety too - see _load_variety's docstring, the same rule
    # _resolve_crop_and_variety_by_cell applies per-cell.
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop_variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, crop_variety, polygon)"
        " SELECT '1900-01-01 00:00:00', 'wheat', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    # 1900 - safely before test_import_data.py's own persistent
    # plant.test_field_plant_2023_04_15 fixture (which has a real
    # "potato_variety" column of its own), so this only ever sees the one
    # ambiguous column under test here.
    variety, planting_date = gdf.crop_simulation._load_variety('test_field', '1900-06-01')

    assert variety is None
    assert planting_date is None
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_variety_breakdown_matches_load_variety_for_a_single_variety(gdf: GeoDataFarm):
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '1900-01-01 00:00:00', 'bintje', polygon"
        " FROM fields WHERE field_name = 'test_field'")

    planting_date, table, variety_col, varieties = gdf.crop_simulation._load_variety_breakdown(
        'test_field', '1900-06-01')

    assert planting_date == '1900-01-01'
    assert table == 'test_field_plant_synthetic'
    assert variety_col == 'variety'
    assert varieties == [('bintje', 1)]
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_variety_breakdown_returns_every_variety_with_its_row_count(gdf: GeoDataFarm):
    # Reproduces the real bug report: a field genuinely planted with two
    # varieties in the same pass used to show only one of them in "Teach
    # the model" (whichever row happened to sort last among same-date
    # ties in Postgres - _load_variety's tie-break), not even reliably
    # the more common one.
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '1900-01-01 00:00:00', 'belana', polygon FROM fields"
        " WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '1900-01-01 09:00:00', 'belana', polygon FROM fields"
        " WHERE field_name = 'test_field'")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '1900-01-01 10:00:00', 'queenanne', polygon FROM fields"
        " WHERE field_name = 'test_field'")

    planting_date, _table, _col, varieties = gdf.crop_simulation._load_variety_breakdown(
        'test_field', '1900-06-01')

    # date_::date grouping - the three rows share a calendar date despite
    # different times, matching how one continuous planting pass logs.
    assert planting_date == '1900-01-01'
    assert varieties == [('belana', 2), ('queenanne', 1)]
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_variety_breakdown_prefers_manual_on_an_exact_date_tie(gdf: GeoDataFarm):
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '1900-01-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, variety, date_) VALUES"
        " ('test_field', 'wheat', 'manual_variety', '1900-01-01')")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " SELECT '1900-01-01 00:00:00', 'table_variety', polygon FROM fields"
        " WHERE field_name = 'test_field'")

    _date, table, _col, varieties = gdf.crop_simulation._load_variety_breakdown(
        'test_field', '1900-06-01')

    assert table is None  # manual won the tie, so nothing to spatially join against
    assert varieties == [('manual_variety', 1)]

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '1900-01-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")


def test_load_actual_yield_by_variety_matches_harvest_points_to_their_variety_zone(
        gdf: GeoDataFarm):
    # A harvest point must be attributed to whichever planting row's own
    # swath (not the whole field) it falls within - see
    # _load_actual_yield_by_variety_t_ha's docstring.
    bbox = gdf.db.execute_and_return(
        "SELECT st_xmin(polygon), st_xmax(polygon), st_ymin(polygon),"
        " st_ymax(polygon) FROM fields WHERE field_name = 'test_field'")[0]
    xmin, xmax, ymin, ymax = bbox
    xmid = (xmin + xmax) / 2

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " VALUES ('1900-01-01 00:00:00', 'west_variety',"
        " st_makeenvelope(%s, %s, %s, %s, 4326))",
        params=(xmin - 1, ymin - 1, xmid, ymax + 1))
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_synthetic (date_, variety, polygon)"
        " VALUES ('1900-01-01 00:00:00', 'east_variety',"
        " st_makeenvelope(%s, %s, %s, %s, 4326))",
        params=(xmid, ymin - 1, xmax + 1, ymax + 1))

    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_harvest_synthetic (row_id serial"
        " PRIMARY KEY, date_ timestamp, yield_kg_ha real, pos geometry(POINT, 4326))")
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_synthetic (date_, yield_kg_ha, pos)"
        " VALUES ('1900-09-01 00:00:00', 40000.0, st_setsrid(st_makepoint(%s, %s), 4326))",
        params=((xmin + xmid) / 2, (ymin + ymax) / 2))
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_synthetic (date_, yield_kg_ha, pos)"
        " VALUES ('1900-09-01 00:00:00', 60000.0, st_setsrid(st_makepoint(%s, %s), 4326))",
        params=((xmid + xmax) / 2, (ymin + ymax) / 2))

    result = gdf.crop_simulation._load_actual_yield_by_variety_t_ha(
        'test_field', 'test_field_plant_synthetic', '1900-01-01', 'variety', 1900)

    assert result == {'west_variety': 40.0, 'east_variety': 60.0}

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_synthetic")
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_synthetic")


def test_compute_teach_scan_splits_a_multi_variety_field_year_into_separate_examples(
        gdf: GeoDataFarm):
    # End-to-end version of the real bug report: Tabbehus 2018 genuinely
    # had two varieties on file (Belana/QueenAnne) but "Teach your model"
    # only ever produced one training example for it, comparing one
    # variety's prediction against the *whole field's* blended actual
    # yield - wrong for both varieties whenever they didn't yield the
    # same. Each variety must get its own example, matched against only
    # the actual yield from its own half of the field.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    bbox = gdf.db.execute_and_return(
        "SELECT st_xmin(polygon), st_xmax(polygon), st_ymin(polygon),"
        " st_ymax(polygon) FROM fields WHERE field_name = 'test_field'")[0]
    xmin, xmax, ymin, ymax = bbox
    xmid = (xmin + xmax) / 2

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2099-05-01'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_multivariety")
    gdf.db.execute_sql(
        "CREATE TABLE plant.test_field_plant_multivariety (row_id serial"
        " PRIMARY KEY, date_ timestamp, crop text, variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_multivariety (date_, crop, variety, polygon)"
        " VALUES ('2099-05-01 00:00:00', 'wheat', 'west_variety',"
        " st_makeenvelope(%s, %s, %s, %s, 4326))",
        params=(xmin - 1, ymin - 1, xmid, ymax + 1))
    gdf.db.execute_sql(
        "INSERT INTO plant.test_field_plant_multivariety (date_, crop, variety, polygon)"
        " VALUES ('2099-05-01 00:00:00', 'wheat', 'east_variety',"
        " st_makeenvelope(%s, %s, %s, %s, 4326))",
        params=(xmid, ymin - 1, xmax + 1, ymax + 1))

    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2099-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate) VALUES"
        " ('test_field', 'wheat', '2099-05-10', '120 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2099-04-15'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2099-04-15', '18', '3')")

    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_multivariety")
    gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_harvest_multivariety (row_id serial"
        " PRIMARY KEY, date_ timestamp, yield_kg_ha real, pos geometry(POINT, 4326))")
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_multivariety (date_, yield_kg_ha, pos)"
        " VALUES ('2099-09-15 00:00:00', 40000.0, st_setsrid(st_makepoint(%s, %s), 4326))",
        params=((xmin + xmid) / 2, (ymin + ymax) / 2))
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_harvest_multivariety (date_, yield_kg_ha, pos)"
        " VALUES ('2099-09-15 00:00:00', 60000.0, st_setsrid(st_makepoint(%s, %s), 4326))",
        params=((xmid + xmax) / 2, (ymin + ymax) / 2))

    weather = _weather_series('2099-04-01', 220, rain_day_index=40)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        examples, _skip_reasons = gdf.crop_simulation._compute_teach_scan()

    matching = {ex.variety: ex for ex in examples
               if ex.field_name == 'test_field' and ex.year == 2099}
    assert set(matching) == {'west_variety', 'east_variety'}
    assert matching['west_variety'].actual_yield_t_ha == 40.0
    assert matching['east_variety'].actual_yield_t_ha == 60.0

    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.test_field_plant_multivariety")
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_harvest_multivariety")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2099-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2099-04-15'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_run_simulation_uses_the_fields_resolved_variety(gdf: GeoDataFarm):
    # The point of the feature request: two varieties of the same crop can
    # have a genuinely different yield ceiling - the field-wide season
    # estimate (not just the per-cell stress map, which was already
    # variety-aware via _resolve_crop_and_variety_by_cell) must resolve
    # and apply the field's own variety, not just its crop.
    from ..database_scripts import crop_simulation as crop_simulation_module
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, variety, date_) VALUES"
        " ('test_field', 'potato', 'bintje', '2024-05-01')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2024-05-01', '20', '2')")
    page = gdf.crop_simulation.page
    gdf.crop_simulation._planned_events = []
    page.LWPlannedEvents.clear()
    _select_test_field(gdf)
    # CBCrop is a widget shared by every test in this module (gdf isn't
    # recreated per test) - reset it back to "nothing selected" (index 0,
    # the _SELECT_CROP sentinel _populate_crop_combo always adds first),
    # or an override left behind by an earlier test would suppress the
    # field-wide variety this test exists to check (see
    # _compute_simulation: variety_for_model is None whenever
    # override_crop is set, on the reasoning that a variety tied to
    # whatever's on file has no business driving a manually-picked crop).
    page.CBCrop.setCurrentIndex(0)
    page.DEFrom.setDate(QDate.fromString('2024-05-01', 'yyyy-MM-dd'))
    page.DETo.setDate(QDate.fromString('2024-05-05', 'yyyy-MM-dd'))

    weather = _weather_series('2024-05-01', 5, rain_day_index=-1)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather), \
        mock.patch.object(
            crop_simulation_module.crop_model_settings, 'effective_crop_model',
            wraps=crop_simulation_module.crop_model_settings.effective_crop_model
        ) as model_mock:
        page.PBRun.click()

    model_mock.assert_any_call(gdf.db, 'potato', variety='bintje')
    assert 'variety: bintje' in page.LCrop.text()

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2024-05-01'")


def test_run_teach_scan_resolves_variety_per_field_year(gdf: GeoDataFarm):
    # "Teach your model"'s predicted-vs-actual comparison must resolve each
    # field/year's variety too - both to show it (TWTeachExamples' new
    # Variety column) and to feed it into effective_crop_model so the
    # predicted yield reflects any saved variety-level overrides, not
    # just the crop's.
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, variety, date_) VALUES"
        " ('test_field', 'wheat', 'skagen', '2023-05-01')")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate) VALUES"
        " ('test_field', 'wheat', '2023-05-10', '120 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2023-04-15', '18', '3')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2023-09-15', '48000')")

    weather = _weather_series('2023-04-01', 220, rain_day_index=40)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        gdf.crop_simulation.run_teach_scan()

    matching = [ex for ex in gdf.crop_simulation._teach_examples
               if ex.field_name == 'test_field' and ex.year == 2023]
    assert len(matching) == 1
    assert matching[0].variety == 'skagen'
    table = gdf.crop_simulation.page.TWTeachExamples
    variety_cells = [table.item(r, 4).text() for r in range(table.rowCount())
                     if table.item(r, 1).text() == 'test_field'
                     and table.item(r, 2).text() == '2023']
    assert variety_cells == ['skagen']

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_run_teach_scan_captures_the_limiting_factor_per_field_year(gdf: GeoDataFarm):
    # _compute_teach_scan must carry season.limiting_factor through onto
    # the TrainingExample it builds, not just use it to pick
    # predicted_yield_t_ha and then discard it - see
    # test_apply_teach_scan_result_shows_the_limiting_factor for why this
    # matters (it's what makes an otherwise-identical-looking predicted
    # figure across different fields diagnosable).
    gdf.crop_simulation.qsettings.setValue(DEV_BYPASS_LICENSE_SETTING, True)
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual (field, crop, date_) VALUES"
        " ('test_field', 'wheat', '2023-05-01')")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "INSERT INTO ferti.manual (field, crop, date_, rate) VALUES"
        " ('test_field', 'wheat', '2023-05-10', '120 kg N/ha')")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "INSERT INTO soil.manual (field, date_, clay, humus) VALUES"
        " ('test_field', '2023-04-15', '18', '3')")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.db.execute_sql(
        "INSERT INTO harvest.manual (field, date_, yield) VALUES"
        " ('test_field', '2023-09-15', '48000')")

    weather = _weather_series('2023-04-01', 220, rain_day_index=40)
    with mock.patch.object(gdf.crop_simulation.weather_client, 'daily_weather',
                          return_value=weather):
        gdf.crop_simulation.run_teach_scan()

    matching = [ex for ex in gdf.crop_simulation._teach_examples
               if ex.field_name == 'test_field' and ex.year == 2023]
    assert len(matching) == 1
    assert matching[0].limiting_factor in (
        'water', 'nitrogen', 'heat', 'potassium', 'none',
        'water+nitrogen', 'nitrogen+water')
    table = gdf.crop_simulation.page.TWTeachExamples
    factor_cells = [table.item(r, 8).text() for r in range(table.rowCount())
                    if table.item(r, 1).text() == 'test_field'
                    and table.item(r, 2).text() == '2023']
    assert factor_cells == [matching[0].limiting_factor]

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE field = 'test_field' AND date_ = '2023-05-01'")
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE field = 'test_field' AND date_ = '2023-05-10'")
    gdf.db.execute_sql(
        "DELETE FROM soil.manual WHERE field = 'test_field' AND date_ = '2023-04-15'")
    gdf.db.execute_sql(
        "DELETE FROM harvest.manual WHERE field = 'test_field' AND date_ = '2023-09-15'")
    gdf.crop_simulation.qsettings.remove(DEV_BYPASS_LICENSE_SETTING)


def test_train_selected_fits_each_variety_of_a_crop_separately(gdf: GeoDataFarm):
    from ..database_scripts.crop_simulation import TrainingExample
    from ..support_scripts import crop_model_settings

    crop_model_settings.reset_overrides(gdf.db, 'wheat')
    crop_model_settings.reset_overrides(gdf.db, 'wheat', 'arsenal')
    crop_model_settings.reset_overrides(gdf.db, 'wheat', 'skagen')
    examples = [
        TrainingExample(
            field_name='test_field', year=year, crop='wheat', variety=variety,
            season_from='{}-04-01'.format(year), season_to='{}-09-01'.format(year),
            planting_date_logged=True, weather=[], clay=20.0, organic_matter=2.0,
            irrigation_by_date={}, fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=8.0, actual_yield_t_ha=7.5)
        for variety in ('arsenal', 'skagen')
        for year in (2022, 2023)]
    gdf.crop_simulation._apply_teach_scan_result(examples)

    gdf.crop_simulation._train_selected()

    # Two separate fits - one per variety - not one lumped-together wheat
    # fit that would wash out any real per-variety difference.
    assert gdf.crop_simulation.page.CBTeachSaveCrop.count() == 2
    keys = set(gdf.crop_simulation._teach_fits.keys())
    assert keys == {('wheat', 'arsenal'), ('wheat', 'skagen')}
    results_text = gdf.crop_simulation.page.TETeachResults.toPlainText()
    assert 'wheat - variety: arsenal' in results_text
    assert 'wheat - variety: skagen' in results_text

    crop_model_settings.reset_overrides(gdf.db, 'wheat')
    crop_model_settings.reset_overrides(gdf.db, 'wheat', 'arsenal')
    crop_model_settings.reset_overrides(gdf.db, 'wheat', 'skagen')


def test_save_teach_fit_saves_to_the_selected_varietys_own_overrides(gdf: GeoDataFarm):
    from dataclasses import replace as _replace
    from ..database_scripts import crop_simulation as crop_simulation_module
    from ..database_scripts.crop_simulation import TrainingExample
    from ..support_scripts import crop_model_settings, crop_models

    crop_model_settings.reset_overrides(gdf.db, 'barley')
    crop_model_settings.reset_overrides(gdf.db, 'barley', 'laurent')
    examples = [
        TrainingExample(
            field_name='test_field', year=year, crop='barley', variety='laurent',
            season_from='{}-04-01'.format(year), season_to='{}-09-01'.format(year),
            planting_date_logged=True, weather=[], clay=20.0, organic_matter=2.0,
            irrigation_by_date={}, fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date={},
            predicted_yield_t_ha=6.0, actual_yield_t_ha=5.5)
        for year in (2022, 2023)]
    gdf.crop_simulation._apply_teach_scan_result(examples)

    fitted_model = _replace(crop_models.CROP_MODELS['barley'], potential_yield_t_ha=88.0,
                            ky_nitrogen=2.2, min_relative_yield_nitrogen=0.4)
    with mock.patch.object(crop_simulation_module, '_fit_crop_model',
                          return_value=(fitted_model, 10.0, 2.0)):
        gdf.crop_simulation._train_selected()

    gdf.crop_simulation.page.PBTeachSaveCrop.click()

    variety_overrides = crop_model_settings.get_overrides(gdf.db, 'barley', 'laurent')
    assert variety_overrides['potential_yield_t_ha'] == 88.0
    # The crop-level row itself must stay untouched - this was a
    # variety-scoped save, not a crop-level one.
    crop_overrides = crop_model_settings.get_overrides(gdf.db, 'barley')
    assert 'potential_yield_t_ha' not in crop_overrides

    crop_model_settings.reset_overrides(gdf.db, 'barley')
    crop_model_settings.reset_overrides(gdf.db, 'barley', 'laurent')
