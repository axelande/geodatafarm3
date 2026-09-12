"""Tests for support_scripts.pesticide_client and the search dialog.

Offline where the plugin can get things wrong on its own - which filters
it sends, how it reads a hit - and against the live register where the
question is whether the two sides still agree. The register's contents
are tested where they are built, in geodatafarm_mobile/api.

The network tests skip themselves when the service is unreachable, so an
offline run stays green.
"""
import pytest

from ..support_scripts import pesticide_client as pc

# Two hits copied verbatim from what the live register returns, rather
# than reduced to the keys a given test needs. A trimmed stand-in is how
# a test ends up asserting something the real record never carries - or
# missing that it does.
APPROVED = {
    'name': 'Boxer',
    'name_kind': 'product',
    'other_names': [],
    'registration_number': '5760',
    'status': 'approved',
    'usable': True,
    'approved_until': '2028-01-31',
    'withdrawn_on': None,
    'use_until': None,
    'permit_until': None,
    'authorisation': 'product',
    'functions': ['HB – Herbicid'],
    'purposes': ['Weeds'],
    'authorisation_classes': ['2 L'],
    'active_substances': 'Prosulfokarb (CAS-nr: 52888-80-9) 800 g/L',
    'use_summary': ('Mot ogräs i odlingar av höstvete, råg, rågvete och '
                    'höstkorn.\nMot ogräs i odlingar av potatis.\n'
                    'Mot ogräs i odlingar av gräs för utsäde.'),
    'uses': None,
    'company': 'Syngenta Nordics A/S',
}
WITHDRAWN = {
    'name': 'Aako Guazatine 350 LS',
    'name_kind': 'product',
    'other_names': [],
    'registration_number': '4632',
    'status': 'withdrawn_use_permitted',
    'usable': False,
    'approved_until': None,
    'withdrawn_on': '2008-12-31',
    'use_until': '2010-12-31',
    'permit_until': None,
    'authorisation': 'product',
    'functions': ['Växtskydd (biologiska produkter som innehåller NIS samt '
                  'ej längre godkända kemiska produkter)', 'FU – Fungicid'],
    'purposes': ['Fungi'],
    'authorisation_classes': ['2 L'],
    'active_substances': 'Guazatinacetater (CAS-nr: 115044-19-4) 350 g/L',
    'use_summary': ('Mot svampsjukdomar i stråsäd genom betning av utsäde.\n'
                    'Endast i betningsmaskin, särskilt avsedd för ändamålet.'),
    'uses': None,
    'company': 'Aako B.V.',
}


class FakeClient(pc.PesticideClient):
    """Records the parameters a search would send, without sending them."""

    def __init__(self, payload=None):
        super().__init__()
        self.calls = []
        self.payload = payload or {'products': [], 'count': 0, 'supported': True}

    def _get(self, path, params):
        self.calls.append((path, params))
        return self.payload


# ---------------------------------------------------------------------
# What the client sends
# ---------------------------------------------------------------------
def test_a_blank_query_still_searches():
    """Opening the dialog should show the shortlist the purpose implies,
    before the user has typed anything."""
    client = FakeClient()

    client.search('SE')

    _path, params = client.calls[0]
    assert params['country'] == 'SE'
    assert 'q' not in params


def test_the_journal_purpose_is_sent_as_a_filter():
    client = FakeClient()

    client.search('SE', query='box', purpose='Weeds')

    _path, params = client.calls[0]
    assert params['purpose'] == 'Weeds'
    assert params['q'] == 'box'


def test_the_other_purpose_does_not_narrow_the_search():
    """'Other' is a journal choice the register has no equivalent for.
    Sending it would return nothing and look like a broken lookup."""
    for purpose in ('', 'Other'):
        client = FakeClient()
        client.search('SE', purpose=purpose)
        _path, params = client.calls[0]
        assert 'purpose' not in params, purpose


def test_status_is_left_to_the_server_by_default():
    """Omitted, the API returns what may still be sprayed today - the
    right default for a form being filled in now."""
    client = FakeClient()

    client.search('SE')

    _path, params = client.calls[0]
    assert 'status' not in params


# ---------------------------------------------------------------------
# Reading a hit
# ---------------------------------------------------------------------
def test_an_approved_product_reads_as_its_name_and_number():
    assert pc.describe(APPROVED) == 'Boxer (5760)'
    assert pc.validity(APPROVED) == 'approved until 2028-01-31'


def test_a_withdrawn_product_says_so():
    """The grower reaching into the back of the shed is exactly who needs
    telling."""
    assert 'withdrawn' in pc.describe(WITHDRAWN)
    assert pc.validity(WITHDRAWN) == \
        'withdrawn 2008-12-31, may be used until 2010-12-31'


def test_a_country_with_no_import_is_not_supported():
    """The API knows how to read a Swedish export long before anyone has
    uploaded one, so the country being listed is not enough."""
    options = {'countries': {
        'SE': {'generation': {'exported_at': '2026-09-01'}},
        'DK': {'generation': None},
    }}

    assert pc.supported_countries(options) == {'SE'}


def test_no_options_means_no_supported_countries():
    assert pc.supported_countries({}) == set()
    assert pc.supported_countries(None) == set()


def test_the_disclosure_carries_the_export_date():
    payload = {'disclosure': {'sv': {'source': 'export 2026-09-01.',
                                     'note': 'Etiketten gäller.'}}}

    assert pc.disclosure_line(payload, 'sv') == 'export 2026-09-01. Etiketten gäller.'
    # Falls back rather than showing nothing in a language it lacks.
    assert 'export' in pc.disclosure_line(payload, 'de')


def test_an_unreachable_register_raises_the_recoverable_error():
    """Never fatal: the product fields are typeable. Port 9 is the discard
    port, so nothing is listening."""
    client = pc.PesticideClient(base_url='http://127.0.0.1:9/api', timeout=2)

    with pytest.raises(pc.PesticideUnavailable):
        client.options()


# ---------------------------------------------------------------------
# Contract with the live register
# ---------------------------------------------------------------------
@pytest.mark.network
def test_the_live_register_has_been_imported_for_sweden():
    client = pc.PesticideClient()
    try:
        options = client.options()
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Product register unreachable: {e}')

    assert 'SE' in pc.supported_countries(options), \
        'no export has been imported - run import_pesticides on the server'


@pytest.mark.network
def test_a_known_product_comes_back_with_its_registration_number():
    """Boxer is 5760 in Kemikalieinspektionen's register. If this stops
    matching, the two sides disagree about what a search returns."""
    client = pc.PesticideClient()
    try:
        payload = client.search('SE', query='Boxer')
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Product register unreachable: {e}')

    hits = [p for p in payload['products'] if p['name'] == 'Boxer']
    assert hits, payload['products']
    assert hits[0]['registration_number'] == '5760'
    assert hits[0]['status'] == pc.STATUS_APPROVED


@pytest.mark.network
def test_the_journals_purposes_are_the_ones_the_register_filters_on():
    """Guards the two vocabularies drifting apart: a purpose the server
    stopped honouring would silently return nothing."""
    from ..support_scripts import journal_fields as jf
    client = pc.PesticideClient()
    try:
        options = client.options()
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Product register unreachable: {e}')

    fields = {f.key: f for f in jf.template_fields('se_2026', 'spray')}
    offered = {c for c in fields['purpose'].choices
               if c and c not in pc.UNFILTERED_PURPOSES}

    assert offered <= set(options['purposes']), \
        f"journal offers purposes the register cannot filter on: " \
        f"{offered - set(options['purposes'])}"


@pytest.mark.network
def test_the_purpose_filter_actually_narrows_the_register():
    """The whole reason the search is usable: ~600 usable products is not
    a list to scroll, and the form has already answered the purpose."""
    client = pc.PesticideClient()
    try:
        everything = client.search('SE', limit=500)
        weeds = client.search('SE', purpose='Weeds', limit=500)
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Product register unreachable: {e}')

    assert 0 < weeds['count'] < everything['count']


@pytest.mark.network
def test_a_registration_sold_under_several_names_carries_its_siblings():
    """One Swedish approval is sold under as many as seven names, and the
    one in the shed may not be the one listed first."""
    client = pc.PesticideClient()
    try:
        payload = client.search('SE', query='MCPA 750')
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Product register unreachable: {e}')

    with_siblings = [p for p in payload['products'] if p.get('other_names')]
    assert with_siblings, 'expected at least one multi-name registration'
    product = with_siblings[0]
    for sibling in product['other_names']:
        assert sibling.get('name')


# ---------------------------------------------------------------------
# The details panel
# ---------------------------------------------------------------------
# The list can only carry a name and a date. The decision a grower is
# about to make - is this the right product for this field, and am I
# allowed to apply it - needs the approved uses, the active substance and
# the authorisation class.
def test_details_lead_with_what_identifies_the_registration():
    rows = dict(pc.details(APPROVED))

    assert rows['Registration number'] == '5760'
    assert 'Prosulfokarb' in rows['Active substances']
    assert rows['Company'] == 'Syngenta Nordics A/S'


def test_details_spell_out_who_may_apply_it():
    """'2 L' is a legal condition on the person, not on the product, and a
    bare code says nothing to someone who does not already know."""
    product = dict(APPROVED, authorisation_classes=['2 L'])

    rows = dict(pc.details(product))

    assert 'licence' in rows['Who may use it']


def test_details_show_the_approved_uses():
    product = dict(APPROVED, use_summary='Mot ogräs i odlingar av potatis.')

    rows = dict(pc.details(product))

    assert 'potatis' in rows['Approved uses']


def test_structured_uses_win_over_the_summary_when_present():
    """Only 4.5 % of registrations carry them, but where they exist they
    are per-use rather than one paragraph."""
    product = dict(APPROVED, uses='Användning 1: Vårvete; ; Mot svampangrepp',
                   use_summary='something vaguer')

    rows = dict(pc.details(product))

    assert 'Användning 1' in rows['Approved uses']


def test_details_leave_out_what_the_record_does_not_carry():
    """A blank row is noise: the panel should be short for a sparse
    registration and long for a well-described one."""
    sparse = {'registration_number': '1', 'status': 'approved'}

    labels = [label for label, _value in pc.details(sparse)]

    assert 'Active substances' not in labels
    assert 'Company' not in labels


def test_details_of_nothing_is_nothing():
    assert pc.details(None) == []
    assert pc.details({}) == []


def test_the_status_row_carries_the_dates_behind_it():
    rows = dict(pc.details(WITHDRAWN))

    assert 'withdrawn' in rows['Status']
    assert '2010-12-31' in rows['Status']


def test_an_emergency_permit_says_what_it_is():
    product = dict(APPROVED, authorisation='emergency_permit')

    assert 'dispens' in dict(pc.details(product))['Authorisation']


# ---------------------------------------------------------------------
# Filling the journal's purpose
# ---------------------------------------------------------------------
def test_a_single_purpose_product_can_fill_the_journals_purpose():
    assert pc.sole_purpose(APPROVED) == 'Weeds'


def test_two_purposes_fill_nothing():
    """Which one this spraying was for is the operator's answer, not the
    register's - an unasked answer in a journal is worse than a blank."""
    product = dict(APPROVED, purposes=['Weeds', 'Growth regulation'])

    assert pc.sole_purpose(product) == ''


def test_no_purposes_fill_nothing():
    assert pc.sole_purpose(dict(APPROVED, purposes=[])) == ''
    assert pc.sole_purpose({}) == ''


# ---------------------------------------------------------------------
# Conditions of use
# ---------------------------------------------------------------------
# Reg 3345 as /api/pesticide-register/products/3345/conditions serves it,
# cut to two of its four approved uses and one further condition. The shape
# is the API's; the values are the decision's.
CONDITIONS = {
    'registration_number': '3345',
    'product_name': 'BASF MCPA 750',
    'available': True,
    'decision': {'type': 'Administrativ förlängning', 'in_force_from': '2024-08-28'},
    'document': {
        'id': 26099,
        'name': '3345_Bilaga_Villkor_för_användning_2024-08-28',
        'url': ('https://www.kemi.se/appresource/4.337d6d69195b250fc611421/'
                '12.6d6369f7195b2763b9e3905e/document?id=26099'),
    },
    'disclosure': {
        'sv': {'source': 'Villkoren kommer från Kemikalieinspektionens beslut '
                         'för registreringsnummer 3345, administrativ '
                         'förlängning med ikraftträdande 2024-08-28.',
               'note': 'Beslutet och etiketten gäller.'},
        'en': {'source': "Conditions from the Swedish Chemicals Agency's "
                         'decision for registration number 3345.',
               'note': 'The decision and the label govern.'},
    },
    'uses': [
        {'crop': 'Höstvete, höstkorn, råg, och rågvete', 'purpose': 'Mot örtogräs',
         'equipment': 'Bomspruta', 'stage': 'BBCH 20–39 Endast vår- behandling',
         'max_treatments': '1 per år', 'max_dose_product': '1 L/ha',
         'max_dose_substance': '750 g MCPA/ha',
         'max_dose': {'text': '1 L/ha', 'value': 1.0, 'unit': 'L', 'per': 'ha'},
         'stage_window': {'text': 'BBCH 20–39 Endast vår- behandling',
                          'from': 20, 'to': 39, 'qualifier': 'Endast vår- behandling'}},
        {'crop': 'Höstsäd med insådd rödklöver eller rödklöver och gräs',
         'purpose': 'Mot örtogräs', 'equipment': 'Bomspruta',
         'stage': 'BBCH 20–31 Endast vår- behandling', 'max_treatments': '1 per år',
         'max_dose_product': '600 mL/ha', 'max_dose_substance': '450 g MCPA/ha',
         'other': 'Utvecklingsstadiet avser höstsäden.',
         'max_dose': {'text': '600 mL/ha', 'value': 0.6, 'unit': 'L', 'per': 'ha'},
         'stage_window': {'text': 'BBCH 20–31 Endast vår- behandling',
                          'from': 20, 'to': 31, 'qualifier': 'Endast vår- behandling'}},
    ],
    'extra_conditions': [
        {'category': 'Anpassade skyddsavstånd vid spridning',
         'condition': 'Ett anpassat skyddsavstånd ska bestämmas med hjälp av '
                      '"Hjälpreda vid bestämning av anpassade skyddsavstånd".',
         'note': 'Villkoret är till för att skydda växter utanför fältet.',
         'change': 'X'},
    ],
    'problems': [],
}

NOTHING_ON_FILE = {'registration_number': '9999', 'available': False}

CHECKED = {
    'registration_number': '3345', 'available': True, 'use_count': 4,
    'checked': {'dose': True, 'stage': True},
    'warnings': [
        {'kind': 'dose', 'entered': '500', 'allowed': '1 L/ha', 'use_count': 4},
        {'kind': 'stage', 'entered': '45',
         'allowed': '20–31, 20–39, 23–31, 23–39', 'use_count': 4},
    ],
    'messages': {
        'sv': ['500 överskrider varje godkänd maxdos för produkten. Den högsta '
               'av dess 4 godkända användningar är 1 L/ha.',
               'BBCH 45 ligger utanför varje godkänt utvecklingsstadium för '
               'produkten. Dess 4 godkända användningar tillåter 20–31, 20–39, '
               '23–31, 23–39.',
               'Kontrollerat mot beslutet, som gäller tillsammans med etiketten.'],
        'en': ['500 exceeds every approved maximum dose for this product. The '
               'highest of its 4 approved uses is 1 L/ha.',
               'BBCH 45 is outside every approved growth stage for this product. '
               'Its 4 approved uses allow 20–31, 20–39, 23–31, 23–39.',
               'Checked against the decision, which governs together with the label.'],
    },
}


def test_conditions_are_asked_for_by_registration_number():
    client = FakeClient(CONDITIONS)

    client.conditions(' 3345 ')

    path, params = client.calls[0]
    assert path == '/products/3345/conditions'
    assert params == {}


def test_the_check_sends_only_what_was_entered():
    """A blank dimension is not checked, and must not be sent as an empty
    string the server would then try to read."""
    client = FakeClient(CHECKED)

    client.check('3345', rate='500', bbch='')

    path, params = client.calls[0]
    assert path == '/products/3345/conditions/check'
    assert params == {'rate': '500'}


def test_the_check_sends_the_journal_strings_as_typed():
    """"0,8" goes as "0,8": the server reads the comma, and quoting the
    entry back in a warning has to show what the operator wrote."""
    client = FakeClient(CHECKED)

    client.check('3345', rate='0,8', bbch='35')

    _path, params = client.calls[0]
    assert params == {'rate': '0,8', 'bbch': '35'}


def test_conditions_rows_of_nothing_is_nothing():
    assert pc.conditions_rows(None) == []
    assert pc.conditions_rows({}) == []
    assert pc.conditions_rows(NOTHING_ON_FILE) == []


def test_conditions_rows_show_each_approved_use_as_printed():
    rows = pc.conditions_rows(CONDITIONS, 'sv')
    labels = [label for label, _ in rows]

    assert labels[0] == 'Approved use 1 of 2'
    assert rows[0][1] == 'Höstvete, höstkorn, råg, och rågvete'
    assert ('Growth stage', 'BBCH 20–39 Endast vår- behandling') in rows
    # Both doses on one row, as the decision prints them - never converted.
    assert ('Max dose', '1 L/ha / 750 g MCPA/ha') in rows
    assert ('Max dose', '600 mL/ha / 450 g MCPA/ha') in rows
    # A blank cell is left out, not shown as a dash or a zero.
    assert 'Days to harvest' not in labels
    assert 'Days between treatments' not in labels


def test_conditions_rows_carry_the_further_conditions():
    rows = dict(pc.conditions_rows(CONDITIONS, 'sv'))
    assert rows['Anpassade skyddsavstånd vid spridning'].startswith(
        'Ett anpassat skyddsavstånd ska bestämmas')
    assert 'Hjälpreda' in rows['Anpassade skyddsavstånd vid spridning']


def test_conditions_rows_end_with_the_decision_and_its_attachment():
    """The provenance and the PDF are the basis for trusting the rows above
    them, so they come last and are never dropped."""
    rows = pc.conditions_rows(CONDITIONS, 'sv')
    assert rows[-3][0] == 'Decision'
    assert 'registreringsnummer 3345' in rows[-3][1]
    assert rows[-2] == ('Note', 'Beslutet och etiketten gäller.')
    assert rows[-1][0] == 'Decision attachment'
    assert rows[-1][1].endswith('document?id=26099')


def test_conditions_rows_fall_back_to_english_words():
    rows = dict(pc.conditions_rows(CONDITIONS, 'de'))
    assert rows['Decision'].startswith('Conditions from the Swedish Chemicals Agency')


def test_warning_lines_come_in_the_journals_language():
    lines = pc.warning_lines(CHECKED, 'sv')
    assert len(lines) == 3
    assert lines[0].startswith('500 överskrider varje godkänd maxdos')
    assert lines[-1].startswith('Kontrollerat mot beslutet')


def test_warning_lines_fall_back_to_english():
    assert pc.warning_lines(CHECKED, 'de')[0].startswith('500 exceeds every')


def test_no_warnings_is_no_lines():
    quiet = dict(CHECKED, warnings=[], messages={'sv': [], 'en': []})
    assert pc.warning_lines(quiet, 'sv') == []
    assert pc.warning_lines(NOTHING_ON_FILE, 'sv') == []
    assert pc.warning_lines(None, 'sv') == []


@pytest.mark.network
def test_the_live_check_agrees_about_duplosan_max():
    """500 l/ha at BBCH 45 is outside every approved use of reg 3345. If
    this stops holding, either the decision changed or the two sides
    disagree about the rule - both worth knowing. Skips until the API
    carrying /conditions/check is deployed."""
    client = pc.PesticideClient()
    try:
        result = client.check('3345', rate='500', bbch='45')
    except pc.PesticideUnavailable as e:
        pytest.skip(f'Conditions check unreachable: {e}')

    assert [w['kind'] for w in result['warnings']] == ['dose', 'stage']
    assert result['warnings'][0]['allowed'] == '1 L/ha'
