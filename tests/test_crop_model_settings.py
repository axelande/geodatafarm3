"""Tests for support_scripts.crop_model_settings.

Uses the shared ``gdf``/database fixture like tests/test_import_data.py, so
it must run as part of the full suite (`pytest tests`), not on its own -
see tests/conftest.py and the project's stateful/order-dependent test setup.
Doesn't touch 'test_field' or any other fixture field, so - unlike the
crop-simulation tests - there's no ordering dependency on tests/test_field.py.
"""
from ..GeoDataFarm import GeoDataFarm
from ..support_scripts import crop_model_settings as settings
from ..support_scripts.crop_models import get_crop_model
from . import gdf

_CROP = 'pytest_test_crop'


def _clear(gdf):
    settings.reset_overrides(gdf.db, _CROP)


def test_effective_crop_model_matches_the_default_with_no_overrides(gdf: GeoDataFarm):
    _clear(gdf)

    model = settings.effective_crop_model(gdf.db, 'potato')

    assert model == get_crop_model('potato')


def test_save_and_apply_a_single_override(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(gdf.db, _CROP, potential_yield_t_ha=123.0)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.potential_yield_t_ha == 123.0
    # Everything else still comes from the default (unrecognised crop name
    # falls back to DEFAULT_CROP_MODEL).
    assert model.ky_mid_season == get_crop_model(_CROP).ky_mid_season

    _clear(gdf)


def test_save_overrides_only_touches_the_fields_given(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(gdf.db, _CROP, potential_yield_t_ha=50.0)
    settings.save_overrides(gdf.db, _CROP, ky_mid_season=1.5)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.potential_yield_t_ha == 50.0
    assert model.ky_mid_season == 1.5

    _clear(gdf)


def test_get_overrides_only_returns_explicitly_set_fields(gdf: GeoDataFarm):
    _clear(gdf)
    settings.save_overrides(gdf.db, _CROP, potential_yield_t_ha=50.0)

    overrides = settings.get_overrides(gdf.db, _CROP)

    assert overrides == {'potential_yield_t_ha': 50.0}

    _clear(gdf)


def test_reset_overrides_reverts_to_the_default(gdf: GeoDataFarm):
    _clear(gdf)
    settings.save_overrides(gdf.db, 'potato', potential_yield_t_ha=999.0)

    settings.reset_overrides(gdf.db, 'potato')
    model = settings.effective_crop_model(gdf.db, 'potato')

    assert model == get_crop_model('potato')
    assert settings.get_overrides(gdf.db, 'potato') == {}


def test_save_overrides_rejects_an_unknown_field(gdf: GeoDataFarm):
    _clear(gdf)

    # leaching_sensitivity is a real CropModel field, deliberately NOT in
    # OVERRIDABLE_FIELDS (it only feeds the separate simple-tier fertilizer-
    # timing risk index, not the settings dialog this module backs) - a
    # genuinely unrecognised name would test the same code path but less
    # meaningfully, since it'd never be a plausible typo for a real field.
    try:
        settings.save_overrides(gdf.db, _CROP, leaching_sensitivity=1.5)
        assert False, 'expected a ValueError'
    except ValueError:
        pass


def test_save_overrides_is_case_insensitive_on_crop_name(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(gdf.db, _CROP.upper(), potential_yield_t_ha=77.0)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.potential_yield_t_ha == 77.0

    _clear(gdf)


def test_variety_overrides_layer_on_top_of_crop_level_overrides(gdf: GeoDataFarm):
    _clear(gdf)
    settings.reset_overrides(gdf.db, _CROP, 'arsenal')

    settings.save_overrides(gdf.db, _CROP, potential_yield_t_ha=40.0, ky_mid_season=1.2)
    settings.save_overrides(gdf.db, _CROP, 'arsenal', potential_yield_t_ha=50.0)

    crop_level = settings.effective_crop_model(gdf.db, _CROP)
    variety_level = settings.effective_crop_model(gdf.db, _CROP, variety='arsenal')

    assert crop_level.potential_yield_t_ha == 40.0
    assert crop_level.ky_mid_season == 1.2
    # The variety only overrode potential yield - ky_mid_season is inherited
    # from the crop-level override, not the built-in default.
    assert variety_level.potential_yield_t_ha == 50.0
    assert variety_level.ky_mid_season == 1.2

    _clear(gdf)
    settings.reset_overrides(gdf.db, _CROP, 'arsenal')


def test_variety_name_is_case_insensitive_and_independent_of_other_varieties(gdf: GeoDataFarm):
    _clear(gdf)
    settings.reset_overrides(gdf.db, _CROP, 'solist')

    settings.save_overrides(gdf.db, _CROP, 'SOLIST', potential_yield_t_ha=33.0)

    assert settings.effective_crop_model(
        gdf.db, _CROP, variety='solist').potential_yield_t_ha == 33.0
    # A different variety (or no variety at all) never sees another
    # variety's override.
    default_yield = get_crop_model(_CROP).potential_yield_t_ha
    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == default_yield
    assert settings.effective_crop_model(
        gdf.db, _CROP, variety='fontane').potential_yield_t_ha == default_yield

    settings.reset_overrides(gdf.db, _CROP, 'solist')


def test_reset_overrides_for_a_variety_does_not_touch_the_crop_level_row(gdf: GeoDataFarm):
    _clear(gdf)
    settings.reset_overrides(gdf.db, _CROP, 'arsenal')
    settings.save_overrides(gdf.db, _CROP, potential_yield_t_ha=40.0)
    settings.save_overrides(gdf.db, _CROP, 'arsenal', potential_yield_t_ha=50.0)

    settings.reset_overrides(gdf.db, _CROP, 'arsenal')

    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 40.0
    assert settings.effective_crop_model(
        gdf.db, _CROP, variety='arsenal').potential_yield_t_ha == 40.0

    _clear(gdf)


def test_save_and_apply_spacing_overrides(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(
        gdf.db, _CROP, reference_spacing_mm=250.0, spacing_sensitivity=0.8)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.reference_spacing_mm == 250.0
    assert model.spacing_sensitivity == 0.8

    _clear(gdf)


def test_ensure_settings_table_migrates_a_pre_spacing_schema(gdf: GeoDataFarm):
    # Reproduces upgrading a farm's database from before the spacing
    # columns existed, but after the variety column already did.
    gdf.db.execute_sql("DROP TABLE IF EXISTS public.crop_model_settings")
    gdf.db.execute_sql(
        "CREATE TABLE public.crop_model_settings (crop_name text NOT NULL,"
        " variety text NOT NULL DEFAULT '',"
        " potential_yield_t_ha double precision,"
        " ky_nitrogen double precision, season_n_demand_kg_ha double precision,"
        " PRIMARY KEY (crop_name, variety))")
    gdf.db.execute_sql(
        "INSERT INTO public.crop_model_settings (crop_name, potential_yield_t_ha)"
        " VALUES (%s, %s)", params=(_CROP, 55.0))

    settings.ensure_settings_table(gdf.db)

    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 55.0
    settings.save_overrides(gdf.db, _CROP, reference_spacing_mm=300.0)
    model = settings.effective_crop_model(gdf.db, _CROP)
    assert model.potential_yield_t_ha == 55.0
    assert model.reference_spacing_mm == 300.0

    _clear(gdf)


def test_save_and_apply_heat_overrides(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(gdf.db, _CROP, heat_stress_threshold_c=28.0, ky_heat=0.9)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.heat_stress_threshold_c == 28.0
    assert model.ky_heat == 0.9

    _clear(gdf)


def test_ensure_settings_table_migrates_a_pre_heat_schema(gdf: GeoDataFarm):
    # Reproduces upgrading a farm's database from before the heat columns
    # existed, but after variety/spacing already did.
    gdf.db.execute_sql("DROP TABLE IF EXISTS public.crop_model_settings")
    gdf.db.execute_sql(
        "CREATE TABLE public.crop_model_settings (crop_name text NOT NULL,"
        " variety text NOT NULL DEFAULT '',"
        " potential_yield_t_ha double precision,"
        " ky_nitrogen double precision, season_n_demand_kg_ha double precision,"
        " reference_spacing_mm double precision, spacing_sensitivity double precision,"
        " PRIMARY KEY (crop_name, variety))")
    gdf.db.execute_sql(
        "INSERT INTO public.crop_model_settings (crop_name, potential_yield_t_ha)"
        " VALUES (%s, %s)", params=(_CROP, 62.0))

    settings.ensure_settings_table(gdf.db)

    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 62.0
    settings.save_overrides(gdf.db, _CROP, ky_heat=1.1)
    model = settings.effective_crop_model(gdf.db, _CROP)
    assert model.potential_yield_t_ha == 62.0
    assert model.ky_heat == 1.1

    _clear(gdf)


def test_save_and_apply_curve_shape_overrides(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(
        gdf.db, _CROP, gdd_base_c=5.0, kc_ini=0.45, kc_mid=1.1, kc_end=0.4,
        kc_ini_end_gdd=200.0, kc_mid_end_gdd=800.0, season_end_gdd=1200.0,
        root_depth_min_cm=12.0, root_depth_max_cm=50.0, root_depth_full_gdd=650.0,
        n_uptake_midpoint_gdd=550.0, n_uptake_steepness=0.01)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.gdd_base_c == 5.0
    assert (model.kc_ini, model.kc_mid, model.kc_end) == (0.45, 1.1, 0.4)
    assert (model.kc_ini_end_gdd, model.kc_mid_end_gdd, model.season_end_gdd) == (
        200.0, 800.0, 1200.0)
    assert (model.root_depth_min_cm, model.root_depth_max_cm, model.root_depth_full_gdd) == (
        12.0, 50.0, 650.0)
    assert (model.n_uptake_midpoint_gdd, model.n_uptake_steepness) == (550.0, 0.01)

    _clear(gdf)


def test_save_overrides_rejects_a_curve_shape_combination_validate_shape_rejects(
        gdf: GeoDataFarm):
    _clear(gdf)

    try:
        settings.save_overrides(
            gdf.db, _CROP, kc_ini_end_gdd=900.0, kc_mid_end_gdd=200.0)
        assert False, 'expected a ValueError'
    except ValueError as e:
        assert 'stage' in str(e).lower() or 'gdd' in str(e).lower()
    # Nothing should have been saved - the whole write was rejected up front.
    assert settings.get_overrides(gdf.db, _CROP) == {}


def test_save_overrides_validates_against_the_existing_effective_model(gdf: GeoDataFarm):
    # A save that only touches one threshold must still be validated
    # against whatever's *already* saved for the others, not in isolation -
    # otherwise two individually-fine saves could combine into a broken
    # curve with neither call ever raising.
    _clear(gdf)
    settings.save_overrides(gdf.db, _CROP, kc_mid_end_gdd=300.0)

    try:
        # Now kc_ini_end_gdd (default ~150-230 depending on crop) combined
        # with the already-saved kc_mid_end_gdd=300 might still be fine -
        # force a real conflict by pushing it past that.
        settings.save_overrides(gdf.db, _CROP, kc_ini_end_gdd=350.0)
        assert False, 'expected a ValueError'
    except ValueError:
        pass
    # The first save must survive - the second was rejected before writing.
    assert settings.get_overrides(gdf.db, _CROP) == {'kc_mid_end_gdd': 300.0}

    _clear(gdf)


def test_ensure_settings_table_migrates_a_pre_curve_shape_schema(gdf: GeoDataFarm):
    # Reproduces upgrading a farm's database from before the curve-shape
    # columns existed, but after variety/spacing/heat already did.
    gdf.db.execute_sql("DROP TABLE IF EXISTS public.crop_model_settings")
    gdf.db.execute_sql(
        "CREATE TABLE public.crop_model_settings (crop_name text NOT NULL,"
        " variety text NOT NULL DEFAULT '',"
        " potential_yield_t_ha double precision,"
        " ky_nitrogen double precision, season_n_demand_kg_ha double precision,"
        " reference_spacing_mm double precision, spacing_sensitivity double precision,"
        " heat_stress_threshold_c double precision, ky_heat double precision,"
        " PRIMARY KEY (crop_name, variety))")
    gdf.db.execute_sql(
        "INSERT INTO public.crop_model_settings (crop_name, potential_yield_t_ha)"
        " VALUES (%s, %s)", params=(_CROP, 71.0))

    settings.ensure_settings_table(gdf.db)

    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 71.0
    settings.save_overrides(gdf.db, _CROP, gdd_base_c=6.0)
    model = settings.effective_crop_model(gdf.db, _CROP)
    assert model.potential_yield_t_ha == 71.0
    assert model.gdd_base_c == 6.0

    _clear(gdf)


def test_save_and_apply_potassium_phosphorus_magnesium_overrides(gdf: GeoDataFarm):
    _clear(gdf)

    settings.save_overrides(
        gdf.db, _CROP, ky_potassium=0.9, season_k_demand_kg_ha=190.0,
        season_p_demand_kg_ha=28.0, season_mg_demand_kg_ha=14.0,
        k_uptake_midpoint_gdd=580.0, k_uptake_steepness=0.011)
    model = settings.effective_crop_model(gdf.db, _CROP)

    assert model.ky_potassium == 0.9
    assert model.season_k_demand_kg_ha == 190.0
    assert model.season_p_demand_kg_ha == 28.0
    assert model.season_mg_demand_kg_ha == 14.0
    assert model.k_uptake_midpoint_gdd == 580.0
    assert model.k_uptake_steepness == 0.011

    _clear(gdf)


def test_ensure_settings_table_migrates_a_pre_potassium_phosphorus_magnesium_schema(
        gdf: GeoDataFarm):
    # Reproduces upgrading a farm's database from before the potassium/
    # phosphorus/magnesium columns existed, but after variety/spacing/heat/
    # curve-shape (including the later stage-Ky and kc_late_start_gdd
    # additions) already did.
    gdf.db.execute_sql("DROP TABLE IF EXISTS public.crop_model_settings")
    gdf.db.execute_sql(
        "CREATE TABLE public.crop_model_settings (crop_name text NOT NULL,"
        " variety text NOT NULL DEFAULT '',"
        " potential_yield_t_ha double precision,"
        " ky_initial double precision, ky_development double precision,"
        " ky_mid_season double precision, ky_late_season double precision,"
        " ky_nitrogen double precision, season_n_demand_kg_ha double precision,"
        " reference_spacing_mm double precision, spacing_sensitivity double precision,"
        " heat_stress_threshold_c double precision, ky_heat double precision,"
        " gdd_base_c double precision,"
        " root_depth_min_cm double precision, root_depth_max_cm double precision,"
        " root_depth_full_gdd double precision,"
        " kc_ini double precision, kc_mid double precision, kc_end double precision,"
        " kc_ini_end_gdd double precision, kc_mid_end_gdd double precision,"
        " kc_late_start_gdd double precision, season_end_gdd double precision,"
        " n_uptake_midpoint_gdd double precision, n_uptake_steepness double precision,"
        " PRIMARY KEY (crop_name, variety))")
    gdf.db.execute_sql(
        "INSERT INTO public.crop_model_settings (crop_name, potential_yield_t_ha)"
        " VALUES (%s, %s)", params=(_CROP, 84.0))

    settings.ensure_settings_table(gdf.db)

    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 84.0
    settings.save_overrides(gdf.db, _CROP, season_k_demand_kg_ha=200.0)
    model = settings.effective_crop_model(gdf.db, _CROP)
    assert model.potential_yield_t_ha == 84.0
    assert model.season_k_demand_kg_ha == 200.0

    _clear(gdf)


def test_ensure_settings_table_migrates_a_pre_variety_schema(gdf: GeoDataFarm):
    # Reproduces upgrading a farm's database from before the variety
    # column existed, when the primary key was just crop_name.
    gdf.db.execute_sql("DROP TABLE IF EXISTS public.crop_model_settings")
    gdf.db.execute_sql(
        "CREATE TABLE public.crop_model_settings (crop_name text PRIMARY KEY,"
        " potential_yield_t_ha double precision,"
        " ky_nitrogen double precision, season_n_demand_kg_ha double precision)")
    gdf.db.execute_sql(
        "INSERT INTO public.crop_model_settings (crop_name, potential_yield_t_ha)"
        " VALUES (%s, %s)", params=(_CROP, 321.0))

    settings.ensure_settings_table(gdf.db)

    # The pre-existing row survives as this crop's crop-level (variety='')
    # settings, and a variety can now be saved alongside it without
    # clobbering it.
    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 321.0
    settings.save_overrides(gdf.db, _CROP, 'arsenal', ky_mid_season=1.7)
    assert settings.effective_crop_model(gdf.db, _CROP).potential_yield_t_ha == 321.0
    variety_model = settings.effective_crop_model(gdf.db, _CROP, variety='arsenal')
    assert variety_model.potential_yield_t_ha == 321.0
    assert variety_model.ky_mid_season == 1.7

    _clear(gdf)
    settings.reset_overrides(gdf.db, _CROP, 'arsenal')
