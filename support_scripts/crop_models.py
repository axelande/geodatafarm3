"""Per-crop parameters for the fertilizer-timing analysis.

These are literature-informed defaults, not site-calibrated values - treat
them as reasonable planning assumptions, not lab-measured constants. Where
the advanced water/nitrogen balance model (see ``fertilizer_timing_model.py``)
needs a curve (root depth, crop coefficient, nitrogen uptake), it is
approximated with a simple analytic shape (linear ramp, 3-stage FAO-56 style
Kc, logistic uptake) driven by accumulated growing degree days (GDD) since
the event date, rather than a full crop-physiology simulation. This is what
lets the water/nitrogen balance respond to *when* in the season something
happens (e.g. a fertilizer application ahead of heavy rain vs. one timed
around it - see season_water_model.py's module docstring) instead of only
to seasonal totals.

Cereal crops (wheat/barley/rye/oats) share a common archetype since GeoDataFarm
does not (yet) have per-cultivar data to distinguish them meaningfully; potato
gets its own tuned parameters since it is the crop the plugin has actually
been validated against.

Sources for the numbers below (see also the comment above CROP_MODELS and
each field's docstring for which specific fields each source backs):

* Allen, R.G., Pereira, L.S., Raes, D. & Smith, M. (1998). *Crop
  evapotranspiration - Guidelines for computing crop water requirements*,
  FAO Irrigation and Drainage Paper 56. https://www.fao.org/4/x0490e/x0490e00.htm
  - Table 12 (Kc ini/mid/end) and Table 11 (typical stage lengths in days,
  by crop and climate region) - the source for kc_ini/kc_mid/kc_end and the
  proportions used to split season_end_gdd into kc_ini_end_gdd/
  kc_mid_end_gdd, for both potato and the shared cereal archetype.
* Base temperature (gdd_base_c) for potato: commonly reported in the 2-5C
  range across cultivars/studies, with ~4.4C (40F) the most widely used
  practical convention in North American extension GDD calculators, e.g.
  https://www.potatogrower.com/2023/06/calculating-growing-degree-days -
  and potato commonly cited as needing on the order of 1000-1100 GDD (at
  that base) to reach harvest readiness, which is what season_end_gdd
  reflects here.
* Base temperature for wheat/barley/oats: 0C is the standard, widely-used
  convention for small-grain cereal GDD, e.g. NDSU NDAWN's wheat/barley GDD
  guidance: https://ndawn.ndsu.nodak.edu/help-wheat-growing-degree-days.html
  and https://ndawn.ndsu.nodak.edu/help-barley-growing-degree-days.html
* The general S-shaped/logistic pattern of season-long nitrogen uptake
  (slow at emergence, fastest during vegetative growth, plateauing near
  maturity - what n_uptake_fraction approximates) is well documented for
  both potato and cereals, e.g. UC Davis/CDFA-FREP's nitrogen uptake and
  partitioning guidelines:
  https://www.cdfa.ca.gov/is/ffldrs/frep/FertilizationGuidelines/N_Potato.html
  and https://www.cdfa.ca.gov/is/ffldrs/frep/FertilizationGuidelines/N_Wheat.html
  - these ground the *shape* of n_uptake_fraction's curve; its exact
  midpoint/steepness numbers below are a reasonable placement consistent
  with that shape, not read off a specific paper's table (see
  n_uptake_midpoint_gdd/n_uptake_steepness's field docs), and root
  development timing (root_depth_full_gdd) is similarly shape-consistent
  but not pinned to one specific source.
* A paper doing exactly this FAO56-to-GDD conversion exists - Paredes et al.
  (2025), "Estimating the lengths of crop growth stages to define the crop
  coefficient curves using growing degree days (GDD): Application of the
  revised FAO56 guidelines" - but its full tables weren't accessible while
  writing this, so its specific numbers aren't reflected here; worth
  revisiting if it becomes accessible.
"""
import math
from dataclasses import dataclass

__author__ = 'Axel Horteborn'


@dataclass(frozen=True)
class CropModel:
    """Parameters for one crop, used by both tiers of the timing analysis.

    Parameters
    ----------
    name: str
    gdd_base_c: float
        Base temperature for growing-degree-day accumulation. Potato: 4.4C,
        the widely-used North American extension convention (reported range
        across studies is 2-5C - see module docstring). Cereals: 0C, the
        standard convention for wheat/barley/oats GDD (also module docstring).
    root_depth_min_cm, root_depth_max_cm: float
        Rooting depth at emergence and at full development.
    root_depth_full_gdd: float
        Cumulative GDD at which rooting depth reaches its maximum - shape-
        consistent with general root-development timing, not pinned to a
        specific source (see module docstring).
    season_n_demand_kg_ha: float
        Typical total-season nitrogen uptake demand, used to scale the
        uptake curve (advanced tier only).
    n_uptake_midpoint_gdd, n_uptake_steepness: float
        Logistic-curve parameters for the fraction of season N demand taken
        up by cumulative GDD - the S-shaped *pattern* this approximates
        (slow at emergence, fastest during vegetative growth, plateauing
        near maturity) is well documented (see module docstring); these two
        specific numbers place/shape that curve consistently with it, not
        read off one paper's table.
    season_k_demand_kg_ha, k_uptake_midpoint_gdd, k_uptake_steepness: float
        The same three ideas as their ``n_`` counterparts, for potassium
        instead - potassium is the other nutrient this plugin gives a full
        day-by-day uptake/leaching balance (see
        support_scripts.season_water_model), since - unlike phosphorus and
        magnesium - it's mobile enough in most soils (held on cation
        exchange sites, but genuinely leachable on sandy/low-CEC ground) for
        *when* it's applied to matter, not just how much (see module
        docstring for sourcing). ``k_uptake_midpoint_gdd`` is later than
        ``n_uptake_midpoint_gdd`` for potato specifically - tuber bulking
        keeps drawing potassium well after nitrogen uptake has peaked.
    season_p_demand_kg_ha, season_mg_demand_kg_ha: float
        Typical total-season phosphorus/magnesium uptake demand - unlike
        nitrogen/potassium, these two get only a season-total supply-vs-
        demand comparison (see season_water_model.py), not a day-by-day
        balance: phosphorus binds tightly to soil particles (moves via
        surface runoff/erosion, not leaching, which this plugin doesn't
        model at all) and magnesium, like potassium, is held on cation
        exchange sites but without potassium's comparable leaching
        literature to justify the same daily mechanic - see module
        docstring.
    kc_ini, kc_mid, kc_end: float
        FAO-56 style crop coefficients for the initial, mid-season and late
        stages.
    kc_ini_end_gdd, kc_mid_end_gdd, kc_late_start_gdd, season_end_gdd: float
        Cumulative GDD marking the boundaries between FAO-56's four growth
        stages: initial ends / development starts at kc_ini_end_gdd,
        development ends / mid-season starts at kc_mid_end_gdd (Kc reaches
        kc_mid here and holds it flat - a genuine plateau, not a single
        instant - until kc_late_start_gdd, where the late-season decline to
        kc_end begins), which ends at season_end_gdd. season_end_gdd is
        potato's commonly-cited ~1000-1100 GDD to harvest readiness (0C for
        cereals - see module docstring); the other three thresholds split
        that total using FAO-56 Table 11's stage-length *proportions*
        (potato: the "Europe" region row; cereals: the "35-45 degrees
        latitude" row) - the day-based lengths in that table don't convert
        to a single universal GDD figure (regional/climate dependent), so
        the proportions are applied to the GDD total above rather than
        FAO-56's day-based lengths being used directly.
    leaching_sensitivity: float
        Multiplier on rainfall used by the *simple* fallback risk index only
        (shallow-rooted/high-value crops such as potato are more sensitive
        to a given amount of rain than deep-rooted cereals).
    ky_initial, ky_development, ky_mid_season, ky_late_season: float
        FAO Irrigation & Drainage Paper 33 yield-response factors, one per
        growth stage (see ``kc_ini_end_gdd`` etc. above for the stage
        boundaries these share) rather than a single seasonal figure -
        water stress during flowering/tuber initiation (mid_season) costs
        far more yield than the same relative deficit during establishment
        or ripening, which one flat seasonal Ky can't represent (FAO-33
        tabulates both a seasonal *and* per-stage Ky for this reason,
        though FAO-56 notes the seasonal figure alone is what's commonly
        used in practice). ``support_scripts.season_water_model`` combines
        the four stages' relative-yield fractions multiplicatively (the
        Jensen (1968) multi-period model FAO-33 itself uses for combining
        several periods' deficits), not via Liebig's law of the minimum -
        that's reserved for combining the independent water/nitrogen/heat
        factors against each other, a separate question. These four values
        are calibrated so a uniform deficit spread evenly across the whole
        season reproduces roughly what a literature seasonal Ky (see
        CROP_MODELS' comment) would predict, while directing most of the
        sensitivity into mid_season and little into initial/late_season,
        consistent with FAO's own irrigation-scheduling guidance (avoid
        deficit at stolonization/tuber initiation and yield formation;
        deficit is tolerable during early vegetative growth and ripening)
        and potato drought-physiology studies - see module docstring. Like
        n_uptake_midpoint_gdd/n_uptake_steepness, the exact per-stage split
        is shape-consistent with that literature, not read off a verified
        FAO-33 per-stage table (which wasn't accessible - see module
        docstring), so treat the *relative* pattern (mid_season much more
        sensitive) as the well-grounded part and the precise numbers as a
        reasonable planning estimate.
    ky_nitrogen: float
        The same yield-response-factor idea, applied to relative nitrogen
        uptake deficit instead of water, as a single seasonal figure (not
        split by stage the way the water Ky values are) - relative yield
        loss = ``ky_nitrogen`` x (1 - actual season N uptake / season N
        demand). Unlike ``ky_initial``/etc., this isn't from a single
        standardised FAO table - it's a planning-grade estimate in the
        same spirit, meant to be adjusted per crop/site via the Crop
        simulation settings dialog rather than trusted as-is.
    min_relative_yield_nitrogen: float
        A floor on the nitrogen factor above - see
        ``season_water_model.py``'s ``relative_yield_nitrogen`` - so that a
        100% logged nitrogen deficit (nothing applied, or nothing on
        record) doesn't zero out the whole season estimate the way
        ``ky_nitrogen`` alone would (1.1 x 100% deficit > 1.0). A real
        zero-N control plot still yields something from soil-supplied
        nitrogen (mineralisation, residual N from the previous crop) -
        field trials commonly put that around 30-60% of a fertilized
        crop's yield. 0.3 (the default for every crop) is a conservative
        pick within that range, in the same planning-grade spirit as
        ``ky_nitrogen`` itself - adjust it per crop/site via the Crop
        simulation settings dialog rather than trusting it as-is.
    ky_potassium: float
        The same idea as ``ky_nitrogen``, applied to relative potassium
        uptake deficit - see ``season_k_demand_kg_ha`` above for why
        potassium (and not phosphorus/magnesium) gets this treatment. Same
        caveat as ``ky_nitrogen``: a planning-grade estimate, not a single
        table figure.
    min_relative_yield_potassium: float
        The same floor as ``min_relative_yield_nitrogen``, for potassium -
        see that field's docstring. Without it, a field that has simply
        never logged any potassium (every crop here ships with
        ``ky_potassium`` at or near 1.0) hits a 100% logged deficit and
        ``relative_yield_potassium`` clips to exactly 0.0, capping the
        whole season estimate at zero via Liebig's law regardless of
        water or nitrogen - not a real zero-potassium-supply outcome, just
        the absence of a floor. 0.3 (the same default and reasoning as
        ``min_relative_yield_nitrogen``) is a conservative planning-grade
        pick, adjustable per crop/site via the Crop simulation settings
        dialog.
    potential_yield_t_ha: float
        A literature "no water/nutrient stress" baseline yield (tonnes/ha).
        The water and nitrogen relative-yield fractions above are combined
        via Liebig's law of the minimum (whichever is more limiting caps
        the yield, they aren't multiplied/averaged) and applied to this
        baseline - see season_water_model.py's module docstring. (Water's
        own relative-yield fraction is itself already a multiplicative
        combination of its four growth stages before it ever reaches this
        step - see ``ky_initial`` above; that's a separate combination
        question from this one.)
    reference_spacing_mm: float
        The in-row planting spacing (mm) at which ``potential_yield_t_ha``
        is actually achieved - unlike every other field here, this has no
        sensible universal literature default (it varies by end-use, e.g.
        seed vs. ware potatoes, far more than by crop), so it defaults to
        0.0, meaning "not modelled": :func:`spacing_yield_multiplier`
        always returns 1.0 until a real farm sets this via the Crop
        simulation settings dialog.
    spacing_sensitivity: float
        How sharply the yield ceiling falls off as actual spacing departs
        from ``reference_spacing_mm`` - see :func:`spacing_yield_multiplier`.
        0.0 (the default) also disables the effect.
    heat_stress_threshold_c: float
        A day's mean temperature above which it counts as a heat-stress
        day (see ``season_water_model.py``'s day-by-day balance) - a
        simplification of what's usually a day/night-temperature and
        growth-stage-dependent effect (e.g. potato tuber set), so treat
        the threshold as indicative rather than precise.
    ky_heat: float
        The same yield-response-factor idea as ``ky_nitrogen`` (a single
        seasonal figure, not split by stage), applied to the *fraction* of
        the season's days that were heat-stress days. Unlike those two, this defaults to
        0.0 (disabled) for every crop rather than a non-zero planning
        estimate - of the three stress factors this is the least
        literature-standardised (a single mean-temperature threshold is a
        real simplification), so it only takes effect once a user
        explicitly sets it above 0 via the Crop simulation settings
        dialog, the same opt-in shape as ``spacing_sensitivity``.
    """
    name: str
    gdd_base_c: float
    root_depth_min_cm: float
    root_depth_max_cm: float
    root_depth_full_gdd: float
    season_n_demand_kg_ha: float
    n_uptake_midpoint_gdd: float
    n_uptake_steepness: float
    season_k_demand_kg_ha: float
    k_uptake_midpoint_gdd: float
    k_uptake_steepness: float
    season_p_demand_kg_ha: float
    season_mg_demand_kg_ha: float
    kc_ini: float
    kc_mid: float
    kc_end: float
    kc_ini_end_gdd: float
    kc_mid_end_gdd: float
    kc_late_start_gdd: float
    season_end_gdd: float
    leaching_sensitivity: float
    ky_initial: float
    ky_development: float
    ky_mid_season: float
    ky_late_season: float
    ky_nitrogen: float
    ky_potassium: float
    potential_yield_t_ha: float
    reference_spacing_mm: float = 0.0
    spacing_sensitivity: float = 0.0
    heat_stress_threshold_c: float = 30.0
    ky_heat: float = 0.0
    min_relative_yield_nitrogen: float = 0.3
    min_relative_yield_potassium: float = 0.3


def growing_degree_days(t_mean_c, base_c):
    """One day's contribution to accumulated GDD (never negative)."""
    return max(0.0, t_mean_c - base_c)


def root_depth_cm(model, cumulative_gdd):
    """Rooting depth (cm) at ``cumulative_gdd``, ramping linearly from
    ``root_depth_min_cm`` to ``root_depth_max_cm`` by ``root_depth_full_gdd``."""
    if cumulative_gdd <= 0:
        return model.root_depth_min_cm
    if cumulative_gdd >= model.root_depth_full_gdd:
        return model.root_depth_max_cm
    frac = cumulative_gdd / model.root_depth_full_gdd
    return model.root_depth_min_cm + frac * (
        model.root_depth_max_cm - model.root_depth_min_cm)


def n_uptake_fraction(model, cumulative_gdd):
    """Fraction (0..1) of the crop's total-season N demand taken up by
    ``cumulative_gdd``, as a logistic curve centred on ``n_uptake_midpoint_gdd``."""
    x = model.n_uptake_steepness * (cumulative_gdd - model.n_uptake_midpoint_gdd)
    x = max(-60.0, min(60.0, x))  # avoid float overflow in exp()
    return 1.0 / (1.0 + math.exp(-x))


def k_uptake_fraction(model, cumulative_gdd):
    """The same idea as :func:`n_uptake_fraction`, for potassium - a
    logistic curve centred on ``k_uptake_midpoint_gdd`` instead (later
    than nitrogen's for potato - see :class:`CropModel`'s docstring)."""
    x = model.k_uptake_steepness * (cumulative_gdd - model.k_uptake_midpoint_gdd)
    x = max(-60.0, min(60.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def validate_shape(model):
    """Raises ValueError if ``model``'s curve-shape parameters (root depth,
    Kc stage thresholds, nitrogen-uptake steepness) don't actually describe
    a sensible curve - used before a user's edited values (see
    support_scripts/crop_model_settings.py's ``save_overrides``) get
    persisted, so a typo can't silently produce a broken curve, e.g.
    :func:`crop_coefficient` treating an out-of-order stage boundary as
    "already at the next stage" for the entire season.

    Raises
    ------
    ValueError
        With every problem found, not just the first.
    """
    problems = []
    if model.root_depth_min_cm > model.root_depth_max_cm:
        problems.append(
            'Root depth at emergence must not be more than root depth at '
            'full development.')
    if model.root_depth_full_gdd <= 0:
        problems.append('"Root depth reaches maximum at" must be a positive GDD value.')
    if not (0 < model.kc_ini_end_gdd < model.kc_mid_end_gdd
           < model.kc_late_start_gdd < model.season_end_gdd):
        problems.append(
            'Growth-stage GDD thresholds must increase in this order: '
            'initial-stage end < development end < mid-season end < '
            'season end (all positive).')
    if model.n_uptake_steepness <= 0:
        problems.append('Nitrogen uptake steepness must be positive.')
    if model.k_uptake_steepness <= 0:
        problems.append('Potassium uptake steepness must be positive.')
    if model.kc_ini <= 0 or model.kc_mid <= 0 or model.kc_end <= 0:
        problems.append('Kc (water demand) values must be positive.')
    if problems:
        raise ValueError(' '.join(problems))


def spacing_yield_multiplier(model, spacing_mm):
    """How much ``model``'s yield ceiling (``potential_yield_t_ha``)
    should be scaled for an actual in-row planting spacing of
    ``spacing_mm``, as a smooth, symmetric falloff around
    ``model.reference_spacing_mm`` - both too close (more competing
    plants than the ceiling assumes) and too wide (fewer plants than the
    ceiling assumes) reduce it:

        multiplier = max(0, 1 - sensitivity * ((spacing - reference) / reference)^2)

    Returns 1.0 (no effect) whenever ``spacing_mm`` is falsy, or the
    model has no ``reference_spacing_mm``/``spacing_sensitivity`` set
    (the default for every crop - see :class:`CropModel`'s docstring for
    why there's no universal literature default here)."""
    if not spacing_mm or model.reference_spacing_mm <= 0 or model.spacing_sensitivity <= 0:
        return 1.0
    relative_deviation = (spacing_mm - model.reference_spacing_mm) / model.reference_spacing_mm
    return max(0.0, 1.0 - model.spacing_sensitivity * relative_deviation ** 2)


def crop_coefficient(model, cumulative_gdd):
    """FAO-56 style 4-stage crop coefficient (Kc) as a function of
    accumulated GDD: flat at kc_ini through the initial stage, a linear
    ramp to kc_mid through development, a genuine flat plateau at kc_mid
    through mid-season (not just a single instantaneous peak - see
    :class:`CropModel`'s docstring), then a linear ramp down to kc_end
    through the late season."""
    if cumulative_gdd <= model.kc_ini_end_gdd:
        return model.kc_ini
    if cumulative_gdd <= model.kc_mid_end_gdd:
        span = max(1e-6, model.kc_mid_end_gdd - model.kc_ini_end_gdd)
        frac = (cumulative_gdd - model.kc_ini_end_gdd) / span
        return model.kc_ini + frac * (model.kc_mid - model.kc_ini)
    if cumulative_gdd <= model.kc_late_start_gdd:
        return model.kc_mid
    if cumulative_gdd >= model.season_end_gdd:
        return model.kc_end
    span = max(1e-6, model.season_end_gdd - model.kc_late_start_gdd)
    frac = (cumulative_gdd - model.kc_late_start_gdd) / span
    return model.kc_mid + frac * (model.kc_end - model.kc_mid)


def crop_growth_stage(model, cumulative_gdd):
    """Which of the FAO-56 four growth stages ``cumulative_gdd`` falls in
    - ``'initial'``, ``'development'``, ``'mid_season'`` or
    ``'late_season'`` - using the exact same thresholds
    :func:`crop_coefficient` ramps/plateaus against, so a caller
    classifying days by stage (e.g. season_water_model.py's per-stage
    yield-response weighting) always agrees with what the Kc curve itself
    is doing that day."""
    if cumulative_gdd <= model.kc_ini_end_gdd:
        return 'initial'
    if cumulative_gdd <= model.kc_mid_end_gdd:
        return 'development'
    if cumulative_gdd <= model.kc_late_start_gdd:
        return 'mid_season'
    return 'late_season'


def harvestable_yield_progress(model, cumulative_gdd):
    """Fraction of the final harvestable yield formed by ``cumulative_gdd``.

    Water stress can affect the crop before harvestable yield exists, but a
    yield map should not report early vegetative growth as harvested tonnes.
    Potato yield formation is therefore delayed until tuber bulking, while
    cereals are delayed until late grain filling. The smooth ramp after each
    onset keeps the projection non-linear without claiming a sharp biological
    switch on one particular day.
    """
    if model.name == 'potato':
        onset_fraction = 0.65
    elif model.name in ('wheat', 'barley', 'rye', 'oats'):
        onset_fraction = 0.82
    else:
        onset_fraction = 0.75
    onset_gdd = model.season_end_gdd * onset_fraction
    if cumulative_gdd <= onset_gdd:
        return 0.0
    formation_fraction = min(
        1.0, (cumulative_gdd - onset_gdd) / (model.season_end_gdd - onset_gdd))
    return formation_fraction ** 2 * (3.0 - 2.0 * formation_fraction)


# Relative per-stage water-Ky weights (initial, development, mid_season,
# late_season) a crop's seasonal Ky figure (the FAO-33-sourced number each
# crop is still defined by below) is split into - calibrated so a uniform
# deficit spread evenly across the whole season reproduces roughly what
# that flat seasonal figure would have predicted for a representative
# ~15% season-average deficit, while directing most of the sensitivity
# into mid_season and little into initial/late_season, consistent with
# FAO's potato irrigation-scheduling guidance and drought-physiology
# literature - see CropModel's ky_initial docstring for the full
# reasoning and its caveats. Shared across every crop in this module
# rather than re-derived per crop, since none of them differ enough in
# stage-length proportions to meaningfully change the calibration.
_KY_STAGE_RATIOS = (0.105, 0.245, 0.6, 0.105)


def _stage_ky(ky_seasonal):
    initial, development, mid_season, late_season = _KY_STAGE_RATIOS
    return dict(
        ky_initial=round(ky_seasonal * initial, 2),
        ky_development=round(ky_seasonal * development, 2),
        ky_mid_season=round(ky_seasonal * mid_season, 2),
        ky_late_season=round(ky_seasonal * late_season, 2))


def _cereal(name, gdd_base_c, season_end_gdd, leaching_sensitivity, ky_seasonal,
           potential_yield_t_ha, ky_nitrogen=1.1, ky_potassium=1.0,
           heat_stress_threshold_c=30.0):
    """Shared archetype for wheat/barley/rye/oats, scaled by season length."""
    return CropModel(
        name=name, gdd_base_c=gdd_base_c,
        root_depth_min_cm=15.0, root_depth_max_cm=110.0,
        # round(..., 0): every GDD-threshold spin box in the settings
        # dialog is whole-number-only (setDecimals(0) - see
        # widgets/crop_settings_dialog.py), so anything less exact than a
        # whole number here - be it 935.0000000000001's ordinary float
        # noise or a genuinely fractional result like 1246.61 - would
        # silently fail an exact equality check against the spin box's
        # own rounded-off value once it round-trips through one.
        root_depth_full_gdd=round(season_end_gdd * 0.55, 0),
        season_n_demand_kg_ha=150.0,
        n_uptake_midpoint_gdd=round(season_end_gdd * 0.42, 0),
        n_uptake_steepness=6.5 / season_end_gdd,
        # Potassium uptake in cereals tracks nitrogen's timing fairly
        # closely (both driven by vegetative growth/stem extension, unlike
        # potato's tuber-bulking-driven K uptake - see CropModel's
        # docstring), so this shares N's curve shape rather than having an
        # independently-derived one - see module docstring's sourcing note.
        season_k_demand_kg_ha=125.0,
        k_uptake_midpoint_gdd=round(season_end_gdd * 0.42, 0),
        k_uptake_steepness=6.5 / season_end_gdd,
        season_p_demand_kg_ha=40.0,
        season_mg_demand_kg_ha=12.0,
        kc_ini=0.4, kc_mid=1.15, kc_end=0.35,
        # FAO-56 Table 11's "35-45 degrees latitude" wheat/barley/oats row:
        # initial 15d, development 30d, mid-season 65d, late 40d (150d
        # total) -> initial stage ends at 15/150=10% of season, development
        # ends (mid-season starts) at (15+30)/150=30%, mid-season ends
        # (late season starts) at (15+30+65)/150=73% - see module docstring.
        kc_ini_end_gdd=round(season_end_gdd * 0.10, 0),
        kc_mid_end_gdd=round(season_end_gdd * 0.30, 0),
        kc_late_start_gdd=round(season_end_gdd * 0.7333, 0),
        season_end_gdd=season_end_gdd,
        leaching_sensitivity=leaching_sensitivity,
        ky_nitrogen=ky_nitrogen,
        ky_potassium=ky_potassium,
        potential_yield_t_ha=potential_yield_t_ha,
        heat_stress_threshold_c=heat_stress_threshold_c,
        **_stage_ky(ky_seasonal),
    )


# ky_seasonal passed into _cereal()/_stage_ky(): FAO Irrigation & Drainage
# Paper 33's Table 24 (potato 1.1 - exact table match; wheat 1.15 for
# spring wheat specifically, FAO tabulates winter wheat separately at 1.05
# - see module docstring for why this module shares one cereal archetype
# regardless). Barley/rye/oats aren't in that ~23-crop table at all, so
# their figures are estimates within the "cereal total-growing-period
# values cluster 1.0-1.2" range FAO/IAEA-compiled studies report, not
# table citations like potato/wheat's - a real, honest gap, not just a
# caveat. Each is then split into four stage-specific ky_initial/
# ky_development/ky_mid_season/ky_late_season figures by _stage_ky() -
# see CropModel's ky_initial docstring for why and how.
# potential_yield_t_ha: a "well-managed, not water/nutrient stressed"
# baseline - potato from commercial attainable-yield ranges (40-70 t/ha,
# UK routinely >50 t/ha); cereals set a few t/ha above Swedish national
# *average* record-year figures (SCB: winter wheat ~7.6 t/ha, spring barley
# ~5.7 t/ha in 2025), since this baseline represents a good field, not a
# national average across all conditions. heat_stress_threshold_c: potato
# lower (27C) than the cereals (30C) since high temperatures are commonly
# flagged as reducing tuber set/bulking earlier than cereal grain-fill heat
# stress thresholds - see CropModel's docstring for why every crop still
# ships with ky_heat=0.0 (disabled) regardless. kc_ini/kc_mid/kc_end are
# FAO-56 Table 12's values directly (potato exactly; cereals kc_mid exactly,
# kc_ini/kc_end a compromise across FAO-56's separate spring/winter-cereal
# rows, since this module deliberately shares one archetype across wheat/
# barley/rye/oats - see module docstring). season_k/p/mg_demand_kg_ha: PDA
# (Potash Development Association) and FAO offtake/removal figures,
# converted from the oxide forms those are conventionally published in to
# elemental kg/ha (K2O -> K x0.83, P2O5 -> P x0.436, MgO -> Mg x0.603) -
# reported ranges are wide (e.g. potato K2O recommendations span 60-300
# kg/ha depending on soil/yield level across sources), so these are
# reasonable mid-range planning figures, not a single precise table
# citation the way potato/wheat's ky_seasonal are - see
# https://www.pda.org.uk/potassium-uptake-requirements-of-some-crops/ and
# https://www.pda.org.uk/nutrient-considerations-for-potatoes/. Magnesium
# especially: PDA itself notes MgO offtake figures are "based on very
# limited data, for guidance only" - treat season_mg_demand_kg_ha as the
# roughest of the nutrient figures here. Same caveat as the rest of this
# module: literature-informed, not site-calibrated.
CROP_MODELS = {
    'potato': CropModel(
        name='potato', gdd_base_c=4.4,
        root_depth_min_cm=10.0, root_depth_max_cm=45.0, root_depth_full_gdd=700.0,
        season_n_demand_kg_ha=180.0,
        n_uptake_midpoint_gdd=500.0, n_uptake_steepness=0.012,
        # Potassium uptake continues later into the season than nitrogen's
        # for potato specifically - tuber bulking keeps drawing K well
        # after N uptake has peaked (see CropModel's docstring) - hence
        # the later midpoint and gentler (smaller) steepness than nitrogen's.
        season_k_demand_kg_ha=210.0,
        k_uptake_midpoint_gdd=600.0, k_uptake_steepness=0.010,
        season_p_demand_kg_ha=30.0, season_mg_demand_kg_ha=15.0,
        kc_ini=0.5, kc_mid=1.15, kc_end=0.75,
        # FAO-56 Table 11's "Europe (April)" potato row: initial 30d,
        # development 35d, mid-season 50d, late 30d (145d total) -> initial
        # stage ends at 30/145=21% of season, development ends (mid-season
        # starts) at (30+35)/145=45%, mid-season ends (late season starts)
        # at (30+35+50)/145=79% - applied onto the ~1000-1100 GDD-to-harvest
        # convention below (module docstring; FAO-56's day-based lengths
        # don't convert to one universal GDD figure, so these are the
        # *proportions* from that table, not its raw day counts).
        kc_ini_end_gdd=228.0, kc_mid_end_gdd=493.0, kc_late_start_gdd=872.0,
        season_end_gdd=1100.0,
        leaching_sensitivity=1.3, ky_nitrogen=1.2, ky_potassium=1.0,
        potential_yield_t_ha=45.0, heat_stress_threshold_c=27.0,
        **_stage_ky(1.1),
    ),
    'wheat': _cereal('wheat', gdd_base_c=0.0, season_end_gdd=1700.0,
                     leaching_sensitivity=0.8, ky_seasonal=1.15, ky_nitrogen=1.2,
                     potential_yield_t_ha=9.5),
    'barley': _cereal('barley', gdd_base_c=0.0, season_end_gdd=1450.0,
                      leaching_sensitivity=0.8, ky_seasonal=1.05, ky_nitrogen=1.0,
                      potential_yield_t_ha=7.5),
    'rye': _cereal('rye', gdd_base_c=0.0, season_end_gdd=1750.0,
                   leaching_sensitivity=0.75, ky_seasonal=1.1, ky_nitrogen=0.9,
                   potential_yield_t_ha=7.0),
    'oats': _cereal('oats', gdd_base_c=0.0, season_end_gdd=1500.0,
                    leaching_sensitivity=0.85, ky_seasonal=1.0, ky_nitrogen=1.0,
                    potential_yield_t_ha=6.5),
}

# Used for any crop name that isn't recognised: a mid-of-the-road average of
# the models above, so the analysis still runs (with a slightly wider margin
# of error) instead of refusing to handle an unrecognised crop.
DEFAULT_CROP_MODEL = CropModel(
    name='default', gdd_base_c=3.0,
    root_depth_min_cm=15.0, root_depth_max_cm=80.0, root_depth_full_gdd=800.0,
    season_n_demand_kg_ha=160.0,
    n_uptake_midpoint_gdd=550.0, n_uptake_steepness=0.010,
    season_k_demand_kg_ha=130.0,
    k_uptake_midpoint_gdd=550.0, k_uptake_steepness=0.010,
    season_p_demand_kg_ha=35.0, season_mg_demand_kg_ha=13.0,
    kc_ini=0.45, kc_mid=1.15, kc_end=0.55,
    # Same 10%/30%/73.33%/100% stage-boundary proportions _cereal() uses -
    # no specific crop to cite a table for here, so this just needs a
    # sensible generic shape, not a distinct derivation.
    kc_ini_end_gdd=130.0, kc_mid_end_gdd=390.0, kc_late_start_gdd=953.0,
    season_end_gdd=1300.0,
    leaching_sensitivity=1.0, ky_nitrogen=1.1, ky_potassium=1.0,
    potential_yield_t_ha=8.0,
    **_stage_ky(1.1),
)


def get_crop_model(crop_name):
    """Looks up a :class:`CropModel` by name, falling back to a substring
    match (e.g. "Potato - Bintje" -> potato) and then to
    :data:`DEFAULT_CROP_MODEL` for anything unrecognised."""
    if not crop_name:
        return DEFAULT_CROP_MODEL
    key = crop_name.strip().lower()
    if key in CROP_MODELS:
        return CROP_MODELS[key]
    for name, model in CROP_MODELS.items():
        if name in key:
            return model
    return DEFAULT_CROP_MODEL
