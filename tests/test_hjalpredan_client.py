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
# One drift-reduction field per variant
# ---------------------------------------------------------------------
# The two books print different classes - 50/75/90 % for the bomspruta,
# 0/25/50/75/90/95/99 % for the fläktspruta - so the journal records them
# in separate fields. Reading the wrong one is silent: the number would
# still be a valid class, just not the one the operator's equipment is
# approved at, and the journal would carry a distance nobody could
# reproduce from the sprayer.


def test_the_orchard_variant_reads_its_own_reduction_field():
    """A 99 % fläktspruta must reach the 99 % column. Sharing the boom
    field would cap it at 90 % and cost the grower distance their
    equipment has earned."""
    row = dict(FULL_ROW, use_type='Fruit growing', foliage='Dense',
               drift_reduction_orchard_percent='99',
               drift_reduction_percent='')

    assert hj.from_journal_values(row)['drift_reduction_percent'] == 99.0


def test_the_boom_variant_ignores_the_orchard_reduction_field():
    """And the other way round: 25 % is a fläktspruta column the boom
    tables do not have, so it must not leak into a boom lookup.

    Read at 50 cm with no spray quality recorded, so the only thing this
    exercises is which *field* the class comes from. With a taller boom or
    a spray quality beside it the column resolution steps in, and that is
    tested on its own further down.
    """
    row = dict(FULL_ROW, boom_height_cm='50', spray_quality='',
               drift_reduction_percent='75',
               drift_reduction_orchard_percent='25')

    assert hj.from_journal_values(row)['drift_reduction_percent'] == 75.0


def test_the_orchard_variant_ignores_the_boom_reduction_field():
    row = dict(FULL_ROW, use_type='Fruit growing', foliage='Sparse',
               drift_reduction_percent='90',
               drift_reduction_orchard_percent='')

    assert hj.from_journal_values(row)['drift_reduction_percent'] is None


def test_the_journal_offers_every_class_each_book_prints():
    """Offline half of the contract: the choices a user can pick have to
    cover the columns, or a sprayer becomes unrecordable."""
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    boom = [c for c in fields[hj.BOOM_REDUCTION_FIELD].choices if c]
    orchard = [c for c in fields[hj.ORCHARD_REDUCTION_FIELD].choices if c]

    assert boom == ['50', '75', '90']
    assert orchard == ['0', '25', '50', '75', '90', '95', '99']


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
    """At a boom height the reduction row is printed for. Higher than that
    the book prints no reduction row and the two stop being alternatives -
    see test_a_high_boom_with_only_a_reduction_class_is_reported_not_sent.
    """
    without_quality = dict(FULL_ROW, boom_height_cm='50', spray_quality='',
                           drift_reduction_percent='75')

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
    # The journal's numeric choices must be steps the tables print. Each
    # book has its own drift-reduction classes, and offering one the server
    # has no column for turns a lookup into a 422 the user cannot act on.
    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}

    def offered(key):
        return {int(c) for c in fields[key].choices if c}

    assert offered('boom_height_cm') <= set(options['boom']['boom_heights_cm'])
    assert offered(hj.BOOM_REDUCTION_FIELD) \
        == set(options['boom']['drift_reduction_percent'])
    assert offered(hj.ORCHARD_REDUCTION_FIELD) \
        == set(options['orchard']['drift_reduction_percent'])


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


# ---------------------------------------------------------------------
# The bomspruta's two column groups
# ---------------------------------------------------------------------
# Every page of that book has a spray-quality group and a drift-reduction
# group, and a reading comes from exactly one. The journal can hold both
# facts, so the client has to choose - and choose in a way the tables can
# actually be read at.
def test_both_columns_recorded_reads_the_reduction_one_when_the_boom_allows():
    """Drift reduction is what the equipment was bought for, and at or
    below the book's reduction row it is readable."""
    row = dict(FULL_ROW, boom_height_cm='50', spray_quality='Medium',
               drift_reduction_percent='75')

    prepared = hj.from_journal_values(row)

    assert prepared['drift_reduction_percent'] == 75
    assert prepared['spray_quality'] is None


def test_both_columns_recorded_falls_back_to_spray_quality_on_a_high_boom():
    """Above the reduction row the book prints nothing, so the
    spray-quality columns are the only reading."""
    row = dict(FULL_ROW, boom_height_cm='60', spray_quality='Medium',
               drift_reduction_percent='75')

    prepared = hj.from_journal_values(row)

    assert prepared['spray_quality'] == 'medium'
    assert prepared['drift_reduction_percent'] is None


def test_a_high_boom_with_only_a_reduction_class_is_reported_not_sent():
    """It would come back 422. Naming the box to fill in is far more use
    than relaying the rejection."""
    row = dict(FULL_ROW, boom_height_cm='60', spray_quality='',
               drift_reduction_percent='75')

    missing = hj.missing_inputs(hj.from_journal_values(row), 'boom')

    assert any('Spray quality' in item for item in missing)
    assert any('50 cm or lower' in item for item in missing)


def test_a_low_boom_with_only_a_reduction_class_is_fine():
    row = dict(FULL_ROW, boom_height_cm='40', spray_quality='',
               drift_reduction_percent='75')

    assert hj.missing_inputs(hj.from_journal_values(row), 'boom') == []


def test_only_one_column_group_is_ever_sent():
    """The lookup rejects a request carrying both, whatever the height."""
    for height in ('25', '40', '50', '60'):
        prepared = hj.from_journal_values(dict(
            FULL_ROW, boom_height_cm=height, spray_quality='Medium',
            drift_reduction_percent='75'))
        both = (prepared['spray_quality'] is not None
                and prepared['drift_reduction_percent'] is not None)
        assert not both, height


@pytest.mark.network
def test_the_service_accepts_what_the_column_resolution_produces():
    """The regression this was written for: the journal offers both boxes,
    the client used to send both, and the lookup answered 422."""
    client = hj.HjalpredanClient()
    for height in ('25', '40', '50', '60'):
        row = dict(FULL_ROW, boom_height_cm=height, spray_quality='Medium',
                   drift_reduction_percent='75')
        prepared = hj.from_journal_values(row)
        assert hj.missing_inputs(prepared, 'boom') == [], height
        try:
            reading = client.boom_sprayer(**prepared)
        except hj.HjalpredanUnavailable as e:
            pytest.skip(f'Hjälpredan service unreachable: {e}')
        assert reading['label'], height


@pytest.mark.network
def test_a_reduction_reading_is_taken_at_the_books_own_row():
    """A 40 cm boom reads the 50 cm row, which is the conservative
    direction since distance grows with height - and the answer says so
    rather than quietly restating 40."""
    client = hj.HjalpredanClient()
    row = dict(FULL_ROW, boom_height_cm='40', spray_quality='',
               drift_reduction_percent='75',
               fixed_buffer_object='Nothing requiring a fixed distance')
    try:
        reading = client.boom_sprayer(**hj.from_journal_values(row))
    except hj.HjalpredanUnavailable as e:
        pytest.skip(f'Hjälpredan service unreachable: {e}')

    assert reading['requested_inputs']['boom_height_cm'] == 40
    assert reading['table_inputs']['boom_height_cm'] == \
        hj.REDUCTION_MAX_BOOM_HEIGHT_CM
    # The booklet's caveat that the equipment's approval conditions still
    # govern travels with the reading.
    assert any('approval conditions' in note for note in reading['notes'])


# ---------------------------------------------------------------------
# Where the Hjälpredan applies
# ---------------------------------------------------------------------
# It is Swedish law - Kemikalieinspektionen's tables plus the fixed minimum
# distances of NFS 2015:2 - and it answers with an edition and a page
# reference, which reads as authoritative wherever it is shown.
def test_the_hjalpredan_applies_in_sweden():
    assert hj.applies_in('SE')
    assert hj.applies_in('se')
    assert hj.applies_in(' SE ')


def test_the_hjalpredan_does_not_apply_elsewhere():
    """A confident wrong buffer distance is worse than an empty box: the
    empty box is visibly the grower's to fill in."""
    for country in ('DK', 'NO', 'FI', 'DE'):
        assert not hj.applies_in(country), country


def test_an_unset_country_does_not_summon_the_hjalpredan():
    """Nothing is assumed from silence. A farm that has not said where it
    is gets no national tool - see journal_fields.farm_country, which
    infers a country from the ruleset actually in force rather than from
    the QGIS language."""
    assert not hj.applies_in('')
    assert not hj.applies_in(None)
