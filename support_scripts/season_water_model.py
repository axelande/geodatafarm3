"""Season-level soil water/nitrogen balance: irrigation need and a rough
yield estimate.

Runs a single day-by-day soil water balance across the whole analysed
period (unlike ``fertilizer_timing_model.py``, which runs a fresh ~30-day
mini water balance per fertilizer application), using the same building
blocks (``support_scripts.crop_models``, ``support_scripts.soil_pedotransfer``).
Two water trackers share the same daily capacity/Kc/ET0 but diverge in how
they handle water:

* **Yield estimate** - a tracker that adds real rain *and* any irrigation
  the user actually logged (see ``irrigation_mm_by_date``; defaults to none,
  i.e. purely rainfed) but is never artificially refilled. FAO Irrigation &
  Drainage Paper 33's yield-response-factor (Ky) approach - relative yield
  loss = Ky x (1 - actual ET / potential ET) - turns its ET deficit into a
  relative-yield fraction, but *per FAO-56 growth stage* (initial,
  development, mid-season, late-season - see
  ``crop_models.CropModel``'s ``ky_initial`` docstring for why a single
  seasonal figure can't represent water stress mattering far more during
  flowering/tuber initiation than during establishment or ripening) rather
  than one lump seasonal deficit. The four stages' relative-yield
  fractions are then combined *multiplicatively* - FAO-33's own Jensen
  (1968) multi-period model - not via Liebig's law of the minimum, which
  is reserved below for combining water against the independent
  nitrogen/heat factors.
* **Irrigation need** - a separate tracker that starts from the same rain +
  logged irrigation, but additionally refills to field capacity whenever it
  crosses a management-allowed-depletion (MAD) threshold (the standard
  FAO-56 net-irrigation-requirement concept). Its cumulative top-up total is
  the *additional* irrigation that would have been needed on top of
  whatever was already logged - not a from-scratch requirement, so it
  doesn't double-count water already applied.

Optionally (when ``fertilizer_kg_n_by_date`` is passed - see
:func:`estimate_season`), a third tracker runs alongside these two: a
running available-nitrogen pool, fed by logged/planned fertilizer events and
drawn down by the crop's daily uptake demand (``crop_models.n_uptake_fraction``'s
logistic curve), giving a second, independent relative-yield fraction the
same way the water tracker does. A fourth, structurally identical tracker
(when ``fertilizer_kg_k_by_date`` is passed) does the same for potassium -
its own pool, its own logistic uptake curve
(``crop_models.k_uptake_fraction``), its own concentration x drainage
leaching. Potassium gets this full treatment (unlike phosphorus/magnesium,
see below) because - like nitrate, though less dramatically - it's mobile
enough on many soils (held on cation exchange sites, but genuinely
leachable on sandy/low-CEC ground) for *when* it's applied to matter, not
just how much; phosphorus by contrast binds tightly to soil particles and
is lost mainly via surface runoff/erosion rather than leaching (a pathway
this module doesn't simulate at all), so a day-by-day drainage-triggered
balance wouldn't reflect how phosphorus actually behaves - see
:class:`crop_models.CropModel`'s docstring. Independently again, a day is
flagged as heat stress whenever its mean temperature exceeds
``model.heat_stress_threshold_c``; the *fraction* of the season's days that
were heat-stress days, scaled by ``model.ky_heat`` the same way the
nitrogen/potassium deficits are scaled by their own Ky, gives a fifth
relative-yield fraction (nitrogen, potassium and heat each use one seasonal
Ky, unlike water's four stage-specific ones). All of these that are
actually "modelled" (nitrogen/potassium need their own
``fertilizer_kg_n_by_date``/``fertilizer_kg_k_by_date``; heat needs
``model.ky_heat`` set above 0 - see :class:`crop_models.CropModel`'s
docstring for why it defaults to 0) are then combined via **Liebig's law of
the minimum**: yield is capped by whichever resource was more limiting over
the season, not their product or average - applying 150% of nitrogen
demand doesn't compensate for a drought, and vice versa. This is
deliberately not a full day-by-day limiting-factor simulation (which would
need a multi-way feedback between water, nitrogen, potassium and heat
stress on daily uptake/transpiration rates); comparing independent
season-total deficits is a coarser but far simpler and more explainable
approximation, in keeping with the rest of this module. Of these, heat is
the least literature-standardised - a single daily-mean-temperature
threshold is a simplification of what's usually a day/night-temperature and
growth-stage-dependent effect (e.g. potato tuber set) - so treat it as the
roughest even once configured.

Phosphorus and magnesium (``phosphorus_applied_kg_ha``/
``magnesium_applied_kg_ha``, both optional on :func:`estimate_season`) get a
much simpler treatment in keeping with the reasoning above: a single
season-total applied-vs-demand comparison (``model.season_p_demand_kg_ha``/
``season_mg_demand_kg_ha``), flagged 'under'/'adequate'/'over' - no daily
tracking, no leaching, and no participation in the Liebig's-law yield
combination above, since this module has no mechanism (runoff/erosion,
cation-exchange dynamics) that would make a day-by-day balance meaningful
for either of them.

Separately again (``planting_date``/``harvest_date``, both optional, on
:func:`estimate_season`/:func:`daily_trace`), the growing-degree-day (GDD)
clock these curves are all driven by otherwise just starts on the first day
of whatever weather was passed in - fine when that's also the real planting
date, wrong (the whole Kc/root-depth/N-uptake timeline shifts) whenever it
isn't. ``planting_date`` anchors it to a real logged planting date instead;
``harvest_date`` forces an early, deliberate end to the season (e.g. a
potato's foliage chemically or mechanically killed weeks before the tubers
are actually lifted, to let the skin set) instead of letting the natural
``season_end_gdd`` decline run its course - see
:func:`_daily_water_balance`'s docstring for exactly how a day outside
``[planting_date, harvest_date]`` is treated.

Separately (when ``spacing_mm`` is passed to :func:`estimate_season`),
actual in-row planting density scales the yield *ceiling* itself
(``potential_yield_t_ha``) via ``crop_models.spacing_yield_multiplier``,
before the water/nitrogen relative-yield fractions above are applied to
it - density isn't a third Liebig's-law factor, since (unlike water or
nitrogen) it doesn't run out or accumulate over the season; it just
changes what the field could have achieved in the first place. This has
no effect unless the crop model actually has a reference spacing/
sensitivity configured - see that function's docstring.

This is a planning aid, not a certified yield forecast: pest, disease and
frost effects still aren't modelled, and the baseline yields/Ky values are
generic literature defaults, not calibrated to this field - see
crop_models.py's ``CROP_MODELS`` comment for the specific sources, and
widgets/crop_settings_dialog.py for where a user can adjust them per crop
(or variety). Treat the yield number as an order-of-magnitude planning
figure, not a forecast.
"""
from collections import namedtuple
from dataclasses import dataclass
from typing import Optional

from . import crop_models
from . import soil_pedotransfer

__author__ = 'Axel Horteborn'

# Management allowed depletion: irrigation is considered "needed" once the
# crop has used this fraction of the readily available water in the root
# zone - a standard FAO-56 irrigation-scheduling threshold (0.5 is the usual
# default for most field crops).
MAD_FRACTION = 0.5

# The four FAO-56 growth stages (see crop_models.crop_growth_stage) that
# estimate_season's water yield-response combines - order doesn't matter
# here (each is looked up by name against its own CropModel.ky_* field).
_KY_STAGES = ('initial', 'development', 'mid_season', 'late_season')

# Generic loam-ish fallback soil texture, used only when no soil sample is
# on file at all - a season estimate with a generic soil assumption is still
# more useful than refusing to run (flagged via SeasonEstimate.used_default_soil).
_FALLBACK_CLAY_PCT = 25.0
_FALLBACK_ORGANIC_MATTER_PCT = 2.0

# Phosphorus/magnesium supply-vs-demand bands (fraction of season demand) -
# a simple, deliberately coarse planning heuristic (not a specific soil-test
# interpretation table), since neither gets the precision a day-by-day
# balance would need in the first place - see module docstring.
_SUPPLY_UNDER_FRACTION = 0.9
_SUPPLY_OVER_FRACTION = 1.3


def _supply_status(applied_kg_ha, demand_kg_ha):
    """'under'/'adequate'/'over' - the season-total comparison
    phosphorus/magnesium get instead of a day-by-day balance (see module
    docstring). ``demand_kg_ha`` <= 0 (no built-in figure for this crop)
    returns 'none' - not enough information to judge either way."""
    if demand_kg_ha <= 0:
        return 'none'
    ratio = applied_kg_ha / demand_kg_ha
    if ratio < _SUPPLY_UNDER_FRACTION:
        return 'under'
    if ratio > _SUPPLY_OVER_FRACTION:
        return 'over'
    return 'adequate'


@dataclass
class SeasonEstimate:
    """The result of :func:`estimate_season`."""
    crop_model: str
    days_with_weather: int
    total_rain_mm: float
    logged_irrigation_mm: float
    actual_et_mm: float
    potential_et_mm: float
    water_stress_days: int
    irrigation_need_mm: float
    potential_yield_t_ha: float
    estimated_yield_t_ha: Optional[float]
    used_default_soil: bool
    note: str
    # Nitrogen side - only populated when estimate_season() is given
    # fertilizer_kg_n_by_date (None, the default, means "not modelled": the
    # estimate is exactly the water-only figure, matching this module's
    # behaviour before nitrogen was added, and nitrogen_modeled is False).
    nitrogen_modeled: bool = False
    nitrogen_applied_kg_ha: float = 0.0
    nitrogen_demand_kg_ha: float = 0.0
    nitrogen_uptake_kg_ha: float = 0.0
    # Nitrogen still sitting in the pool (applied but not yet taken up)
    # that leached below the root zone on a drainage day - see
    # _daily_water_balance's leaching step. Already reflected in
    # nitrogen_uptake_kg_ha being lower than it otherwise would be
    # (leaching and uptake draw from the same pool); exposed separately so
    # a caller can explain *why* uptake fell short, not just that it did.
    nitrogen_leached_kg_ha: float = 0.0
    # Rain/irrigation that landed beyond field capacity on some day and
    # drained away unused - the mechanism that makes a single large
    # irrigation dose (or a big rain event) less effective than the same
    # total spread out, since the excess on that day is lost outright
    # rather than banked for a later dry spell.
    water_drainage_mm: float = 0.0
    # Which resource actually capped the estimate via Liebig's law -
    # 'water', 'nitrogen', 'heat', a '+'-joined combination for a tie among
    # more than one, or 'none' (neither nitrogen nor heat modelled - see
    # nitrogen_modeled/heat_modeled).
    limiting_factor: str = 'none'
    # What the estimate would have been from water alone (Liebig's law
    # ignored) - lets a caller show "nitrogen is what's holding you back"
    # explicitly rather than just a single blended number.
    estimated_yield_water_only_t_ha: Optional[float] = None
    # Planting density - only has an effect when both spacing_mm is passed
    # to estimate_season() AND the crop model has a reference_spacing_mm/
    # spacing_sensitivity set (see crop_models.spacing_yield_multiplier;
    # neither is true for any crop's built-in default). Unlike water/
    # nitrogen this scales potential_yield_t_ha itself (the achievable
    # ceiling for this spacing) rather than acting as a third Liebig's-law
    # factor - a planting density doesn't "run out" over the season the
    # way water or nitrogen can.
    spacing_mm: Optional[float] = None
    spacing_yield_multiplier: float = 1.0
    # The crop's raw (spacing-unadjusted) ceiling - only set when spacing
    # actually changed it, i.e. spacing_yield_multiplier != 1.0.
    potential_yield_before_spacing_t_ha: Optional[float] = None
    # Heat stress - modelled whenever the crop model's ky_heat is above 0
    # (0.0, the default for every crop, means "not modelled": heat_modeled
    # is False and this has no effect on estimated_yield_t_ha, matching
    # this module's behaviour before heat was added - see
    # crop_models.CropModel's docstring for why there's no non-zero
    # built-in default here, unlike ky_nitrogen/the water Ky values).
    heat_modeled: bool = False
    heat_stress_days: int = 0
    heat_stress_day_fraction: float = 0.0
    # Which of the four FAO-56 growth stages (see crop_models.CropModel's
    # ky_initial docstring) contributed the largest relative-yield hit to
    # the water factor above - 'none' if no stage saw any deficit at all.
    # The four stages' relative-yield fractions are combined
    # multiplicatively (Jensen 1968's multi-period model), not via Liebig's
    # law - that's reserved for combining water against nitrogen/heat.
    water_limiting_stage: str = 'none'
    # Potassium side - structurally identical to the nitrogen fields above
    # (own pool, own uptake curve, own leaching - see module docstring for
    # why potassium gets this and phosphorus/magnesium below don't).
    # potassium_modeled False (fertilizer_kg_k_by_date omitted) means
    # potassium has no effect on estimated_yield_t_ha at all, the same
    # "omitting it is not the same as zero" contract nitrogen_modeled uses.
    potassium_modeled: bool = False
    potassium_applied_kg_ha: float = 0.0
    potassium_demand_kg_ha: float = 0.0
    potassium_uptake_kg_ha: float = 0.0
    potassium_leached_kg_ha: float = 0.0
    # Phosphorus/magnesium - a single season-total applied-vs-demand
    # comparison only (no daily tracking, no leaching, no Liebig's-law
    # participation - see module docstring for why). *_modeled False
    # (the *_applied_kg_ha parameter omitted) means "not modelled", the
    # same contract as nitrogen_modeled/potassium_modeled; *_status is
    # 'under'/'adequate'/'over' relative to the crop's season demand, or
    # 'none' if not modelled.
    phosphorus_modeled: bool = False
    phosphorus_applied_kg_ha: float = 0.0
    phosphorus_demand_kg_ha: float = 0.0
    phosphorus_status: str = 'none'
    magnesium_modeled: bool = False
    magnesium_applied_kg_ha: float = 0.0
    magnesium_demand_kg_ha: float = 0.0
    magnesium_status: str = 'none'
    # The individual Liebig's-law factors (0-1) estimated_yield_t_ha's
    # relative_yield was the min() of - exposed so a caller can re-derive
    # a *different* combination than the field-wide one above without
    # rerunning the whole water/nitrogen/potassium/heat balance. Concretely:
    # CropSimulation._compute_cell_traces' per-cell yield map, where only
    # water genuinely varies cell to cell (soil/crop/variety/irrigation are
    # each resolved per cell - see that method's docstring); nitrogen/
    # potassium/heat aren't spatially resolved at all, so every cell reuses
    # these same field-wide figures as its own ceiling for those factors,
    # exactly as if the whole field were uniformly fertilized/heat-exposed.
    # Each defaults to 1.0 (no penalty), matching *_modeled=False's "not
    # modelled at all" contract for the ones that aren't.
    relative_yield_water: float = 1.0
    relative_yield_nitrogen: float = 1.0
    relative_yield_potassium: float = 1.0
    relative_yield_heat: float = 1.0


@dataclass
class DailyStress:
    """One day of the same water balance :func:`estimate_season` runs,
    exposed for callers that need the day-by-day trace instead of (or as
    well as) the season summary - e.g. a date-slider stress map (see
    database_scripts/crop_simulation.py). Nitrogen isn't included here -
    the per-cell stress map is water-only for now, see that module's
    docstring."""
    date: str
    soil_water_mm: float
    capacity_mm: float
    actual_et_mm: float
    potential_et_mm: float
    water_stress: bool
    # 0 (empty) - 1 (at field capacity); the natural quantity to colour a
    # per-cell stress map with, since it's already bounded and comparable
    # across cells/crops regardless of their absolute capacity_mm.
    wetness_fraction: float


_DayStep = namedtuple('_DayStep', [
    'day', 'precip', 'logged_irrigation', 'capacity_mm', 'potential_et',
    'actual_et', 'soil_water_mm', 'mad_threshold_mm', 'refill_mm',
    'drainage_mm', 'n_applied', 'n_demand', 'n_uptake', 'n_leached',
    'k_applied', 'k_demand', 'k_uptake', 'k_leached',
    'heat_stress_day', 'growth_stage',
])


def _daily_water_balance(weather, model, awc, irrigation_mm_by_date,
                         fertilizer_kg_n_by_date=None, fertilizer_kg_k_by_date=None,
                         planting_date=None, harvest_date=None):
    """Shared day-by-day soil water (and, optionally, nitrogen/potassium)
    balance stepper - :func:`estimate_season` (which aggregates this into a
    season summary) and :func:`daily_trace` (which just returns each day's
    water state) are thin wrappers around this, so they can never drift
    apart on the actual maths. See this module's docstring for the tracker
    design.

    The nitrogen and potassium pools are always computed (cheap
    bookkeeping) but are only *meaningful* when ``fertilizer_kg_n_by_date``/
    ``fertilizer_kg_k_by_date`` is a real dict - see :func:`estimate_season`'s
    handling of ``nitrogen_modeled``/``potassium_modeled``.

    ``planting_date``/``harvest_date`` (``YYYY-MM-DD``, both optional):
    without them, the growing-degree-day (GDD) clock starts on the first
    day of ``weather`` regardless of when the crop was actually planted -
    fine when that first day *is* the real planting date, wrong (the whole
    Kc/root-depth/N-uptake timeline shifts) whenever it isn't. Give
    ``planting_date`` to hold the crop "not yet present" (GDD frozen at 0,
    Kc/water use/N demand/heat stress all zero, same as bare, unplanted
    ground) for any day before it; ``harvest_date`` does the same for any
    day after it, modelling a hard stop - natural senescence via
    ``season_end_gdd`` otherwise runs its full course, which doesn't
    represent a deliberate early termination like potato haulm-killing
    (foliage desiccated weeks before the tubers are actually lifted, to
    let the skin set) or a cereal being combined.

    Yields
    ------
    _DayStep
        Named tuple, one per day with complete weather data, oldest first.
    """
    irrigation_mm_by_date = irrigation_mm_by_date or {}
    fertilizer_kg_n_by_date = fertilizer_kg_n_by_date or {}
    fertilizer_kg_k_by_date = fertilizer_kg_k_by_date or {}
    dates_sorted = sorted({w.date for w in weather})
    weather_by_date = {w.date: w for w in weather}

    cumulative_gdd = 0.0
    previous_cumulative_gdd = 0.0
    soil_water_mm = None
    sched_water_mm = None
    n_pool_kg_ha = 0.0
    k_pool_kg_ha = 0.0

    for day in dates_sorted:
        w = weather_by_date[day]
        if (w.precipitation_mm is None or w.et0_mm is None
                or w.temp_mean_c is None):
            continue
        precip, et0, temp = w.precipitation_mm, w.et0_mm, w.temp_mean_c
        logged_irrigation = irrigation_mm_by_date.get(day, 0.0) or 0.0

        crop_present = ((planting_date is None or day >= planting_date)
                        and (harvest_date is None or day <= harvest_date))
        if crop_present:
            cumulative_gdd += crop_models.growing_degree_days(temp, model.gdd_base_c)
        depth_cm = crop_models.root_depth_cm(model, cumulative_gdd)
        capacity_mm = awc * (depth_cm * 10.0)
        kc = crop_models.crop_coefficient(model, cumulative_gdd) if crop_present else 0.0
        potential_et = kc * et0
        # None while the crop isn't present - a pre-planting/post-harvest
        # day shouldn't count toward any growth stage's water-Ky weighting
        # (see estimate_season's per-stage relative-yield combination).
        growth_stage = crop_models.crop_growth_stage(model, cumulative_gdd) if crop_present else None

        if soil_water_mm is None:
            soil_water_mm = capacity_mm  # conservative start: at field capacity
        available = soil_water_mm + precip + logged_irrigation
        # Can't evapotranspire water the soil doesn't have - this is what
        # lets a dry spell show up as an actual/potential ET deficit.
        actual_et = min(potential_et, available)
        post_et_water_mm = available - actual_et
        # Water beyond field capacity drains below the root zone (and, see
        # the nitrogen step below, carries dissolved N with it) - this is
        # what makes a single large irrigation/rain event less effective
        # than the same total spread out: whatever lands beyond capacity
        # on a given day is lost outright, not banked for a later dry
        # spell the way a smaller, better-timed dose would be.
        drainage_mm = max(0.0, post_et_water_mm - capacity_mm)
        soil_water_mm = max(0.0, min(capacity_mm, post_et_water_mm))
        mad_threshold_mm = capacity_mm * (1.0 - MAD_FRACTION)

        if sched_water_mm is None:
            sched_water_mm = capacity_mm
        # An irrigated crop is assumed to transpire at its potential rate -
        # that's the point of irrigating - so this tracker always loses
        # potential_et, not the (possibly lower) actual_et.
        sched_water_mm = min(
            capacity_mm, sched_water_mm + precip + logged_irrigation - potential_et)
        refill_mm = 0.0
        if sched_water_mm < mad_threshold_mm:
            refill_mm = capacity_mm - sched_water_mm
            sched_water_mm = capacity_mm  # a refill event tops it back up

        # Nitrogen: a running available-N pool, topped up by fertilizer
        # events and drawn down by that day's *share* of season N demand -
        # the derivative of the cumulative uptake curve between yesterday's
        # and today's GDD, not the whole curve at once.
        n_applied = fertilizer_kg_n_by_date.get(day, 0.0) or 0.0
        n_pool_kg_ha += n_applied
        demand_frac_today = 0.0
        if crop_present:
            demand_frac_today = max(0.0, crop_models.n_uptake_fraction(model, cumulative_gdd)
                                    - crop_models.n_uptake_fraction(model, previous_cumulative_gdd))
        n_demand = demand_frac_today * model.season_n_demand_kg_ha
        n_uptake = min(n_demand, max(0.0, n_pool_kg_ha))
        n_pool_kg_ha -= n_uptake

        # Leaching: this same day's drainage carries away nitrogen still
        # sitting in the pool (not yet taken up), proportional to how
        # concentrated it is in the root zone's water right now - the same
        # concentration x drainage mechanic fertilizer_timing_model.py's
        # advanced tier uses for one isolated application, applied here to
        # the whole season's running pool instead. This is what actually
        # makes *when* you apply matter, not just how much: N that's
        # already been taken up is safe, N still waiting in the pool when
        # a big drainage event hits is at risk - so one lump application
        # sitting unused ahead of heavy rain leaches more than the same
        # total split into smaller, better-timed doses.
        n_leached = 0.0
        if capacity_mm > 0 and n_pool_kg_ha > 0 and drainage_mm > 0:
            concentration = n_pool_kg_ha / capacity_mm  # kg N per mm of soil water
            n_leached = min(n_pool_kg_ha, concentration * drainage_mm)
        n_pool_kg_ha -= n_leached

        # Potassium: the same running-pool/logistic-uptake/concentration x
        # drainage mechanic as nitrogen above, just against its own pool
        # and its own uptake curve (k_uptake_fraction, generally later-
        # peaking than nitrogen's for potato - see CropModel's docstring) -
        # see this module's docstring for why potassium gets this and
        # phosphorus/magnesium don't.
        k_applied = fertilizer_kg_k_by_date.get(day, 0.0) or 0.0
        k_pool_kg_ha += k_applied
        k_demand_frac_today = 0.0
        if crop_present:
            k_demand_frac_today = max(0.0, crop_models.k_uptake_fraction(model, cumulative_gdd)
                                      - crop_models.k_uptake_fraction(model, previous_cumulative_gdd))
        k_demand = k_demand_frac_today * model.season_k_demand_kg_ha
        k_uptake = min(k_demand, max(0.0, k_pool_kg_ha))
        k_pool_kg_ha -= k_uptake
        k_leached = 0.0
        if capacity_mm > 0 and k_pool_kg_ha > 0 and drainage_mm > 0:
            k_concentration = k_pool_kg_ha / capacity_mm
            k_leached = min(k_pool_kg_ha, k_concentration * drainage_mm)
        k_pool_kg_ha -= k_leached

        previous_cumulative_gdd = cumulative_gdd

        # Heat: a day's mean temperature above the crop's threshold counts
        # as a heat-stress day - see estimate_season()'s heat_modeled
        # handling for how the season's fraction of such days turns into a
        # relative-yield fraction (only meaningful once ky_heat > 0). Never
        # true while the crop isn't present - nothing to stress.
        heat_stress_day = crop_present and temp > model.heat_stress_threshold_c

        yield _DayStep(
            day=day, precip=precip, logged_irrigation=logged_irrigation,
            capacity_mm=capacity_mm, potential_et=potential_et, actual_et=actual_et,
            soil_water_mm=soil_water_mm, mad_threshold_mm=mad_threshold_mm,
            refill_mm=refill_mm, drainage_mm=drainage_mm,
            n_applied=n_applied, n_demand=n_demand, n_uptake=n_uptake,
            n_leached=n_leached, k_applied=k_applied, k_demand=k_demand,
            k_uptake=k_uptake, k_leached=k_leached,
            heat_stress_day=heat_stress_day, growth_stage=growth_stage)


def daily_trace(weather, crop_name, clay_pct=None, organic_matter_pct=None,
                irrigation_mm_by_date=None, crop_model=None, planting_date=None,
                harvest_date=None):
    """The same soil water balance as :func:`estimate_season`, returned as
    a day-by-day trace instead of a season summary - see
    :class:`DailyStress`.

    Parameters are identical to :func:`estimate_season` (minus the
    nitrogen ones - the per-cell map is water-only, see :class:`DailyStress`).

    Returns
    -------
    list[DailyStress]
    """
    model = crop_model or crop_models.get_crop_model(crop_name)
    if clay_pct is None:
        clay_pct = _FALLBACK_CLAY_PCT
        organic_matter_pct = _FALLBACK_ORGANIC_MATTER_PCT
    awc = soil_pedotransfer.available_water_capacity(clay_pct, organic_matter_pct or 0.0)
    out = []
    for step in _daily_water_balance(weather, model, awc, irrigation_mm_by_date,
                                     planting_date=planting_date, harvest_date=harvest_date):
        out.append(DailyStress(
            date=step.day, soil_water_mm=round(step.soil_water_mm, 1),
            capacity_mm=round(step.capacity_mm, 1), actual_et_mm=round(step.actual_et, 2),
            potential_et_mm=round(step.potential_et, 2),
            water_stress=step.soil_water_mm < step.mad_threshold_mm,
            wetness_fraction=(round(step.soil_water_mm / step.capacity_mm, 3)
                              if step.capacity_mm > 0 else 0.0)))
    return out


def _relative_yield_from_stage_et(model, stage_actual_et, stage_potential_et):
    """FAO-33's Jensen (1968) multi-period model: each growth stage's own
    relative-yield fraction (its own Ky against its own ET deficit, not
    the season's aggregate deficit) multiplied together, rather than
    Liebig's-law-style minimum (that's for combining water against
    nitrogen/potassium/heat, not stages against each other) or a single
    flat seasonal Ky. A stage the analysed period didn't cover
    (stage_potential_et <= 0) contributes no penalty at all - not the
    same as "no stress happened", just "no information about it either
    way". Shared by :func:`estimate_season` (field-wide) and
    ``CropSimulation._compute_cell_traces``' per-cell yield map (water is
    the one factor that's genuinely resolved per cell - see that
    method's docstring), so the two can never drift apart on this maths.

    Returns
    -------
    (relative_yield_water, water_limiting_stage, stage_deficit_fraction)
    """
    stage_ky = {
        'initial': model.ky_initial, 'development': model.ky_development,
        'mid_season': model.ky_mid_season, 'late_season': model.ky_late_season,
    }
    relative_yield_water = 1.0
    stage_deficit_fraction = {}
    for stage in _KY_STAGES:
        stage_potential = stage_potential_et[stage]
        if stage_potential <= 0:
            continue
        deficit = max(0.0, 1.0 - stage_actual_et[stage] / stage_potential)
        stage_deficit_fraction[stage] = deficit
        relative_yield_water *= max(0.0, 1.0 - stage_ky[stage] * deficit)
    water_limiting_stage = 'none'
    if stage_deficit_fraction:
        worst_stage = max(stage_deficit_fraction, key=stage_deficit_fraction.get)
        if stage_deficit_fraction[worst_stage] > 0.01:
            water_limiting_stage = worst_stage
    return relative_yield_water, water_limiting_stage, stage_deficit_fraction


def daily_trace_with_relative_yield(weather, crop_name, clay_pct=None, organic_matter_pct=None,
                                    irrigation_mm_by_date=None, crop_model=None,
                                    planting_date=None, harvest_date=None,
                                    include_daily_relative_yield=False):
    """Combines :func:`daily_trace`'s day-by-day stress trace and
    :func:`estimate_season`'s water-only relative-yield calculation into
    one pass over :func:`_daily_water_balance`, instead of the two
    separate passes calling both those functions back to back would take -
    see ``CropSimulation._compute_cell_traces``, which needs both *per
    cell* and would otherwise double the cost of an already-expensive
    per-cell loop (a large field can have thousands of cells - see
    support_scripts/field_grid.py's cell budget).

    Nitrogen/potassium/heat aren't included here, unlike
    :func:`estimate_season`'s own combined relative yield - none of those
    are resolved per cell (only field-wide fertilizer application data
    exists), so this is a water-only estimate of how much of its own
    potential yield a cell's own soil/crop/variety/irrigation would let
    it reach - the caller combines it with the field-wide non-water
    factors (see :class:`SeasonEstimate`'s ``relative_yield_nitrogen``/
    ``relative_yield_potassium``/``relative_yield_heat``) via the same
    Liebig's-law minimum :func:`estimate_season` uses, not a full
    independent per-cell prediction.

    Returns
    -------
    (list[DailyStress], float, str[, dict[str, float]])
        The same trace :func:`daily_trace` returns, the water-only
        relative yield fraction (0-1), and which growth stage was most
        water-limited (see :class:`SeasonEstimate`'s
        ``water_limiting_stage``). When ``include_daily_relative_yield`` is
        true, a fourth item maps each date to the water-only relative yield
        after that date's accumulated stress.
    """
    model = crop_model or crop_models.get_crop_model(crop_name)
    if clay_pct is None:
        clay_pct = _FALLBACK_CLAY_PCT
        organic_matter_pct = _FALLBACK_ORGANIC_MATTER_PCT
    awc = soil_pedotransfer.available_water_capacity(clay_pct, organic_matter_pct or 0.0)
    out = []
    daily_relative_yield = {}
    cumulative_gdd = 0.0
    weather_by_date = {w.date: w for w in weather}
    stage_actual_et = {stage: 0.0 for stage in _KY_STAGES}
    stage_potential_et = {stage: 0.0 for stage in _KY_STAGES}
    for step in _daily_water_balance(weather, model, awc, irrigation_mm_by_date,
                                     planting_date=planting_date, harvest_date=harvest_date):
        out.append(DailyStress(
            date=step.day, soil_water_mm=round(step.soil_water_mm, 1),
            capacity_mm=round(step.capacity_mm, 1), actual_et_mm=round(step.actual_et, 2),
            potential_et_mm=round(step.potential_et, 2),
            water_stress=step.soil_water_mm < step.mad_threshold_mm,
            wetness_fraction=(round(step.soil_water_mm / step.capacity_mm, 3)
                              if step.capacity_mm > 0 else 0.0)))
        if step.growth_stage:
            stage_actual_et[step.growth_stage] += step.actual_et
            stage_potential_et[step.growth_stage] += step.potential_et
        if include_daily_relative_yield:
            if step.growth_stage:
                weather_day = weather_by_date.get(step.day)
                if weather_day is not None:
                    cumulative_gdd += crop_models.growing_degree_days(
                        weather_day.temp_mean_c, model.gdd_base_c)
            maturity_progress = crop_models.harvestable_yield_progress(
                model, cumulative_gdd)
            stress_fraction = _relative_yield_from_stage_et(
                model, stage_actual_et, stage_potential_et)[0]
            daily_relative_yield[step.day] = maturity_progress * stress_fraction
    relative_yield_water, water_limiting_stage, _stage_deficit = (
        _relative_yield_from_stage_et(model, stage_actual_et, stage_potential_et))
    if include_daily_relative_yield:
        return out, relative_yield_water, water_limiting_stage, daily_relative_yield
    return out, relative_yield_water, water_limiting_stage


def estimate_season(weather, crop_name, clay_pct=None, organic_matter_pct=None,
                    irrigation_mm_by_date=None, fertilizer_kg_n_by_date=None,
                    fertilizer_kg_k_by_date=None, phosphorus_applied_kg_ha=None,
                    magnesium_applied_kg_ha=None, crop_model=None, spacing_mm=None,
                    planting_date=None, harvest_date=None):
    """Runs a season-length soil water (and, optionally, nitrogen) balance
    for ``crop_name`` and derives an irrigation-need figure and a rough
    yield estimate from it.

    Parameters
    ----------
    weather: list[fertilizer_timing_model.DailyWeather]
        The analysis period's daily weather (precipitation, ET0, mean temp).
        Days missing any of the three are skipped.
    crop_name: str
        Looked up via ``crop_models.get_crop_model`` unless ``crop_model``
        is given directly.
    clay_pct, organic_matter_pct: float, optional
        The field's soil texture. Falls back to a generic loam estimate if
        not supplied (see :data:`_FALLBACK_CLAY_PCT`) - unlike
        ``fertilizer_timing_model.analyse_events``, a season estimate with a
        generic soil assumption is still more useful than refusing to run;
        the fallback is flagged via ``SeasonEstimate.used_default_soil``.
    irrigation_mm_by_date: dict[str, float], optional
        Actually-logged irrigation (see
        import_data/handle_irrigation.py's ``_store_dated_operation``),
        keyed by ``YYYY-MM-DD``. Added to the water balance like rain on
        that day. Omitted/empty means a purely rainfed estimate, same as
        before this parameter existed.
    fertilizer_kg_n_by_date: dict[str, float], optional
        Nitrogen applied (kg N/ha), keyed by ``YYYY-MM-DD`` - see
        ``fertilizer_timing_model.FertilizerEvent.rate_kg_n_ha``. **Omitted
        (``None``, the default) means nitrogen isn't modelled at all** -
        the estimate is exactly the water-only figure, and
        ``SeasonEstimate.nitrogen_modeled`` is False. Passed as an empty
        dict ``{}`` instead means "nitrogen *is* modelled, and genuinely
        nothing was applied" - a real, potentially yield-capping input, not
        the same as omitting it. This distinction exists so every existing
        caller that doesn't know about nitrogen yet keeps getting the exact
        water-only estimate it always has.
    fertilizer_kg_k_by_date: dict[str, float], optional
        The same idea as ``fertilizer_kg_n_by_date``, for potassium - see
        ``fertilizer_timing_model.FertilizerEvent.rate_kg_k_ha`` and
        ``SeasonEstimate.potassium_modeled``'s same omitted-vs-empty
        distinction.
    phosphorus_applied_kg_ha, magnesium_applied_kg_ha: float, optional
        Total phosphorus/magnesium applied (kg/ha) across the *whole*
        analysed period - unlike the nitrogen/potassium parameters above
        this is one season-total number, not a per-date dict, since
        neither gets a day-by-day balance (see module docstring for why -
        in short, neither moves through soil the way nitrate/potassium
        can, so a drainage-triggered leaching mechanic wouldn't reflect
        how either is actually lost). Omitted (``None``, the default)
        means "not modelled" (``SeasonEstimate.phosphorus_modeled``/
        ``magnesium_modeled`` False); ``0.0`` means "modelled, and
        genuinely nothing was applied" - the same omitted-vs-zero
        distinction ``fertilizer_kg_n_by_date`` draws.
    crop_model: crop_models.CropModel, optional
        Use this model directly instead of looking ``crop_name`` up - how a
        user's edited/saved settings (see
        support_scripts/crop_model_settings.py) get applied. Heat stress
        has no dedicated parameter of its own here (unlike nitrogen/
        spacing) - it's entirely driven by this model's
        ``heat_stress_threshold_c``/``ky_heat`` (temperature is already
        part of ``weather``), and is only "modelled"
        (``SeasonEstimate.heat_modeled``) once ``ky_heat`` is set above its
        default of 0.
    spacing_mm: float, optional
        Actual in-row planting spacing (mm). Scales the yield *ceiling*
        (``potential_yield_t_ha``) via
        ``crop_models.spacing_yield_multiplier`` before water/nitrogen
        stress is applied to it - unlike those two, density isn't a
        Liebig's-law limiting factor (it doesn't run out over the season),
        it changes what the field could achieve in the first place. Has no
        effect unless ``crop_model`` (or ``crop_name``'s default) actually
        has a ``reference_spacing_mm``/``spacing_sensitivity`` set - see
        that function's docstring for why there's no built-in default.
    planting_date, harvest_date: str (``YYYY-MM-DD``), optional
        See :func:`_daily_water_balance`'s docstring - anchors the growing-
        degree-day (GDD) clock to a real planting date instead of just the
        first day of ``weather``, and/or forces an early, deliberate end to
        the season (e.g. potato haulm-killing) instead of letting the
        natural ``season_end_gdd`` decline run its course. Omitting both
        (the default) is exactly this function's behaviour from before
        either parameter existed.

    Returns
    -------
    SeasonEstimate
    """
    model = crop_model or crop_models.get_crop_model(crop_name)
    used_default_soil = clay_pct is None
    if used_default_soil:
        clay_pct = _FALLBACK_CLAY_PCT
        organic_matter_pct = _FALLBACK_ORGANIC_MATTER_PCT
    awc = soil_pedotransfer.available_water_capacity(clay_pct, organic_matter_pct or 0.0)
    nitrogen_modeled = fertilizer_kg_n_by_date is not None
    potassium_modeled = fertilizer_kg_k_by_date is not None
    phosphorus_modeled = phosphorus_applied_kg_ha is not None
    magnesium_modeled = magnesium_applied_kg_ha is not None
    heat_modeled = model.ky_heat > 0
    spacing_multiplier = crop_models.spacing_yield_multiplier(model, spacing_mm)
    effective_potential_yield = model.potential_yield_t_ha * spacing_multiplier
    potential_yield_before_spacing = (
        model.potential_yield_t_ha if spacing_multiplier != 1.0 else None)

    total_rain = 0.0
    logged_irrigation_total = 0.0
    actual_et_total = 0.0
    potential_et_total = 0.0
    water_stress_days = 0
    irrigation_need_mm = 0.0
    days_with_weather = 0
    nitrogen_applied_total = 0.0
    nitrogen_demand_total = 0.0
    nitrogen_uptake_total = 0.0
    nitrogen_leached_total = 0.0
    potassium_applied_total = 0.0
    potassium_demand_total = 0.0
    potassium_uptake_total = 0.0
    potassium_leached_total = 0.0
    water_drainage_total = 0.0
    heat_stress_days_total = 0
    stage_actual_et = {stage: 0.0 for stage in _KY_STAGES}
    stage_potential_et = {stage: 0.0 for stage in _KY_STAGES}

    for step in _daily_water_balance(weather, model, awc, irrigation_mm_by_date,
                                     fertilizer_kg_n_by_date, fertilizer_kg_k_by_date,
                                     planting_date=planting_date, harvest_date=harvest_date):
        days_with_weather += 1
        total_rain += step.precip
        logged_irrigation_total += step.logged_irrigation
        potential_et_total += step.potential_et
        actual_et_total += step.actual_et
        if step.growth_stage:
            stage_potential_et[step.growth_stage] += step.potential_et
            stage_actual_et[step.growth_stage] += step.actual_et
        if step.soil_water_mm < step.mad_threshold_mm:
            water_stress_days += 1
        irrigation_need_mm += step.refill_mm
        water_drainage_total += step.drainage_mm
        nitrogen_applied_total += step.n_applied
        nitrogen_demand_total += step.n_demand
        nitrogen_uptake_total += step.n_uptake
        nitrogen_leached_total += step.n_leached
        potassium_applied_total += step.k_applied
        potassium_demand_total += step.k_demand
        potassium_uptake_total += step.k_uptake
        potassium_leached_total += step.k_leached
        if step.heat_stress_day:
            heat_stress_days_total += 1

    if days_with_weather == 0 or potential_et_total <= 0:
        return SeasonEstimate(
            crop_model=model.name, days_with_weather=days_with_weather,
            total_rain_mm=total_rain, logged_irrigation_mm=round(logged_irrigation_total, 1),
            actual_et_mm=0.0, potential_et_mm=0.0,
            water_stress_days=0, irrigation_need_mm=0.0,
            potential_yield_t_ha=effective_potential_yield,
            estimated_yield_t_ha=None, used_default_soil=used_default_soil,
            note='Not enough weather data to estimate yield or irrigation need.',
            spacing_mm=spacing_mm, spacing_yield_multiplier=spacing_multiplier,
            potential_yield_before_spacing_t_ha=potential_yield_before_spacing,
            heat_modeled=heat_modeled, heat_stress_days=heat_stress_days_total,
            heat_stress_day_fraction=0.0,
            nitrogen_leached_kg_ha=round(nitrogen_leached_total, 1),
            potassium_leached_kg_ha=round(potassium_leached_total, 1),
            water_drainage_mm=round(water_drainage_total, 1))

    # Season-total deficit, kept only for the note text below - the actual
    # yield-response calculation is per-stage (see the loop just below),
    # not this one aggregate number, precisely because *when* a deficit
    # happened matters (see crop_models.CropModel's ky_initial docstring).
    et_deficit_fraction = max(0.0, 1.0 - actual_et_total / potential_et_total)

    # FAO-33's Jensen (1968) multi-period model - see
    # _relative_yield_from_stage_et's own docstring; shared with
    # CropSimulation._compute_cell_traces' per-cell yield map so the two
    # can never drift apart on this maths.
    relative_yield_water, water_limiting_stage, stage_deficit_fraction = (
        _relative_yield_from_stage_et(model, stage_actual_et, stage_potential_et))

    relative_yield_nitrogen = 1.0
    n_deficit_fraction = 0.0
    if nitrogen_modeled and nitrogen_demand_total > 0:
        n_deficit_fraction = max(0.0, 1.0 - nitrogen_uptake_total / nitrogen_demand_total)
        relative_yield_nitrogen = max(
            model.min_relative_yield_nitrogen, 1.0 - model.ky_nitrogen * n_deficit_fraction)

    relative_yield_potassium = 1.0
    k_deficit_fraction = 0.0
    if potassium_modeled and potassium_demand_total > 0:
        k_deficit_fraction = max(0.0, 1.0 - potassium_uptake_total / potassium_demand_total)
        relative_yield_potassium = max(
            model.min_relative_yield_potassium, 1.0 - model.ky_potassium * k_deficit_fraction)

    heat_stress_day_fraction = heat_stress_days_total / days_with_weather
    relative_yield_heat = 1.0
    if heat_modeled:
        relative_yield_heat = max(0.0, 1.0 - model.ky_heat * heat_stress_day_fraction)

    # Liebig's law of the minimum: yield is capped by whichever resource
    # was more limiting, not their product/average - see module docstring.
    # Planting density scales the ceiling itself beforehand (see this
    # function's spacing_mm docstring) rather than acting as a limiting
    # factor here.
    relative_yield = min(relative_yield_water, relative_yield_nitrogen,
                         relative_yield_heat, relative_yield_potassium)
    estimated_yield = round(relative_yield * effective_potential_yield, 1)
    estimated_yield_water_only = round(relative_yield_water * effective_potential_yield, 1)

    if not heat_modeled and not potassium_modeled:
        # Unchanged from before heat/potassium existed - every existing
        # caller keeps getting exactly the same limiting_factor values
        # (including the literal 'both' tie string) it always has.
        if not nitrogen_modeled:
            limiting_factor = 'none'
        elif relative_yield_water < relative_yield_nitrogen:
            limiting_factor = 'water'
        elif relative_yield_nitrogen < relative_yield_water:
            limiting_factor = 'nitrogen'
        else:
            limiting_factor = 'both'
    else:
        candidates = [('water', relative_yield_water)]
        if heat_modeled:
            candidates.append(('heat', relative_yield_heat))
        if nitrogen_modeled:
            candidates.append(('nitrogen', relative_yield_nitrogen))
        if potassium_modeled:
            candidates.append(('potassium', relative_yield_potassium))
        min_value = min(value for _, value in candidates)
        tied = [name for name, value in candidates if value == min_value]
        limiting_factor = tied[0] if len(tied) == 1 else '+'.join(tied)

    phosphorus_status = 'none'
    if phosphorus_modeled:
        phosphorus_status = _supply_status(
            phosphorus_applied_kg_ha, model.season_p_demand_kg_ha)
    magnesium_status = 'none'
    if magnesium_modeled:
        magnesium_status = _supply_status(
            magnesium_applied_kg_ha, model.season_mg_demand_kg_ha)

    basis = ('Rainfed estimate (no irrigation logged)' if logged_irrigation_total <= 0
            else 'Estimate including {:.0f} mm of logged irrigation'.format(
                logged_irrigation_total))
    note = (
        '{basis}: {defpct:.0f}% cumulative evapotranspiration deficit vs. '
        'potential for {crop}, applied per growth stage (FAO-33\'s '
        'yield-response factor, Ky) and combined across stages the way '
        'FAO-33\'s multi-period model does.'
    ).format(basis=basis, defpct=et_deficit_fraction * 100, crop=model.name)
    if water_limiting_stage != 'none':
        note += (
            ' The {stage} stage saw the largest water deficit ({defpct:.0f}%) '
            'and drove most of the water-side yield loss.'
        ).format(stage=water_limiting_stage.replace('_', ' '),
                defpct=stage_deficit_fraction[water_limiting_stage] * 100)
    if water_drainage_total > 1.0:
        note += (
            ' An estimated {drainage:.0f} mm of rain/irrigation drained below the '
            'root zone rather than being used - this happens when a dose lands on '
            'soil that\'s already near capacity, so spreading applications out '
            'instead of dosing heavily at once makes better use of the same total.'
        ).format(drainage=water_drainage_total)
    if nitrogen_modeled:
        note += (
            ' Nitrogen: {applied:.0f} kg N/ha applied vs. {demand:.0f} kg N/ha '
            'season demand ({defpct:.0f}% deficit, Ky-N={ky:.2f})'
        ).format(applied=nitrogen_applied_total, demand=nitrogen_demand_total,
                defpct=n_deficit_fraction * 100, ky=model.ky_nitrogen)
        if nitrogen_leached_total > 0.1:
            leached_pct = (100.0 * nitrogen_leached_total / nitrogen_applied_total
                          if nitrogen_applied_total > 0 else 0.0)
            note += (
                ', of which an estimated {leached:.0f} kg N/ha ({pct:.0f}%) '
                'leached below the root zone before the crop could take it up - '
                'nitrogen still sitting unused when a drainage event hits is '
                'what\'s at risk, so splitting doses to better match crop demand '
                '(or timing them away from heavy rain) reduces this'
            ).format(leached=nitrogen_leached_total, pct=leached_pct)
        note += '.'
    if potassium_modeled:
        note += (
            ' Potassium: {applied:.0f} kg K/ha applied vs. {demand:.0f} kg K/ha '
            'season demand ({defpct:.0f}% deficit, Ky-K={ky:.2f})'
        ).format(applied=potassium_applied_total, demand=potassium_demand_total,
                defpct=k_deficit_fraction * 100, ky=model.ky_potassium)
        if potassium_leached_total > 0.1:
            k_leached_pct = (100.0 * potassium_leached_total / potassium_applied_total
                            if potassium_applied_total > 0 else 0.0)
            note += (
                ', of which an estimated {leached:.0f} kg K/ha ({pct:.0f}%) '
                'leached below the root zone before the crop could take it up'
            ).format(leached=potassium_leached_total, pct=k_leached_pct)
        note += '.'
    if phosphorus_modeled:
        note += (
            ' Phosphorus: {applied:.0f} kg P/ha applied vs. {demand:.0f} kg P/ha '
            'season demand - {status} (season total only, no leaching '
            'tracked - see "Sources" for why).'
        ).format(applied=phosphorus_applied_kg_ha, demand=model.season_p_demand_kg_ha,
                status=phosphorus_status)
    if magnesium_modeled:
        note += (
            ' Magnesium: {applied:.0f} kg Mg/ha applied vs. {demand:.0f} kg Mg/ha '
            'season demand - {status} (season total only, same as phosphorus).'
        ).format(applied=magnesium_applied_kg_ha, demand=model.season_mg_demand_kg_ha,
                status=magnesium_status)
    if limiting_factor != 'none':
        note += (
            ' {limiting} was the more limiting factor this run (Liebig\'s law '
            'of the minimum).'
        ).format(limiting=limiting_factor.capitalize())
    if heat_modeled:
        note += (
            ' Heat: {days} of {total} day(s) exceeded {threshold:.0f}°C '
            '({pct:.0f}% of the period, Ky-heat={ky:.2f}).'
        ).format(days=heat_stress_days_total, total=days_with_weather,
                threshold=model.heat_stress_threshold_c,
                pct=heat_stress_day_fraction * 100, ky=model.ky_heat)
    if potential_yield_before_spacing is not None:
        note += (
            ' Planting spacing: {spacing:.0f} mm vs. a {reference:.0f} mm '
            'reference for {crop} scaled the achievable ceiling from '
            '{before:.1f} to {after:.1f} t/ha.'
        ).format(spacing=spacing_mm, reference=model.reference_spacing_mm,
                crop=model.name, before=potential_yield_before_spacing,
                after=effective_potential_yield)
    if used_default_soil:
        note += (' Used a generic loam-like soil texture (no soil sample on '
                 'file for this field), so treat this as a rougher estimate.')
    if planting_date:
        note += (
            ' Water/nitrogen/potassium timing anchored to a logged planting '
            'date of {planted} rather than the start of the analysed period.'
        ).format(planted=planting_date)
    if harvest_date:
        note += (
            ' Growth was treated as stopped from {harvest} onward (per the '
            'run\'s override) rather than following the crop\'s natural '
            'end-of-season decline.'
        ).format(harvest=harvest_date)

    return SeasonEstimate(
        crop_model=model.name, days_with_weather=days_with_weather,
        total_rain_mm=round(total_rain, 1),
        logged_irrigation_mm=round(logged_irrigation_total, 1),
        actual_et_mm=round(actual_et_total, 1),
        potential_et_mm=round(potential_et_total, 1),
        water_stress_days=water_stress_days,
        irrigation_need_mm=round(irrigation_need_mm, 1),
        potential_yield_t_ha=effective_potential_yield,
        estimated_yield_t_ha=estimated_yield,
        used_default_soil=used_default_soil, note=note,
        nitrogen_modeled=nitrogen_modeled,
        nitrogen_applied_kg_ha=round(nitrogen_applied_total, 1),
        nitrogen_demand_kg_ha=round(nitrogen_demand_total, 1),
        nitrogen_uptake_kg_ha=round(nitrogen_uptake_total, 1),
        nitrogen_leached_kg_ha=round(nitrogen_leached_total, 1),
        water_drainage_mm=round(water_drainage_total, 1),
        limiting_factor=limiting_factor,
        estimated_yield_water_only_t_ha=estimated_yield_water_only,
        spacing_mm=spacing_mm, spacing_yield_multiplier=spacing_multiplier,
        potential_yield_before_spacing_t_ha=potential_yield_before_spacing,
        heat_modeled=heat_modeled, heat_stress_days=heat_stress_days_total,
        heat_stress_day_fraction=round(heat_stress_day_fraction, 3),
        water_limiting_stage=water_limiting_stage,
        potassium_modeled=potassium_modeled,
        potassium_applied_kg_ha=round(potassium_applied_total, 1),
        potassium_demand_kg_ha=round(potassium_demand_total, 1),
        potassium_uptake_kg_ha=round(potassium_uptake_total, 1),
        potassium_leached_kg_ha=round(potassium_leached_total, 1),
        phosphorus_modeled=phosphorus_modeled,
        phosphorus_applied_kg_ha=round(phosphorus_applied_kg_ha, 1) if phosphorus_modeled else 0.0,
        phosphorus_demand_kg_ha=round(model.season_p_demand_kg_ha, 1),
        phosphorus_status=phosphorus_status,
        magnesium_modeled=magnesium_modeled,
        magnesium_applied_kg_ha=round(magnesium_applied_kg_ha, 1) if magnesium_modeled else 0.0,
        magnesium_demand_kg_ha=round(model.season_mg_demand_kg_ha, 1),
        magnesium_status=magnesium_status,
        relative_yield_water=relative_yield_water,
        relative_yield_nitrogen=relative_yield_nitrogen,
        relative_yield_potassium=relative_yield_potassium,
        relative_yield_heat=relative_yield_heat)
