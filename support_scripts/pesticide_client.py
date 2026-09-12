"""Client for the plant-protection product lookup on api.geodatafarm.com.

The spraying journal asks for the product and its registration number
(:mod:`support_scripts.journal_fields`), and both were free text until
now - typed off the can, with nothing to catch a transposed digit or a
product whose approval ran out two seasons ago.

The register behind this is Kemikalieinspektionen's. There is no API and
no bulk download; a person downloads their export by hand and an
importer in the GeoDataFarm API turns it into a searchable register (see
``geodatafarm_mobile/api``, modules ``import_pesticides`` and
``pesticide_store``). That is also why this is a lookup rather than a
copy: the register is a shared, dated artefact, and a plugin carrying
its own would drift from the phone app's.

Per country, and it declares which ones it has. A farm in a country the
API has no register for gets no search and keeps typing, which is the
same graceful nothing the Hjälpredan does outside Sweden (see
:func:`supported_countries` and hjalpredan_client.applies_in).

Nothing here raises on a network failure. The product fields are
typeable, and a journal entry must never be blocked by a server being
unreachable.
"""
from typing import Self
from urllib.parse import quote

import requests

from .__init__ import TR

__author__ = 'Axel Horteborn'

BASE_URL = 'https://api.geodatafarm.com/api/pesticide-register'
# Short, because a person is waiting on a search box.
TIMEOUT_S = 15
# Shorter still for the conditions check, which runs when Save is pressed:
# a slow server must not turn saving a journal entry into a wait, and the
# check is help, not a gate - see GeoDataFarm._warn_about_conditions.
CHECK_TIMEOUT_S = 5

# How many hits to ask for. The register holds ~600 usable products for
# Sweden and the purpose filter roughly halves that, so this is generous
# for anything a farmer would actually type - and the answer says whether
# it was truncated.
DEFAULT_LIMIT = 50

# The journal's own purpose choices are already the API's vocabulary, so
# there is nothing to translate - except 'Other', which the register has
# no equivalent for and which must therefore not narrow the search at
# all. Sending it would return nothing and look like a broken lookup.
UNFILTERED_PURPOSES = ('', 'Other')

# What a result's ``status`` can say. ``usable`` on the record is the
# short answer - it folds these into "may this still be sprayed today" -
# but the status itself is what a journal entry should be able to show.
STATUS_APPROVED = 'approved'
STATUS_WITHDRAWN_USE_PERMITTED = 'withdrawn_use_permitted'
STATUS_WITHDRAWN = 'withdrawn'
STATUS_UNDATED = 'undated'


class PesticideUnavailable(Exception):
    """The register could not be reached or did not answer usefully. The
    caller should carry on and let the user type - never fatal."""


class PesticideClient:
    """Thin client for the register's options and search endpoints."""

    def __init__(self: Self, base_url: str = BASE_URL, timeout: int = TIMEOUT_S) -> None:
        translate = TR('PesticideClient')
        self.tr = translate.tr
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def options(self: Self) -> dict:
        """Which countries have a register, out of which export, plus the
        vocabulary the filters accept.

        Worth calling before offering the search at all: a country whose
        ``generation`` is null has no import behind it, and a search box
        that always returns nothing is worse than no search box.
        """
        return self._get('', {})

    def search(self: Self, country: str, query: str = '', purpose: str = '',
               status: str = '', limit: int = DEFAULT_LIMIT) -> dict:
        """Products matching ``query``.

        Parameters
        ----------
        country: str
            The farm's country - see journal_fields.farm_country.
        query: str
            Free text, matched against the product name and the
            registration number.
        purpose: str
            One of the journal's own purpose choices. Usually already
            answered on the form, and it is what cuts the register down
            to a shortlist before the user types anything.
        status: str
            Comma-separated statuses, or 'any'. Left out, the API
            returns what may still be sprayed today - so a withdrawn
            product has to be asked for, which is the right default for
            a form being filled in now and the wrong one for reading an
            old entry back.
        """
        params = {'country': country, 'limit': limit}
        if query:
            params['q'] = query
        if purpose and purpose not in UNFILTERED_PURPOSES:
            params['purpose'] = purpose
        if status:
            params['status'] = status
        return self._get('/products', params)

    def conditions(self: Self, registration_number: str) -> dict:
        """The conditions of use behind one registration's decision.

        One row per approved use - crop, equipment, BBCH window,
        treatments per year, days to harvest, maximum dose - read out of
        Kemikalieinspektionen's "Villkor för användning" attachment by the
        API (``geodatafarm_mobile/api``, module ``pesticide_conditions``).
        The register export the search runs on carries none of this.

        ``available`` false in the answer means no decision has been
        fetched for that registration; it is not an error and the product
        is still perfectly pickable.
        """
        return self._get(
            f'/products/{quote(str(registration_number).strip())}/conditions',
            {})

    def check(self: Self, registration_number: str, rate=None, bbch=None) -> dict:
        """What a journal entry says that no approved use of this product
        allows.

        The rule lives on the server, not here, so that this plugin and
        the phone app cannot disagree about a compliance statement - the
        same reason the Hjälpredan is served rather than copied. It warns
        only when the entry is outside *every* approved use; which row
        applies depends on the crop, and the API deliberately does not
        guess that. The answer's ``messages`` are ready sentences per
        language - see :func:`warning_lines`.

        ``rate`` and ``bbch`` are the journal's own strings, as typed.
        Only what was entered is sent; a dimension left blank is simply not
        checked.
        """
        params = {}
        if rate not in (None, ''):
            params['rate'] = str(rate)
        if bbch not in (None, ''):
            params['bbch'] = str(bbch)
        return self._get(
            f'/products/{quote(str(registration_number).strip())}/conditions/check',
            params)

    def _get(self: Self, path: str, params: dict) -> dict:
        try:
            response = requests.get(self.base_url + path, params=params,
                                    timeout=self.timeout)
        except requests.RequestException as e:
            raise PesticideUnavailable(self.tr(
                'Could not reach the product register: {}').format(e)) from e
        if response.status_code != 200:
            raise PesticideUnavailable(self.tr(
                'The product register answered {}.').format(response.status_code))
        try:
            return response.json()
        except ValueError as e:
            raise PesticideUnavailable(self.tr(
                'The product register sent something that was not JSON.')) from e


def supported_countries(options) -> set:
    """The countries an import has actually run for.

    A country can be listed in the options and still have no register -
    the API knows how to read a Swedish export before anyone has
    uploaded one - so presence is not enough; the generation is what
    says there is something to search.
    """
    countries = (options or {}).get('countries') or {}
    return {code for code, entry in countries.items()
            if (entry or {}).get('generation')}


def disclosure_line(payload, language='en') -> str:
    """The one line to show beside results: which register the data came
    from and when it was exported, and that the label governs.

    Comes from the server rather than this module so that the export's
    date is the one actually being searched, not one a client cached.

    Falls back through English to whatever language the payload does
    carry. This is the line that says the package label governs, and it
    is worth more in the wrong language than not at all - a client asking
    for one the server has never heard of should still see it.
    """
    disclosure = (payload or {}).get('disclosure') or {}
    text = disclosure.get(language) or disclosure.get('en')
    if not text:
        text = next((value for value in disclosure.values() if value), {})
    parts = [text.get('source'), text.get('note')]
    return ' '.join(part for part in parts if part)


def describe(product) -> str:
    """One line describing a hit, for a results list.

    Leads with what is printed on the can - the name and the registration
    number - and then says whether it may still be used, because a
    grower reaching for something in the back of the shed is exactly who
    needs to be told it was withdrawn in 2008.
    """
    bits = [product.get('name') or '', f"({product.get('registration_number')})"]
    status = product.get('status')
    if status and status != STATUS_APPROVED:
        bits.append(f'- {STATUS_LABELS.get(status, status)}')
    return ' '.join(bit for bit in bits if bit)


# Shown against a hit. Kept here rather than taken from the server
# because these are UI words, not part of the register's own vocabulary -
# the wire values are what travel, and they are matched exactly.
STATUS_LABELS = {
    STATUS_APPROVED: 'approved',
    STATUS_WITHDRAWN_USE_PERMITTED: 'withdrawn, may still be used',
    STATUS_WITHDRAWN: 'withdrawn',
    STATUS_UNDATED: 'no approval date on record',
}


# Behörighetsklass decides who may apply the product at all: class 1 and
# 2 need a licence, 'L' marks the ones that also need the professional
# use permit. Worth spelling out rather than showing a bare code, since
# it is a legal condition on the person, not on the product.
AUTHORISATION_CLASS_NOTES = {
    '1': 'class 1 - permit required',
    '1 L': 'class 1 L - permit and professional-use licence required',
    '1 So': 'class 1 So - permit required, special conditions',
    '1 Sox': 'class 1 Sox - permit required, special conditions',
    '2': 'class 2 - professional use',
    '2 L': 'class 2 L - professional-use licence required',
    '3': 'class 3 - may be used by anyone',
}

# What a registration is, when it is not an ordinary product approval.
AUTHORISATION_NOTES = {
    'parallel_trade': 'parallel trade permit',
    'emergency_permit': 'emergency permit (dispens) - time limited',
    'additional_name': 'an additional name for another registration',
}


def details(product) -> list:
    """The full record for one hit, as ``(label, value)`` pairs to show
    beside the list.

    The point is the decision the grower is about to make. The register
    cannot say whether a product is right for this field - the crops it
    names are Swedish prose, not codes - but it can put the approved
    uses, the active substance and the authorisation class in front of
    someone before they commit the name to a journal. That is the
    difference between picking from a list and knowing what was picked.

    Only what the record actually carries: an absent value is left out
    rather than shown as a blank row, so the panel is short for a sparse
    registration and long for a well-described one.
    """
    if not product:
        return []
    rows = [
        ('Registration number', product.get('registration_number')),
        ('Status', _status_text(product)),
        ('Authorisation', AUTHORISATION_NOTES.get(product.get('authorisation'))),
        ('Function', ', '.join(product.get('functions') or [])),
        ('Purpose', ', '.join(product.get('purposes') or [])),
        ('Who may use it', ', '.join(
            AUTHORISATION_CLASS_NOTES.get(c, c)
            for c in (product.get('authorisation_classes') or []))),
        ('Active substances', product.get('active_substances')),
        ('Company', product.get('company')),
        ('Approved uses', product.get('uses') or product.get('use_summary')),
        ('Also sold as', ', '.join(
            entry.get('name', '') for entry in (product.get('other_names') or []))),
    ]
    return [(label, str(value)) for label, value in rows if value]


def _status_text(product) -> str:
    """The status and the dates behind it, as one phrase."""
    label = STATUS_LABELS.get(product.get('status'), product.get('status') or '')
    when = validity(product)
    return f'{label} ({when})' if when and label else (label or when)


def sole_purpose(product) -> str:
    """The product's purpose when it has exactly one, else ''.

    Used to fill the journal's own purpose field when it is still blank.
    A product with two purposes says nothing about which one this
    spraying was for, and guessing would put an unasked answer into a
    journal that has to be defensible.
    """
    purposes = product.get('purposes') or []
    return purposes[0] if len(purposes) == 1 else ''


def validity(product) -> str:
    """When a product's approval runs out, or ran out - the part of a hit
    that a journal entry may need to justify itself later."""
    if product.get('approved_until'):
        return f"approved until {product['approved_until']}"
    if product.get('use_until'):
        return (f"withdrawn {product.get('withdrawn_on')}, "
                f"may be used until {product['use_until']}")
    if product.get('withdrawn_on'):
        return f"withdrawn {product['withdrawn_on']}"
    return ''


# ---------------------------------------------------------------------
# Conditions of use, for the search dialog and the save-time check
# ---------------------------------------------------------------------
# One decision row -> the (label, value) pairs the dialog shows. Labels are
# English literals like details()' and are translated by the dialog; values
# are the decision's own Swedish text and are shown as printed. A blank cell
# is left out rather than shown as a dash: an empty karens column means the
# decision sets no karens, not that it sets one of nought days.
_USE_ROWS = (
    ('Purpose', 'purpose'),
    ('Equipment', 'equipment'),
    ('Growth stage', 'stage'),
    ('Max treatments', 'max_treatments'),
    ('Days between treatments', 'min_days_between'),
    ('Days to harvest', 'min_days_to_harvest'),
    ('Other conditions', 'other'),
)


def conditions_rows(payload, language='en') -> list:
    """The approved uses and further conditions as ``(label, value)`` pairs,
    to follow :func:`details` in the dialog's panel.

    Empty when nothing is on file, so a product without a fetched decision
    shows exactly what it showed before. The decision's own provenance line
    and the link to the PDF come last, because they are the whole basis on
    which the rows above can be trusted and must not be dropped on the way
    to the screen.
    """
    if not payload or not payload.get('available'):
        return []
    uses = payload.get('uses') or []
    rows = []
    for index, use in enumerate(uses, 1):
        where = ' / '.join(part for part in (use.get('crop'), use.get('where')) if part)
        rows.append((f'Approved use {index} of {len(uses)}',
                     where or '(no crop stated)'))
        for label, key in _USE_ROWS:
            if use.get(key):
                rows.append((label, use[key]))
        dose = ' / '.join(part for part in (
            use.get('max_dose_product'), use.get('max_dose_substance')) if part)
        if dose:
            rows.append(('Max dose', dose))
    for extra in payload.get('extra_conditions') or []:
        text = ' — '.join(part for part in (
            extra.get('condition'), extra.get('note')) if part)
        if text:
            rows.append((extra.get('category') or 'Further condition', text))
    disclosure = (payload.get('disclosure') or {})
    words = disclosure.get(language) or disclosure.get('en') or {}
    if words.get('source'):
        rows.append(('Decision', words['source']))
    if words.get('note'):
        rows.append(('Note', words['note']))
    url = (payload.get('document') or {}).get('url')
    if url:
        rows.append(('Decision attachment', url))
    return rows


def warning_lines(payload, language='en') -> list:
    """The check's warnings as sentences in ``language``, English if the
    server has no sentence in that language. Empty for no warnings - and
    for a product with nothing on file, which is the ordinary case."""
    if not payload:
        return []
    messages = payload.get('messages') or {}
    return list(messages.get(language) or messages.get('en') or [])
