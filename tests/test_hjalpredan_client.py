"""Tests for support_scripts.hjalpredan_client and the journal wiring
around it.

Most of these are offline: they check the translation between what the
journal records and what the API's tables are keyed on, which is where
this plugin can actually get things wrong. The transcription itself is
tested where it lives, in geodatafarm_mobile/api.

One test does hit the live service, marked so it can be deselected. It
earns its keep: the whole reason the lookup is server-side is that the
plugin and the phone app must not disagree about a compliance number, and
a contract test is the only thing that notices when the two drift apart.
"""
import pytest

from ..support_scripts import hjalpredan_client as hj
from ..support_scripts import journal_fields as jf
from ..widgets.add_data_form import AddDataForm, FieldSpec


# A journal row with everything the boom lookup needs, spelled the way the
# form produces it (every value a string, choices as their English label).
FULL_ROW = {
    'use_type': 'Field',
    'temperature_c': '15',
    'wind_speed': '3.0',
    'boom_height_cm': '60',
    'sensitivity': 'Special',
    'rate': '1.0',
    'label_max_dose': '2.0',
    'spray_quality': 'Medium',
    'fixed_buffer_object': 'Watercourse or lake',
}


# ---------------------------------------------------------------------
# Journal values -> the API's vocabulary
# ---------------------------------------------------------------------
def test_journal_choices_translate_to_the_apis_wire_values():
    prepared = hj.from_journal_values(FULL_ROW)

    assert prepared['sensitivity'] == 'special'
    assert prepared['spray_quality'] == 'medium'
    assert prepared['nearest_object'] == 'watercourse'
    assert prepared['temperature_c'] == 15.0
    assert prepared['boom_height_cm'] == 60.0


def test_a_renamed_choice_is_dropped_rather_than_guessed():
    """A user may rename a choice in the journal settings. Sending the
    label through unmapped would have the API reject the whole request
    over a parameter that is optional anyway."""
    prepared = hj.from_journal_values(dict(FULL_ROW, fixed_buffer_object='Å'))

    assert prepared['nearest_object'] is None


def test_a_decimal_comma_survives_the_trip():
    prepared = hj.from_journal_values(dict(FULL_ROW, wind_speed='3,0'))

    assert prepared['wind_speed_ms'] == 3.0


def test_the_use_type_picks_the_variant():
    assert hj.variant_for(FULL_ROW) == 'boom'
    assert hj.variant_for(dict(FULL_ROW, use_type='Fruit growing')) == 'orchard'


def test_the_orchard_variant_asks_for_foliage_not_boom_height():
    row = dict(FULL_ROW, use_type='Fruit growing', foliage='Dense')

    prepared = hj.from_journal_values(row)

    assert prepared['foliage'] == 'dense'
    assert 'boom_height_cm' not in prepared
    assert 'temperature_c' not in prepared


# ---------------------------------------------------------------------
# Naming what is missing
# ---------------------------------------------------------------------
def test_a_complete_row_is_missing_nothing():
    assert hj.missing_inputs(hj.from_journal_values(FULL_ROW), 'boom') == []


def test_missing_inputs_names_the_journal_fields_not_the_api_parameters():
    """The user has to know which box to go and fill in."""
    row = dict(FULL_ROW, boom_height_cm='', temperature_c='')

    missing = hj.missing_inputs(hj.from_journal_values(row), 'boom')

    assert 'Boom height' in missing
    assert 'Temperature' in missing


def test_the_dose_is_missing_unless_both_halves_are_given():
    """The class is a fraction of the label's highest dose - one without
    the other says nothing."""
    row = dict(FULL_ROW, label_max_dose='')

    missing = hj.missing_inputs(hj.from_journal_values(row), 'boom')

    assert 'Dose and label maximum dose' in missing


def test_either_spray_quality_or_drift_reduction_will_do():
    without_quality = dict(FULL_ROW, spray_quality='', drift_reduction_percent='75')

    assert hj.missing_inputs(hj.from_journal_values(without_quality), 'boom') == []

    neither = dict(FULL_ROW, spray_quality='', drift_reduction_percent='')
    assert 'Spray quality or drift reduction class' in \
        hj.missing_inputs(hj.from_journal_values(neither), 'boom')


def test_the_orchard_variant_does_not_demand_drift_reduction():
    """Its tables have a 0 % column, so leaving it out is an answer."""
    row = dict(FULL_ROW, use_type='Fruit growing', foliage='Sparse',
               spray_quality='', drift_reduction_percent='')

    assert hj.missing_inputs(hj.from_journal_values(row), 'orchard') == []


# ---------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------
def test_an_unreachable_service_raises_the_recoverable_error():
    """Never fatal: the distance is a field the user can type. Port 9 is
    the discard port, so nothing is listening."""
    client = hj.HjalpredanClient(base_url='http://127.0.0.1:9/api/hjalpredan',
                                 timeout=2)

    with pytest.raises(hj.HjalpredanUnavailable):
        client.options()


# ---------------------------------------------------------------------
# The form wiring
# ---------------------------------------------------------------------
def _form(qtbot):
    form = AddDataForm()
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(form)
    return form


def test_a_field_action_puts_a_button_beside_that_field(qtbot):
    from qgis.PyQt.QtWidgets import QPushButton
    pressed = []
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Adapted buffer zone', 'adapted_buffer_m', 'm', 'number')]
    form.field_actions = {'adapted_buffer_m': ('Hjälpredan…', lambda: pressed.append(1))}

    form._open('opSpraying')
    cell = form._edits['adapted_buffer_m'].parent()
    buttons = cell.findChildren(QPushButton)

    assert len(buttons) == 1
    buttons[0].click()
    assert pressed == [1]


def test_choosing_a_buffer_object_reports_the_change(qtbot):
    seen = []
    form = _form(qtbot)
    form.field_provider = lambda op: [
        FieldSpec('Object', 'fixed_buffer_object', None, 'choice',
                  ('', 'Open ditch or drain', 'Watercourse or lake'))]
    form.value_changed_callback = lambda key, value: seen.append((key, value))

    form._open('opSpraying')
    form._edits['fixed_buffer_object'].setCurrentText('Watercourse or lake')

    assert ('fixed_buffer_object', 'Watercourse or lake') in seen


def test_typing_does_not_fire_the_value_changed_callback(qtbot):
    """It would fill other fields in from a half-typed value."""
    seen = []
    form = _form(qtbot)
    form.field_provider = lambda op: [FieldSpec('Notes', 'nozzle_type')]
    form.value_changed_callback = lambda key, value: seen.append((key, value))

    form._open('opSpraying')
    form._edits['nozzle_type'].setText('ID')

    assert seen == []


# ---------------------------------------------------------------------
# Contract with the live service
# ---------------------------------------------------------------------
@pytest.mark.network
def test_the_live_service_answers_the_journals_own_values():
    """The booklet's own worked example (bomspruta pp. 22-25): 15 °C,
    3 m/s, särskild hänsyn, halv dos, medium droplets, 60 cm boom -> 16 m.

    Hits api.geodatafarm.com on purpose. This is the test that catches the
    plugin and the API disagreeing, which is the entire reason the tables
    live server-side rather than in both.
    """
    client = hj.HjalpredanClient()
    row = dict(FULL_ROW, temperature_c='15', wind_speed='3.0',
               boom_height_cm='60', sensitivity='Special',
               rate='1.0', label_max_dose='2.0', spray_quality='Medium',
               fixed_buffer_object='Nothing requiring a fixed distance')
    try:
        reading = client.boom_sprayer(**hj.from_journal_values(row))
    except hj.HjalpredanUnavailable as e:
        pytest.skip(f'Hjälpredan service unreachable: {e}')

    assert reading['distance_m'] == 16
    assert reading['governed_by'] == hj.GOVERNED_BY_TABLE
    assert reading['edition']


@pytest.mark.network
def test_the_fixed_distance_wins_when_the_table_would_be_shorter():
    """Next to a watercourse the 6 m floor governs, and the answer says
    so - the journal has to record which rule produced the number."""
    client = hj.HjalpredanClient()
    row = dict(FULL_ROW, temperature_c='10', wind_speed='1.5',
               sensitivity='General', boom_height_cm='25',
               rate='0.5', label_max_dose='2.0', spray_quality='Coarse',
               fixed_buffer_object='Watercourse or lake')
    try:
        reading = client.boom_sprayer(**hj.from_journal_values(row))
    except hj.HjalpredanUnavailable as e:
        pytest.skip(f'Hjälpredan service unreachable: {e}')

    assert reading['distance_m'] == 6
    assert reading['governed_by'] == hj.GOVERNED_BY_FIXED
    # The table alone would have given 2 m here, which is shorter than the
    # law allows next to a watercourse - the point of recording which rule
    # won.
    assert reading['hjalpredan_distance_m'] == 2
    assert hj.OBJECT_LABELS[reading['nearest_object']] == 'Watercourse or lake'


@pytest.mark.network
def test_the_journals_choices_are_the_ones_the_service_accepts():
    """Guards the two vocabularies drifting apart - a renamed wire value
    on the server would otherwise only surface as a silent 'None' in a
    request, and a journal with no adapted distance in it."""
    client = hj.HjalpredanClient()
    try:
        options = client.options()
    except hj.HjalpredanUnavailable as e:
        pytest.skip(f'Hjälpredan service unreachable: {e}')

    assert set(hj.NEAREST_OBJECTS.values()) <= set(options['nearest_objects'])
    assert set(hj.SENSITIVITIES.values()) <= set(options['sensitivities'])
    assert set(hj.SPRAY_QUALITIES.values()) <= set(options['boom']['spray_qualities'])
    assert set(hj.FOLIAGES.values()) <= set(options['orchard']['foliages'])
    # The journal's boom-height choices must be steps the tables print.
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}
    offered = {int(c) for c in fields['boom_height_cm'].choices if c}
    assert offered <= set(options['boom']['boom_heights_cm'])


@pytest.mark.network
def test_the_governed_by_values_are_the_ones_this_plugin_checks_for():
    """The constants are what GeoDataFarm._reading_summary branches on, so
    a rename on the server would silently stop the journal ever saying a
    distance came from the fixed minimum rather than the tables. That is
    exactly the bug this test was written after."""
    client = hj.HjalpredanClient()
    base = dict(FULL_ROW, temperature_c='10', wind_speed='1.5',
                sensitivity='General', boom_height_cm='25', rate='0.5',
                label_max_dose='2.0', spray_quality='Coarse')
    try:
        from_table = client.boom_sprayer(**hj.from_journal_values(
            dict(base, fixed_buffer_object='Nothing requiring a fixed distance')))
        from_floor = client.boom_sprayer(**hj.from_journal_values(
            dict(base, fixed_buffer_object='Drinking water well')))
    except hj.HjalpredanUnavailable as e:
        pytest.skip(f'Hjälpredan service unreachable: {e}')

    assert from_table['governed_by'] == hj.GOVERNED_BY_TABLE
    assert from_floor['governed_by'] == hj.GOVERNED_BY_FIXED
    assert from_floor['distance_m'] == 12
