"""Tests for support_scripts.journal_fields and the user-defined journal
fields it drives through the Add-data form and the spraying-journal report.

Uses the shared ``gdf``/database fixture like tests/test_crop_model_settings.py,
so it must run as part of the full suite (`pytest tests`), not on its own -
see tests/conftest.py.

Every test restores the spraying field list to the default template on the
way out: the Add-data form reads it live, so a test that left the
Jordbruksverket template applied would change what every later form test
sees.
"""
import pytest

from ..GeoDataFarm import GeoDataFarm
from ..support_scripts import journal_fields as jf
from ..support_scripts.__init__ import db_rows
from ..widgets.journal_fields_dialog import JournalFieldsDialog
from ..widgets.add_data_form import (
    AddDataForm, FieldSpec, OPERATIONS, _normalise_number, specs_from_config)
from . import gdf

_FIELD = 'pytest_journal_field'


@pytest.fixture
def spray_default(gdf: GeoDataFarm):
    """Leaves spraying on the default template whatever the test did."""
    jf.apply_template(gdf.db, 'spray', jf.DEFAULT_TEMPLATE)
    yield
    jf.apply_template(gdf.db, 'spray', jf.DEFAULT_TEMPLATE)


# ---------------------------------------------------------------------
# Templates and keys - no database needed
# ---------------------------------------------------------------------
def test_the_generic_template_matches_the_forms_static_field_list():
    """The default template must reproduce OPERATIONS exactly, or simply
    upgrading the plugin would silently change what every existing farm's
    manual form asks for."""
    for obj_name, cfg in OPERATIONS.items():
        op = cfg['op']
        if op not in jf.MANUAL_TABLES or cfg.get('custom_save'):
            continue
        template = jf.template_fields(jf.DEFAULT_TEMPLATE, op)
        assert [f.key for f in template] == [key for _, key, _ in cfg['fields']], op
        assert [f.label for f in template] == [label for label, _, _ in cfg['fields']], op
        assert [f.unit for f in template] == [unit or None for _, _, unit in cfg['fields']], op


def test_a_template_falls_back_to_generic_for_operations_it_does_not_override():
    se = jf.template_fields('se_2026', 'harvest')

    assert se == jf.template_fields('generic', 'harvest')


def test_the_swedish_template_covers_the_2026_requirements():
    keys = {f.key for f in jf.template_fields('se_2026', 'spray')}

    # The eight items Jordbruksverket marks "Nytt 2026", plus the three the
    # sprayer operator needs that no regulation asks for.
    assert {'purpose', 'use_type', 'location', 'eppo_code', 'bbch',
            'reg_number', 'treated_area_ha', 'variety'} <= keys
    assert {'water_volume_l_ha', 'nozzle_type', 'pressure_bar'} <= keys


def test_the_swedish_template_reuses_the_existing_spray_columns():
    """'variety' and 'rate' must stay column-backed - the report generator
    and the crop/fertilizer models read those columns directly."""
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    assert fields['variety'].storage == 'column'
    assert fields['rate'].storage == 'column'
    assert fields['nozzle_type'].storage == 'extra'


def test_make_key_avoids_reserved_column_names():
    """A field called "Other" must not claim the row's own ``other``
    column."""
    assert jf.make_key('Other') != 'other'
    assert jf.make_key('Field') != 'field'
    assert jf.make_key('Nozzle type') == 'nozzle_type'


def test_make_key_avoids_keys_already_in_use():
    assert jf.make_key('Nozzle type', taken=('nozzle_type',)) == 'nozzle_type_2'


# ---------------------------------------------------------------------
# Splitting values between real columns and the jsonb payload
# ---------------------------------------------------------------------
def test_split_values_sends_known_columns_to_columns_and_the_rest_to_extra():
    fields = jf.template_fields('se_2026', 'spray')
    values = {'variety': 'Boxer', 'rate': '2.5', 'nozzle_type': 'ID 03',
              'pressure_bar': '3'}

    columns, extra = jf.split_values(fields, values)

    assert columns['variety'] == 'Boxer'
    assert columns['rate'] == '2.5'
    assert extra['nozzle_type'] == 'ID 03'
    assert 'variety' not in extra


def test_split_values_drops_blanks_from_extra_but_keeps_the_column_null():
    fields = jf.template_fields('se_2026', 'spray')

    columns, extra = jf.split_values(fields, {'variety': '', 'nozzle_type': ''})

    # The column has to be listed in the INSERT either way, so it becomes an
    # explicit NULL; an unset jsonb key is simply absent.
    assert columns['variety'] is None
    assert 'nozzle_type' not in extra


def test_missing_required_names_the_blank_required_fields():
    fields = jf.template_fields('se_2026', 'spray')

    missing = jf.missing_required(fields, {'variety': 'Boxer'})

    assert 'Purpose of the treatment' in missing
    assert 'Plant protection product' not in missing


def test_nothing_is_required_on_the_default_template():
    """Existing farms must not suddenly be blocked from saving."""
    fields = jf.template_fields(jf.DEFAULT_TEMPLATE, 'spray')

    assert jf.missing_required(fields, {}) == []


def test_extra_of_treats_a_pre_migration_null_as_no_extra_fields():
    assert jf.extra_of(None) == {}
    assert jf.extra_of({'nozzle_type': 'ID 03'}) == {'nozzle_type': 'ID 03'}


def test_value_of_reads_each_field_from_where_it_is_stored():
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    assert jf.value_of(fields['rate'], {'rate': '2.5'}, {}) == '2.5'
    assert jf.value_of(fields['nozzle_type'], {}, {'nozzle_type': 'ID 03'}) == 'ID 03'
    assert jf.value_of(fields['nozzle_type'], {}, {}) == ''


def test_json_param_is_null_for_an_empty_payload():
    assert jf.json_param({}) is None
    assert jf.json_param({'a': 'b'}) is not None


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------
def test_a_fresh_operation_is_seeded_from_the_default_template(gdf: GeoDataFarm,
                                                               spray_default):
    fields = jf.get_fields(gdf.db, 'spray')

    assert [f.key for f in fields] == [f.key for f in
                                       jf.template_fields(jf.DEFAULT_TEMPLATE, 'spray')]


def test_applying_a_template_replaces_the_builtin_fields(gdf: GeoDataFarm,
                                                         spray_default):
    jf.apply_template(gdf.db, 'spray', 'se_2026')

    fields = jf.get_fields(gdf.db, 'spray')

    assert 'nozzle_type' in {f.key for f in fields}
    assert jf.active_template(gdf.db, 'spray') == 'se_2026'


def test_a_user_added_field_survives_a_template_change(gdf: GeoDataFarm,
                                                       spray_default):
    """The whole point of user-defined fields: switching to a national
    template must not throw away what the grower added for their own
    sprayer."""
    fields = jf.get_fields(gdf.db, 'spray', enabled_only=False)
    fields.append(jf.JournalField(
        operation='spray', key='boom_height_cm', label='Boom height',
        unit='cm', field_type=jf.NUMBER, builtin=False))
    jf.save_fields(gdf.db, 'spray', fields)

    jf.apply_template(gdf.db, 'spray', 'se_2026')

    keys = [f.key for f in jf.get_fields(gdf.db, 'spray')]
    assert 'boom_height_cm' in keys
    # Appended after the template's own fields, so the regulation's ordering
    # is what the journal prints.
    assert keys.index('boom_height_cm') > keys.index('purpose')


def test_a_disabled_field_is_hidden_but_not_lost(gdf: GeoDataFarm, spray_default):
    fields = jf.get_fields(gdf.db, 'spray', enabled_only=False)
    fields[0].enabled = False
    jf.save_fields(gdf.db, 'spray', fields)

    assert fields[0].key not in {f.key for f in jf.get_fields(gdf.db, 'spray')}
    assert fields[0].key in {f.key for f in
                             jf.get_fields(gdf.db, 'spray', enabled_only=False)}


def test_disabling_every_field_is_not_undone_by_reseeding(gdf: GeoDataFarm,
                                                          spray_default):
    """ensure_seeded keys off a settings row, not off the row count - see
    its docstring."""
    jf.save_fields(gdf.db, 'spray', [])

    assert jf.get_fields(gdf.db, 'spray') == []


def test_save_fields_round_trips_every_attribute(gdf: GeoDataFarm, spray_default):
    original = jf.JournalField(
        operation='spray', key='pytest_field', label='Pytest field', unit='l/ha',
        field_type=jf.CHOICE, choices=('', 'Yes', 'No'), required=True,
        sort_order=0, enabled=True, builtin=False)
    jf.save_fields(gdf.db, 'spray', [original])

    stored = jf.get_fields(gdf.db, 'spray', enabled_only=False)[0]

    assert stored == original


def test_choices_keep_their_empty_not_answered_entry(gdf: GeoDataFarm, spray_default):
    """An empty first choice is how a CHOICE field offers "not answered";
    a split that filtered blanks would silently make the field required in
    practice."""
    jf.save_fields(gdf.db, 'spray', [jf.JournalField(
        operation='spray', key='pytest_choice', label='Pytest choice',
        field_type=jf.CHOICE, choices=('', 'Yes', 'No'))])

    assert jf.get_fields(gdf.db, 'spray')[0].choices == ('', 'Yes', 'No')


def test_settings_round_trip(gdf: GeoDataFarm):
    jf.set_setting(gdf.db, jf.DEFAULT_OPERATOR_KEY, 'Pytest Operator')

    assert jf.get_setting(gdf.db, jf.DEFAULT_OPERATOR_KEY) == 'Pytest Operator'

    jf.set_setting(gdf.db, jf.DEFAULT_OPERATOR_KEY, None)
    assert jf.get_setting(gdf.db, jf.DEFAULT_OPERATOR_KEY) is None


def test_ensure_extra_column_is_idempotent(gdf: GeoDataFarm):
    jf.ensure_extra_column(gdf.db, 'spray.manual')
    jf.ensure_extra_column(gdf.db, 'spray.manual')

    rows = db_rows(gdf.db.execute_and_return(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'spray'"
        " AND table_name = 'manual' AND column_name = 'extra'"))
    assert len(rows) == 1


# ---------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------
def _form(qtbot):
    """An Add-data form registered with whichever qtbot the environment
    supplies - pytest-qgis's QgisBot has no addWidget, so the same guard the
    other Qt tests use applies here (see tests/test_create_recipe_qt.py)."""
    form = AddDataForm()
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(form)
    return form


def test_the_form_falls_back_to_the_static_field_list_without_a_provider(qtbot):
    form = _form(qtbot)

    form._open('opSpraying')

    assert set(form._edits) == {key for _, key, _ in OPERATIONS['opSpraying']['fields']}


def test_the_form_renders_the_provided_field_list(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Nozzle type', 'nozzle_type'),
        FieldSpec('Purpose', 'purpose', None, 'choice', ('', 'Weeds', 'Fungi')),
        FieldSpec('Harvest date', 'harvest_date', None, 'date')]

    form._open('opSpraying')

    assert list(form._edits) == ['nozzle_type', 'purpose', 'harvest_date']
    # 'variety' etc. are gone - the configuration decides, not OPERATIONS.
    assert 'variety' not in form._edits


def test_an_unfilled_date_field_reads_as_blank(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [FieldSpec('Harvest date', 'harvest_date',
                                                None, 'date')]

    form._open('opSpraying')

    assert form.values()['harvest_date'] is None


def test_an_empty_choice_entry_reads_as_blank(qtbot):
    """Otherwise a required CHOICE field would pass its required check
    while still unanswered."""
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Purpose', 'purpose', None, 'choice', ('', 'Weeds'), required=True)]

    form._open('opSpraying')

    assert form.values()['purpose'] is None


def test_set_value_never_overwrites_what_the_user_typed(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [FieldSpec('Operator', 'operator')]
    form._open('opSpraying')

    form.set_value('operator', 'Default Name')
    assert form.values()['operator'] == 'Default Name'

    form._edits['operator'].setText('Someone Else')
    form.set_value('operator', 'Default Name')
    assert form.values()['operator'] == 'Someone Else'


def test_a_decimal_comma_is_normalised_on_number_fields(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Rate', 'rate', 'l/ha', 'number'),
        FieldSpec('Nozzle type', 'nozzle_type')]
    form._open('opSpraying')

    form._edits['rate'].setText('2,5')
    form._edits['nozzle_type'].setText('ID 03,05')

    assert form.values()['rate'] == '2.5'
    # Not a number, so left exactly as typed.
    assert form.values()['nozzle_type'] == 'ID 03,05'


def test_normalise_number_leaves_free_text_alone():
    assert _normalise_number('2,5') == '2.5'
    assert _normalise_number('2,5 l/ha') == '2,5 l/ha'


def test_specs_from_config_keeps_the_nutrient_choice_list():
    specs = {s.key: s for s in specs_from_config(OPERATIONS['opFertilizing']['fields'])}

    assert specs['nutrient'].field_type == 'choice'
    assert 'N' in specs['nutrient'].choices


# ---------------------------------------------------------------------
# Saving and reading back a row
# ---------------------------------------------------------------------
def _cleanup_rows(gdf):
    gdf.db.execute_sql("DELETE FROM spray.manual WHERE field = %s", params=(_FIELD,))


def test_a_configured_field_is_saved_to_the_json_column(gdf: GeoDataFarm,
                                                        spray_default):
    """End to end: a user-added field the manual table has no column for
    still lands in the row and comes back out."""
    jf.ensure_extra_column(gdf.db, 'spray.manual')
    fields = jf.get_fields(gdf.db, 'spray', enabled_only=False)
    fields.append(jf.JournalField(
        operation='spray', key='nozzle_type', label='Nozzle type', builtin=False))
    jf.save_fields(gdf.db, 'spray', fields)
    _cleanup_rows(gdf)

    columns, extra = jf.split_values(
        jf.get_fields(gdf.db, 'spray'),
        {'variety': 'Boxer', 'rate': '2.5', 'nozzle_type': 'ID 03'})
    gdf.db.execute_sql(
        "INSERT INTO spray.manual (field, crop, date_, date_text, variety, rate,"
        " extra, table_) VALUES (%s, 'pytest_crop', '2026-05-01', '2026-05-01',"
        " %s, %s, %s, 'None')",
        params=(_FIELD, columns['variety'], columns['rate'], jf.json_param(extra)))

    row = db_rows(gdf.db.execute_and_return(
        "SELECT variety, rate, extra FROM spray.manual WHERE field = %s",
        params=(_FIELD,)))[0]
    assert row[0] == 'Boxer'
    assert row[1] == '2.5'
    assert jf.extra_of(row[2])['nozzle_type'] == 'ID 03'

    _cleanup_rows(gdf)


def test_the_spray_journal_collects_column_and_json_fields_together(gdf: GeoDataFarm,
                                                                    spray_default):
    from ..support_scripts.generate_reports import RapportGen

    jf.apply_template(gdf.db, 'spray', 'se_2026')
    _cleanup_rows(gdf)
    fields = jf.get_fields(gdf.db, 'spray')
    columns, extra = jf.split_values(fields, {
        'variety': 'Boxer', 'rate': '2.5', 'nozzle_type': 'ID 03',
        'purpose': 'Weeds', 'water_volume_l_ha': '150'})
    gdf.db.execute_sql(
        "INSERT INTO spray.manual (field, crop, date_, date_text, variety, rate,"
        " extra, table_) VALUES (%s, 'pytest_crop', '2026-05-01', '2026-05-01',"
        " %s, %s, %s, 'None')",
        params=(_FIELD, columns['variety'], columns['rate'], jf.json_param(extra)))

    applications = RapportGen.collect_spray_journal(gdf.db, fields, year='2026')

    ours = [(h, v) for h, v in applications if h['field'] == _FIELD]
    assert len(ours) == 1
    header, values = ours[0]
    assert header['date'] == '2026-05-01'
    assert values['variety'] == 'Boxer'
    assert values['nozzle_type'] == 'ID 03'
    assert values['water_volume_l_ha'] == '150'
    # Never filled in - an empty cell on the journal, not a missing key.
    assert values['bbch'] == ''

    _cleanup_rows(gdf)


# ---------------------------------------------------------------------
# The settings dialog
# ---------------------------------------------------------------------
def _dialog(gdf, qtbot, operation='spray'):
    dialog = JournalFieldsDialog(gdf.db, operation)
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(dialog)
    return dialog


def test_the_dialog_lists_every_field_including_the_disabled_ones(
        gdf: GeoDataFarm, qtbot, spray_default):
    fields = jf.get_fields(gdf.db, 'spray', enabled_only=False)
    fields[0].enabled = False
    jf.save_fields(gdf.db, 'spray', fields)

    dialog = _dialog(gdf, qtbot)

    assert dialog.table.rowCount() == len(fields)


def test_adding_a_field_in_the_dialog_derives_a_key_and_saves_it(
        gdf: GeoDataFarm, qtbot, spray_default):
    dialog = _dialog(gdf, qtbot)
    before = dialog.table.rowCount()

    dialog._add_field()
    dialog.table.item(before, 1).setText('Boom height')
    dialog.table.item(before, 3).setText('cm')
    dialog._save()

    stored = {f.key: f for f in jf.get_fields(gdf.db, 'spray')}
    assert stored['boom_height'].label == 'Boom height'
    assert stored['boom_height'].unit == 'cm'
    # Derived, so it is a user field and survives a template reset.
    assert stored['boom_height'].builtin is False


def test_an_abandoned_new_row_is_not_saved(gdf: GeoDataFarm, qtbot, spray_default):
    dialog = _dialog(gdf, qtbot)
    before = dialog.table.rowCount()

    dialog._add_field()
    dialog.table.item(before, 1).setText('')
    dialog._save()

    assert len(jf.get_fields(gdf.db, 'spray', enabled_only=False)) == before


def test_moving_a_field_reorders_it(gdf: GeoDataFarm, qtbot, spray_default):
    dialog = _dialog(gdf, qtbot)
    first, second = (f.key for f in jf.get_fields(gdf.db, 'spray')[:2])

    dialog.table.setCurrentCell(0, 1)
    dialog._move(1)
    dialog._save()

    assert [f.key for f in jf.get_fields(gdf.db, 'spray')][:2] == [second, first]


def test_edits_to_two_operations_are_both_saved(gdf: GeoDataFarm, qtbot,
                                                spray_default):
    """Switching operation parks the pending edits rather than dropping
    them - see JournalFieldsDialog._operation_changed."""
    dialog = _dialog(gdf, qtbot)
    dialog.table.item(0, 1).setText('Spray relabelled')

    dialog.cbOperation.setCurrentIndex(dialog.cbOperation.findData('plowing'))
    dialog.table.item(0, 1).setText('Plowing relabelled')
    dialog._save()

    assert jf.get_fields(gdf.db, 'spray')[0].label == 'Spray relabelled'
    assert jf.get_fields(gdf.db, 'plowing')[0].label == 'Plowing relabelled'

    jf.apply_template(gdf.db, 'plowing', jf.DEFAULT_TEMPLATE)


def test_a_builtin_field_cannot_be_deleted_only_disabled(
        gdf: GeoDataFarm, qtbot, spray_default, monkeypatch):
    from qgis.PyQt.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)
    dialog = _dialog(gdf, qtbot)
    before = dialog.table.rowCount()

    dialog.table.setCurrentCell(0, 1)
    dialog._remove_field()

    assert dialog.table.rowCount() == before


# ---------------------------------------------------------------------
# Suggestions from what was entered before
# ---------------------------------------------------------------------
def test_free_text_and_numbers_remember_by_default_but_dates_do_not():
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    assert fields['operator'].suggestible
    assert fields['pressure_bar'].suggestible
    # A date is different every time, and a fixed list already is a shortlist.
    assert not fields['harvest_date'].suggestible
    assert not fields['purpose'].suggestible
    # Derived from the selected field, so a history list would only repeat
    # what the form fills in by itself.
    assert not fields['location'].suggestible
    assert not fields['treated_area_ha'].suggestible


def test_a_field_with_remember_switched_off_offers_nothing():
    field = jf.JournalField(operation='spray', key='operator', label='Operator',
                            remember=False)

    assert not field.suggestible


def test_recent_values_returns_past_entries_newest_first(gdf: GeoDataFarm,
                                                         spray_default):
    jf.apply_template(gdf.db, 'spray', 'se_2026')
    _cleanup_rows(gdf)
    fields = jf.get_fields(gdf.db, 'spray')
    for date_, operator, nozzle in [('2026-05-01', 'Karl', 'ID 03'),
                                    ('2026-05-10', 'Anna', 'ID 03'),
                                    ('2026-05-20', 'Karl', 'TeeJet XR')]:
        _, extra = jf.split_values(fields, {'operator': operator,
                                            'nozzle_type': nozzle})
        gdf.db.execute_sql(
            "INSERT INTO spray.manual (field, crop, date_, date_text, extra,"
            " table_) VALUES (%s, 'pytest_crop', %s, %s, %s, 'None')",
            params=(_FIELD, date_, date_, jf.json_param(extra)))

    history = jf.recent_values(gdf.db, 'spray', fields)

    # Newest first, and each value only once even though Karl sprayed twice.
    assert history['operator'] == ['Karl', 'Anna']
    assert history['nozzle_type'] == ['TeeJet XR', 'ID 03']

    _cleanup_rows(gdf)


def test_recent_values_skips_fields_that_do_not_remember(gdf: GeoDataFarm,
                                                         spray_default):
    jf.apply_template(gdf.db, 'spray', 'se_2026')
    _cleanup_rows(gdf)
    fields = jf.get_fields(gdf.db, 'spray')
    _, extra = jf.split_values(fields, {'purpose': 'Weeds', 'location': 'Home field'})
    gdf.db.execute_sql(
        "INSERT INTO spray.manual (field, crop, date_, date_text, extra, table_)"
        " VALUES (%s, 'pytest_crop', '2026-05-01', '2026-05-01', %s, 'None')",
        params=(_FIELD, jf.json_param(extra)))

    history = jf.recent_values(gdf.db, 'spray', fields)

    assert 'purpose' not in history
    assert 'location' not in history

    _cleanup_rows(gdf)


def test_recent_values_reads_column_backed_fields_too(gdf: GeoDataFarm,
                                                      spray_default):
    """'variety' is a real column, not a jsonb key - the history has to
    span both halves of the split storage."""
    _cleanup_rows(gdf)
    gdf.db.execute_sql(
        "INSERT INTO spray.manual (field, crop, date_, date_text, variety,"
        " table_) VALUES (%s, 'pytest_crop', '2026-05-01', '2026-05-01',"
        " 'Boxer', 'None')", params=(_FIELD,))

    history = jf.recent_values(gdf.db, 'spray', jf.get_fields(gdf.db, 'spray'))

    assert 'Boxer' in history['variety']

    _cleanup_rows(gdf)


def test_the_form_offers_suggestions_as_an_editable_combo(qtbot):
    from qgis.PyQt.QtWidgets import QComboBox
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Operator', 'operator', suggestions=('Karl', 'Anna'))]

    form._open('opSpraying')
    edit = form._edits['operator']

    assert isinstance(edit, QComboBox)
    assert edit.isEditable()
    # Starts blank, so tabbing past it never files someone else's name.
    assert form.values()['operator'] is None
    assert [edit.itemText(i) for i in range(edit.count())] == ['', 'Karl', 'Anna']


def test_a_suggestion_field_still_accepts_a_new_value(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Operator', 'operator', suggestions=('Karl',))]
    form._open('opSpraying')

    form._edits['operator'].setEditText('Someone New')

    assert form.values()['operator'] == 'Someone New'


def test_a_number_field_with_suggestions_still_normalises_the_comma(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Pressure', 'pressure_bar', 'bar', 'number', suggestions=('3',))]
    form._open('opSpraying')

    form._edits['pressure_bar'].setEditText('2,5')

    assert form.values()['pressure_bar'] == '2.5'


def test_set_value_fills_a_suggestion_combo_with_an_unseen_value(qtbot):
    """The treated area of a field sprayed for the first time is not in the
    history, but is still derived and should appear."""
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Operator', 'operator', suggestions=('Karl',))]
    form._open('opSpraying')

    form.set_value('operator', 'Brand New')

    assert form.values()['operator'] == 'Brand New'


def test_clearing_resets_a_suggestion_combo(qtbot):
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Operator', 'operator', suggestions=('Karl',))]
    form._open('opSpraying')
    form._edits['operator'].setEditText('Karl')

    form.clear()

    assert form.values()['operator'] is None


def test_a_fixed_choice_field_renders_as_a_real_combo(qtbot):
    """Guards the screenshot question: the SE template's Purpose must be a
    drop-down, not a text box."""
    from qgis.PyQt.QtWidgets import QComboBox
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Purpose', 'purpose', None, 'choice', ('', 'Weeds', 'Fungi'))]

    form._open('opSpraying')
    edit = form._edits['purpose']

    assert isinstance(edit, QComboBox)
    # Fixed list: not typeable, unlike a history one.
    assert not edit.isEditable()


def test_the_remember_flag_round_trips(gdf: GeoDataFarm, spray_default):
    jf.save_fields(gdf.db, 'spray', [jf.JournalField(
        operation='spray', key='pytest_remember', label='Pytest remember',
        remember=False)])

    assert jf.get_fields(gdf.db, 'spray')[0].remember is False


def test_a_farm_configured_before_remember_existed_is_migrated(gdf: GeoDataFarm,
                                                               spray_default):
    """The column is added to a table that predates it, and existing rows
    default to remembering - so an already-configured farm gets the
    suggestions without having to go and tick every box."""
    gdf.db.execute_sql('ALTER TABLE public.journal_fields DROP COLUMN remember')

    fields = jf.get_fields(gdf.db, 'spray')

    assert all(f.remember for f in fields)


def test_the_time_of_day_is_required_by_the_swedish_template():
    """Jordbruksverket's form heads each application column with both
    "Datum:" and "Klockslag:" - the time is a requirement, not a note."""
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    assert fields['spray_time'].required


def test_the_swedish_template_records_which_sprayer_was_used():
    keys = {f.key for f in jf.template_fields('se_2026', 'spray')}

    assert {'equipment', 'nozzle_type'} <= keys


# ---------------------------------------------------------------------
# Buffer zones
# ---------------------------------------------------------------------
def test_both_buffer_rows_record_an_object_as_well_as_a_distance():
    """Jordbruksverket's form asks for "objekt och avstånd" on both rows -
    a bare distance does not meet the requirement."""
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    for key in ('fixed_buffer_object', 'fixed_buffer_m',
                'adapted_buffer_object', 'adapted_buffer_m'):
        assert fields[key].required, key


def test_the_fixed_buffer_object_offers_the_objects_the_law_names():
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    choices = fields['fixed_buffer_object'].choices
    assert set(jf.FIXED_BUFFER_DISTANCES_M) <= set(choices)


def test_the_fixed_distance_follows_from_the_object():
    """NFS 2015:2: ditch 2 m, watercourse 6 m, drinking-water well 12 m."""
    assert jf.fixed_buffer_distance('Open ditch or drain') == 2
    assert jf.fixed_buffer_distance('Watercourse or lake') == 6
    assert jf.fixed_buffer_distance('Drinking water well') == 12


def test_no_fixed_distance_is_distinguishable_from_not_asked():
    assert jf.fixed_buffer_distance('Nothing requiring a fixed distance') is None
    assert jf.fixed_buffer_distance('') is None
    # A renamed choice must not silently produce a wrong distance.
    assert jf.fixed_buffer_distance('Dike') is None


def test_the_template_records_every_hjalpredan_input():
    """The lookup needs these; without them the journal cannot answer it."""
    keys = {f.key for f in jf.template_fields('se_2026', 'spray')}

    assert {'temperature_c', 'wind_speed', 'boom_height_cm', 'sensitivity',
            'label_max_dose', 'rate'} <= keys
    # Either of these answers the drift-reduction column.
    assert {'spray_quality', 'drift_reduction_percent'} <= keys
