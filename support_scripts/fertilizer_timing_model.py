"""Fertilizer-timing / rain-interaction analysis engine.

Turns a list of fertilizer application events and a daily weather series
into a leaching-risk read-out per event. Each event is analysed with one of
two tiers, decided independently per event:

* **Advanced tier** (:func:`_advanced_event_result`) - a simplified,
  NLEAP-style daily soil-water and nitrogen mass balance, run forward from
  the event date for a fixed horizon. Needs a numeric N rate for the event,
  daily precipitation + ET0 + mean temperature for that window, and the
  field's clay%/organic-matter% (for the water-holding-capacity estimate via
  ``support_scripts.soil_pedotransfer``). Each event is simulated in
  isolation (its own mini water/N balance starting at its own date) rather
  than as part of one whole-season, multi-event balance - that keeps the
  question answerable per application ("was *this* dose well-timed against
  the rain that actually followed?") without needing a full crop-nitrogen
  simulator. Nitrogen mineralisation from soil organic matter is not
  modelled, so the estimate is a conservative upper bound on leaching from
  the applied fertilizer N alone.
* **Simple tier** (:func:`_simple_event_result`) - a rainfall-since
  -application risk index. Needs only the event date and daily
  precipitation. Used whenever the advanced tier's inputs are missing, or
  the event's rate can't be parsed as a number.

This is a planning aid grounded in the physical mechanism (rain soon after
application drives nitrate leaching - see the crop/weather research this was
scoped from), not a certified agronomic model - treat its output as a
directional risk flag, not a lab-grade nitrogen balance.
"""
import re
from dataclasses import dataclass
from typing import Optional

from . import crop_models
from . import soil_pedotransfer

__author__ = 'Axel Horteborn'

_NUMBER_RE = re.compile(r'-?\d+(?:[.,]\d+)?')


def _parse_rate(text):
    """Best-effort numeric rate parsed from free text (e.g. ``"150 kg N/ha"``,
    ``"testa 33kg"`` -> 33.0), or ``None`` if no number could be found -
    shared by every one of FertilizerEvent's per-nutrient rate_kg_*_ha
    properties below."""
    if not text:
        return None
    match = _NUMBER_RE.search(text.replace(',', '.'))
    if not match:
        return None
    try:
        return float(match.group().replace(',', '.'))
    except ValueError:
        return None

# Simple-tier risk thresholds: total rain (mm, scaled by the crop's
# leaching_sensitivity) within the following window that counts as a
# "moderate" or "high" leaching risk.
_SIMPLE_WINDOW_DAYS = 3
_SIMPLE_HIGH_MM = 20.0
_SIMPLE_MODERATE_MM = 8.0

# Advanced-tier: how many days forward from the event date to simulate, and
# how many of those days need usable et0/temperature data before the
# advanced tier is even attempted (otherwise it falls back to the simple
# tier for that event).
ADVANCED_HORIZON_DAYS = 30
_ADVANCED_MIN_USABLE_DAYS = 7

# Advanced-tier risk thresholds: percent of the applied N estimated lost to
# leaching within the simulated horizon.
_ADVANCED_HIGH_PCT = 25.0
_ADVANCED_MODERATE_PCT = 10.0


@dataclass
class FertilizerEvent:
    """One fertilizer application to analyse - potentially several
    nutrients at once (a real compound product, e.g. an NPK blend,
    delivers them together on the same date/pass).

    Parameters
    ----------
    date: str
        ``YYYY-MM-DD``.
    rate_text: str
        The free-text nitrogen rate as stored in ``ferti.manual``/imported
        ferti tables (e.g. ``"150 kg N/ha"``, ``"120"``). Parsed best-effort
        by :attr:`rate_kg_n_ha`. Only nitrogen and potassium (see
        ``rate_text_k``) get a day-by-day uptake/leaching balance (see
        season_water_model.py) - phosphorus and magnesium are far less
        mobile in soil (bound to soil particles/held on cation exchange
        sites rather than moving with soil water the way nitrate and,
        to a lesser extent, potassium do), so a leaching-timing mechanic
        wouldn't reflect how they're actually lost - see
        ``rate_text_p``/``rate_text_mg``.
    rate_text_p, rate_text_k, rate_text_mg: str, optional
        The same free-text idea, for phosphorus, potassium and magnesium -
        parsed by :attr:`rate_kg_p_ha`/:attr:`rate_kg_k_ha`/
        :attr:`rate_kg_mg_ha` respectively. All independently optional;
        leaving one blank just means that nutrient isn't modelled for this
        event, the same as leaving ``rate_text`` blank already meant for
        nitrogen.
    crop: str, optional
        Crop name, looked up via :func:`crop_models.get_crop_model`.
    """
    date: str
    rate_text: str = ''
    crop: str = ''
    rate_text_p: str = ''
    rate_text_k: str = ''
    rate_text_mg: str = ''

    @property
    def rate_kg_n_ha(self) -> Optional[float]:
        """Best-effort numeric N rate parsed from :attr:`rate_text`, or
        ``None`` if no number could be found - which alone forces the
        simple-tier fallback for this event."""
        return _parse_rate(self.rate_text)

    @property
    def rate_kg_p_ha(self) -> Optional[float]:
        return _parse_rate(self.rate_text_p)

    @property
    def rate_kg_k_ha(self) -> Optional[float]:
        return _parse_rate(self.rate_text_k)

    @property
    def rate_kg_mg_ha(self) -> Optional[float]:
        return _parse_rate(self.rate_text_mg)


@dataclass
class DailyWeather:
    """One day of weather for the analysis window."""
    date: str
    precipitation_mm: Optional[float]
    et0_mm: Optional[float] = None
    temp_mean_c: Optional[float] = None
    solar_radiation_mj_m2: Optional[float] = None
    daylight_hours: Optional[float] = None


@dataclass
class EventResult:
    """The outcome of analysing one :class:`FertilizerEvent`."""
    date: str
    tier: str  # 'advanced' or 'simple'
    risk: str  # 'low', 'moderate', 'high', or 'unknown' (no weather data)
    rain_mm_after: float
    detail: str
    crop_model: str  # crop_models.CropModel.name actually used for this event
    estimated_n_leached_kg_ha: Optional[float] = None  # advanced tier only
    # Echoes FertilizerEvent.rate_kg_n_ha - None means this event's rate_text
    # had no number _NUMBER_RE could find, so it contributed nothing to the
    # season nitrogen balance and couldn't use the advanced tier either
    # (see analyse_events); a caller renders this so that's never silent.
    rate_kg_n_ha: Optional[float] = None
    # Echoes FertilizerEvent's rate_kg_p_ha/rate_kg_k_ha/rate_kg_mg_ha -
    # unlike nitrogen these never affect tier choice (see analyse_events),
    # just carried through so a caller can show the same "understood as X"
    # confirmation for every nutrient a rate was given for.
    rate_kg_p_ha: Optional[float] = None
    rate_kg_k_ha: Optional[float] = None
    rate_kg_mg_ha: Optional[float] = None


def analyse_events(events, weather, clay_pct=None, organic_matter_pct=None):
    """Analyses a list of fertilizer events against a daily weather series.

    Parameters
    ----------
    events: list[FertilizerEvent]
    weather: list[DailyWeather]
        Need not be sorted; covering from the first event date through to
        the end of the analysis window gives the best results.
    clay_pct, organic_matter_pct: float, optional
        The field's soil texture. Required for the advanced tier; when
        ``clay_pct`` is None every event uses the simple tier.

    Returns
    -------
    list[EventResult]
        One entry per event, in the same order as ``events``.
    """
    weather_by_date = {w.date: w for w in weather}
    dates_sorted = sorted(weather_by_date)
    results = []
    for ev in events:
        model = crop_models.get_crop_model(ev.crop)
        rate = ev.rate_kg_n_ha
        if (rate is not None and clay_pct is not None
                and _has_advanced_weather(weather_by_date, dates_sorted, ev.date)):
            result = _advanced_event_result(
                ev, rate, model, weather_by_date, dates_sorted,
                clay_pct, organic_matter_pct or 0.0)
        else:
            result = _simple_event_result(ev, model, weather_by_date, dates_sorted, rate)
        # P/K/Mg never affect tier choice above (only N does) or the detail
        # text either function already built - just echoed onto the result
        # so a caller can render "(read as X kg P/ha)" etc. for every
        # nutrient a rate_text_* was given for, the same as rate_kg_n_ha.
        result.rate_kg_p_ha = ev.rate_kg_p_ha
        result.rate_kg_k_ha = ev.rate_kg_k_ha
        result.rate_kg_mg_ha = ev.rate_kg_mg_ha
        results.append(result)
    return results


def summarize(results):
    """A short, human-readable summary of tier usage and risk counts."""
    n = len(results)
    if n == 0:
        return 'No fertilizer applications found for this field/period.'
    advanced = sum(1 for r in results if r.tier == 'advanced')
    high = sum(1 for r in results if r.risk == 'high')
    moderate = sum(1 for r in results if r.risk == 'moderate')
    return (
        '{n} application(s) analysed - {a} with the advanced model, {s} with '
        'the simple model (missing a numeric rate or soil/weather data). '
        '{h} high-risk, {m} moderate-risk.'
    ).format(n=n, a=advanced, s=n - advanced, h=high, m=moderate)


def _rain_in_window(weather_by_date, dates_sorted, start_date, window_days):
    """Sums precipitation from ``start_date`` through ``window_days`` after
    it (inclusive of ``start_date``). Returns None if there is no weather
    data at all in that window."""
    if start_date not in weather_by_date:
        return None
    idx = dates_sorted.index(start_date)
    window = dates_sorted[idx: idx + 1 + window_days]
    total = 0.0
    any_data = False
    for d in window:
        p = weather_by_date[d].precipitation_mm
        if p is not None:
            total += p
            any_data = True
    return total if any_data else None


def _has_advanced_weather(weather_by_date, dates_sorted, event_date):
    """Whether there is enough usable et0/temperature/precipitation data
    from ``event_date`` forward to bother running the advanced tier."""
    if event_date not in weather_by_date:
        return False
    idx = dates_sorted.index(event_date)
    window = dates_sorted[idx: idx + ADVANCED_HORIZON_DAYS]
    if len(window) < _ADVANCED_MIN_USABLE_DAYS:
        return False
    usable = sum(
        1 for d in window
        if weather_by_date[d].et0_mm is not None
        and weather_by_date[d].temp_mean_c is not None
        and weather_by_date[d].precipitation_mm is not None)
    return usable >= _ADVANCED_MIN_USABLE_DAYS


def _simple_event_result(ev, model, weather_by_date, dates_sorted, rate_kg_n_ha):
    rain_after = _rain_in_window(weather_by_date, dates_sorted, ev.date,
                                 _SIMPLE_WINDOW_DAYS)
    if rain_after is None:
        return EventResult(
            date=ev.date, tier='simple', risk='unknown', rain_mm_after=0.0,
            detail='No weather data available for the days after this '
                   'application.', crop_model=model.name,
            rate_kg_n_ha=rate_kg_n_ha)
    adjusted = rain_after * model.leaching_sensitivity
    if adjusted >= _SIMPLE_HIGH_MM:
        risk = 'high'
    elif adjusted >= _SIMPLE_MODERATE_MM:
        risk = 'moderate'
    else:
        risk = 'low'
    detail = (
        '{rain:.0f} mm rain in the {days} days after application ({date}) '
        '- {risk} leaching risk for {crop}.'
    ).format(rain=rain_after, days=_SIMPLE_WINDOW_DAYS, date=ev.date,
            risk=risk, crop=model.name)
    return EventResult(date=ev.date, tier='simple', risk=risk,
                       rain_mm_after=rain_after, detail=detail,
                       crop_model=model.name, rate_kg_n_ha=rate_kg_n_ha)


def _advanced_event_result(ev, rate_kg_n_ha, model, weather_by_date,
                           dates_sorted, clay_pct, organic_matter_pct):
    idx = dates_sorted.index(ev.date)
    window = dates_sorted[idx: idx + ADVANCED_HORIZON_DAYS]
    awc = soil_pedotransfer.available_water_capacity(clay_pct, organic_matter_pct)

    cumulative_gdd = 0.0
    soil_water_mm = None
    soil_n_kg_ha = rate_kg_n_ha
    leached_total = 0.0
    rain_total = 0.0

    for day in window:
        w = weather_by_date[day]
        precip = w.precipitation_mm or 0.0
        et0 = w.et0_mm if w.et0_mm is not None else 0.0
        temp = w.temp_mean_c if w.temp_mean_c is not None else model.gdd_base_c
        rain_total += precip

        gdd_today = crop_models.growing_degree_days(temp, model.gdd_base_c)
        gdd_before = cumulative_gdd
        cumulative_gdd += gdd_today

        depth_cm = crop_models.root_depth_cm(model, cumulative_gdd)
        capacity_mm = awc * (depth_cm * 10.0)
        kc = crop_models.crop_coefficient(model, cumulative_gdd)
        actual_et = kc * et0

        if soil_water_mm is None:
            soil_water_mm = capacity_mm  # conservative start: at field capacity
        available = soil_water_mm + precip - actual_et
        drainage = max(0.0, available - capacity_mm)
        soil_water_mm = max(0.0, min(capacity_mm, available))

        uptake_before = crop_models.n_uptake_fraction(model, gdd_before)
        uptake_after = crop_models.n_uptake_fraction(model, cumulative_gdd)
        uptake_demand = max(0.0, uptake_after - uptake_before) * model.season_n_demand_kg_ha
        uptake = min(soil_n_kg_ha, uptake_demand)
        soil_n_kg_ha -= uptake

        if capacity_mm > 0 and soil_n_kg_ha > 0 and drainage > 0:
            concentration = soil_n_kg_ha / capacity_mm  # kg N per mm of soil water
            leached = min(soil_n_kg_ha, concentration * drainage)
        else:
            leached = 0.0
        soil_n_kg_ha -= leached
        leached_total += leached

        if soil_n_kg_ha <= 0.001:
            break

    leached_pct = 0.0 if rate_kg_n_ha <= 0 else min(
        100.0, 100.0 * leached_total / rate_kg_n_ha)
    if leached_pct >= _ADVANCED_HIGH_PCT:
        risk = 'high'
    elif leached_pct >= _ADVANCED_MODERATE_PCT:
        risk = 'moderate'
    else:
        risk = 'low'
    detail = (
        'Estimated {pct:.0f}% of the applied N ({leached:.0f} of {rate:.0f} '
        'kg N/ha) leached below the root zone within {days} days, given '
        '{rain:.0f} mm of rain in that window - {risk} leaching risk for '
        '{crop}.'
    ).format(pct=leached_pct, leached=leached_total, rate=rate_kg_n_ha,
            days=len(window), rain=rain_total, risk=risk, crop=model.name)
    return EventResult(
        date=ev.date, tier='advanced', risk=risk, rain_mm_after=rain_total,
        detail=detail, crop_model=model.name,
        estimated_n_leached_kg_ha=round(leached_total, 1),
        rate_kg_n_ha=rate_kg_n_ha)
