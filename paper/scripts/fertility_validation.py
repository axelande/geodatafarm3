"""Objective O3: validate the fertility index against the following season.

Reads every ``*_cells_*.csv`` produced by ``export_grid_cells.py`` and, for
each field and each pair of consecutive harvest years (t-1, t), builds

* ``yield_only``        - yield(t-1) alone (a monotone transform of last
                          year's map: this measures year-to-year rank persistence)
* ``soil_only``         - the soil sources alone, equal weights per source
* ``combined_equal``    - yield(t-1) plus every soil source, one weight per
                          source (the plugin's default)
* ``combined_grouped``  - as above but weights per source group, so the
                          conductivity depths count as one source and the
                          laboratory columns as one, each group equal to yield
* ``combined_datadriven`` - weights proportional to each source's absolute
                          rank correlation with yield(t-1), with the rank
                          reversed for a negatively associated source; uses
                          only information available before season t
* ``zscore_grouped``    - standardised-score average instead of percentile
                          ranks, grouped weights (a conventional comparator)
* ``combined_soil_w0.5``, ``combined_soil_w2``, ``combined_3cls``,
  ``combined_7cls``     - sensitivity variants of the plugin default
* ``combined_2y``       - two previous yields plus soil, when t-2 exists

and scores each against yield(t) with Spearman rank correlation on all
cells, a Kruskal-Wallis test across classes on a spatially thinned subsample,
and the top-minus-bottom class yield difference on all cells as a percentage
of the field mean.

Outputs ``fertility_results.csv`` (one row per field, pair, variant),
``fertility_sources.csv`` (per-source rank correlations with sign) and
``fertility_summary.csv`` (per-variant medians, paired comparisons on the
pairs that have a soil source, and per-field aggregation).

Run through ``run_in_qgis_env.bat`` (imports the plugin's index module).
"""
import argparse
import csv
import glob
import math
import os
import re
import statistics
from collections import defaultdict

import paper_common as pc

fertility_index = pc.import_plugin_module('database_scripts.fertility_index')
combine_sources = fertility_index.combine_sources
classify_index = fertility_index.classify_index
percentile_ranks = fertility_index.percentile_ranks

import numpy as np
try:
    from scipy.stats import kruskal, spearmanr
except ImportError:  # scipy is not shipped in the OSGeo4W Python
    from stats_fallback import kruskal, spearmanr


# Exported soil columns that are not soil properties: sample number,
# sampling year, a prescription rate, a label.
NOT_A_PROPERTY = ('soil_provnr', 'soil_r', 'soil_rx_rate', 'soil_m_rkning')
# A source must cover at least this many cells to be used at all.
MIN_CELLS = 300
MIN_VALID_PAIR = 30


def harmonise_units(values):
    """A harvest column can mix t/ha and kg/ha within one year (F34 2023:
    median 11, 99th percentile 48 661). Bring the minority unit onto the
    majority's scale. Returns the values and the number converted."""
    valid = [v for v in values if v is not None]
    med = statistics.median(valid)
    converted = 0
    out = []
    for v in values:
        if v is None:
            out.append(None)
        elif med < 100 and v >= 1000:
            out.append(v / 1000.0)
            converted += 1
        elif med >= 1000 and 0 < v < 200:
            out.append(v * 1000.0)
            converted += 1
        else:
            out.append(v)
    return out, converted


def read_cells(path):
    with open(path, newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    keys = [k for k in rows[0] if k not in ('cell_id', 'x', 'y') and k not in NOT_A_PROPERTY
            and k != 'harvest_2000']
    data = {k: [float(r[k]) if r[k] not in ('', None) else None for r in rows] for k in keys}
    notes = {}
    for k in list(data):
        if k.startswith('soil_eca'):  # -1 or 0 marks no data
            data[k] = [v if v is not None and v > 0 else None for v in data[k]]
    for k in list(data):
        valid = [v for v in data[k] if v is not None]
        if len(valid) < MIN_CELLS or (k.startswith('harvest_') and statistics.median(valid) <= 0):
            del data[k]
            continue
        if k.startswith('harvest_'):
            data[k], converted = harmonise_units(data[k])
            if converted:
                notes[k] = converted
    xy = [(float(r['x']), float(r['y'])) for r in rows]
    if all(abs(x) <= 180 and abs(y) <= 90 for x, y in xy):
        lat0 = math.radians(sum(y for _, y in xy) / len(xy))
        xy = [(x * 111320.0 * math.cos(lat0), y * 110540.0) for x, y in xy]
    return data, xy, notes


def variogram_range(values, xy, max_lag=100.0, n_bins=20):
    """Crude empirical range: first lag where semivariance reaches 95 % of
    the sample variance; max_lag if never reached. The 100 m cap is
    deliberate: on these 5 to 15 ha fields a larger range means a field-
    scale trend, and thinning to it would leave too few cells to test."""
    pts = [(x, y, v) for (x, y), v in zip(xy, values) if v is not None]
    if len(pts) > 1500:
        step = len(pts) // 1500
        pts = pts[::step]
    if len(pts) < 30:
        return max_lag
    arr = np.array(pts)
    dx = arr[:, 0][:, None] - arr[:, 0][None, :]
    dy = arr[:, 1][:, None] - arr[:, 1][None, :]
    d = np.sqrt(dx * dx + dy * dy)
    g = 0.5 * (arr[:, 2][:, None] - arr[:, 2][None, :]) ** 2
    sill = np.var(arr[:, 2])
    edges = np.linspace(0, max_lag, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (d > lo) & (d <= hi)
        if mask.sum() < 30:
            continue
        if g[mask].mean() >= 0.95 * sill:
            return float(hi)
    return max_lag


def thin(indices, xy, spacing):
    kept, occupied = [], set()
    for i in indices:
        key = (int(xy[i][0] // spacing), int(xy[i][1] // spacing))
        if key not in occupied:
            occupied.add(key)
            kept.append(i)
    return kept


def score(index_values, classes, target, xy, class_count):
    valid = [i for i, (v, t) in enumerate(zip(index_values, target))
             if v is not None and t is not None]
    if len(valid) < MIN_VALID_PAIR:
        return None
    rho, _ = spearmanr([index_values[i] for i in valid], [target[i] for i in valid])
    target_masked = [target[i] if i in set(valid) else None for i in range(len(target))]
    rng = variogram_range(target_masked, xy)
    thinned = thin(valid, xy, max(rng, 4.0))
    groups = defaultdict(list)
    for i in thinned:
        groups[classes[i]].append(target[i])
    filled = [g for g in groups.values() if len(g) >= 3]
    kw_p = kruskal(*filled).pvalue if len(filled) >= 2 else float('nan')
    # Class difference on ALL cells, relative to the field mean.
    all_groups = defaultdict(list)
    for i in valid:
        all_groups[classes[i]].append(target[i])
    top, bottom = all_groups.get(class_count, []), all_groups.get(1, [])
    field_mean = statistics.mean(target[i] for i in valid)
    diff = (100 * (statistics.mean(top) - statistics.mean(bottom)) / field_mean
            if top and bottom and field_mean else float('nan'))
    return dict(n_cells=len(valid), n_thinned=len(thinned), range_m=round(rng, 1),
                spearman=round(float(rho), 3), kw_p=round(float(kw_p), 4),
                class_top_minus_bottom_pct=round(diff, 1))


def crop_guess(values):
    valid = [v for v in values if v is not None]
    med = statistics.median(valid)
    if med >= 1000:
        med = med / 1000.0
    return 'potato' if med >= 20 else 'cereal_or_rape'


def source_group(name):
    if name.startswith('y'):
        return 'yield'
    if name.startswith('soil_eca'):
        return 'conductivity'
    return 'laboratory'


def grouped_weights(sources):
    counts = defaultdict(int)
    for name in sources:
        counts[source_group(name)] += 1
    return {name: 1.0 / counts[source_group(name)] for name in sources}


def rho_with(a, b):
    idx = [i for i, (x, y) in enumerate(zip(a, b)) if x is not None and y is not None]
    if len(idx) < MIN_VALID_PAIR:
        return float('nan'), len(idx)
    return float(spearmanr([a[i] for i in idx], [b[i] for i in idx])[0]), len(idx)


def datadriven(sources, y_prev):
    """Weights |rho| with previous yield, sign-reversed sources flipped."""
    adjusted, weights = {}, {}
    for name, values in sources.items():
        if name == 'y':
            adjusted[name], weights[name] = values, 1.0
            continue
        rho, _ = rho_with(values, y_prev)
        if math.isnan(rho) or abs(rho) < 0.05:
            continue
        weights[name] = abs(rho)
        adjusted[name] = values if rho >= 0 else [None if v is None else -v for v in values]
    return adjusted, weights


def zscore_index(sources, weights):
    z = {}
    for name, values in sources.items():
        valid = [v for v in values if v is not None]
        mu, sd = statistics.mean(valid), statistics.pstdev(valid) or 1.0
        z[name] = [None if v is None else (v - mu) / sd for v in values]
    out = []
    for i in range(len(next(iter(z.values())))):
        num = den = 0.0
        for name, values in z.items():
            if values[i] is not None:
                num += weights[name] * values[i]
                den += weights[name]
        out.append(num / den if den else None)
    # rescale to 0-100 ranks so the same class boundaries apply
    return percentile_ranks(out)


def build(sources, weights, class_count, kind='rank'):
    if kind == 'zscore':
        index_values = zscore_index(sources, weights or {k: 1.0 for k in sources})
    else:
        index_values = combine_sources(sources, weights)
    classes = classify_index(index_values, None, class_count)
    return index_values, classes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=pc.DATA_DIR)
    args = parser.parse_args()
    results, source_rows, unit_notes = [], [], []
    for path in sorted(glob.glob(os.path.join(args.data, '*_cells_*.csv'))):
        match = re.match(r'(.+)_cells_(F\d+)\.csv', os.path.basename(path))
        farm, field = match.groups()
        data, xy, notes = read_cells(path)
        for k, n in notes.items():
            unit_notes.append(dict(farm=farm, field=field, column=k, cells_converted=n))
        years = sorted(int(k.split('_')[1]) for k in data if k.startswith('harvest_'))
        soil = {k: data[k] for k in data if k in ('clay', 'humus', 'ph') or k.startswith('soil_')}
        for prev, cur in zip(years[:-1], years[1:]):
            if cur - prev != 1:
                continue
            y_prev, y_cur = data['harvest_{}'.format(prev)], data['harvest_{}'.format(cur)]
            crop_prev, crop_cur = crop_guess(y_prev), crop_guess(y_cur)
            # per-source association with the target, with sign, and with the
            # part of the target not explained by the previous yield rank
            # (rank of y_cur regressed on rank of y_prev; residual rank)
            idx = [i for i, (a, b) in enumerate(zip(y_prev, y_cur)) if a is not None and b is not None]
            resid = [None] * len(y_cur)
            if len(idx) >= MIN_VALID_PAIR:
                rp = percentile_ranks([y_prev[i] for i in idx]); rc = percentile_ranks([y_cur[i] for i in idx])
                mp, mc = statistics.mean(rp), statistics.mean(rc)
                sxy = sum((a - mp) * (b - mc) for a, b in zip(rp, rc)); sxx = sum((a - mp) ** 2 for a in rp) or 1.0
                slope = sxy / sxx
                for i, a, b in zip(idx, rp, rc):
                    resid[i] = b - (mc + slope * (a - mp))
            for name, values in dict(y=y_prev, **soil).items():
                rho_cur, n_cur = rho_with(values, y_cur)
                rho_prev, _ = rho_with(values, y_prev) if name != 'y' else (float('nan'), 0)
                rho_res, _ = rho_with(values, resid) if name != 'y' else (float('nan'), 0)
                source_rows.append(dict(farm=farm, field=field, year_from=prev, year_to=cur,
                                        source=name, group=source_group(name), n=n_cur,
                                        rho_with_next_yield=round(rho_cur, 3),
                                        rho_with_previous_yield=round(rho_prev, 3),
                                        rho_with_residual_of_next_yield=round(rho_res, 3)))
            variants = {'yield_only': ({'y': y_prev}, None, 5, 'rank')}
            if soil:
                full = dict(y=y_prev, **soil)
                gw = grouped_weights(full)
                variants['soil_only'] = (dict(soil), None, 5, 'rank')
                variants['combined_equal'] = (full, None, 5, 'rank')
                variants['combined_grouped'] = (full, gw, 5, 'rank')
                adj, dw = datadriven(full, y_prev)
                variants['combined_datadriven'] = (adj, dw, 5, 'rank')
                variants['zscore_grouped'] = (full, gw, 5, 'zscore')
                variants['combined_soil_w0.5'] = (full, dict({k: 0.5 for k in soil}, y=1.0), 5, 'rank')
                variants['combined_soil_w2'] = (full, dict({k: 2.0 for k in soil}, y=1.0), 5, 'rank')
                variants['combined_3cls'] = (full, None, 3, 'rank')
                variants['combined_7cls'] = (full, None, 7, 'rank')
                if prev - 1 in years:
                    variants['combined_2y'] = (
                        dict(y1=data['harvest_{}'.format(prev - 1)], y=y_prev, **soil), None, 5, 'rank')
            for name, (sources, weights, class_count, kind) in variants.items():
                index_values, classes = build(sources, weights, class_count, kind)
                s = score(index_values, classes, y_cur, xy, class_count)
                if s:
                    results.append(dict(farm=farm, field=field, year_from=prev, year_to=cur,
                                        crop_from=crop_prev, crop_to=crop_cur,
                                        has_soil=int(bool(soil)),
                                        soil_sources=' '.join(sorted(soil)), variant=name, **s))
                    print(farm, field, prev, cur, name, s['spearman'])
    if not results:
        raise SystemExit('No usable field pairs found.')
    with open(os.path.join(args.data, 'fertility_results.csv'), 'w', newline='',
              encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    with open(os.path.join(args.data, 'fertility_sources.csv'), 'w', newline='',
              encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)
    if unit_notes:
        with open(os.path.join(args.data, 'fertility_unit_notes.csv'), 'w', newline='',
                  encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(unit_notes[0]))
            writer.writeheader()
            writer.writerows(unit_notes)

    def summarise(label, rows):
        rho = [r['spearman'] for r in rows]
        diffs = [r['class_top_minus_bottom_pct'] for r in rows
                 if not math.isnan(r['class_top_minus_bottom_pct'])]
        return dict(variant=label, n_pairs=len(rows), n_fields=len({r['field'] for r in rows}),
                    spearman_median=round(statistics.median(rho), 3),
                    spearman_q1=round(float(np.percentile(rho, 25)), 3),
                    spearman_q3=round(float(np.percentile(rho, 75)), 3),
                    share_kw_p_below_0_05=round(sum(r['kw_p'] < 0.05 for r in rows) / len(rows), 2),
                    class_diff_pct_median=round(statistics.median(diffs), 1) if diffs else '',
                    n_thinned_median=int(statistics.median(r['n_thinned'] for r in rows)))

    summary = []
    by_variant = defaultdict(list)
    for r in results:
        by_variant[r['variant']].append(r)
    for variant, rows in sorted(by_variant.items()):
        summary.append(summarise(variant, rows))
    # Same-pairs comparison: yield-only restricted to pairs with a soil source
    soil_pairs = {(r['field'], r['year_from']) for r in results if r['has_soil']}
    yo_soil = [r for r in by_variant['yield_only'] if (r['field'], r['year_from']) in soil_pairs]
    if yo_soil:
        summary.append(summarise('yield_only | pairs with soil', yo_soil))
    # Per-field aggregation: median rho per field, then across fields
    for variant in ('yield_only', 'combined_equal', 'combined_grouped', 'soil_only'):
        per_field = defaultdict(list)
        for r in by_variant.get(variant, []):
            per_field[r['field']].append(r['spearman'])
        if per_field:
            meds = [statistics.median(v) for v in per_field.values()]
            summary.append(dict(variant=variant + ' | per field', n_pairs=len(meds),
                                n_fields=len(meds), spearman_median=round(statistics.median(meds), 3),
                                spearman_q1=round(float(np.percentile(meds, 25)), 3),
                                spearman_q3=round(float(np.percentile(meds, 75)), 3)))
    # By transition, yield-only
    by_tr = defaultdict(list)
    for r in by_variant['yield_only']:
        by_tr[r['crop_from'] + ' -> ' + r['crop_to']].append(r)
    for tr, rows in sorted(by_tr.items()):
        summary.append(summarise('yield_only | ' + tr, rows))
    # Paired differences against yield-only on the same pairs
    yo = {(r['field'], r['year_from']): r['spearman'] for r in by_variant['yield_only']}
    for variant in ('combined_equal', 'combined_grouped', 'combined_datadriven',
                    'zscore_grouped', 'soil_only'):
        rows = by_variant.get(variant, [])
        d = [r['spearman'] - yo[(r['field'], r['year_from'])] for r in rows
             if (r['field'], r['year_from']) in yo]
        if d:
            worse = sum(1 for x in d if x < 0)
            n = len(d)
            # two-sided sign test
            p = min(1.0, 2 * sum(math.comb(n, i) for i in range(0, min(worse, n - worse) + 1)) / 2 ** n)
            summary.append(dict(variant=variant + ' minus yield_only (paired)', n_pairs=n,
                                n_fields=len({r['field'] for r in rows}),
                                spearman_median=round(statistics.median(d), 3),
                                spearman_q1=round(float(np.percentile(d, 25)), 3),
                                spearman_q3=round(float(np.percentile(d, 75)), 3),
                                share_kw_p_below_0_05='', class_diff_pct_median='',
                                n_thinned_median='', lower_than_yield_only=worse,
                                sign_test_p=round(p, 4)))
    keys = []
    for row in summary:
        for k in row:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(args.data, 'fertility_summary.csv'), 'w', newline='',
              encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(summary)
    print('Wrote fertility_results.csv, fertility_sources.csv and fertility_summary.csv')


if __name__ == '__main__':
    main()
