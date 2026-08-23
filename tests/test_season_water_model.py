"""Pure-function tests for support_scripts.season_water_model.

No DB, no network - independent of the ordered/stateful part of the suite.
"""
from datetime import date, timedelta

from geodatafarm.support_scripts.fertilizer_timing_model import DailyWeather
from geodatafarm.support_scripts.season_water_model import daily_trace, estimate_season


def _make_weather(start, days, total_rain_mm, et0=4.0, temp=16.0):
    d0 = date.fromisoformat(start)
    per_day_rain = total_rain_mm / days
    return [
        DailyWeather(date=(d0 + timedelta(days=i)).isoformat(),
                    precipitation_mm=per_day_rain, et0_mm=et0, temp_mean_c=temp)
        for i in range(days)
    ]


def _make_weather_with_rain_event(start, days, rain_by_day_index, et0=3.0, temp=18.0):
    """Like _make_weather, but ``rain_by_day_index`` ({day_index: mm}) puts
    all the rain on specific days instead of spreading it evenly - needed
    to test drainage/leaching, which only happen when a day's water
    exceeds field capacity, not from gentle even rainfall."""
    d0 = date.fromisoformat(start)
    return [
        DailyWeather(date=(d0 + timedelta(days=i)).isoformat(),
                    precipitation_mm=rain_by_day_index.get(i, 0.0), et0_mm=et0, temp_mean_c=temp)
        for i in range(days)
    ]


def test_well_watered_season_reaches_potential_yield_with_no_irrigation_need():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.water_stress_days == 0
    assert result.irrigation_need_mm == 0.0
    assert result.estimated_yield_t_ha == result.potential_yield_t_ha


def test_drought_season_reduces_yield_and_raises_irrigation_need():
    wet = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    dry = _make_weather('2024-04-01', 120, total_rain_mm=20.0)

    wet_result = estimate_season(wet, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    dry_result = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert dry_result.estimated_yield_t_ha < wet_result.estimated_yield_t_ha
    assert dry_result.irrigation_need_mm > wet_result.irrigation_need_mm
    assert dry_result.water_stress_days > wet_result.water_stress_days


def test_irrigation_need_is_bounded_by_the_seasons_potential_et():
    # A naive "sum the daily shortfall on every day below threshold" bug
    # would let this blow past several times the season's actual water
    # demand; a correct MAD-triggered-refill calculation stays in that
    # same order of magnitude.
    dry = _make_weather('2024-04-01', 120, total_rain_mm=0.0)

    result = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.irrigation_need_mm < result.potential_et_mm * 1.5


def test_missing_soil_data_falls_back_and_is_flagged():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'wheat')

    assert result.used_default_soil is True
    assert result.estimated_yield_t_ha is not None


def test_no_weather_data_returns_none_yield_without_crashing():
    result = estimate_season([], 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.estimated_yield_t_ha is None
    assert result.days_with_weather == 0


def test_unknown_crop_falls_back_to_default_model_but_still_runs():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'quinoa', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.crop_model == 'default'
    assert result.estimated_yield_t_ha is not None


def test_logged_irrigation_improves_yield_and_reduces_additional_need():
    dry = _make_weather('2024-04-01', 120, total_rain_mm=20.0)
    d0 = date(2024, 4, 1)
    irrigation = {(d0 + timedelta(days=i)).isoformat(): 15.0 for i in range(0, 120, 5)}

    unirrigated = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    irrigated = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                                irrigation_mm_by_date=irrigation)

    assert irrigated.logged_irrigation_mm == sum(irrigation.values())
    assert irrigated.estimated_yield_t_ha > unirrigated.estimated_yield_t_ha
    # irrigation_need_mm is the *additional* water needed on top of what was
    # already logged, so logging more should never increase it.
    assert irrigated.irrigation_need_mm < unirrigated.irrigation_need_mm


def test_no_logged_irrigation_matches_the_original_rainfed_behaviour():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=20.0)

    with_none_arg = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    with_empty_dict = estimate_season(weather, 'potato', clay_pct=20.0,
                                      organic_matter_pct=3.0, irrigation_mm_by_date={})

    assert with_none_arg.logged_irrigation_mm == 0.0
    assert with_none_arg.estimated_yield_t_ha == with_empty_dict.estimated_yield_t_ha
    assert with_none_arg.irrigation_need_mm == with_empty_dict.irrigation_need_mm


def test_daily_trace_has_one_point_per_day_with_weather():
    weather = _make_weather('2024-04-01', 30, total_rain_mm=200.0)

    trace = daily_trace(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert len(trace) == 30
    assert [p.date for p in trace] == [w.date for w in weather]
    assert all(0.0 <= p.wetness_fraction <= 1.0 for p in trace)


def test_daily_trace_shows_more_stress_days_when_dry():
    wet = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    dry = _make_weather('2024-04-01', 120, total_rain_mm=20.0)

    wet_trace = daily_trace(wet, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    dry_trace = daily_trace(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert sum(p.water_stress for p in wet_trace) == 0
    assert sum(p.water_stress for p in dry_trace) > 0
    # A dry trace should end up drier (lower wetness) than a wet one.
    assert dry_trace[-1].wetness_fraction < wet_trace[-1].wetness_fraction


def test_daily_trace_and_estimate_season_agree_on_stress_day_count():
    # Both are thin wrappers around the same day-stepper - the season
    # summary's water_stress_days must equal the trace's count exactly.
    dry = _make_weather('2024-04-01', 120, total_rain_mm=20.0)

    season = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    trace = daily_trace(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert season.water_stress_days == sum(p.water_stress for p in trace)


def test_daily_trace_falls_back_to_default_soil_when_none_given():
    weather = _make_weather('2024-04-01', 30, total_rain_mm=200.0)

    trace = daily_trace(weather, 'wheat')

    assert len(trace) == 30
    assert all(p.capacity_mm > 0 for p in trace)


# -- Nitrogen / Liebig's-law tests -------------------------------------

def test_omitting_fertilizer_data_matches_the_original_water_only_behaviour():
    # fertilizer_kg_n_by_date=None (the default) must be indistinguishable
    # from this parameter never having existed - every caller that doesn't
    # know about nitrogen yet must keep getting the exact water-only figure.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.nitrogen_modeled is False
    assert result.limiting_factor == 'none'
    assert result.estimated_yield_t_ha == result.estimated_yield_water_only_t_ha


def test_zero_applied_nitrogen_caps_yield_via_liebigs_law():
    # An explicit {} (as opposed to omitting the parameter) means "nitrogen
    # is modelled, and genuinely none was applied" - a real constraint.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    well_watered_no_n = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date={})

    assert well_watered_no_n.nitrogen_modeled is True
    assert well_watered_no_n.limiting_factor == 'nitrogen'
    assert well_watered_no_n.nitrogen_uptake_kg_ha == 0.0
    assert well_watered_no_n.estimated_yield_t_ha < well_watered_no_n.potential_yield_t_ha
    # Water alone was not limiting - only the nitrogen deficit dragged the
    # actual estimate below what water alone would have given.
    assert well_watered_no_n.estimated_yield_water_only_t_ha == well_watered_no_n.potential_yield_t_ha


def test_min_relative_yield_nitrogen_floor_prevents_a_total_wipeout():
    # ky_nitrogen alone (1.1 for potato) drives relative_yield_nitrogen to
    # 0.0 at a 100% deficit (1.1 x 1.0 > 1.0) - min_relative_yield_nitrogen
    # (0.3 by default, for every crop) exists precisely to stop that: a
    # real zero-fertilizer plot still yields something from soil-supplied
    # nitrogen, it doesn't fail completely.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date={})

    assert result.limiting_factor == 'nitrogen'
    assert result.estimated_yield_t_ha == round(0.3 * result.potential_yield_t_ha, 1)


def test_min_relative_yield_nitrogen_floor_does_not_apply_when_nitrogen_is_not_modelled():
    # Omitting fertilizer_kg_n_by_date entirely (unlike passing {} above)
    # means nitrogen isn't tracked for this run at all - the floor must not
    # invent a nitrogen constraint that was never modelled in the first place.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.nitrogen_modeled is False
    assert result.estimated_yield_t_ha == result.potential_yield_t_ha


def test_ample_nitrogen_does_not_cap_yield_below_the_water_only_estimate():
    # 450mm, not 600mm: over a 120-day window this crop now matures well
    # before day 120 (see crop_models.py's potato gdd_base_c/kc thresholds),
    # so a wetter fixture spends its last weeks at low late-season Kc,
    # under-using a constant daily rain and draining/leaching some of the
    # applied N - a real effect (see season_water_model.py's leaching
    # mechanism) this test isn't meant to be exercising; 450mm keeps the
    # season genuinely non-water-limiting without triggering it.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=450.0)
    d0 = date(2024, 4, 1)
    # Comfortably above potato's season N demand (~180 kg N/ha).
    ample_n = {(d0 + timedelta(days=i)).isoformat(): 60.0 for i in range(0, 90, 15)}

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                             fertilizer_kg_n_by_date=ample_n)

    assert result.nitrogen_modeled is True
    assert result.limiting_factor in ('water', 'both')
    assert result.estimated_yield_t_ha == result.estimated_yield_water_only_t_ha


def test_partial_nitrogen_gives_a_yield_between_zero_and_full_application():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    d0 = date(2024, 4, 1)
    ample_n = {(d0 + timedelta(days=i)).isoformat(): 60.0 for i in range(0, 90, 15)}
    # 40, not e.g. 20: min_relative_yield_nitrogen's 0.3 floor means a dose
    # too small to lift uptake past the floor-crossing point gives exactly
    # the same (floored) yield as zero applied at all - 40 clears it with
    # comfortable margin so this stays a genuine three-way progression.
    partial_n = {(d0 + timedelta(days=i)).isoformat(): 40.0 for i in range(0, 90, 20)}

    zero = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_n_by_date={})
    partial = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                              fertilizer_kg_n_by_date=partial_n)
    full = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_n_by_date=ample_n)

    assert zero.estimated_yield_t_ha < partial.estimated_yield_t_ha < full.estimated_yield_t_ha


def test_nitrogen_limitation_applies_even_when_water_is_also_short():
    # Liebig's law: the WORSE of the two deficits wins - a nitrogen
    # shortage should still cap yield even during a drought. 100mm, not a
    # catastrophic near-zero rain total: min_relative_yield_nitrogen's 0.3
    # floor means an extreme-enough drought would make *water* the worse
    # (and therefore limiting) deficit instead, which would defeat the
    # point of this test - 100mm keeps water meaningfully short without
    # dropping its own relative yield below nitrogen's floor.
    dry = _make_weather('2024-04-01', 120, total_rain_mm=100.0)

    dry_only = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    dry_and_no_n = estimate_season(dry, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                                   fertilizer_kg_n_by_date={})

    assert dry_and_no_n.limiting_factor == 'nitrogen'
    assert dry_and_no_n.estimated_yield_t_ha <= dry_only.estimated_yield_t_ha


def test_estimate_season_accepts_a_crop_model_override():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    weather = _make_weather('2024-04-01', 30, total_rain_mm=200.0)
    custom_model = dataclasses.replace(get_crop_model('potato'), potential_yield_t_ha=99.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                             crop_model=custom_model)

    assert result.potential_yield_t_ha == 99.0
    assert result.crop_model == 'potato'


def test_omitting_spacing_mm_matches_the_original_behaviour_before_it_existed():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    without_param = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    with_explicit_none = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0, spacing_mm=None)

    assert without_param == with_explicit_none
    assert without_param.spacing_yield_multiplier == 1.0
    assert without_param.potential_yield_before_spacing_t_ha is None


def test_spacing_mm_has_no_effect_unless_the_crop_model_configures_a_reference():
    from geodatafarm.support_scripts.crop_models import get_crop_model

    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                             spacing_mm=500.0)

    # potato's built-in default has reference_spacing_mm=0.0 (disabled) -
    # see crop_models.py's CropModel docstring for why there's no
    # universal literature default for this.
    assert result.spacing_yield_multiplier == 1.0
    assert result.potential_yield_before_spacing_t_ha is None
    assert result.potential_yield_t_ha == get_crop_model('potato').potential_yield_t_ha


def test_spacing_away_from_the_reference_reduces_the_yield_ceiling():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    configured = dataclasses.replace(
        get_crop_model('potato'), reference_spacing_mm=250.0, spacing_sensitivity=1.0)

    at_reference = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                                   crop_model=configured, spacing_mm=250.0)
    away_from_reference = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        crop_model=configured, spacing_mm=350.0)

    assert at_reference.spacing_yield_multiplier == 1.0
    assert at_reference.potential_yield_before_spacing_t_ha is None
    assert at_reference.potential_yield_t_ha == configured.potential_yield_t_ha

    assert away_from_reference.spacing_yield_multiplier < 1.0
    assert away_from_reference.potential_yield_before_spacing_t_ha == configured.potential_yield_t_ha
    assert away_from_reference.potential_yield_t_ha < at_reference.potential_yield_t_ha
    # The ceiling shrinking must also pull the actual estimate down with it.
    assert away_from_reference.estimated_yield_t_ha < at_reference.estimated_yield_t_ha


def test_spacing_penalty_applies_to_both_a_narrower_and_a_wider_spacing():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    configured = dataclasses.replace(
        get_crop_model('potato'), reference_spacing_mm=250.0, spacing_sensitivity=1.0)

    narrower = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                               crop_model=configured, spacing_mm=125.0)
    wider = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                            crop_model=configured, spacing_mm=350.0)

    assert narrower.potential_yield_t_ha < configured.potential_yield_t_ha
    assert wider.potential_yield_t_ha < configured.potential_yield_t_ha


def test_default_ky_heat_is_disabled_and_fully_backward_compatible():
    # potato's built-in default has ky_heat=0.0 - even a very hot season
    # must have zero effect on the estimate, matching this module's
    # behaviour before heat was added (see crop_models.py's CropModel
    # docstring for why heat, unlike water/nitrogen, defaults to disabled).
    hot_weather = _make_weather('2024-07-01', 30, total_rain_mm=200.0, temp=35.0)

    result = estimate_season(hot_weather, 'potato', clay_pct=20.0, organic_matter_pct=2.0)

    assert result.heat_modeled is False
    assert result.heat_stress_days == 30  # still counted, just inert
    assert result.limiting_factor == 'none'


def test_configuring_ky_heat_makes_heat_a_limiting_factor_in_a_hot_season():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    configured = dataclasses.replace(get_crop_model('potato'), ky_heat=1.5)
    hot_weather = _make_weather('2024-07-01', 30, total_rain_mm=300.0, temp=35.0)

    result = estimate_season(hot_weather, 'potato', clay_pct=20.0, organic_matter_pct=2.0,
                             crop_model=configured)

    assert result.heat_modeled is True
    assert result.heat_stress_days == 30
    assert result.limiting_factor == 'heat'
    assert result.estimated_yield_t_ha < result.potential_yield_t_ha
    assert 'Heat:' in result.note


def test_heat_stress_causes_no_penalty_when_no_day_exceeds_the_threshold():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    configured = dataclasses.replace(get_crop_model('potato'), ky_heat=1.5)
    cool_weather = _make_weather('2024-07-01', 30, total_rain_mm=300.0, temp=18.0)

    result = estimate_season(cool_weather, 'potato', clay_pct=20.0, organic_matter_pct=2.0,
                             crop_model=configured)

    assert result.heat_stress_days == 0
    # The meaningful invariant is no yield penalty - not the tie label
    # itself, which (like the pre-existing 'both' for water/nitrogen) just
    # reports every modelled factor that's tied at the achieved value,
    # even when that value is the ceiling (no one actually limited it).
    assert result.estimated_yield_t_ha == result.potential_yield_t_ha


def test_heat_stress_combines_with_nitrogen_via_liebigs_law():
    import dataclasses
    from geodatafarm.support_scripts.crop_models import get_crop_model

    configured = dataclasses.replace(get_crop_model('potato'), ky_heat=1.5)
    hot_weather = _make_weather('2024-07-01', 30, total_rain_mm=300.0, temp=35.0)

    heat_only = estimate_season(hot_weather, 'potato', clay_pct=20.0, organic_matter_pct=2.0,
                                crop_model=configured)
    heat_and_no_nitrogen = estimate_season(
        hot_weather, 'potato', clay_pct=20.0, organic_matter_pct=2.0,
        crop_model=configured, fertilizer_kg_n_by_date={})

    # Adding a second, independently-limiting factor (no nitrogen applied
    # at all) can only cap the estimate further, never raise it.
    assert heat_and_no_nitrogen.estimated_yield_t_ha <= heat_only.estimated_yield_t_ha


def test_no_drainage_means_no_leaching_matching_pre_leaching_behaviour():
    # A dry, evenly-rainfed season never crosses field capacity, so there's
    # nothing to leach - this is the backward-compatible "nothing changed"
    # case for every existing caller that doesn't have a big rain/
    # irrigation event in its weather.
    weather = _make_weather('2024-05-01', 60, total_rain_mm=30.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                             fertilizer_kg_n_by_date={'2024-05-01': 180.0})

    assert result.water_drainage_mm == 0.0
    assert result.nitrogen_leached_kg_ha == 0.0
    assert 'leached' not in result.note
    assert 'drained' not in result.note


def test_a_lump_nitrogen_dose_ahead_of_heavy_rain_leaches_more_than_splitting_around_it():
    # This is the concrete "does timing matter" case: the SAME 180 kg N/ha
    # total, either all applied on day 1 (well before an 80mm rain event),
    # or split into three doses with two of them held back until after the
    # rain has passed. Applying it all up front risks far more of it,
    # since N still sitting in the pool when a drainage event hits is what
    # gets carried away - N already taken up, or not yet applied, is safe.
    rain_event = {9: 80.0}  # a single 80mm day, ~day 10
    weather = _make_weather_with_rain_event('2024-05-01', 60, rain_event)

    lump = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_n_by_date={'2024-05-01': 180.0})
    split_around_rain = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date={
            '2024-05-01': 60.0, '2024-05-20': 60.0, '2024-06-05': 60.0})

    assert lump.nitrogen_leached_kg_ha > split_around_rain.nitrogen_leached_kg_ha
    assert lump.estimated_yield_t_ha <= split_around_rain.estimated_yield_t_ha
    assert 'leached' in lump.note


def test_a_single_large_irrigation_dose_drains_more_than_the_same_total_spread_out():
    # Same total irrigation (150mm), either one large dose or six smaller
    # ones spaced out - the field-capacity cap in the water balance means
    # a big dose landing on already-near-capacity soil wastes more of it
    # to drainage than the same total applied gradually.
    weather = _make_weather('2024-05-01', 60, total_rain_mm=30.0)

    lump = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           irrigation_mm_by_date={'2024-05-05': 150.0})
    spread = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        irrigation_mm_by_date={
            '2024-05-05': 25.0, '2024-05-10': 25.0, '2024-05-15': 25.0,
            '2024-05-20': 25.0, '2024-05-25': 25.0, '2024-05-30': 25.0})

    assert lump.water_drainage_mm > spread.water_drainage_mm
    assert lump.estimated_yield_t_ha <= spread.estimated_yield_t_ha
    assert 'drained' in lump.note


# -- Potassium (full day-by-day balance, mirrors nitrogen) --------------

def test_omitting_potassium_data_matches_the_original_behaviour():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.potassium_modeled is False
    assert result.limiting_factor == 'none'
    assert result.estimated_yield_t_ha == result.estimated_yield_water_only_t_ha


def test_zero_applied_potassium_caps_yield_via_liebigs_law():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    well_watered_no_k = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_k_by_date={})

    assert well_watered_no_k.potassium_modeled is True
    assert well_watered_no_k.limiting_factor == 'potassium'
    assert well_watered_no_k.potassium_uptake_kg_ha == 0.0
    assert well_watered_no_k.estimated_yield_t_ha < well_watered_no_k.potential_yield_t_ha
    assert (well_watered_no_k.estimated_yield_water_only_t_ha
            == well_watered_no_k.potential_yield_t_ha)


def test_ample_potassium_does_not_cap_yield_below_the_water_only_estimate():
    # 450mm, not 600mm - same late-season-drainage pitfall as nitrogen's
    # equivalent test above (see that test's comment): a wetter fixture
    # matures before day 120 and leaches whatever's still unused in the
    # pool during the low-Kc tail, which isn't what this test means to
    # exercise.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=450.0)
    d0 = date(2024, 4, 1)
    # Comfortably above potato's season K demand (210 kg K/ha).
    ample_k = {(d0 + timedelta(days=i)).isoformat(): 70.0 for i in range(0, 90, 15)}

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                             fertilizer_kg_k_by_date=ample_k)

    assert result.potassium_modeled is True
    # Unlike nitrogen-only's 'both' (a special-cased literal for backward
    # compatibility, see estimate_season), once potassium/heat exist the
    # tie is reported as a joined 'water+potassium' string - the
    # meaningful assertion is the yield equality below.
    assert result.limiting_factor in ('water', 'water+potassium')
    assert result.estimated_yield_t_ha == result.estimated_yield_water_only_t_ha


def test_partial_potassium_gives_a_yield_between_zero_and_full_application():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    d0 = date(2024, 4, 1)
    ample_k = {(d0 + timedelta(days=i)).isoformat(): 70.0 for i in range(0, 90, 15)}
    partial_k = {(d0 + timedelta(days=i)).isoformat(): 20.0 for i in range(0, 90, 20)}

    zero = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_k_by_date={})
    partial = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                              fertilizer_kg_k_by_date=partial_k)
    full = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_k_by_date=ample_k)

    assert zero.estimated_yield_t_ha < partial.estimated_yield_t_ha < full.estimated_yield_t_ha


def test_a_lump_potassium_dose_ahead_of_heavy_rain_leaches_more_than_splitting_around_it():
    rain_event = {9: 80.0}
    weather = _make_weather_with_rain_event('2024-05-01', 60, rain_event)

    lump = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                           fertilizer_kg_k_by_date={'2024-05-01': 210.0})
    split_around_rain = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_k_by_date={
            '2024-05-01': 70.0, '2024-05-20': 70.0, '2024-06-05': 70.0})

    assert lump.potassium_leached_kg_ha > split_around_rain.potassium_leached_kg_ha
    assert lump.estimated_yield_t_ha <= split_around_rain.estimated_yield_t_ha
    assert 'Potassium' in lump.note


def test_nitrogen_and_potassium_are_independent_liebig_factors():
    # A severe potassium deficit must still cap yield even when nitrogen
    # is ample, and vice versa - Liebig's law takes the worse of the two,
    # not some blend.
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    d0 = date(2024, 4, 1)
    ample_n = {(d0 + timedelta(days=i)).isoformat(): 60.0 for i in range(0, 90, 15)}
    ample_k = {(d0 + timedelta(days=i)).isoformat(): 70.0 for i in range(0, 90, 15)}

    ample_n_no_k = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date=ample_n, fertilizer_kg_k_by_date={})
    ample_k_no_n = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date={}, fertilizer_kg_k_by_date=ample_k)
    both_ample = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date=ample_n, fertilizer_kg_k_by_date=ample_k)

    assert ample_n_no_k.limiting_factor == 'potassium'
    assert ample_k_no_n.limiting_factor == 'nitrogen'
    assert both_ample.estimated_yield_t_ha > ample_n_no_k.estimated_yield_t_ha
    assert both_ample.estimated_yield_t_ha > ample_k_no_n.estimated_yield_t_ha


# -- Phosphorus / Magnesium (season-total supply check only) ------------

def test_omitting_phosphorus_and_magnesium_matches_the_original_behaviour():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.phosphorus_modeled is False
    assert result.magnesium_modeled is False
    assert result.phosphorus_status == 'none'
    assert result.magnesium_status == 'none'


def test_zero_applied_phosphorus_and_magnesium_are_flagged_under_but_never_cap_yield():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    no_p_mg = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        phosphorus_applied_kg_ha=0.0, magnesium_applied_kg_ha=0.0)

    assert no_p_mg.phosphorus_modeled is True
    assert no_p_mg.magnesium_modeled is True
    assert no_p_mg.phosphorus_status == 'under'
    assert no_p_mg.magnesium_status == 'under'
    # Never a limiting factor and never reduces the estimate - P/Mg only
    # ever get a season-total supply check, not a yield-capping balance.
    assert no_p_mg.limiting_factor == 'none'
    assert no_p_mg.estimated_yield_t_ha == no_p_mg.potential_yield_t_ha


def test_ample_phosphorus_and_magnesium_are_flagged_adequate():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)
    # potato's built-in demand: season_p_demand_kg_ha=30.0, season_mg_demand_kg_ha=15.0.
    result = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        phosphorus_applied_kg_ha=32.0, magnesium_applied_kg_ha=16.0)

    assert result.phosphorus_status == 'adequate'
    assert result.magnesium_status == 'adequate'
    assert 'Phosphorus' in result.note
    assert 'Magnesium' in result.note


def test_surplus_phosphorus_and_magnesium_are_flagged_over():
    weather = _make_weather('2024-04-01', 120, total_rain_mm=600.0)

    result = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        phosphorus_applied_kg_ha=200.0, magnesium_applied_kg_ha=100.0)

    assert result.phosphorus_status == 'over'
    assert result.magnesium_status == 'over'
    assert result.limiting_factor == 'none'
    assert result.estimated_yield_t_ha == result.potential_yield_t_ha


# -- planting_date / harvest_date (growth-stop) tests -------------------

def test_planting_date_delays_water_use_until_the_crop_is_actually_present():
    # No rain, so any evapotranspiration before "planting" would otherwise
    # draw the soil down - delaying the crop's presence must mean fewer
    # active days, and therefore strictly less potential/actual ET over
    # the same 60-day window, regardless of the exact Kc curve shape.
    weather = _make_weather('2024-04-01', 60, total_rain_mm=0.0, temp=18.0)

    unanchored = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    delayed = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                              planting_date='2024-04-21')

    assert delayed.potential_et_mm < unanchored.potential_et_mm
    assert delayed.actual_et_mm < unanchored.actual_et_mm
    assert 'anchored to a logged planting date' in delayed.note
    assert 'anchored to a logged planting date' not in unanchored.note


def test_harvest_date_stops_nitrogen_uptake_from_that_date_on():
    # A generous nitrogen dose applied right at the start of a warm 60-day
    # season would normally be substantially taken up by the end of it;
    # cutting the season short on day 4 (well before any meaningful
    # growing-degree-day accumulation) must leave nearly all of it unused.
    weather = _make_weather('2024-04-01', 60, total_rain_mm=200.0, temp=20.0)
    fertilizer = {'2024-04-01': 150.0}

    full_season = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date=fertilizer)
    cut_short = estimate_season(
        weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
        fertilizer_kg_n_by_date=fertilizer, harvest_date='2024-04-04')

    assert full_season.nitrogen_uptake_kg_ha > 10.0
    assert cut_short.nitrogen_uptake_kg_ha < 1.0
    assert 'Growth was treated as stopped' in cut_short.note
    assert 'Growth was treated as stopped' not in full_season.note


def test_daily_trace_shows_zero_et_before_planting_and_after_harvest():
    weather = _make_weather('2024-04-01', 10, total_rain_mm=100.0, temp=18.0)

    trace = daily_trace(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0,
                        planting_date='2024-04-04', harvest_date='2024-04-08')
    by_date = {p.date: p for p in trace}

    assert by_date['2024-04-01'].potential_et_mm == 0.0
    assert by_date['2024-04-01'].actual_et_mm == 0.0
    assert by_date['2024-04-10'].potential_et_mm == 0.0
    assert by_date['2024-04-10'].actual_et_mm == 0.0
    # A day within [planting_date, harvest_date] should behave normally -
    # the crop is present, so it actually uses water.
    assert by_date['2024-04-06'].potential_et_mm > 0.0


# -- Per-growth-stage water Ky (FAO-33's Jensen multi-period model) -----

def _weather_with_dry_window(start, days, dry_start_idx, dry_len, wet_rain=6.0,
                             et0=4.0, temp=18.0):
    """Wet every day except a contiguous dry window - the inverse of
    _make_weather_with_rain_event, needed here to place a *shortfall* at
    a specific point in the season rather than a surplus."""
    rain_by_day = {i: wet_rain for i in range(days)
                  if not (dry_start_idx <= i < dry_start_idx + dry_len)}
    return _make_weather_with_rain_event(
        start, days, rain_by_day, et0=et0, temp=temp)


def test_the_same_dry_spell_costs_more_yield_in_mid_season_than_late_season():
    # The exact concern this feature was built for: potato water stress
    # matters far more during tuber initiation/bulking (mid-season) than
    # during ripening (late season) - a flat seasonal Ky couldn't tell the
    # two apart, since it only sees the season-total deficit.
    # 18 degC, base 4.4 -> 13.6 GDD/day - mid-season spans roughly days
    # 36-64 from planting (GDD 493-872), late season roughly days 64-81
    # (GDD 872-1100).
    dry_mid = _weather_with_dry_window('2024-04-01', 100, dry_start_idx=40, dry_len=15)
    dry_late = _weather_with_dry_window('2024-04-01', 100, dry_start_idx=68, dry_len=15)

    result_mid = estimate_season(dry_mid, 'potato', clay_pct=20.0, organic_matter_pct=3.0)
    result_late = estimate_season(dry_late, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result_mid.estimated_yield_t_ha < result_late.estimated_yield_t_ha
    assert result_mid.water_limiting_stage == 'mid_season'


def test_water_limiting_stage_is_none_when_no_stage_saw_a_deficit():
    weather = _make_weather('2024-04-01', 100, total_rain_mm=800.0)

    result = estimate_season(weather, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert result.water_limiting_stage == 'none'
    assert result.estimated_yield_t_ha == result.potential_yield_t_ha


def test_stage_ky_note_mentions_the_worst_stage():
    dry_mid = _weather_with_dry_window('2024-04-01', 100, dry_start_idx=40, dry_len=15)

    result = estimate_season(dry_mid, 'potato', clay_pct=20.0, organic_matter_pct=3.0)

    assert 'mid season' in result.note
    assert 'largest water deficit' in result.note
