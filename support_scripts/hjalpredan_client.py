"""Client for the Hjälpredan lookup on api.geodatafarm.com.

The spraying journal's ``adapted_buffer_m`` is the one number on
Jordbruksverket's form whose row says "använd hjälpredan"
(:mod:`support_scripts.journal_fields`). The tables behind it are
Kemikalieinspektionen's, and they were transcribed cell by cell into the
GeoDataFarm API (``geodatafarm_mobile/api``, module ``hjalpredan``) - so
this plugin calls that rather than carrying a second copy. Two
transcriptions of 1062 cells diverge sooner or later, and the one number
they must never disagree about is a compliance number: the plugin and
the phone app have to give an inspector the same answer.

The endpoints take no session. Nothing about a farm goes in or comes out
- the inputs are a temperature, a wind speed and a few equipment
settings, and the answer is published in a booklet anyone can download.
That is also what makes this reachable from here at all: the plugin
stores only the *hash* of the farm password (see
database_scripts/create_new_farm.py), which is the one thing
``/api/login`` cannot accept, because it hashes what it is given.

Nothing here raises on a network failure. The Hjälpredan is a
convenience on top of a field the user can always fill in by hand, and a
journal entry must never be blocked by a server being unreachable -
:class:`HjalpredanError` is for a *rejected* input (the API answers 422
naming the tabulated range), which is worth showing the user because
they can fix it.
"""
from typing import Self

import requests

from .__init__ import TR

__author__ = 'Axel Horteborn'

BASE_URL = 'https://api.geodatafarm.com/api/hjalpredan'
# Short: this sits behind a button the user pressed and is waiting on. A
# slow answer is worse than no answer, because the field is typeable.
TIMEOUT_S = 15

# Journal choice text -> the wire value the API expects. The journal
# offers human labels (see journal_fields._SE_2026_SPRAY); the API takes
# the vocabulary its tables are keyed on. Anything not listed is sent as
# nothing rather than guessed - see :func:`_wire`.
NEAREST_OBJECTS = {
    'Nothing requiring a fixed distance': 'none',
    'Open ditch or drain': 'open_ditch',
    'Watercourse or lake': 'watercourse',
    'Drinking water well': 'drinking_water_well',
}
SENSITIVITIES = {'General': 'general', 'Special': 'special'}
SPRAY_QUALITIES = {'Fine': 'fine', 'Medium': 'medium', 'Coarse': 'coarse'}
FOLIAGES = {'Sparse': 'sparse', 'Dense': 'dense'}

# The journal's ``use_type`` choice that means the orchard tables apply.
# Every other use type reads the boom sprayer's.
ORCHARD_USE_TYPE = 'Fruit growing'

# The Hjälpredan is Swedish law: Kemikalieinspektionen's tables plus the
# fixed minimum distances of Naturvårdsverket's NFS 2015:2. It answers a
# question about Swedish fields and nothing else.
COUNTRY = 'SE'


def applies_in(country: str) -> bool:
    """Whether the Hjälpredan governs a farm in ``country``.

    Guards the button that fills the adapted buffer distance in. Offering
    it elsewhere would hand a grower a Swedish number complete with
    edition and page reference - and a confident wrong distance is worse
    than an empty box, because an empty box is visibly the user's to
    fill and a filled one is not.
    """
    return (country or '').strip().upper() == COUNTRY

# The drift-reduction class is recorded in a different journal field per
# variant, because the two books print different classes: 50/75/90 % for the
# bomspruta, 0/25/50/75/90/95/99 % for the fläktspruta. One shared field
# would either cap a fruit grower at 90 %, or offer an arable user a 25 %
# the boom tables have no column for.
BOOM_REDUCTION_FIELD = 'drift_reduction_percent'
ORCHARD_REDUCTION_FIELD = 'drift_reduction_orchard_percent'

# The bomspruta booklet prints its drift-reduction columns on one boom
# height only - the height approved equipment is tested at (p. 19). A boom
# at or below it reads that row, which is the conservative direction since
# distance grows with height; above it the book gives nothing to read and
# the lookup refuses, so the spray-quality columns are the only way in.
REDUCTION_MAX_BOOM_HEIGHT_CM = 50

# What a reading's ``governed_by`` can say. The tables can give a shorter
# distance than NFS 2015:2 allows next to water, in which case the fixed
# minimum wins - and which rule produced the number is part of what makes
# a journal entry defensible.
GOVERNED_BY_TABLE = 'hjalpredan'
GOVERNED_BY_FIXED = 'fixed'

# Wire value -> the journal's own choice text, for reporting a reading
# back to the user in the words the form uses.
OBJECT_LABELS = {wire: label for label, wire in NEAREST_OBJECTS.items()}


class HjalpredanError(Exception):
    """An input the Hjälpredan rejects - out of the tabulated range, or a
    column that does not exist. The message is the API's own, which names
    the range or the column set, so it is worth showing verbatim."""


class HjalpredanUnavailable(Exception):
    """The lookup could not be reached or did not answer usefully. Distinct
    from :class:`HjalpredanError` because the user can do nothing about
    it except type the distance in themselves."""


def _wire(mapping, value):
    """Translates a journal choice to its wire value, or None.

    None when the choice is blank or is one this plugin does not
    recognise - a user may rename or extend a choice list in the journal
    settings, and sending an unmapped label would have the API reject the
    whole request over a field the caller could simply omit.
    """
    return mapping.get((value or '').strip())


def _number(value):
    """Journal values are text. Returns a float, or None if this one is
    blank or isn't a number - the caller decides whether that is fatal."""
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None


class HjalpredanClient:
    """Thin client for the two adapted-buffer-distance endpoints."""

    def __init__(self: Self, base_url: str = BASE_URL, timeout: int = TIMEOUT_S) -> None:
        translate = TR('HjalpredanClient')
        self.tr = translate.tr
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def options(self: Self) -> dict:
        """The tabulated steps and the edition, straight from the server.

        Worth preferring over this module's own constants wherever a list
        is shown to the user: the tables get revised, and a plugin build
        still offering a step the server has dropped would produce
        readings the server never gave.
        """
        return self._get('', {})

    def boom_sprayer(self: Self, temperature_c, wind_speed_ms, boom_height_cm,
                     sensitivity, used_dose=None, label_maximum_dose=None,
                     dose=None, spray_quality=None, drift_reduction_percent=None,
                     nearest_object=None) -> dict:
        """The adapted buffer distance for a lantbruksspruta med bom.

        Parameters are the journal's own values; the caller passes them
        as they were entered and this translates. ``dose`` is the class
        (quarter/half/full) when it is already known, otherwise pass
        ``used_dose`` with ``label_maximum_dose`` and let the server work
        the class out - the fraction is of the label's *highest* dose,
        not of the dose that was planned.
        """
        params = {
            'temperature_c': temperature_c,
            'wind_speed_ms': wind_speed_ms,
            'boom_height_cm': boom_height_cm,
            'sensitivity': sensitivity,
        }
        self._add_dose(params, dose, used_dose, label_maximum_dose)
        if spray_quality:
            params['spray_quality'] = spray_quality
        if drift_reduction_percent is not None:
            params['drift_reduction_percent'] = drift_reduction_percent
        if nearest_object:
            params['nearest_object'] = nearest_object
        return self._get('/boom-sprayer', params)

    def orchard_sprayer(self: Self, wind_speed_ms, foliage, sensitivity,
                        used_dose=None, label_maximum_dose=None, dose=None,
                        drift_reduction_percent=None, nearest_object=None) -> dict:
        """The adapted buffer distance for a fläktspruta i fruktodling.

        Note the different input list: no temperature and no boom height,
        and the wind speed is the one measured at 4 m inside the
        planting. That is the booklet's model, not a simplification.
        """
        params = {
            'wind_speed_ms': wind_speed_ms,
            'foliage': foliage,
            'sensitivity': sensitivity,
        }
        self._add_dose(params, dose, used_dose, label_maximum_dose)
        if drift_reduction_percent is not None:
            params['drift_reduction_percent'] = drift_reduction_percent
        if nearest_object:
            params['nearest_object'] = nearest_object
        return self._get('/orchard-sprayer', params)

    @staticmethod
    def _add_dose(params, dose, used_dose, label_maximum_dose):
        """Either the class outright, or the pair the server derives it
        from. Sending neither lets the server say so in its own words,
        which names both accepted forms."""
        if dose:
            params['dose'] = dose
        elif used_dose is not None and label_maximum_dose is not None:
            params['used_dose'] = used_dose
            params['label_maximum_dose'] = label_maximum_dose

    def _get(self: Self, path: str, params: dict) -> dict:
        try:
            response = requests.get(self.base_url + path, params=params,
                                    timeout=self.timeout)
        except requests.RequestException as e:
            raise HjalpredanUnavailable(self.tr(
                'Could not reach the Hjälpredan service: {}').format(e)) from e
        if response.status_code == 422:
            # The API's 422s are all inputs the caller can fix, and the
            # message names the tabulated range or the column set.
            raise HjalpredanError(_detail(response, self.tr(
                'The Hjälpredan rejected those values.')))
        if response.status_code != 200:
            raise HjalpredanUnavailable(self.tr(
                'The Hjälpredan service answered {}.').format(response.status_code))
        try:
            return response.json()
        except ValueError as e:
            raise HjalpredanUnavailable(self.tr(
                'The Hjälpredan service sent something that was not JSON.')) from e


def _detail(response, fallback):
    """FastAPI puts the reason in ``detail``; fall back if it did not."""
    try:
        payload = response.json()
    except ValueError:
        return fallback
    detail = payload.get('detail') if isinstance(payload, dict) else None
    if isinstance(detail, list):
        # FastAPI's own validation errors are a list of dicts.
        return '; '.join(str(item.get('msg', item)) for item in detail)
    return str(detail) if detail else fallback


def variant_for(values) -> str:
    """Which set of tables a journal row reads: ``'orchard'`` for a
    fläktspruta i fruktodling, ``'boom'`` for everything else.

    Taken from the journal's own ``use_type``, so the user never picks
    the variant twice.
    """
    return 'orchard' if (values.get('use_type') or '').strip() == ORCHARD_USE_TYPE \
        else 'boom'


def from_journal_values(values) -> dict:
    """Pulls the Hjälpredan's inputs out of a journal row's values.

    Returns the keyword arguments for the variant :func:`variant_for`
    chooses, with anything the journal did not record left as None - so
    the caller can name exactly which fields are still missing rather
    than sending a half-filled request and reading a 422 back.

    Parameters
    ----------
    values: dict
        keyed by journal field key, as produced by
        widgets.add_data_form.AddDataForm.values.
    """
    shared = {
        'wind_speed_ms': _number(values.get('wind_speed')),
        'sensitivity': _wire(SENSITIVITIES, values.get('sensitivity')),
        'used_dose': _number(values.get('rate')),
        'label_maximum_dose': _number(values.get('label_max_dose')),
        'nearest_object': _wire(NEAREST_OBJECTS, values.get('fixed_buffer_object')),
    }
    if variant_for(values) == 'orchard':
        # No temperature and no boom height in the orchard tables, and the
        # wind speed is the one measured inside the planting - the
        # booklet's own model, not a simplification.
        shared['foliage'] = _wire(FOLIAGES, values.get('foliage'))
        # Its own field, because the two books print different classes -
        # see journal_fields._SE_2026_SPRAY. Reading the boom sprayer's
        # here would cap a fruit grower at 90 % and silently cost them the
        # 95 % and 99 % columns their equipment may be approved for.
        shared['drift_reduction_percent'] = _number(
            values.get(ORCHARD_REDUCTION_FIELD))
        return shared
    shared['temperature_c'] = _number(values.get('temperature_c'))
    shared['boom_height_cm'] = _number(values.get('boom_height_cm'))
    shared['spray_quality'] = _wire(SPRAY_QUALITIES, values.get('spray_quality'))
    shared['drift_reduction_percent'] = _number(
        values.get(BOOM_REDUCTION_FIELD))
    _resolve_boom_columns(shared)
    return shared


def _resolve_boom_columns(prepared) -> None:
    """Picks one of the bomspruta's two column groups, in place.

    Every page of that book has a spray-quality group and a
    drift-reduction group, and the booklet has the operator read one or
    the other (steps 6 and 7) - the lookup rejects a request carrying
    both. A journal legitimately holds both facts, though: a grower knows
    their nozzle gives medium droplets *and* that their equipment is
    approved to 75 %, and filling in both boxes is the natural thing to
    do. So the choice is made here rather than handed to the user as an
    error.

    Drift reduction wins where the book allows it to be read, because
    that is what the equipment was bought for and what its approval
    entitles the operator to. Above :data:`REDUCTION_MAX_BOOM_HEIGHT_CM`
    the book prints no reduction row at all, so spray quality is the only
    reading there. Either way the answer's ``table_inputs`` names the
    column actually read, and its notes carry the booklet's own caveat
    that the equipment's approval conditions - boom height, nozzle
    pressure, 8 km/h - still govern.
    """
    if prepared.get('spray_quality') is None \
            or prepared.get('drift_reduction_percent') is None:
        return
    height = prepared.get('boom_height_cm')
    if height is not None and height <= REDUCTION_MAX_BOOM_HEIGHT_CM:
        prepared['spray_quality'] = None
    else:
        prepared['drift_reduction_percent'] = None


# The inputs each variant cannot be called without, and the journal field
# label to name when one is blank.
REQUIRED_INPUTS = {
    'boom': (('temperature_c', 'Temperature'),
             ('wind_speed_ms', 'Wind speed'),
             ('boom_height_cm', 'Boom height'),
             ('sensitivity', 'Consideration')),
    'orchard': (('wind_speed_ms', 'Wind speed'),
                ('foliage', 'Foliage (orchard)'),
                ('sensitivity', 'Consideration')),
}


def missing_inputs(prepared, variant='boom') -> list:
    """What the user still has to fill in before the lookup can be called.

    Mostly blank fields, but not only: an entry can be complete and still
    unreadable, and naming that here is far better than sending a request
    that comes back 422.

    The dose is checked as a pair: the class is a fraction of the label's
    highest dose, so one of the two without the other tells the lookup
    nothing. Drift reduction is an alternative to spray quality, and only
    on the boom variant - the orchard tables have a 0 % column, so
    leaving it out there is an answer rather than a gap.
    """
    missing = [label for name, label in REQUIRED_INPUTS[variant]
               if prepared.get(name) is None]
    if prepared.get('used_dose') is None or prepared.get('label_maximum_dose') is None:
        missing.append('Dose and label maximum dose')
    if variant == 'boom':
        missing.extend(_missing_boom_columns(prepared))
    return missing


def _missing_boom_columns(prepared) -> list:
    """Whether the bomspruta tables can be read at all for this row.

    Two ways they cannot. Neither column group filled in is the ordinary
    gap. The other is subtler and would otherwise only surface as a 422:
    a drift-reduction class recorded for a boom running higher than the
    book's reduction row, where there is nothing to read and the
    spray-quality columns are the only way to an answer.
    """
    quality = prepared.get('spray_quality')
    reduction = prepared.get('drift_reduction_percent')
    if quality is None and reduction is None:
        return ['Spray quality or drift reduction class']
    height = prepared.get('boom_height_cm')
    if quality is None and height is not None \
            and height > REDUCTION_MAX_BOOM_HEIGHT_CM:
        return ['Spray quality - the drift-reduction columns are only '
                'printed for booms at {} cm or lower'.format(
                    REDUCTION_MAX_BOOM_HEIGHT_CM)]
    return []
