from qgis.PyQt.QtWidgets import QWidget, QGridLayout, QComboBox

from ..GeoDataFarm import GeoDataFarm
from ..import_data.insert_manual_from_file import ManualFromFile
from ..database_scripts.crop_simulation import CropSimulation
from . import gdf


class _FakeImportWidget:
    """Minimal stand-in for ImportTextDialog: ManualFromFile only ever
    touches GLSpecific (a layout it adds spec-column rows to) and
    CBCrop (read once for the crop name)."""
    def __init__(self):
        self._container = QWidget()
        self.GLSpecific = QGridLayout(self._container)
        self.CBCrop = QComboBox()
        self.CBCrop.addItem('Potatoes')


def _make_manual_from_file(db, spec_columns=('Variety',)):
    widget = _FakeImportWidget()
    return ManualFromFile(db, widget, list(spec_columns)), widget


def test_selecting_a_per_row_column_stores_the_sanitized_column_name(gdf: GeoDataFarm):
    """Picking "this attribute varies per row, read it from column X" in
    the import UI stores the column's own (sanitized) NAME, not a value -
    that's intentional: generate_reports.py's retrieve_distinct reads it
    straight back as a column reference into this row's table_ to build
    the "advanced" report. It's CropSimulation._resolve_manual_field's
    job to recognise this encoding and not treat it as a literal value
    (see test_load_variety_ignores_a_column_name_reference_from_manual
    below) - this test only pins down what actually gets stored."""
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table'")
    mff, widget = _make_manual_from_file(gdf.db)
    mff.prepare_data(['some other col', 'Potato Variety'])
    combo = mff.manual_values[0]['Combo']
    combo.setCurrentIndex(combo.findText('Potato Variety'))

    suc = mff.insert_manual_data(
        date_='c_2024-01-01', field='manual_from_file_test_table',
        table='manual_from_file_test_table', data_type='plant')

    assert suc
    rows = gdf.db.execute_and_return(
        "SELECT variety FROM plant.manual WHERE table_ = %s",
        params=('manual_from_file_test_table',))
    assert [row[0] for row in rows] == ['potato_variety']
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table'")


def test_not_applicable_checkbox_still_stores_none(gdf: GeoDataFarm):
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table2'")
    mff, widget = _make_manual_from_file(gdf.db)
    mff.prepare_data(['some_other_col'])
    mff.manual_values[0]['checkbox'].setChecked(True)

    suc = mff.insert_manual_data(
        date_='c_2024-01-01', field='manual_from_file_test_table2',
        table='manual_from_file_test_table2', data_type='plant')

    assert suc
    rows = gdf.db.execute_and_return(
        "SELECT variety FROM plant.manual WHERE table_ = %s",
        params=('manual_from_file_test_table2',))
    assert [row[0] for row in rows] == ['None']
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table2'")


def test_a_typed_fixed_value_is_still_stored_as_a_c_prefixed_literal(gdf: GeoDataFarm):
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table3'")
    mff, widget = _make_manual_from_file(gdf.db)
    mff.prepare_data(['some_other_col'])
    # addItems() leaves the combo on its first entry - clear that selection
    # so currentText() is '' and _resolve falls through to the line edit,
    # exactly like a user who never touched the combo at all.
    mff.manual_values[0]['Combo'].setCurrentIndex(-1)
    mff.manual_values[0]['line_edit'].setText('fontane')

    suc = mff.insert_manual_data(
        date_='c_2024-01-01', field='manual_from_file_test_table3',
        table='manual_from_file_test_table3', data_type='plant')

    assert suc
    rows = gdf.db.execute_and_return(
        "SELECT variety FROM plant.manual WHERE table_ = %s",
        params=('manual_from_file_test_table3',))
    assert [row[0] for row in rows] == ['c_fontane']
    gdf.db.execute_sql("DELETE FROM plant.manual WHERE table_ = 'manual_from_file_test_table3'")


def test_resolve_manual_field_decodes_the_three_way_convention():
    resolve = CropSimulation._resolve_manual_field
    # A column-name reference (file-imported row, no 'c_'/'None' encoding)
    # is not a literal value - the real per-row value lives in table_.
    assert resolve('potato_variety', 'some_imported_table') is None
    # A fixed value typed for the whole import.
    assert resolve('c_fontane', 'some_imported_table') == 'fontane'
    # Explicitly "not applicable".
    assert resolve('None', 'some_imported_table') is None
    assert resolve('None', 'None') is None
    assert resolve(None, 'some_imported_table') is None
    # A row entered directly through a manual-entry form (table_ = 'None'
    # or unset) holds a genuine literal with none of the above encoding -
    # even one that happens to start with 'c_' or look like a column name.
    assert resolve('fontane', 'None') == 'fontane'
    assert resolve('c_fontane', 'None') == 'c_fontane'
    assert resolve('150 kg N/ha', None) == '150 kg N/ha'


def test_load_variety_ignores_a_column_name_reference_from_manual(gdf: GeoDataFarm):
    """End-to-end regression test for the live bug: importing a file and
    picking "variety varies per row, use column X" must not make
    _load_variety surface that column's NAME as if every field using
    this planting record had a cultivar literally called that."""
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.manual_from_file_variety_regression")
    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE table_ = 'manual_from_file_variety_regression'")
    gdf.db.execute_sql(
        "CREATE TABLE plant.manual_from_file_variety_regression"
        " (date_ timestamp, potato_variety text, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO plant.manual_from_file_variety_regression (date_, potato_variety, polygon)"
        " SELECT '2024-01-01'::timestamp, 'inova', polygon FROM fields"
        " WHERE field_name = 'test_field'")

    mff, widget = _make_manual_from_file(gdf.db)
    mff.prepare_data(['potato_variety'])
    combo = mff.manual_values[0]['Combo']
    combo.setCurrentIndex(combo.findText('potato_variety'))
    suc = mff.insert_manual_data(
        date_='c_2024-01-01', field='test_field',
        table='manual_from_file_variety_regression', data_type='plant')
    assert suc

    crop_sim = gdf.crop_simulation
    variety, planting_date = crop_sim._load_variety('test_field', '2024-06-01')
    assert variety == 'inova'
    assert planting_date == '2024-01-01'

    gdf.db.execute_sql(
        "DELETE FROM plant.manual WHERE table_ = 'manual_from_file_variety_regression'")
    gdf.db.execute_sql("DROP TABLE IF EXISTS plant.manual_from_file_variety_regression")


def test_nutrient_column_renders_as_a_fixed_choice_combo_not_a_column_picker(gdf: GeoDataFarm):
    # Unlike Variety/Rate, a ferti import's nutrient never varies row to
    # row (one product per spreading pass) - the combo must offer the
    # fixed N/P/K/Mg/S/Na choices from the start, not the imported
    # file's own column names, and prepare_data() (called once real
    # column names are known) must not overwrite that.
    mff, widget = _make_manual_from_file(gdf.db, ['Variety', 'Nutrient', 'Rate', 'Depth'])
    nutrient_combo = mff.manual_values[1]['Combo']
    assert [nutrient_combo.itemText(i) for i in range(nutrient_combo.count())] == [
        'N', 'P', 'K', 'Mg', 'S', 'Na']

    mff.prepare_data(['some_real_column_from_the_file', 'another_one'])

    assert [nutrient_combo.itemText(i) for i in range(nutrient_combo.count())] == [
        'N', 'P', 'K', 'Mg', 'S', 'Na']


def test_insert_manual_data_writes_the_selected_nutrient_for_ferti(gdf: GeoDataFarm):
    # Reproduces the real gap: an imported fertilizer application had no
    # way to be tagged as anything but nitrogen at all - ferti.manual.
    # nutrient must end up holding exactly the case-sensitive code
    # _load_events/_FERTI_RATE_KEYS match on ('K', not 'k' - check_text()
    # would have lowercased it, which is exactly why the fixed-choice
    # combo bypasses that sanitiser entirely, see _resolve).
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE table_ = 'manual_from_file_ferti_nutrient_test'")
    mff, widget = _make_manual_from_file(gdf.db, ['Variety', 'Nutrient', 'Rate', 'Depth'])
    mff.manual_values[1]['Combo'].setCurrentIndex(
        mff.manual_values[1]['Combo'].findText('K'))

    suc = mff.insert_manual_data(
        date_='c_2024-01-01', field='manual_from_file_ferti_nutrient_test',
        table='manual_from_file_ferti_nutrient_test', data_type='ferti')

    assert suc
    rows = gdf.db.execute_and_return(
        "SELECT nutrient FROM ferti.manual WHERE table_ = %s",
        params=('manual_from_file_ferti_nutrient_test',))
    assert [row[0] for row in rows] == ['K']
    gdf.db.execute_sql(
        "DELETE FROM ferti.manual WHERE table_ = 'manual_from_file_ferti_nutrient_test'")


def test_iso_ferti_nutrient_prompt_defaults_to_nitrogen_in_test_mode(gdf: GeoDataFarm):
    # A real modal QInputDialog can't run headless in test mode (see
    # Iso11783._prompt_ferti_nutrient) - it must short-circuit to the
    # legacy nitrogen-only assumption by default, but stay overridable
    # (via _test_ferti_nutrient) so the routing itself (see
    # test_load_imported_ferti_events_routes_a_tagged_nutrient_to_its_
    # own_slot) can still be exercised end to end in tests.
    from ..import_data.handle_iso11783 import Iso11783

    class _FakeParent:
        db = gdf.db
        populate = None
        test_mode = True

    importer = Iso11783(_FakeParent(), 'ferti')
    assert importer._prompt_ferti_nutrient() == 'N'

    importer._test_ferti_nutrient = 'K'
    assert importer._prompt_ferti_nutrient() == 'K'
