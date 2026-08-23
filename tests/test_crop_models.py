"""Pure-function tests for support_scripts.crop_models and
support_scripts.soil_pedotransfer.

No DB, no network - independent of the ordered/stateful part of the suite.
"""
from geodatafarm.support_scripts import crop_models
from geodatafarm.support_scripts.soil_pedotransfer import (
    available_water_capacity, field_capacity_and_wilting_point)


def test_get_crop_model_exact_and_substring_match():
    assert crop_models.get_crop_model('potato').name == 'potato'
    assert crop_models.get_crop_model('Potato - Bintje').name == 'potato'
    assert crop_models.get_crop_model('WHEAT').name == 'wheat'


def test_get_crop_model_unknown_falls_back_to_default():
    assert crop_models.get_crop_model('quinoa') is crop_models.DEFAULT_CROP_MODEL
    assert crop_models.get_crop_model('') is crop_models.DEFAULT_CROP_MODEL
    assert crop_models.get_crop_model(None) is crop_models.DEFAULT_CROP_MODEL


def test_root_depth_ramps_from_min_to_max():
    model = crop_models.CROP_MODELS['potato']
    assert crop_models.root_depth_cm(model, 0) == model.root_depth_min_cm
    assert crop_models.root_depth_cm(
        model, model.root_depth_full_gdd) == model.root_depth_max_cm
    assert crop_models.root_depth_cm(
        model, model.root_depth_full_gdd * 10) == model.root_depth_max_cm
    mid = crop_models.root_depth_cm(model, model.root_depth_full_gdd / 2)
    assert model.root_depth_min_cm < mid < model.root_depth_max_cm


def test_n_uptake_fraction_is_increasing_bounded_and_centered_at_midpoint():
    model = crop_models.CROP_MODELS['potato']
    early = crop_models.n_uptake_fraction(model, 0)
    mid = crop_models.n_uptake_fraction(model, model.n_uptake_midpoint_gdd)
    late = crop_models.n_uptake_fraction(model, model.n_uptake_midpoint_gdd * 4)
    assert 0.0 <= early < mid < late <= 1.0
    assert abs(mid - 0.5) < 1e-6


def test_k_uptake_fraction_is_increasing_bounded_and_centered_at_midpoint():
    model = crop_models.CROP_MODELS['potato']
    early = crop_models.k_uptake_fraction(model, 0)
    mid = crop_models.k_uptake_fraction(model, model.k_uptake_midpoint_gdd)
    late = crop_models.k_uptake_fraction(model, model.k_uptake_midpoint_gdd * 4)
    assert 0.0 <= early < mid < late <= 1.0
    assert abs(mid - 0.5) < 1e-6


def test_every_crop_model_has_positive_k_p_mg_demand():
    for model in list(crop_models.CROP_MODELS.values()) + [crop_models.DEFAULT_CROP_MODEL]:
        assert model.season_k_demand_kg_ha > 0.0
        assert model.season_p_demand_kg_ha > 0.0
        assert model.season_mg_demand_kg_ha > 0.0
        assert model.k_uptake_steepness > 0.0
        assert model.ky_potassium >= 0.0


def test_crop_coefficient_four_stage_shape():
    model = crop_models.CROP_MODELS['potato']
    assert crop_models.crop_coefficient(model, 0) == model.kc_ini
    assert crop_models.crop_coefficient(model, model.season_end_gdd) == model.kc_end
    # Development: ramps between kc_ini and kc_mid.
    development_midpoint = (model.kc_ini_end_gdd + model.kc_mid_end_gdd) / 2
    development_val = crop_models.crop_coefficient(model, development_midpoint)
    assert model.kc_ini < development_val < model.kc_mid
    # Mid-season: a genuine flat plateau at kc_mid, not just a single
    # instantaneous peak - FAO-56's four-stage method, not three.
    assert crop_models.crop_coefficient(model, model.kc_mid_end_gdd) == model.kc_mid
    plateau_midpoint = (model.kc_mid_end_gdd + model.kc_late_start_gdd) / 2
    assert crop_models.crop_coefficient(model, plateau_midpoint) == model.kc_mid
    assert crop_models.crop_coefficient(model, model.kc_late_start_gdd) == model.kc_mid
    # Late season: ramps down from kc_mid to kc_end.
    late_midpoint = (model.kc_late_start_gdd + model.season_end_gdd) / 2
    late_val = crop_models.crop_coefficient(model, late_midpoint)
    assert model.kc_end < late_val < model.kc_mid


def test_crop_growth_stage_matches_crop_coefficient_segments():
    model = crop_models.CROP_MODELS['potato']
    assert crop_models.crop_growth_stage(model, 0) == 'initial'
    assert crop_models.crop_growth_stage(
        model, (model.kc_ini_end_gdd + model.kc_mid_end_gdd) / 2) == 'development'
    assert crop_models.crop_growth_stage(
        model, (model.kc_mid_end_gdd + model.kc_late_start_gdd) / 2) == 'mid_season'
    assert crop_models.crop_growth_stage(
        model, (model.kc_late_start_gdd + model.season_end_gdd) / 2) == 'late_season'


def test_growing_degree_days_never_negative():
    assert crop_models.growing_degree_days(-5.0, 7.0) == 0.0
    assert crop_models.growing_degree_days(15.0, 7.0) == 8.0


def test_field_capacity_increases_with_clay_and_organic_matter():
    fc_sand, wp_sand = field_capacity_and_wilting_point(clay_pct=3.0)
    fc_clay, wp_clay = field_capacity_and_wilting_point(clay_pct=55.0)
    assert fc_sand < fc_clay
    assert wp_sand < wp_clay
    fc_plain, _ = field_capacity_and_wilting_point(clay_pct=20.0, organic_matter_pct=0.0)
    fc_om, _ = field_capacity_and_wilting_point(clay_pct=20.0, organic_matter_pct=5.0)
    assert fc_om > fc_plain


def test_available_water_capacity_matches_field_capacity_minus_wilting_point():
    for clay in (2.0, 15.0, 35.0, 80.0):
        awc = available_water_capacity(clay, organic_matter_pct=2.0)
        fc, wp = field_capacity_and_wilting_point(clay, organic_matter_pct=2.0)
        assert awc > 0.0
        assert abs(awc - (fc - wp)) < 1e-9


def test_validate_shape_accepts_every_built_in_crop_model():
    for model in list(crop_models.CROP_MODELS.values()) + [crop_models.DEFAULT_CROP_MODEL]:
        crop_models.validate_shape(model)  # must not raise


def test_validate_shape_rejects_root_depth_min_above_max():
    import dataclasses
    bad = dataclasses.replace(
        crop_models.CROP_MODELS['potato'], root_depth_min_cm=100.0, root_depth_max_cm=10.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'root depth' in str(e).lower()


def test_validate_shape_rejects_out_of_order_stage_thresholds():
    import dataclasses
    bad = dataclasses.replace(
        crop_models.CROP_MODELS['potato'], kc_ini_end_gdd=900.0, kc_mid_end_gdd=200.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'stage' in str(e).lower() or 'gdd' in str(e).lower()


def test_validate_shape_rejects_kc_late_start_gdd_out_of_order():
    import dataclasses
    # kc_late_start_gdd (mid-season plateau end) before kc_mid_end_gdd
    # (development end / plateau start) - the plateau would have negative
    # length.
    bad = dataclasses.replace(
        crop_models.CROP_MODELS['potato'], kc_mid_end_gdd=700.0, kc_late_start_gdd=500.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'stage' in str(e).lower() or 'gdd' in str(e).lower()


def test_validate_shape_rejects_non_positive_n_uptake_steepness():
    import dataclasses
    bad = dataclasses.replace(crop_models.CROP_MODELS['potato'], n_uptake_steepness=0.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'steepness' in str(e).lower()


def test_validate_shape_rejects_non_positive_k_uptake_steepness():
    import dataclasses
    bad = dataclasses.replace(crop_models.CROP_MODELS['potato'], k_uptake_steepness=0.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'steepness' in str(e).lower()


def test_validate_shape_rejects_non_positive_kc_values():
    import dataclasses
    bad = dataclasses.replace(crop_models.CROP_MODELS['potato'], kc_mid=0.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'kc' in str(e).lower()


def test_validate_shape_reports_multiple_problems_together():
    import dataclasses
    bad = dataclasses.replace(
        crop_models.CROP_MODELS['potato'], root_depth_min_cm=100.0,
        root_depth_max_cm=10.0, kc_ini=-1.0)
    try:
        crop_models.validate_shape(bad)
        assert False, 'expected a ValueError'
    except ValueError as e:
        message = str(e).lower()
        assert 'root depth' in message
        assert 'kc' in message
