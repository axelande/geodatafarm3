"""Objectives O1 and O2: leave-one-field-year-out cross-validation, learning
curves, baselines, parameter stability and sensitivity runs, from exported
training examples.

Reads every ``*_training_examples.pkl`` in the data directory, merges the
per-nutrient rates from ``<farm>_ferti_rows.csv`` (see ``attach_nutrients``)
and writes, each with ``--suffix`` appended:

* ``cv_predictions.csv`` - one row per held-out example and method, with the
  relative-yield terms and the limiting factor derived from them.
* ``cv_metrics.csv`` - metrics per method at example level, at field-year
  level (the primary unit), and for subsets (with/without a nitrogen
  record, before/from 2018).
* ``cv_tests.csv`` - paired Wilcoxon tests on per-field-year mean absolute
  error.
* ``fitted_params.csv`` - fitted triple per fold, with edge flags.
* ``learning_curve.csv`` - RMSE against training field-years, with the
  k-matched training-mean baseline, and ``learning_curve_params.csv`` with
  the fitted parameters of every training subset.
* ``bootstrap_params.csv`` - fitted parameters over bootstrap resamples of
  field-years.
* ``objective_surface_py_floor.csv`` and ``objective_surface_kyn_floor.csv``.
* ``summary_stats.csv`` - variance decomposition and other single numbers.

The fitting routine mirrors ``_fit_crop_model`` in
``database_scripts/crop_simulation.py`` (same ranges, same 6-step coarse-to-
fine grid) but is copied here so the analysis does not import the QGIS task
machinery. Keep the two in sync if the plugin's search changes.

Run through ``run_in_qgis_env.bat``.
"""
import argparse
import csv
import glob
import itertools
import math
import os
import pickle  # nosec B403 - loads only the pickles export_training_examples.py wrote
import random
from collections import defaultdict
from dataclasses import replace as dataclasses_replace

import paper_common as pc

season_water_model = pc.import_plugin_module('support_scripts.season_water_model')
crop_models = pc.import_plugin_module('support_scripts.crop_models')
estimate_season = season_water_model.estimate_season

try:
    from scipy.stats import wilcoxon
except ImportError:  # scipy is not shipped in the OSGeo4W Python
    from stats_fallback import wilcoxon

# Mirrors crop_simulation.py's module constants.
GRID_STEPS = 6
POTENTIAL_YIELD_RANGE_FACTOR = (0.4, 2.5)
KY_NITROGEN_RANGE = (0.0, 3.0)
MIN_YIELD_FLOOR_RANGE = (0.0, 1.0)
# Learning curve: k training field-years, a bounded number of random
# combinations per k (one fit is ~432 season evaluations).
MAX_COMBINATIONS = 25
LEARNING_CURVE_K = (1, 2, 3, 4, 6, 8, 12, 16, 20)
RANDOM_SEED = 20260926
# A factor counts as limiting only when it actually reduces yield.
LIMITING_THRESHOLD = 0.95

# How a field-year with no logged application of a nutrient is treated.
# 'floor' is the plugin's behaviour: the nutrient is modelled with zero
# applied, so its relative yield sits at the floor (0.3 by default) and caps
# the estimate. 'unmodelled' passes None instead, so the nutrient drops out
# of the Liebig combination for that field-year and only water (and any
# logged nutrient) limits yield. Set from the command line; see main().
UNLOGGED_NUTRIENTS = 'floor'


def linspace(lo, hi, steps):
    if steps <= 1 or hi <= lo:
        return [lo]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def _nutrient(record):
    if UNLOGGED_NUTRIENTS == 'unmodelled' and not record:
        return None
    return record


def run(model, ex):
    return estimate_season(
        ex.weather, ex.crop, ex.clay, ex.organic_matter, ex.irrigation_by_date,
        fertilizer_kg_n_by_date=_nutrient(ex.fertilizer_kg_n_by_date),
        fertilizer_kg_k_by_date=_nutrient(ex.fertilizer_kg_k_by_date),
        crop_model=model, spacing_mm=ex.spacing_mm,
        planting_date=ex.season_from if ex.planting_date_logged else None)


def predict(model, ex):
    return run(model, ex).estimated_yield_t_ha or 0.0


def limiting_from(season):
    """The factor with the lowest relative yield among those modelled, or
    'none' when nothing reduces yield below LIMITING_THRESHOLD. The model's
    own label is 'none' whenever no nutrient is modelled, whatever the
    water term says, so it is not used here."""
    factors = [('water', season.relative_yield_water)]
    if season.nitrogen_modeled:
        factors.append(('nitrogen', season.relative_yield_nitrogen))
    if season.potassium_modeled:
        factors.append(('potassium', season.relative_yield_potassium))
    name, value = min(factors, key=lambda f: f[1])
    return name if value < LIMITING_THRESHOLD else 'none'


def sse(model, examples):
    return sum((predict(model, ex) - ex.actual_yield_t_ha) ** 2 for ex in examples)


def fit(base_model, examples):
    """Coarse-to-fine grid search identical to the plugin's."""
    py0 = base_model.potential_yield_t_ha

    def search(py_range, kyn_range, floor_range):
        best, best_sse = None, None
        for py in linspace(*py_range, GRID_STEPS):
            for kyn in linspace(*kyn_range, GRID_STEPS):
                for floor in linspace(*floor_range, GRID_STEPS):
                    cand = dataclasses_replace(
                        base_model, potential_yield_t_ha=py, ky_nitrogen=kyn,
                        min_relative_yield_nitrogen=floor)
                    value = sse(cand, examples)
                    if best_sse is None or value < best_sse:
                        best, best_sse = (py, kyn, floor), value
        return best, best_sse

    coarse_py = (py0 * POTENTIAL_YIELD_RANGE_FACTOR[0], py0 * POTENTIAL_YIELD_RANGE_FACTOR[1])
    (py, kyn, floor), _ = search(coarse_py, KY_NITROGEN_RANGE, MIN_YIELD_FLOOR_RANGE)
    py_step = (coarse_py[1] - coarse_py[0]) / (GRID_STEPS - 1)
    kyn_step = (KY_NITROGEN_RANGE[1] - KY_NITROGEN_RANGE[0]) / (GRID_STEPS - 1)
    floor_step = (MIN_YIELD_FLOOR_RANGE[1] - MIN_YIELD_FLOOR_RANGE[0]) / (GRID_STEPS - 1)
    (py, kyn, floor), _ = search(
        (max(coarse_py[0], py - py_step), min(coarse_py[1], py + py_step)),
        (max(KY_NITROGEN_RANGE[0], kyn - kyn_step), min(KY_NITROGEN_RANGE[1], kyn + kyn_step)),
        (max(MIN_YIELD_FLOOR_RANGE[0], floor - floor_step),
         min(MIN_YIELD_FLOOR_RANGE[1], floor + floor_step)))
    fitted = dataclasses_replace(
        base_model, potential_yield_t_ha=round(py, 1), ky_nitrogen=round(kyn, 2),
        min_relative_yield_nitrogen=round(floor, 2))
    edge = {
        'py_at_edge': int(py <= coarse_py[0] + 1e-9 or py >= coarse_py[1] - 1e-9),
        'kyn_at_edge': int(kyn <= KY_NITROGEN_RANGE[0] + 1e-9 or kyn >= KY_NITROGEN_RANGE[1] - 1e-9),
        'floor_at_edge': int(floor <= MIN_YIELD_FLOOR_RANGE[0] + 1e-9
                             or floor >= MIN_YIELD_FLOOR_RANGE[1] - 1e-9),
    }
    return fitted, edge


def fit_py_only(base_model, examples):
    """One-parameter arm: potential yield alone, same range, 25 + 25 steps."""
    py0 = base_model.potential_yield_t_ha
    lo, hi = py0 * POTENTIAL_YIELD_RANGE_FACTOR[0], py0 * POTENTIAL_YIELD_RANGE_FACTOR[1]

    def search(a, b, steps):
        best, best_sse = None, None
        for py in linspace(a, b, steps):
            value = sse(dataclasses_replace(base_model, potential_yield_t_ha=py), examples)
            if best_sse is None or value < best_sse:
                best, best_sse = py, value
        return best

    py = search(lo, hi, 25)
    step = (hi - lo) / 24
    py = search(max(lo, py - step), min(hi, py + step), 25)
    return dataclasses_replace(base_model, potential_yield_t_ha=round(py, 1))


_VARIETY_ALIASES = {'qa': 'queen_anne', 'queenanne': 'queen_anne', 'kingedward': 'king_edvard',
                    'king_edward': 'king_edvard', 'kingedvard': 'king_edvard'}


def canonical_variety(name):
    """The journal spells the same cultivar several ways (Queen Anne,
    QueenAnne, qa, queen_anne); one key per cultivar."""
    key = (name or '').strip().lower().replace(' ', '_')
    return _VARIETY_ALIASES.get(key, key)


def field_years_of(examples):
    return {(ex.field_name, ex.year) for ex in examples}


def fit_variety_potential_yield(fitted, train, min_field_years=2):
    """Variety-aware calibration, the way the plugin fits per (crop,
    variety): with the crop-level nitrogen factor and floor from ``fitted``
    held fixed, potential yield is refitted on each variety's own training
    examples when that variety occurs in at least ``min_field_years``
    training field-years. Returns {variety: potential_yield}; any other
    variety keeps the crop-level value."""
    by_variety = defaultdict(list)
    for ex in train:
        by_variety[canonical_variety(ex.variety)].append(ex)
    out = {}
    for variety, exs in by_variety.items():
        if variety and len(field_years_of(exs)) >= min_field_years:
            out[variety] = fit_py_only(fitted, exs).potential_yield_t_ha
    return out


def variety_model(fitted, variety_py, ex):
    py = variety_py.get(canonical_variety(ex.variety))
    return dataclasses_replace(fitted, potential_yield_t_ha=py) if py else fitted


def load_field_ec(data_dir, min_cells=300):
    """Mean shallow EM38 conductivity per field from the cell exports, as a
    standardised score across the fields that have one (0 for a field
    without a survey)."""
    means = {}
    for path in glob.glob(os.path.join(data_dir, '*_cells_*.csv')):
        field = os.path.basename(path).split('_cells_')[1][:-4]
        with open(path, newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        if 'soil_eca_1' not in rows[0]:
            continue
        values = [float(r['soil_eca_1']) for r in rows if r['soil_eca_1'] not in ('', None)
                  and float(r['soil_eca_1']) > 0]
        if len(values) >= min_cells:
            means[field] = sum(values) / len(values)
    if len(means) < 3:
        return {}
    mu = sum(means.values()) / len(means)
    sd = (sum((v - mu) ** 2 for v in means.values()) / (len(means) - 1)) ** 0.5 or 1.0
    return {field: (v - mu) / sd for field, v in means.items()}


EC_SLOPES = [round(-0.6 + 1.2 * i / 24, 3) for i in range(25)]


def fit_ec_slope(fitted, train, ec_z):
    """Per-field potential-yield offset from the field's conductivity score:
    PY_field = PY x (1 + b z_field). b is fitted by grid with the crop-level
    parameters held fixed; a field without a survey has z = 0."""
    best, best_sse = 0.0, None
    for b in EC_SLOPES:
        value = sum((predict(ec_model(fitted, b, ec_z, ex), ex) - ex.actual_yield_t_ha) ** 2
                    for ex in train)
        if best_sse is None or value < best_sse:
            best, best_sse = b, value
    return best


def ec_model(fitted, b, ec_z, ex):
    z = ec_z.get(ex.field_name, 0.0)
    return dataclasses_replace(fitted, potential_yield_t_ha=max(
        1.0, fitted.potential_yield_t_ha * (1 + b * z)))


def metrics(pairs):
    """pairs: list of (predicted, observed)."""
    n = len(pairs)
    if n == 0:
        return {}
    errors = [p - o for p, o in pairs]
    observed = [o for _, o in pairs]
    mean_obs = sum(observed) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    ss_res = sum(e * e for e in errors)
    ss_tot = sum((o - mean_obs) ** 2 for o in observed)
    return {
        'n': n,
        'rmse': round(rmse, 2),
        'rrmse_pct': round(100 * rmse / mean_obs, 1) if mean_obs else '',
        'mae': round(sum(abs(e) for e in errors) / n, 2),
        'bias': round(sum(errors) / n, 2),
        'nse': round(1 - ss_res / ss_tot, 2) if ss_tot > 0 else '',
    }


def group_key(ex):
    return crop_models.get_crop_model(ex.crop).name


def load_ferti_rows(data_dir, farm):
    """Per-nutrient journal rows from ``<farm>_ferti_rows.csv`` (written by
    export_training_examples.py), as {field: [(date, nutrient, rate, crop)]}.
    The plugin's own loader dropped PDF-imported rows whose ``table_`` is
    set (fixed on 2026-09-26); the analysis rebuilds the nutrient record
    from the raw rows so the export did not have to be repeated."""
    path = os.path.join(data_dir, '{}_ferti_rows.csv'.format(farm))
    rows = defaultdict(list)
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8') as handle:
        for r in csv.DictReader(handle):
            try:
                rate = float(str(r.get('rate', '')).replace(',', '.'))
            except ValueError:
                continue
            rows[r['field']].append((r['date_'], (r.get('nutrient') or '').strip().upper(),
                                     rate, (r.get('crop') or '').lower()))
    return rows


def attach_nutrients(ex, ferti_rows):
    """Replace the example's N and K records with the journal's rows for
    its field and season. Rows for another crop on the same field (the
    journal assigns rows by field, and a field can carry two crops in one
    season) are skipped when the row names a crop and it is not the
    example's crop."""
    crop = crop_models.get_crop_model(ex.crop).name
    crop_words = {'potato': ('potat',), 'wheat': ('vete', 'wheat'), 'barley': ('korn', 'barley'),
                  'rye': ('råg', 'rye'), 'oats': ('havre', 'oat')}.get(crop, ())
    n_by_date, k_by_date = {}, {}
    for date, nutrient, rate, row_crop in ferti_rows.get(ex.field_name, []):
        if not (ex.season_from <= date <= ex.season_to):
            continue
        if row_crop and crop_words and not any(w in row_crop for w in crop_words):
            continue
        if nutrient == 'N':
            n_by_date[date] = n_by_date.get(date, 0.0) + rate
        elif nutrient == 'K':
            k_by_date[date] = k_by_date.get(date, 0.0) + rate
    return dataclasses_replace(ex, fertilizer_kg_n_by_date=n_by_date,
                               fertilizer_kg_k_by_date=k_by_date)


def load_examples(data_dir, exclude_years=(), exclude_field_years=()):
    groups = defaultdict(list)  # (farm, crop) -> examples
    for path in sorted(glob.glob(os.path.join(data_dir, '*_training_examples.pkl'))):
        with open(path, 'rb') as handle:
            payload = pickle.load(handle)  # nosec B301 - our own export, see module docstring
        ferti_rows = load_ferti_rows(data_dir, payload['farm'])
        for ex in payload['examples']:
            if ex.year in exclude_years or (ex.field_name, ex.year) in exclude_field_years:
                continue
            if ferti_rows:
                ex = attach_nutrients(ex, ferti_rows)
            groups[(payload['farm'], group_key(ex))].append(ex)
    with_n = sum(1 for exs in groups.values() for ex in exs if ex.fertilizer_kg_n_by_date)
    with_k = sum(1 for exs in groups.values() for ex in exs if ex.fertilizer_kg_k_by_date)
    print('examples with a nitrogen record: {}, potassium: {}'.format(with_n, with_k))
    return groups


def write_csv(path, rows):
    if not rows:
        print('nothing to write for', os.path.basename(path))
        return
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=pc.DATA_DIR)
    parser.add_argument('--min-examples', type=int, default=3)
    parser.add_argument('--unlogged-nutrients', choices=('floor', 'unmodelled'),
                        default='floor', help='see UNLOGGED_NUTRIENTS')
    parser.add_argument('--suffix', default='', help='appended to every output file name')
    parser.add_argument('--exclude-years', default='',
                        help='comma-separated harvest years to drop, e.g. 2015,2016,2017')
    parser.add_argument('--exclude-field-years', default='',
                        help='comma-separated FIELD:YEAR pairs to drop, e.g. F07:2019,F15:2021')
    parser.add_argument('--no-learning-curve', action='store_true')
    parser.add_argument('--bootstrap', type=int, default=0,
                        help='number of bootstrap resamples of field-years (0 = none)')
    args = parser.parse_args()
    global UNLOGGED_NUTRIENTS
    UNLOGGED_NUTRIENTS = args.unlogged_nutrients
    rng = random.Random(RANDOM_SEED)  # nosec B311 - statistical resampling, not security
    exclude_years = {int(y) for y in args.exclude_years.split(',') if y}
    exclude_fy = {(p.split(':')[0], int(p.split(':')[1]))
                  for p in args.exclude_field_years.split(',') if p}
    groups = load_examples(args.data, exclude_years, exclude_fy)
    if not groups:
        raise SystemExit('No *_training_examples.pkl found in {}'.format(args.data))
    out = pc.ensure_dir(args.data)
    sfx = args.suffix
    ec_z = load_field_ec(args.data)
    print('fields with a conductivity score: {}'.format(len(ec_z)))

    predictions, params, curve, curve_params, boot, summary = [], [], [], [], [], []
    for (farm, crop), examples in sorted(groups.items()):
        if len(examples) < args.min_examples:
            print('skip {} {}: only {} examples'.format(farm, crop, len(examples)))
            continue
        base = crop_models.get_crop_model(crop)
        print('{} {}: {} examples'.format(farm, crop, len(examples)))

        # The unit of cross-validation is the field-year: every variety
        # example of one field-year shares its weather, soil, irrigation
        # and field, so they are held out together.
        field_years = defaultdict(list)
        for ex in examples:
            field_years[(ex.field_name, ex.year)].append(ex)
        groups_list = [field_years[key] for key in sorted(field_years)]
        print('  {} field-years'.format(len(groups_list)))
        by_field_years = defaultdict(dict)  # field -> {year: mean observed}
        for (field, year), exs in field_years.items():
            by_field_years[field][year] = sum(e.actual_yield_t_ha for e in exs) / len(exs)

        # Variance decomposition of observed yield: between vs within field-year
        obs_all = [e.actual_yield_t_ha for e in examples]
        grand = sum(obs_all) / len(obs_all)
        ss_total = sum((o - grand) ** 2 for o in obs_all)
        ss_within = sum((e.actual_yield_t_ha - by_field_years[e.field_name][e.year]) ** 2
                        for e in examples)
        summary.append(dict(farm=farm, crop=crop, key='observed_mean', value=round(grand, 2)))
        summary.append(dict(farm=farm, crop=crop, key='observed_sd_sample',
                            value=round(math.sqrt(ss_total / (len(obs_all) - 1)), 2)))
        summary.append(dict(farm=farm, crop=crop, key='within_field_year_share_of_variance_pct',
                            value=round(100 * ss_within / ss_total, 1)))
        ranges = [max(e.actual_yield_t_ha for e in exs) - min(e.actual_yield_t_ha for e in exs)
                  for exs in field_years.values() if len(exs) > 1]
        ranges.sort()
        summary.append(dict(farm=farm, crop=crop, key='within_field_year_range_median',
                            value=round(ranges[len(ranges) // 2], 1)))
        summary.append(dict(farm=farm, crop=crop, key='within_field_year_range_max',
                            value=round(max(ranges), 1)))

        # Leave-one-field-year-out
        for i, held_group in enumerate(groups_list):
            train = [ex for g in groups_list[:i] + groups_list[i + 1:] for ex in g]
            fitted, edge = fit(base, train)
            fitted_py = fit_py_only(base, train)
            variety_py = fit_variety_potential_yield(fitted, train)
            b_ec = fit_ec_slope(fitted, train, ec_z) if ec_z else 0.0
            farm_mean = sum(t.actual_yield_t_ha for t in train) / len(train)
            held_field, held_year = held_group[0].field_name, held_group[0].year
            other_years = [v for y, v in by_field_years[held_field].items() if y != held_year]
            field_mean = sum(other_years) / len(other_years) if other_years else None
            train_by_variety = defaultdict(list)
            for t in train:
                train_by_variety[canonical_variety(t.variety)].append(t.actual_yield_t_ha)
            for held in held_group:
                common = dict(farm=farm, crop=crop, field=held.field_name, year=held.year,
                              variety=held.variety or '',
                              variety_fitted=int(canonical_variety(held.variety) in variety_py),
                              n_record=int(bool(held.fertilizer_kg_n_by_date)),
                              k_record=int(bool(held.fertilizer_kg_k_by_date)),
                              observed=round(held.actual_yield_t_ha, 3))
                same_variety = train_by_variety.get(canonical_variety(held.variety), [])
                variety_mean = (sum(same_variety) / len(same_variety) if same_variety
                                else farm_mean)
                predictions.append(dict(common, method='variety_mean',
                                        predicted=round(variety_mean, 3), limiting_factor=''))
                for method, model in (('default', base), ('calibrated', fitted),
                                      ('calibrated_py_only', fitted_py),
                                      ('calibrated_variety', variety_model(fitted, variety_py, held)),
                                      ('calibrated_ec', ec_model(fitted, b_ec, ec_z, held))):
                    season = run(model, held)
                    predictions.append(dict(
                        common, method=method,
                        predicted=round(season.estimated_yield_t_ha or 0.0, 3),
                        ry_water=round(season.relative_yield_water, 3),
                        ry_nitrogen=round(season.relative_yield_nitrogen, 3)
                        if season.nitrogen_modeled else '',
                        ry_potassium=round(season.relative_yield_potassium, 3)
                        if season.potassium_modeled else '',
                        limiting_factor=limiting_from(season)))
                predictions.append(dict(common, method='farm_mean',
                                        predicted=round(farm_mean, 3), limiting_factor=''))
                if field_mean is not None:
                    predictions.append(dict(common, method='field_mean',
                                            predicted=round(field_mean, 3), limiting_factor=''))
            params.append(dict(farm=farm, crop=crop, held_out_field=held_field,
                               held_out_year=held_year,
                               n_train_field_years=len(groups_list) - 1, n_train=len(train),
                               potential_yield_t_ha=fitted.potential_yield_t_ha,
                               ky_nitrogen=fitted.ky_nitrogen,
                               min_relative_yield_nitrogen=fitted.min_relative_yield_nitrogen,
                               py_only_potential_yield_t_ha=fitted_py.potential_yield_t_ha,
                               varieties_fitted=len(variety_py), ec_slope=b_ec,
                               variety_py=' '.join('{}={}'.format(v, p)
                                                   for v, p in sorted(variety_py.items())),
                               **edge))

        # Learning curve: k is the number of training field-years; the
        # k-matched baseline predicts every test example with the mean of
        # the k training field-years.
        n = len(groups_list)
        if not args.no_learning_curve:
            for k in [k for k in LEARNING_CURVE_K if k < n]:
                if math.comb(n, k) <= MAX_COMBINATIONS:
                    combos = list(itertools.combinations(range(n), k))
                else:
                    combos = {tuple(sorted(rng.sample(range(n), k)))
                              for _ in range(MAX_COMBINATIONS * 3)}
                    combos = list(combos)[:MAX_COMBINATIONS]
                print('  learning curve k={} ({} combinations)'.format(k, len(combos)))
                for combo in combos:
                    train = [ex for i in combo for ex in groups_list[i]]
                    test = [ex for i in range(n) if i not in combo for ex in groups_list[i]]
                    fitted, _ = fit(base, train)
                    fitted_py = fit_py_only(base, train)
                    variety_py = fit_variety_potential_yield(fitted, train)
                    train_mean = sum(t.actual_yield_t_ha for t in train) / len(train)
                    tv = defaultdict(list)
                    for t in train:
                        tv[canonical_variety(t.variety)].append(t.actual_yield_t_ha)
                    m = metrics([(predict(fitted, t), t.actual_yield_t_ha) for t in test])
                    m_py = metrics([(predict(fitted_py, t), t.actual_yield_t_ha) for t in test])
                    m_var = metrics([(predict(variety_model(fitted, variety_py, t), t),
                                      t.actual_yield_t_ha) for t in test])
                    m_mean = metrics([(train_mean, t.actual_yield_t_ha) for t in test])
                    m_vmean = metrics([
                        (sum(tv[canonical_variety(t.variety)]) / len(tv[canonical_variety(t.variety)])
                         if tv.get(canonical_variety(t.variety)) else train_mean,
                         t.actual_yield_t_ha) for t in test])
                    curve.append(dict(farm=farm, crop=crop, k=k, n_test=len(test),
                                      rmse=m['rmse'], bias=m['bias'],
                                      rmse_py_only=m_py['rmse'],
                                      rmse_variety=m_var['rmse'],
                                      rmse_train_mean=m_mean['rmse'],
                                      rmse_variety_mean=m_vmean['rmse']))
                    curve_params.append(dict(
                        farm=farm, crop=crop, k=k,
                        potential_yield_t_ha=fitted.potential_yield_t_ha,
                        ky_nitrogen=fitted.ky_nitrogen,
                        min_relative_yield_nitrogen=fitted.min_relative_yield_nitrogen,
                        py_only_potential_yield_t_ha=fitted_py.potential_yield_t_ha))

        # Bootstrap over field-years
        for b in range(args.bootstrap):
            sample = [groups_list[rng.randrange(n)] for _ in range(n)]
            train = [ex for g in sample for ex in g]
            fitted, _ = fit(base, train)
            boot.append(dict(farm=farm, crop=crop, resample=b,
                             potential_yield_t_ha=fitted.potential_yield_t_ha,
                             ky_nitrogen=fitted.ky_nitrogen,
                             min_relative_yield_nitrogen=fitted.min_relative_yield_nitrogen))

        # Objective surfaces at the all-data fit
        fitted, _ = fit(base, examples)
        surface = []
        for py in linspace(base.potential_yield_t_ha * POTENTIAL_YIELD_RANGE_FACTOR[0],
                           base.potential_yield_t_ha * POTENTIAL_YIELD_RANGE_FACTOR[1], 25):
            for floor in linspace(0.0, 1.0, 21):
                cand = dataclasses_replace(base, potential_yield_t_ha=py,
                                           ky_nitrogen=fitted.ky_nitrogen,
                                           min_relative_yield_nitrogen=floor)
                surface.append(dict(potential_yield_t_ha=round(py, 2), floor=round(floor, 3),
                                    sse=round(sse(cand, examples), 3)))
        write_csv(os.path.join(out, 'objective_surface_py_floor{}.csv'.format(sfx)), surface)
        surface = []
        for kyn in linspace(*KY_NITROGEN_RANGE, 25):
            for floor in linspace(0.0, 1.0, 21):
                cand = dataclasses_replace(base, potential_yield_t_ha=fitted.potential_yield_t_ha,
                                           ky_nitrogen=kyn, min_relative_yield_nitrogen=floor)
                surface.append(dict(ky_nitrogen=round(kyn, 3), floor=round(floor, 3),
                                    sse=round(sse(cand, examples), 3)))
        write_csv(os.path.join(out, 'objective_surface_kyn_floor{}.csv'.format(sfx)), surface)
        summary.append(dict(farm=farm, crop=crop, key='all_data_fit_potential_yield',
                            value=fitted.potential_yield_t_ha))
        summary.append(dict(farm=farm, crop=crop, key='all_data_fit_ky_nitrogen',
                            value=fitted.ky_nitrogen))
        summary.append(dict(farm=farm, crop=crop, key='all_data_fit_floor',
                            value=fitted.min_relative_yield_nitrogen))

    write_csv(os.path.join(out, 'cv_predictions{}.csv'.format(sfx)), predictions)
    write_csv(os.path.join(out, 'fitted_params{}.csv'.format(sfx)), params)
    write_csv(os.path.join(out, 'learning_curve{}.csv'.format(sfx)), curve)
    write_csv(os.path.join(out, 'learning_curve_params{}.csv'.format(sfx)), curve_params)
    write_csv(os.path.join(out, 'bootstrap_params{}.csv'.format(sfx)), boot)
    write_csv(os.path.join(out, 'summary_stats{}.csv'.format(sfx)), summary)

    # Metrics: example level, field-year level (primary), and subsets
    rows = []
    methods = ['default', 'calibrated', 'calibrated_py_only', 'calibrated_variety',
               'calibrated_ec', 'farm_mean', 'variety_mean', 'field_mean']
    per_fy = defaultdict(lambda: defaultdict(list))  # (field, year) -> method -> preds; obs list
    obs_fy = defaultdict(list)
    for p in predictions:
        per_fy[(p['field'], p['year'])][p['method']].append(p['predicted'])
        if p['method'] == 'default':
            obs_fy[(p['field'], p['year'])].append(p['observed'])
    subsets = {
        'all': lambda p: True,
        'with_n_record': lambda p: p['n_record'] == 1,
        'without_n_record': lambda p: p['n_record'] == 0,
        'before_2018': lambda p: p['year'] < 2018,
        'from_2018': lambda p: p['year'] >= 2018,
    }
    for method in methods:
        for name, keep in subsets.items():
            pairs = [(p['predicted'], p['observed']) for p in predictions
                     if p['method'] == method and keep(p)]
            if pairs:
                rows.append(dict(level='example', subset=name, method=method, **metrics(pairs)))
        # field-year level: mean prediction vs mean observed per field-year
        fy_pairs = []
        for key, preds in per_fy.items():
            if method in preds:
                fy_pairs.append((key, sum(preds[method]) / len(preds[method]),
                                 sum(obs_fy[key]) / len(obs_fy[key])))
        for name, keep in subsets.items():
            pairs = [(pr, ob) for (field, year), pr, ob in fy_pairs
                     if keep({'n_record': int(any(p['n_record'] for p in predictions
                                                  if (p['field'], p['year']) == (field, year))),
                              'year': year})]
            if pairs:
                rows.append(dict(level='field_year', subset=name, method=method,
                                 **metrics(pairs)))
    write_csv(os.path.join(out, 'cv_metrics{}.csv'.format(sfx)), rows)

    # Paired tests on per-field-year mean absolute error
    fy_err = defaultdict(dict)
    for key, preds in per_fy.items():
        ob = sum(obs_fy[key]) / len(obs_fy[key])
        for method, values in preds.items():
            fy_err[key][method] = abs(sum(values) / len(values) - ob)
    tests = []
    for a, b in (('default', 'calibrated'), ('calibrated', 'farm_mean'),
                 ('calibrated_py_only', 'calibrated'), ('calibrated_py_only', 'farm_mean'),
                 ('calibrated', 'field_mean'), ('calibrated_variety', 'calibrated'),
                 ('calibrated_variety', 'variety_mean'), ('calibrated_variety', 'farm_mean'),
                 ('variety_mean', 'farm_mean'), ('calibrated_ec', 'calibrated')):
        pairs = [(v[a], v[b]) for v in fy_err.values() if a in v and b in v]
        if len(pairs) >= 6:
            stat, pvalue = wilcoxon([x for x, _ in pairs], [y for _, y in pairs])
            wins = sum(1 for x, y in pairs if x < y)
            tests.append(dict(first=a, second=b, n_field_years=len(pairs),
                              first_lower_in=wins, wilcoxon_w=round(stat, 1),
                              p_value=round(pvalue, 4)))
            print('Wilcoxon |error| {} vs {}: W={:.1f} p={:.4f} n={} ({} lower)'.format(
                a, b, stat, pvalue, len(pairs), wins))
    write_csv(os.path.join(out, 'cv_tests{}.csv'.format(sfx)), tests)
    print('Done. Outputs in', out)


if __name__ == '__main__':
    main()
