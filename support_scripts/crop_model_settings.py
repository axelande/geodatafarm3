"""Persistent, per-crop (and optionally per-variety) overrides for
support_scripts.crop_models.CROP_MODELS.

crop_models.py's defaults are literature-informed planning assumptions, not
site-calibrated values (see that module's docstring) - this lets a user
adjust the parameters that drive the yield estimate (see
widgets/crop_settings_dialog.py) and have that adjustment stick for every
field that uses that crop, in this farm's own database, rather than
editing plugin source code. Two tiers of overridable field, shown as two
separate sections in the settings dialog: the "big lever" fields (yield,
Ky/Ky-N/Ky-heat, spacing) most farmers have an intuition for, and the
curve-shape fields (Kc stages, GDD thresholds, rooting depth, nitrogen-
uptake timing) that control *when* during the season water/nitrogen
demand ramps up and down rather than how much overall - shown behind an
"Advanced" toggle since getting these wrong (e.g. stages out of order)
breaks the curve outright rather than just shifting a number, which is
why :func:`save_overrides` validates the resulting model (see
crop_models.validate_shape) before persisting a curve-shape change.

A field left NULL in the database means "use crop_models.py's built-in
default for that field" - a row doesn't have to override everything at
once.

Overrides are two-level: a crop-level row (``variety = ''``) applies to
every field/cell using that crop, and an optional variety-level row layers
on top of it for cells whose own imported planting data names a specific
variety (see database_scripts/crop_simulation.py's per-cell crop/variety
resolution) - e.g. "arsenal" starts from potato's crop-level settings and
only needs to override what's actually different for that variety.
"""
from dataclasses import replace

from psycopg2 import sql as pgsql

from . import crop_models
from . import db_rows

__author__ = 'Axel Horteborn'

_TABLE = 'crop_model_settings'
# The "big lever" fields shown in the settings dialog's main section - see
# module docstring for how these differ from CURVE_SHAPE_FIELDS below.
BIG_LEVER_FIELDS = (
    'potential_yield_t_ha', 'ky_initial', 'ky_development', 'ky_mid_season',
    'ky_late_season', 'ky_nitrogen', 'min_relative_yield_nitrogen', 'season_n_demand_kg_ha',
    'ky_potassium', 'min_relative_yield_potassium', 'season_k_demand_kg_ha',
    'season_p_demand_kg_ha', 'season_mg_demand_kg_ha',
    'reference_spacing_mm', 'spacing_sensitivity',
    'heat_stress_threshold_c', 'ky_heat')
# The curve-shape fields shown behind the settings dialog's "Advanced"
# toggle - see module docstring. Validated together (crop_models.
# validate_shape) before saving, since these can produce a genuinely
# broken curve if set inconsistently, unlike BIG_LEVER_FIELDS.
CURVE_SHAPE_FIELDS = (
    'gdd_base_c', 'root_depth_min_cm', 'root_depth_max_cm', 'root_depth_full_gdd',
    'kc_ini', 'kc_mid', 'kc_end', 'kc_ini_end_gdd', 'kc_mid_end_gdd',
    'kc_late_start_gdd', 'season_end_gdd',
    'n_uptake_midpoint_gdd', 'n_uptake_steepness',
    'k_uptake_midpoint_gdd', 'k_uptake_steepness')
# Every field a user can override here, big-lever or curve-shape.
OVERRIDABLE_FIELDS = BIG_LEVER_FIELDS + CURVE_SHAPE_FIELDS
# The key used for a crop-level row (as opposed to a specific variety's).
_CROP_LEVEL = ''


def _normalize(name):
    return (name or '').strip().lower()


def ensure_settings_table(db):
    """Creates the overrides table if it doesn't exist yet - lazy, like
    every other table in this codebase (see e.g.
    import_data/handle_irrigation.py's ``_store_dated_operation``).

    Also migrates a table created before the ``variety`` column existed
    (when the primary key was just ``crop_name``) by adding the column -
    existing rows become that crop's crop-level settings (``variety =
    ''``) - and widening the primary key to ``(crop_name, variety)``; and
    a table created before a later batch of :data:`OVERRIDABLE_FIELDS`
    existed (spacing, then heat), by adding those columns - see
    :func:`_ensure_columns_exist`."""
    column_defs = pgsql.SQL(', ').join(
        pgsql.SQL('{} double precision').format(pgsql.Identifier(f))
        for f in OVERRIDABLE_FIELDS)
    db.execute_sql(pgsql.SQL(
        "CREATE TABLE IF NOT EXISTS public.{tbl} (crop_name text NOT NULL,"
        " variety text NOT NULL DEFAULT '', {cols},"
        " PRIMARY KEY (crop_name, variety))"
    ).format(tbl=pgsql.Identifier(_TABLE), cols=column_defs))
    has_variety = db_rows(db.execute_and_return(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
        " AND table_name = %s AND column_name = 'variety'", params=(_TABLE,)))
    if not has_variety:
        db.execute_sql(pgsql.SQL(
            "ALTER TABLE public.{tbl} ADD COLUMN variety text NOT NULL DEFAULT ''"
        ).format(tbl=pgsql.Identifier(_TABLE)))
        pkey_rows = db_rows(db.execute_and_return(
            "SELECT constraint_name FROM information_schema.table_constraints"
            " WHERE table_schema = 'public' AND table_name = %s"
            " AND constraint_type = 'PRIMARY KEY'", params=(_TABLE,)))
        if pkey_rows:
            db.execute_sql(pgsql.SQL("ALTER TABLE public.{tbl} DROP CONSTRAINT {c}").format(
                tbl=pgsql.Identifier(_TABLE), c=pgsql.Identifier(pkey_rows[0][0])))
        db.execute_sql(pgsql.SQL(
            "ALTER TABLE public.{tbl} ADD PRIMARY KEY (crop_name, variety)"
        ).format(tbl=pgsql.Identifier(_TABLE)))
    _ensure_columns_exist(db, ('reference_spacing_mm', 'spacing_sensitivity'))
    _ensure_columns_exist(db, ('heat_stress_threshold_c', 'ky_heat'))
    _ensure_columns_exist(db, CURVE_SHAPE_FIELDS)
    # Both added after CURVE_SHAPE_FIELDS's original batch above - their
    # own separate migration calls, not folded into it, since
    # _ensure_columns_exist only checks its first column and would
    # otherwise wrongly conclude "already migrated" for a table that has
    # every earlier curve-shape column but not these newer ones.
    _ensure_columns_exist(db, ('ky_initial', 'ky_development', 'ky_mid_season', 'ky_late_season'))
    _ensure_columns_exist(db, ('kc_late_start_gdd',))
    # Potassium/phosphorus/magnesium - added later still, so their own
    # separate batches too (see the comment above these two calls).
    _ensure_columns_exist(db, ('ky_potassium', 'season_k_demand_kg_ha',
                              'k_uptake_midpoint_gdd', 'k_uptake_steepness'))
    _ensure_columns_exist(db, ('season_p_demand_kg_ha', 'season_mg_demand_kg_ha'))
    _ensure_columns_exist(db, ('min_relative_yield_nitrogen',))
    _ensure_columns_exist(db, ('min_relative_yield_potassium',))


def _ensure_columns_exist(db, columns):
    """Adds whichever of ``columns`` are actually missing from the settings
    table. Migrates a table created before that batch existed (see
    :func:`ensure_settings_table`'s docstring).

    Checked column-by-column, not just the first one: if a batch was ever
    left partially applied (e.g. an earlier ALTER TABLE call for it failed
    partway through, for any reason), checking only the first column would
    see it as "already migrated" forever and never add the rest - silently
    breaking every future SELECT that lists the missing ones (see
    :func:`get_overrides`, which lists every :data:`OVERRIDABLE_FIELDS`
    column; :func:`support_scripts.db_rows` turns that failure into a
    silent empty result, not a visible error - see its own docstring),
    with no way to self-heal. Checking every column lets this call fix
    that on its very next run instead."""
    existing = {row[0] for row in db_rows(db.execute_and_return(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s"
        " AND column_name = ANY(%s)", params=(_TABLE, list(columns))))}
    missing = [c for c in columns if c not in existing]
    if not missing:
        return
    add_clause = pgsql.SQL(', ').join(
        pgsql.SQL('ADD COLUMN {} double precision').format(pgsql.Identifier(c))
        for c in missing)
    db.execute_sql(pgsql.SQL("ALTER TABLE public.{tbl} {add}").format(
        tbl=pgsql.Identifier(_TABLE), add=add_clause))


def get_overrides(db, crop_name, variety=_CROP_LEVEL):
    """The raw saved overrides for ``crop_name``/``variety``, as
    ``{field_name: value}`` - only the fields that are actually overridden
    (not NULL) are included, so a caller populating a settings form can
    tell "explicitly set to X" apart from "using the default" cleanly.

    Pass ``variety=''`` (the default) for the crop-level row; a specific
    variety's row is entirely separate from - and layered on top of, see
    :func:`effective_crop_model` - its crop's row.

    Returns
    -------
    dict
    """
    ensure_settings_table(db)
    key = _normalize(crop_name)
    if not key:
        return {}
    rows = db_rows(db.execute_and_return(
        pgsql.SQL("SELECT {cols} FROM public.{tbl} WHERE crop_name = %s AND variety = %s").format(
            cols=pgsql.SQL(', ').join(pgsql.Identifier(f) for f in OVERRIDABLE_FIELDS),
            tbl=pgsql.Identifier(_TABLE)),
        params=(key, _normalize(variety))))
    if not rows:
        return {}
    return {field: value for field, value in zip(OVERRIDABLE_FIELDS, rows[0])
            if value is not None}


def effective_crop_model(db, crop_name, variety=None):
    """The :class:`crop_models.CropModel` that should actually drive a
    simulation for ``crop_name`` (and, optionally, a specific ``variety``
    of it): the built-in default (or, for an unrecognised name,
    :data:`crop_models.DEFAULT_CROP_MODEL`), with any saved crop-level
    overrides applied, then any saved variety-level overrides applied on
    top of those - each level only touches the fields it explicitly set.

    ``variety=None`` (the default) or an empty/unrecognised variety name
    just returns the crop-level model, unchanged from before this
    parameter existed.

    Returns
    -------
    crop_models.CropModel
    """
    base = crop_models.get_crop_model(crop_name)
    crop_overrides = get_overrides(db, crop_name)
    model = replace(base, **crop_overrides) if crop_overrides else base
    variety_key = _normalize(variety)
    if not variety_key:
        return model
    variety_overrides = get_overrides(db, crop_name, variety_key)
    return replace(model, **variety_overrides) if variety_overrides else model


def save_overrides(db, crop_name, variety=_CROP_LEVEL, **fields):
    """Saves (upserts) one or more overrides for ``crop_name``/``variety``.
    Only fields in :data:`OVERRIDABLE_FIELDS` may be passed; omitted
    fields are left as whatever was already saved (not reset to NULL) -
    use :func:`reset_overrides` to clear a field back to the default.

    Pass ``variety=''`` (the default) to save crop-level settings, or a
    variety name to save that variety's own overrides instead - see
    :func:`effective_crop_model` for how the two combine.

    If ``fields`` touches any of :data:`CURVE_SHAPE_FIELDS`, the resulting
    *model* (this crop/variety's current effective settings with ``fields``
    applied on top - not just the fields being saved in isolation, since a
    change to one threshold can conflict with an existing override of
    another) is validated via :func:`crop_models.validate_shape` before
    anything is written; a nonsensical combination raises ``ValueError``
    and nothing is saved.

    Raises
    ------
    ValueError
        For an unrecognised field name, or a curve-shape combination
        :func:`crop_models.validate_shape` rejects.
    """
    ensure_settings_table(db)
    unknown = set(fields) - set(OVERRIDABLE_FIELDS)
    if unknown:
        raise ValueError('Not an overridable crop model field: {}'.format(sorted(unknown)))
    if not fields:
        return
    key = _normalize(crop_name)
    if not key:
        return
    if set(fields) & set(CURVE_SHAPE_FIELDS):
        current = effective_crop_model(db, crop_name, variety=variety or None)
        crop_models.validate_shape(replace(current, **fields))
    field_names = list(fields.keys())
    insert_cols = pgsql.SQL(', ').join(pgsql.Identifier(f) for f in field_names)
    insert_placeholders = pgsql.SQL(', ').join(pgsql.SQL('%s') for _ in field_names)
    set_clause = pgsql.SQL(', ').join(
        pgsql.SQL('{col} = EXCLUDED.{col}').format(col=pgsql.Identifier(f))
        for f in field_names)
    query = pgsql.SQL(
        "INSERT INTO public.{tbl} (crop_name, variety, {cols}) VALUES (%s, %s, {placeholders})"
        " ON CONFLICT (crop_name, variety) DO UPDATE SET {set_clause}"
    ).format(tbl=pgsql.Identifier(_TABLE), cols=insert_cols,
            placeholders=insert_placeholders, set_clause=set_clause)
    params = tuple([key, _normalize(variety)] + [fields[f] for f in field_names])
    db.execute_sql(query, params=params)


def reset_overrides(db, crop_name, variety=_CROP_LEVEL):
    """Clears every saved override for ``crop_name``/``variety``,
    reverting it to crop_models.py's built-in default (or, for a variety,
    back to its crop's settings - see :func:`effective_crop_model`).
    Resetting a crop's own (``variety=''``) row never touches its
    varieties' own saved overrides, and vice versa."""
    ensure_settings_table(db)
    key = _normalize(crop_name)
    if not key:
        return
    db.execute_sql(
        pgsql.SQL("DELETE FROM public.{tbl} WHERE crop_name = %s AND variety = %s")
        .format(tbl=pgsql.Identifier(_TABLE)), params=(key, _normalize(variety)))
