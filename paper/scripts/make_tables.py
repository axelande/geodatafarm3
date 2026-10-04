"""Tables 3 and 4 for the main text, and Supplementary Tables S3 to S5, as
Markdown from the analysis outputs.

Table 3: field-year-level cross-validation, six methods, two treatments.
Table 4: fertility-index variants, six rows, paired against yield-only.
S3: example-level metrics, subsets and paired tests.
S4: sensitivity runs.
S5: index sensitivity variants and crop transitions.

Plain Python; no QGIS needed.
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
DATA = os.path.join(PAPER, 'data')
OUT = os.path.join(PAPER, 'tables')

METHOD = {'default': 'Literature defaults',
          'calibrated': 'Farm-calibrated, three parameters',
          'calibrated_py_only': 'Farm-calibrated, potential yield only',
          'calibrated_variety': 'Farm-calibrated, potential yield per variety',
          'calibrated_ec': 'Farm-calibrated, with conductivity offset per field',
          'farm_mean': 'Baseline: farm mean',
          'variety_mean': 'Baseline: variety mean',
          'field_mean': 'Baseline: field mean'}
ORDER = list(METHOD)
TREATMENT = {'_floor': 'Unlogged nutrient at its floor (plugin default)',
             '_unmodelled': 'Unlogged nutrient not modelled (post hoc)'}


def read(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def metric_rows(suffix, level, subset='all'):
    rows = [r for r in read('cv_metrics{}.csv'.format(suffix))
            if r['level'] == level and r['subset'] == subset]
    rows.sort(key=lambda r: ORDER.index(r['method']) if r['method'] in ORDER else 9)
    return rows


def fmt(value, digits=1):
    try:
        return '{:.{d}f}'.format(float(value), d=digits)
    except (TypeError, ValueError):
        return ''


def table3():
    lines = ['Table 3. How well each method predicted the yield of a field-year it had not seen '
             '(leave-one-field-year-out, 22 potato field-years). Typical error is the RMSE in t/ha '
             'and as a percentage of the mean observed yield (58 t/ha); bias is the mean signed '
             'error; NSE compares with predicting the overall mean yield (0 = no better, negative '
             '= worse). The first block is the plugin as implemented (an unlogged nutrient modelled '
             'as zero applied), the second the post hoc diagnostic variant (an unlogged nutrient '
             'treated as unknown); the baselines do not depend on the treatment. The last block '
             'repeats the main comparison at the quality-screened level, without the three '
             'field-years above 80 t/ha.', '',
             '| Method | Typical error, t/ha | Typical error, % | Bias, t/ha | NSE |',
             '|---|---|---|---|---|']

    def block(label, suffix, methods):
        lines.append('| *{}* | | | | |'.format(label))
        for r in metric_rows(suffix, 'field_year'):
            if r['method'] in methods:
                lines.append('| {} | {} | {} | {} | {} |'.format(
                    METHOD[r['method']], fmt(r['rmse']), fmt(r['rrmse_pct'], 0),
                    fmt(r['bias']), fmt(r['nse'], 2)))
    block('Implemented plugin default, all operational records (22 field-years)', '_floor',
          ('default', 'calibrated'))
    block('Post hoc variant, all operational records (22 field-years)', '_unmodelled',
          ('default', 'calibrated', 'calibrated_py_only', 'calibrated_variety'))
    block('Baselines, all operational records (22 field-years)', '_unmodelled',
          ('farm_mean', 'variety_mean'))
    block('Post hoc variant and baselines, quality-screened records (19 field-years)',
          '_unmodelled_nosuspect', ('calibrated', 'calibrated_variety', 'farm_mean', 'variety_mean'))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'table3_cv_metrics.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('wrote table3')


def tableS3():
    lines = ['Table S3. Cross-validation detail, unlogged nutrient not modelled. (a) Metrics at '
             'example level (48 variety observations) and field-year level for every method, '
             'with the field-mean baseline where a field has another potato year. (b) Field-'
             'year-level metrics on subsets. (c) Paired comparisons: in how many of the 22 '
             'field-years the first method had the smaller absolute error, with the Wilcoxon '
             'signed-rank statistic and two-sided p.', '', '(a)', '',
             '| Method | Level | n | RMSE | rRMSE % | MAE | Bias | NSE |', '|---|---|---|---|---|---|---|---|']
    for level in ('field_year', 'example'):
        for r in metric_rows('_unmodelled', level):
            lines.append('| {} | {} | {} | {} | {} | {} | {} | {} |'.format(
                METHOD.get(r['method'], r['method']), level.replace('_', '-'), r['n'],
                fmt(r['rmse']), fmt(r['rrmse_pct']), fmt(r['mae']), fmt(r['bias']), fmt(r['nse'], 2)))
    subsets = [('with_n_record', 'With a nitrogen record'),
               ('without_n_record', 'Without a nitrogen record'),
               ('before_2018', 'Seasons 2015 to 2017 (no irrigation record)'),
               ('from_2018', 'Seasons 2018 to 2025 (irrigation recorded)')]
    lines += ['', '(b)', '', '| Subset | Method | n | RMSE | rRMSE % | Bias |', '|---|---|---|---|---|---|']
    for key, label in subsets:
        first = True
        for r in metric_rows('_unmodelled', 'field_year', key):
            if r['method'] in ('default', 'calibrated', 'calibrated_variety', 'farm_mean',
                               'variety_mean'):
                lines.append('| {} | {} | {} | {} | {} | {} |'.format(
                    label if first else '', METHOD[r['method']], r['n'], fmt(r['rmse']),
                    fmt(r['rrmse_pct']), fmt(r['bias'])))
                first = False
    tests = read('cv_tests_unmodelled.csv')
    lines += ['', '(c)', '', '| Comparison | Field-years | First has lower error in | W | p |',
              '|---|---|---|---|---|']
    for t in tests:
        lines.append('| {} vs {} | {} | {} | {} | {} |'.format(
            METHOD.get(t['first'], t['first']), METHOD.get(t['second'], t['second']),
            t['n_field_years'], t['first_lower_in'], t['wilcoxon_w'], t['p_value']))
    with open(os.path.join(OUT, 'tableS3_cv_detail.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('wrote tableS3')


def tableS4():
    lines = ['Table S4. Sensitivity of the field-year-level cross-validation (unlogged nutrient '
             'not modelled) to the seasons without an irrigation record and to the three '
             'field-years with observed yields above 80 t/ha.', '',
             '| Run | Method | n | RMSE | rRMSE % | Bias | NSE |', '|---|---|---|---|---|---|---|']
    for suffix, label in (('_unmodelled', 'All 22 field-years'),
                          ('_unmodelled_from2018', '2018 to 2025 only (17 field-years)'),
                          ('_unmodelled_nosuspect', 'Without F07 2019, F15 2021, F16 2017')):
        first = True
        for r in metric_rows(suffix, 'field_year'):
            if r['method'] in ('default', 'calibrated', 'calibrated_variety', 'farm_mean',
                               'variety_mean'):
                lines.append('| {} | {} | {} | {} | {} | {} | {} |'.format(
                    label if first else '', METHOD[r['method']], r['n'], fmt(r['rmse']),
                    fmt(r['rrmse_pct']), fmt(r['bias']), fmt(r['nse'], 2)))
                first = False
        params = read('fitted_params{}.csv'.format(suffix))
        if params:
            py = sorted(float(p['potential_yield_t_ha']) for p in params)
            lines.append('| | fitted potential yield, median (range) | {} | {} ({} to {}) | | | |'.format(
                len(py), py[len(py) // 2], py[0], py[-1]))
    struct = read('structure_sensitivity.csv')
    if struct:
        lines += ['', 'Model structure: the fitted relative-yield terms of each fold recombined by the '
                  'Liebig minimum (as implemented) or multiplicatively, without refitting, '
                  'field-year level:', '',
                  '| Combination | n | RMSE | rRMSE % | Bias |', '|---|---|---|---|---|']
        for r in struct:
            lines.append('| {} | {} | {} | {} | {} |'.format(
                r['combination'], r['n'], r['rmse'], r['rrmse_pct'], r['bias']))
    prof = read('parameter_profiles.csv')
    if prof:
        import collections
        lines += ['', 'Practical identifiability: range of each parameter over which the sum of squared '
                  'errors, minimised over the other axis of the objective surface at the all-data fit, '
                  'stays within 5 % of its minimum:', '',
                  '| Parameter | Range within 5 % of minimum SSE | Search range | Fine grid step |',
                  '|---|---|---|---|']
        by = collections.defaultdict(list)
        for r in prof:
            by[r['parameter']].append((float(r['value']), float(r['min_sse_over_other_axis'])))
        meta = {'potential_yield_t_ha': ('Potential yield (t/ha)', '18 to 112.5', '7.6'),
                'ky_nitrogen': ('Ky nitrogen', '0 to 3', '0.24'),
                'min_relative_yield_nitrogen': ('Nitrogen floor', '0 to 1', '0.08')}
        for key, pts in by.items():
            m = min(v for _, v in pts)
            inside = [x for x, v in pts if v <= 1.05 * m]
            lines.append('| {} | {:.2f} to {:.2f} | {} | {} |'.format(
                meta[key][0], min(inside), max(inside), meta[key][1], meta[key][2]))
    with open(os.path.join(OUT, 'tableS4_sensitivity.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('wrote tableS4')


PRETTY = {'yield_only': 'Previous yield only',
          'soil_only': 'Soil only',
          'combined_equal': 'Yield + soil, one weight per source (plugin default)',
          'combined_grouped': 'Yield + soil, one weight per source group',
          'combined_datadriven': 'Yield + soil, weights from association with previous yield',
          'zscore_grouped': 'Yield + soil, z-score average, grouped weights',
          'combined_soil_w0.5': 'Plugin default, soil weight 0.5',
          'combined_soil_w2': 'Plugin default, soil weight 2',
          'combined_3cls': 'Plugin default, 3 classes',
          'combined_7cls': 'Plugin default, 7 classes',
          'combined_2y': 'Two previous yields + soil'}


def table4():
    rows = read('fertility_summary.csv')
    by = {r['variant']: r for r in rows}
    paired = {r['variant'].replace(' minus yield_only (paired)', ''): r for r in rows
              if r['variant'].endswith('(paired)')}
    lines = ['Table 4. How well each index variant ranked the cells of a field by their yield in '
             'the following season, on the 13 field-year pairs (8 fields) that have a soil layer. '
             'Spearman rho over all cells: 1 means the index ordered every cell correctly, 0 no better than '
             'chance. "Lower than yield-only" counts the pairs in which the variant did worse '
             'than the previous-yield map alone; 6 or 7 of 13 is what chance gives. Top minus '
             'bottom class: yield difference between the best and worst fifth of the field by '
             'index, as a percentage of the field mean. The yield-only row over all 21 pairs is '
             'given for reference; the class-separation test is in Table S5.', '',
             '| Index variant | Pairs | Spearman rho, median (IQR) | Lower than yield-only | Top minus bottom class, % |',
             '|---|---|---|---|---|']
    yo = by.get('yield_only')
    if yo:
        lines.append('| {} (all pairs) | {} | {} ({} to {}) | | {} |'.format(
            PRETTY['yield_only'], yo['n_pairs'], yo['spearman_median'], yo['spearman_q1'],
            yo['spearman_q3'], yo['class_diff_pct_median']))
    ys = by.get('yield_only | pairs with soil')
    if ys:
        lines.append('| {} (pairs with soil) | {} | {} ({} to {}) | | {} |'.format(
            PRETTY['yield_only'], ys['n_pairs'], ys['spearman_median'], ys['spearman_q1'],
            ys['spearman_q3'], ys['class_diff_pct_median']))
    for key in ('soil_only', 'combined_equal', 'combined_grouped', 'combined_datadriven',
                'zscore_grouped'):
        r, p = by.get(key), paired.get(key)
        if r:
            lines.append('| {} | {} | {} ({} to {}) | {} of {} | {} |'.format(
                PRETTY[key], r['n_pairs'], r['spearman_median'], r['spearman_q1'],
                r['spearman_q3'], p['lower_than_yield_only'] if p else '', r['n_pairs'],
                r['class_diff_pct_median']))
    with open(os.path.join(OUT, 'table4_fertility.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('wrote table4')


def tableS5():
    rows = read('fertility_summary.csv')
    by = {r['variant']: r for r in rows}
    lines = ['Table S5. Productivity index: sensitivity variants of the plugin default, the '
             'two-year variant, the per-field aggregation, crop transitions, and the sign tests '
             'for the paired comparisons of Table 4. Classes differ: share of pairs with '
             'Kruskal-Wallis p < 0.05 on the spatially thinned subsample (median thinned cells '
             'given).', '',
             '| Variant | Pairs (fields) | Spearman rho, median (IQR) | Classes differ | Thinned cells | Top minus bottom, % |',
             '|---|---|---|---|---|---|']
    for key in ('combined_soil_w0.5', 'combined_soil_w2', 'combined_3cls', 'combined_7cls',
                'combined_2y'):
        r = by.get(key)
        if r:
            lines.append('| {} | {} ({}) | {} ({} to {}) | {} % | {} | {} |'.format(
                PRETTY[key], r['n_pairs'], r['n_fields'], r['spearman_median'], r['spearman_q1'],
                r['spearman_q3'], int(round(100 * float(r['share_kw_p_below_0_05']))),
                r['n_thinned_median'], r['class_diff_pct_median']))
    lines += ['', 'Per field (median over a field\'s pairs) and by crop transition, previous yield only:',
              '', '| Grouping | Pairs (fields) | Spearman rho, median (IQR) |', '|---|---|---|']
    for r in rows:
        if r['variant'].endswith('| per field') or (r['variant'].startswith('yield_only | ')
                                                     and 'pairs with soil' not in r['variant']):
            label = r['variant'].replace('cereal_or_rape', 'cereal or rape').replace('->', 'to') \
                .replace('_', ' ')
            lines.append('| {} | {} ({}) | {} ({} to {}) |'.format(
                label, r['n_pairs'], r['n_fields'], r['spearman_median'], r['spearman_q1'],
                r['spearman_q3']))
    lines += ['', 'Sign tests, variant minus yield-only on the same pairs:', '',
              '| Variant | Pairs | Median difference (IQR) | Lower in | p |', '|---|---|---|---|---|']
    for r in rows:
        if r['variant'].endswith('(paired)'):
            name = r['variant'].replace(' minus yield_only (paired)', '')
            lines.append('| {} | {} | {} ({} to {}) | {} | {} |'.format(
                PRETTY.get(name, name), r['n_pairs'], r['spearman_median'], r['spearman_q1'],
                r['spearman_q3'], r['lower_than_yield_only'], r['sign_test_p']))
    src = read('fertility_sources.csv')
    if src and 'rho_with_residual_of_next_yield' in src[0]:
        import statistics
        lines += ['', 'Per-layer association with next-season yield and with the part of it not '
                  'explained by the previous yield map (rank of next yield regressed on rank of '
                  'previous yield; Spearman rho of each layer with the residual):', '',
                  '| Layer group | Layer-pair combinations | rho with next yield, median (min to max) | '
                  'abs rho with residual, median (max) | abs rho with residual above 0.2 |',
                  '|---|---|---|---|---|']
        for group, label in (('conductivity', 'EM38 conductivity'), ('laboratory', 'Laboratory sampling')):
            rows_g = [r for r in src if r['group'] == group
                      and r['rho_with_residual_of_next_yield'] not in ('nan', '')]
            if not rows_g:
                continue
            rn = [float(r['rho_with_next_yield']) for r in rows_g]
            rr = [abs(float(r['rho_with_residual_of_next_yield'])) for r in rows_g]
            lines.append('| {} | {} | {:.2f} ({:.2f} to {:.2f}) | {:.2f} ({:.2f}) | {} |'.format(
                label, len(rows_g), statistics.median(rn), min(rn), max(rn),
                statistics.median(rr), max(rr), sum(1 for v in rr if v > 0.2)))
    with open(os.path.join(OUT, 'tableS5_fertility_detail.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
    print('wrote tableS5')


if __name__ == '__main__':
    table3()
    table4()
    tableS3()
    tableS4()
    tableS5()
