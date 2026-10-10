"""Draw Figures 2 to 8 and S1 from the CSV outputs of the analysis scripts.

Reads from ``paper/data`` and writes PNG (300 dpi) and PDF to
``paper/figures``. Every figure that lacks its input is skipped with a
message. ``--suffix`` selects the cross-validation variant for Figures 3 to
6 and S1 (default ``_unmodelled``).

Palette: the first three categorical slots of the validated reference palette
(blue, orange, aqua), one blue sequential ramp for magnitudes. Print-safe:
thin marks, no dual axes, direct labels where a legend would be needed. The
farm is labelled "Farm A" in every figure.

Run through ``run_in_qgis_env.bat`` (matplotlib and numpy are available there).
"""
import argparse
import csv
import glob
import math
import os
import re
from collections import Counter, defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.ticker import MaxNLocator

import paper_common as pc

DATA, FIG = pc.DATA_DIR, pc.ensure_dir(pc.FIGURES_DIR)
SUFFIX = '_unmodelled'
FARM_LABEL = 'Farm A'

SERIES = {'default': '#2a78d6', 'calibrated': '#eb6834', 'farm_mean': '#1baf7a',
          'calibrated_py_only': '#52514e', 'field_mean': '#e34948',
          'calibrated_variety': '#eda100', 'variety_mean': '#4a3aa7'}
LABEL = {'default': 'Literature defaults', 'calibrated': 'Farm-calibrated, 3 parameters',
         'calibrated_py_only': 'Potential yield only', 'farm_mean': 'Farm mean',
         'field_mean': 'Field mean', 'calibrated_variety': 'Potential yield per variety',
         'variety_mean': 'Variety mean (baseline)'}
SEQ = LinearSegmentedColormap.from_list(
    'seqblue', ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'])
CLASSES = ListedColormap(['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850'])
# Yield maps in the red-to-green convention farmers and the plugin use; a
# red-yellow-green ramp keeps a luminance gradient for colour-vision deficiency.
YIELD = LinearSegmentedColormap.from_list('yield', ['#d73027', '#fc8d59', '#fee08b', '#91cf60', '#1a9850'])
TEXT, MUTED, GRID = '#0b0b0b', '#52514e', '#e4e3df'

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.edgecolor': MUTED,
    'axes.labelcolor': TEXT, 'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
    'axes.axisbelow': True, 'legend.frameon': False, 'figure.dpi': 110})


def read(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        print('missing', name)
        return None
    with open(path, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def save(fig, name):
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FIG, '{}.{}'.format(name, ext)), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('wrote', name)


# Figure 2: data inventory -------------------------------------------------
def fig2():
    rows = []
    for path in glob.glob(os.path.join(DATA, '*_training_examples.csv')):
        rows += read(os.path.basename(path))
    skips = []
    for path in glob.glob(os.path.join(DATA, '*_skip_reasons.csv')):
        skips += read(os.path.basename(path))
    if not rows:
        return
    years = list(range(min(int(r['year']) for r in rows), max(int(r['year']) for r in rows) + 1))
    fig = plt.figure(figsize=(7.2, 5.6))
    grid = fig.add_gridspec(2, 2, width_ratios=[3, 2], height_ratios=[1, 1.05], hspace=0.55, wspace=0.25)
    ax1, ax2 = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    ax3 = fig.add_subplot(grid[1, :])
    counts = np.array([len({(r['farm'], r['field']) for r in rows if int(r['year']) == y})
                       for y in years])
    ax1.bar(years, counts, color='#2a78d6', width=0.7, edgecolor='white', linewidth=1)
    for y, c in zip(years, counts):
        if c == 0:
            ax1.text(y, 0.1, 'none', ha='center', va='bottom', fontsize=7, color=MUTED,
                     rotation=90)
    ax1.set_xlabel('Harvest year')
    ax1.set_ylabel('Potato field-years with a usable\ntraining example')
    ax1.set_xticks(years)
    ax1.tick_params(axis='x', rotation=45)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
    short_names = {
        'no crop/planting record': 'No planting record for the year',
        'planting record on file is from a different': 'Planting record from another year',
        'no usable harvest yield': 'No usable yield for the year',
        'no harvest data on file': 'No harvest data on file',
        'no weather data': 'No weather data',
        'could not produce': 'Model produced no estimate',
    }
    reasons = Counter()
    for s in skips:
        label = re.sub(r'\s*\(.*', '', s['reason'])
        for key, short in short_names.items():
            if key in label:
                label = short
                break
        reasons[label[:40]] += int(s['count'])
    labels, values = zip(*reasons.most_common()) if reasons else ([], [])
    ax2.barh(range(len(labels)), values, color='#52514e', height=0.45)
    ax2.set_yticks([])
    ax2.invert_yaxis()
    ax2.set_xlabel('Field-years excluded')
    ax2.set_xlim(0, max(values) * 1.15 if values else 1)
    for i, (label, v) in enumerate(zip(labels, values)):
        ax2.text(0, i - 0.42, label, va='bottom', ha='left', fontsize=7, color=TEXT)
        ax2.text(v, i, ' {}'.format(v), va='center', fontsize=7.5, color=TEXT)
    # (c) the observed yields themselves: every variety observation by
    # field-year, with the field-year mean, ordered by harvest year
    by_fy = defaultdict(list)
    for r in rows:
        by_fy[(int(r['year']), r['field'])].append(num(r['actual_t_ha']))
    keys = sorted(by_fy)
    for i, key in enumerate(keys):
        vals = by_fy[key]
        ax3.plot([i, i], [min(vals), max(vals)], color=GRID, linewidth=3, zorder=1)
        ax3.scatter([i] * len(vals), vals, s=14, color='#2a78d6', zorder=3, linewidths=0)
        ax3.plot([i - 0.3, i + 0.3], [np.mean(vals)] * 2, color='#eb6834', linewidth=1.6, zorder=4)
    ax3.axhline(np.mean([v for vals in by_fy.values() for v in vals]), color=MUTED, linewidth=0.8,
                linestyle='--', zorder=0)
    ax3.set_xticks(range(len(keys)))
    ax3.set_xticklabels(['{}:{}'.format(f, y) for y, f in keys], rotation=90, fontsize=6.5)
    ax3.set_xlim(-0.7, len(keys) - 0.3)
    ax3.set_ylabel('Observed yield (t/ha)')
    ax3.set_xlabel('Field-year (field:harvest year)')
    ax3.text(len(keys) * 0.8, np.mean([v for vals in by_fy.values() for v in vals]) + 1,
             'mean of all 48 observations', ha='center', va='bottom', fontsize=7, color=MUTED)
    ax3.text(0.01, 0.03, 'dots: variety observations; orange mark: field-year mean',
             transform=ax3.transAxes, ha='left', va='bottom', fontsize=7, color=MUTED)
    ax1.set_title('a', loc='left', fontweight='bold')
    ax2.set_title('b', loc='left', fontweight='bold', x=-0.04)
    ax3.set_title('c', loc='left', fontweight='bold')
    save(fig, 'fig2_data_inventory')


# Figure 2 (new): percentile-ranking schematic --------------------------------
def fig_percentile_schematic():
    """How the productivity index is built, on a nine-cell field: three
    sources in different units, their percentile ranks (Eq. 5), the
    equal-weight index with a missing cell dropped, and the classes. The
    numbers are computed by the plugin's own functions."""
    fertility_index = pc.import_plugin_module('database_scripts.fertility_index')
    values = {
        'Yield 2023 (t/ha)': [48, 52, 61, 45, 55, 63, 40, 50, 58],
        'Yield 2024 (kg/ha)': [41000, 47000, 53000, 38000, 47000, None, 36000, 44000, 50000],
        'Clay content (%)': [12, 14, 15, 11, 13, 16, 10, 13, 18],
    }
    ranks = {k: fertility_index.percentile_ranks(v) for k, v in values.items()}
    index = fertility_index.combine_sources(values)
    classes = fertility_index.classify_index(index)

    def fmt(v):
        if v is None:
            return 'no data'
        if isinstance(v, float) and not float(v).is_integer():
            return '{:.1f}'.format(v)
        return '{:g}'.format(v)

    def grid(ax, vals, cmap, title, vmin=None, vmax=None, text_fmt=fmt):
        arr = np.array([[math.nan if v is None else float(v) for v in vals[i * 3:i * 3 + 3]]
                        for i in range(3)])
        ax.imshow(np.where(np.isnan(arr), np.nan, arr), cmap=cmap, vmin=vmin, vmax=vmax)
        for i in range(3):
            for j in range(3):
                v = vals[i * 3 + j]
                ax.text(j, i, text_fmt(v), ha='center', va='center', fontsize=7.5 if v is not None else 6,
                        color=TEXT if v is not None else MUTED)
        ax.set_xticks(np.arange(-0.5, 3, 1))
        ax.set_yticks(np.arange(-0.5, 3, 1))
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(length=0)
        ax.grid(True, color='white', linewidth=1.5)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(MUTED)
        ax.set_title(title, fontsize=8)

    neutral = LinearSegmentedColormap.from_list('neutral', ['#f2f2f2', '#f2f2f2'])
    fig, axes = plt.subplots(3, 3, figsize=(6.4, 6.6))
    for ax, (name, vals) in zip(axes[0], values.items()):
        grid(ax, vals, neutral, name)
    for ax, (name, vals) in zip(axes[1], ranks.items()):
        grid(ax, vals, YIELD, 'Rank of {}\n(0 to 100)'.format(name.split(' (')[0].lower()), 0, 100)
    grid(axes[2][0], index, YIELD, 'Index: mean of the\navailable ranks', 0, 100)
    grid(axes[2][1], classes, CLASSES, 'Classes at\n20, 40, 60 and 80', 1, 5,
         text_fmt=lambda v: 'class {:g}'.format(v))
    axes[2][2].axis('off')
    axes[2][2].text(0, 0.95, 'Equal weights, one per source.\n\nThe cell without a 2024 value\n'
                             'takes the mean of its two\nremaining ranks.\n\nEach source scores its best\n'
                             'cell 100 and its worst 0,\nwhatever the unit.',
                    transform=axes[2][2].transAxes, fontsize=7.5, va='top', color=TEXT)
    for row, letter in zip(axes, 'abc'):
        row[0].text(-0.3, 1.08, letter, transform=row[0].transAxes, fontweight='bold', fontsize=10)
    fig.subplots_adjust(hspace=0.5, wspace=0.3, left=0.1)
    save(fig, 'fig_percentile_schematic')


# Figure 3: predicted vs observed, field-year level (primary unit) -----------
def _fig3_impl(level, name):
    rows = read('cv_predictions{}.csv'.format(SUFFIX))
    if not rows:
        return
    methods = ['default', 'calibrated', 'calibrated_variety', 'variety_mean']
    fig, axes = plt.subplots(2, 2, figsize=(6.4, 6.4), sharex=True, sharey=True)
    axes = axes.ravel()
    lim = (0, 105)
    for ax, method, letter in zip(axes, methods, 'abcd'):
        sub = [r for r in rows if r['method'] == method]
        if level == 'field_year':
            by_fy = defaultdict(lambda: ([], []))
            for r in sub:
                by_fy[(r['field'], r['year'])][0].append(num(r['observed']))
                by_fy[(r['field'], r['year'])][1].append(num(r['predicted']))
            obs = np.array([np.mean(o) for o, _ in by_fy.values()])
            pred = np.array([np.mean(p) for _, p in by_fy.values()])
            n_label = '{} field-years'.format(len(obs))
        else:
            obs = np.array([num(r['observed']) for r in sub])
            pred = np.array([num(r['predicted']) for r in sub])
            by_fy = defaultdict(list)
            for r in sub:
                by_fy[(r['field'], r['year'])].append((num(r['observed']), num(r['predicted'])))
            for pts in by_fy.values():
                if len(pts) > 1:
                    xs = [p[0] for p in pts]
                    ax.plot([min(xs), max(xs)], [pts[0][1], pts[0][1]], color='#c3c2b7',
                            linewidth=0.8, zorder=1)
            n_label = '{} variety observations'.format(len(obs))
        ax.plot(lim, lim, color=MUTED, linewidth=0.8, linestyle='--')
        ax.scatter(obs, pred, s=22, facecolor=SERIES[method], edgecolor='white',
                   linewidth=0.5, alpha=0.9, zorder=2)
        rmse = math.sqrt(np.mean((pred - obs) ** 2))
        bias = np.mean(pred - obs)
        ax.text(0.03, 0.97, '{}\n{}\nRMSE {:.1f}, bias {:+.1f} t/ha'.format(
            LABEL[method], n_label, rmse, bias), transform=ax.transAxes, va='top', fontsize=7.5)
        ax.set_xlabel('Observed yield (t/ha)')
        ax.set_aspect('equal')
        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_title(letter, loc='left', fontweight='bold')
    axes[0].set_ylabel('Predicted yield (t/ha)')
    axes[2].set_ylabel('Predicted yield (t/ha)')
    save(fig, name)


def fig3():
    _fig3_impl('field_year', 'fig3_predicted_vs_observed')
    _fig3_impl('example', 'figS2_predicted_vs_observed_examples')


# Figure 4: learning curve -------------------------------------------------
def fig4():
    rows = read('learning_curve{}.csv'.format(SUFFIX))
    params = read('learning_curve_params{}.csv'.format(SUFFIX))
    metrics = read('cv_metrics{}.csv'.format(SUFFIX))
    if not rows:
        return
    by_k = defaultdict(lambda: defaultdict(list))
    for r in rows:
        k = int(r['k'])
        by_k['rmse'][k].append(num(r['rmse']))
        by_k['rmse_py_only'][k].append(num(r['rmse_py_only']))
        by_k['rmse_train_mean'][k].append(num(r['rmse_train_mean']))
        if 'rmse_variety' in r:
            by_k['rmse_variety'][k].append(num(r['rmse_variety']))
            by_k['rmse_variety_mean'][k].append(num(r['rmse_variety_mean']))
    ks = sorted(by_k['rmse'])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3), gridspec_kw={'width_ratios': [3, 2]})
    for key, color, label in (('rmse', '#eb6834', 'Farm-calibrated, 3 parameters'),
                              ('rmse_py_only', '#52514e', 'Potential yield only'),
                              ('rmse_variety', '#eda100', 'Potential yield per variety'),
                              ('rmse_train_mean', '#1baf7a', 'Mean of the same training field-years'),
                              ('rmse_variety_mean', '#4a3aa7', 'Variety mean of the training field-years')):
        if key not in by_k:
            continue
        med = [np.nanmedian(by_k[key][k]) for k in ks]
        q1 = [np.nanpercentile(by_k[key][k], 25) for k in ks]
        q3 = [np.nanpercentile(by_k[key][k], 75) for k in ks]
        ax.fill_between(ks, q1, q3, color=color, alpha=0.15, linewidth=0)
        ax.plot(ks, med, color=color, linewidth=2, marker='o', markersize=3.5, label=label)
    if metrics:
        for r in metrics:
            if r['level'] == 'example' and r['subset'] == 'all' and r['method'] == 'default':
                ax.axhline(num(r['rmse']), color=MUTED, linewidth=0.8, linestyle='--')
                ax.text(0.02, num(r['rmse']), 'literature defaults', va='bottom', fontsize=7.5,
                        color=MUTED, transform=ax.get_yaxis_transform())
    ax.set_xlabel('Training field-years')
    ax.set_ylabel('RMSE on the remaining field-years (t/ha)')
    ax.set_xscale('log')
    ax.set_xticks(ks)
    ax.set_xticklabels(ks)
    ax.set_xlim(0.9, max(ks) * 1.15)
    ax.legend(fontsize=7, loc='upper right', bbox_to_anchor=(1.0, 0.9))
    ax.set_title('a', loc='left', fontweight='bold')
    if params:
        py = defaultdict(list)
        for r in params:
            py[int(r['k'])].append(num(r['potential_yield_t_ha']))
        pk = sorted(py)
        ax2.fill_between(pk, [np.nanpercentile(py[k], 25) for k in pk],
                         [np.nanpercentile(py[k], 75) for k in pk], color='#eb6834', alpha=0.15,
                         linewidth=0)
        ax2.plot(pk, [np.nanmedian(py[k]) for k in pk], color='#eb6834', linewidth=2, marker='o',
                 markersize=3.5)
        ax2.set_xscale('log')
        ax2.set_xticks(pk)
        ax2.set_xticklabels(pk)
        ax2.set_xlabel('Training field-years')
        ax2.set_ylabel('Fitted potential yield (t/ha)')
        ax2.set_title('b', loc='left', fontweight='bold')
    save(fig, 'fig4_learning_curve')


# Figure 5: parameter stability ---------------------------------------------
def fig5():
    rows = read('fitted_params{}.csv'.format(SUFFIX))
    boot = read('bootstrap_params{}.csv'.format(SUFFIX)) or []
    if not rows:
        return
    params = [('potential_yield_t_ha', 'Potential yield (t/ha)'),
              ('ky_nitrogen', 'Ky nitrogen'),
              ('min_relative_yield_nitrogen', 'Nitrogen floor')]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8))
    fig.subplots_adjust(wspace=0.55)
    for ax, (key, label) in zip(axes, params):
        folds = [num(r[key]) for r in rows]
        bs = [num(r[key]) for r in boot]
        data = [folds] + ([bs] if bs else [])
        box = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=False,
                         medianprops=dict(color=TEXT, linewidth=1.4),
                         whiskerprops=dict(color=MUTED), capprops=dict(color=MUTED))
        for patch in box['boxes']:
            patch.set(facecolor='#9ec5f4', edgecolor='#256abf', linewidth=0.8)
        for i, d in enumerate(data, start=1):
            ax.scatter(np.random.normal(i, 0.06, len(d)), d, s=8, color='#0d366b', alpha=0.5,
                       zorder=3)
        ax.set_xticks(range(1, len(data) + 1))
        ax.set_xticklabels(['Leave-one-out\nfolds (n={})'.format(len(folds))] +
                           (['Bootstrap\n(n={})'.format(len(bs))] if bs else []), fontsize=7.5)
        ax.set_ylabel(label)
    save(fig, 'fig5_parameter_stability')


# Figure 6: limiting factors -------------------------------------------------
def fig6():
    rows = read('cv_predictions{}.csv'.format(SUFFIX))
    if not rows:
        return
    sub = [r for r in rows if r['method'] == 'calibrated']
    years = sorted({int(r['year']) for r in sub})
    factors = ['water', 'nitrogen', 'potassium', 'none']
    colors = {'water': '#2a78d6', 'nitrogen': '#eb6834', 'potassium': '#1baf7a',
              'none': '#c3c2b7'}
    labels = {'water': 'water', 'nitrogen': 'nitrogen', 'potassium': 'potassium',
              'none': 'none below 0.95'}
    counts = defaultdict(Counter)
    for r in sub:
        counts[int(r['year'])][r['limiting_factor'] or 'none'] += 1
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3), gridspec_kw={'width_ratios': [3, 2]})
    bottom = np.zeros(len(years))
    for f in factors:
        vals = np.array([counts[y][f] for y in years])
        if vals.sum() == 0:
            continue
        ax.bar(years, vals, bottom=bottom, color=colors[f], width=0.7, edgecolor='white',
               linewidth=1, label=labels[f])
        bottom += vals
    ax.set_xlabel('Harvest year')
    ax.set_ylabel('Training examples')
    ax.set_xticks(years)
    ax.tick_params(axis='x', rotation=45)
    ax.legend(title='Lowest relative-yield term', ncol=2, fontsize=7.5, title_fontsize=7.5)
    ax.set_title('a', loc='left', fontweight='bold')
    # b: water relative yield per field-year against logged irrigation
    seen = {}
    ex = read('hortegarden_training_examples.csv') or []
    irr = {(r['field'], int(r['year'])): num(r['irrigation_mm']) for r in ex}
    for r in sub:
        key = (r['field'], int(r['year']))
        seen[key] = (irr.get(key, math.nan), num(r['ry_water']))
    xs = [v[0] for v in seen.values()]
    ys = [v[1] for v in seen.values()]
    cs = ['#eb6834' if k[1] < 2018 else '#2a78d6' for k in seen]
    ax2.scatter(xs, ys, s=22, c=cs, edgecolor='white', linewidth=0.5)
    ax2.axhline(0.95, color=MUTED, linewidth=0.8, linestyle='--')
    ax2.set_xlabel('Logged irrigation (mm per season)')
    ax2.set_ylabel('Water relative yield, calibrated model')
    ax2.set_ylim(0.4, 1.02)
    ax2.text(0.98, 0.04, 'orange: 2015 to 2017,\nno irrigation record', transform=ax2.transAxes,
             ha='right', va='bottom', fontsize=7, color=MUTED)
    ax2.set_title('b', loc='left', fontweight='bold')
    save(fig, 'fig6_limiting_factors')



# Figure 7: fields, harvest years and scored pairs -----------------------
def fig7():
    _fig7_impl(compact=True, name='fig7_pairs_matrix')
    _fig7_impl(compact=False, name='figS3_pairs_matrix_all')


def _fig7_impl(compact, name):
    """A field-by-year matrix: which fields have a yield map in which year,
    the inferred crop, the soil maps on file, and which consecutive pairs
    were scored for the fertility index."""
    results = read('fertility_results.csv')
    paths = sorted(glob.glob(os.path.join(DATA, '*_cells_*.csv')))
    if not paths:
        return
    import statistics
    fields = []
    for path in paths:
        field = os.path.basename(path).split('_cells_')[1][:-4]
        with open(path, newline='', encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        years = {}
        for key in rows[0]:
            if key.startswith('harvest_') and 2001 <= int(key[8:]) <= 2025:
                vals = [float(r[key]) for r in rows if r[key] not in ('', None)]
                if len(vals) >= 300:
                    med = statistics.median(vals)
                    med = med / 1000 if med >= 1000 else med
                    years[int(key[8:])] = 'potato' if med >= 20 else 'other'
        soil = 'lab' if 'clay' in rows[0] else ('ec' if any(k.startswith('soil_eca') for k in rows[0]) else '')
        if years:
            fields.append((field, years, soil))
    fields.sort(key=lambda f: (-len(f[1]), f[0]))
    scored = {}
    for r in results or []:
        if r['variant'] == 'yield_only':
            scored[(r['field'], int(r['year_from']))] = r['has_soil'] == '1'
    if compact:
        fields = [f for f in fields if any((f[0], y) in scored for y in f[1])]
    all_years = list(range(min(y for _, ys, _ in fields for y in ys),
                           max(y for _, ys, _ in fields for y in ys) + 1))
    fig, ax = plt.subplots(figsize=(7.2, 0.30 * len(fields) + 1.4))
    for i, (field, years, soil) in enumerate(fields):
        for y, crop in years.items():
            ax.scatter(y, i, s=46, marker='s', color='#eb6834' if crop == 'potato' else '#2a78d6',
                       edgecolor='white', linewidth=0.6, zorder=3)
        for y in years:
            if (field, y) in scored:
                ax.plot([y + 0.12, y + 0.88], [i, i], color='#0b0b0b', linewidth=2.2, zorder=2)
                if scored[(field, y)]:
                    ax.scatter(y + 0.5, i, s=18, marker='D', color='#0b0b0b', zorder=4)
        if soil:
            ax.text(all_years[-1] + 0.7, i, 'lab' if soil == 'lab' else 'EM38', va='center',
                    fontsize=8, color=MUTED)
    ax.set_yticks(range(len(fields)))
    ax.set_yticklabels([f[0] for f in fields], fontsize=8)
    ax.invert_yaxis()
    ax.set_xticks(all_years)
    ax.set_xticklabels(all_years, rotation=45, fontsize=8.5)
    ax.set_xlim(all_years[0] - 0.6, all_years[-1] + 1.6)
    ax.set_xlabel('Harvest year')
    ax.grid(False)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker='s', linestyle='', color='#eb6834', markersize=7, label='potato yield map'),
               Line2D([], [], marker='s', linestyle='', color='#2a78d6', markersize=7, label='cereal or rape yield map'),
               Line2D([], [], color='#0b0b0b', linewidth=2.2, label='consecutive pair scored'),
               Line2D([], [], marker='D', linestyle='', color='#0b0b0b', markersize=4, label='pair with a soil map')]
    ax.legend(handles=handles, fontsize=7, loc='lower left', ncol=2, bbox_to_anchor=(0, 1.0))
    save(fig, name)

# Figure 8: example field maps ----------------------------------------------
def _cells(path):
    rows = read(os.path.basename(path))
    keys = [k for k in rows[0] if k not in ('cell_id', 'x', 'y')]
    xy = np.array([[num(r['x']), num(r['y'])] for r in rows])
    if np.all(np.abs(xy[:, 0]) <= 180):
        lat0 = math.radians(np.nanmean(xy[:, 1]))
        xy = np.column_stack([xy[:, 0] * 111320 * math.cos(lat0), xy[:, 1] * 110540])
    xy -= np.nanmin(xy, axis=0)
    data = {k: np.array([num(r[k]) for r in rows]) for k in keys}
    return xy, data


def fig8():
    results = read('fertility_results.csv')
    if not results:
        return
    fertility_index = pc.import_plugin_module('database_scripts.fertility_index')
    # the pair with the median yield-only correlation among pairs with soil,
    # so the example is typical rather than the best case
    cand = sorted((r for r in results if r['variant'] == 'yield_only' and r['has_soil'] == '1'),
                  key=lambda r: num(r['spearman']))
    pick = cand[len(cand) // 2]
    farm, field, y0, y1 = pick['farm'], pick['field'], int(pick['year_from']), int(pick['year_to'])
    xy, data = _cells(os.path.join(DATA, '{}_cells_{}.csv'.format(farm, field)))

    def t_ha(values):
        v = values.copy()
        med = np.nanmedian(v)
        if med >= 1000:
            v = np.where(v < 200, v * 1000, v) / 1000
        else:
            v = np.where(v >= 1000, v / 1000, v)
        return v

    prev, cur = t_ha(data['harvest_{}'.format(y0)]), t_ha(data['harvest_{}'.format(y1)])
    sources = dict(y=[None if math.isnan(v) else v for v in prev])
    index = np.array([math.nan if v is None else v
                      for v in fertility_index.combine_sources(sources)])
    classes = np.array([math.nan if c is None else c
                        for c in fertility_index.classify_index(list(index))])
    rho_prev = pick['spearman']

    def crop(values):  # the same yield-magnitude rule as the pairs matrix
        return 'potato' if np.nanmedian(values) >= 20 else 'cereal or rape'

    panels = [('{}\nyield {} (t/ha)'.format(crop(prev).capitalize(), y0), prev, YIELD),
              ('Index from\nyield {} (0-100)'.format(y0), index, YIELD),
              ('Index\nclasses', classes, CLASSES),
              ('{}\nyield {} (t/ha)'.format(crop(cur).capitalize(), y1), cur, YIELD)]
    fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.6))
    for ax, (title, values, cmap) in zip(axes, panels):
        ok = ~np.isnan(values)
        vmin, vmax = (None, None) if cmap is CLASSES else np.nanpercentile(values[ok], [2, 98])
        sc = ax.scatter(xy[ok, 0], xy[ok, 1], c=values[ok], s=3, marker='s', cmap=cmap,
                        linewidths=0, vmin=vmin, vmax=vmax)
        ax.set_aspect('equal')
        ax.set_title(title, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        fig.colorbar(sc, ax=ax, fraction=0.05, pad=0.02, shrink=0.8)
    # scale bar on the first panel
    x0, y0b = np.nanmin(xy[:, 0]) + 5, np.nanmin(xy[:, 1]) + 5
    axes[0].plot([x0, x0 + 100], [y0b, y0b], color=TEXT, linewidth=2)
    axes[0].text(x0 + 50, y0b + 6, '100 m', ha='center', fontsize=7, color=TEXT)
    fig.suptitle('{}, field {}: index from the {} yield map against the {} map '
                 '(Spearman rho {})'.format(FARM_LABEL, field, y0, y1, rho_prev), fontsize=9,
                 y=1.04)
    save(fig, 'fig8_example_field')


# Figure 8: index performance -----------------------------------------------
def fig9():
    rows = read('fertility_results.csv')
    if not rows:
        return
    order = ['yield_only', 'soil_only', 'combined_equal', 'combined_grouped',
             'combined_datadriven', 'zscore_grouped']
    names = ['Yield only', 'Soil only', 'Yield + soil,\nequal weights',
             'Yield + soil,\ngrouped', 'Yield + soil,\ndata-driven', 'Z-score,\ngrouped']
    soil_pairs = {(r['field'], r['year_from']) for r in rows if r['has_soil'] == '1'}
    per_pair = defaultdict(dict)
    for r in rows:
        if (r['field'], r['year_from']) in soil_pairs and r['variant'] in order:
            per_pair[(r['field'], r['year_from'])][r['variant']] = num(r['spearman'])
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for pair, values in per_pair.items():
        xs = [order.index(v) + 1 for v in order if v in values]
        ys = [values[v] for v in order if v in values]
        ax.plot(xs, ys, color='#c3c2b7', linewidth=0.7, zorder=1)
    for i, v in enumerate(order, start=1):
        d = [values[v] for values in per_pair.values() if v in values]
        ax.scatter([i] * len(d), d, s=18, color='#0d366b', alpha=0.7, zorder=3)
        if d:
            med = float(np.median(d))
            ax.plot([i - 0.25, i + 0.25], [med, med], color='#eb6834', linewidth=2.2, zorder=4)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels(names, fontsize=7.5)
    ax.set_ylabel('Spearman rho, index vs next-season yield')
    ax.set_xlabel('Index variant; the {} field-year pairs with a soil source, joined per pair; '
                  'orange bar = median'.format(len(per_pair)), fontsize=7.5)
    save(fig, 'fig9_index_performance')


# Figure S1: objective surfaces ------------------------------------------
def figS1():
    panels = [('objective_surface_py_floor{}.csv'.format(SUFFIX), 'potential_yield_t_ha',
               'Potential yield (t/ha)', 'unlogged nutrient not modelled'),
              ('objective_surface_kyn_floor{}.csv'.format(SUFFIX), 'ky_nitrogen',
               'Ky nitrogen', 'unlogged nutrient not modelled'),
              ('objective_surface_py_floor_floor.csv', 'potential_yield_t_ha',
               'Potential yield (t/ha)', 'unlogged nutrient at its floor')]
    panels = [p for p in panels if os.path.exists(os.path.join(DATA, p[0]))]
    if not panels:
        print('missing objective surfaces')
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(3.4 * len(panels), 3), squeeze=False)
    for ax, (name, xkey, xlabel, title), letter in zip(axes[0], panels, 'abc'):
        rows = read(name)
        xs = sorted({num(r[xkey]) for r in rows})
        fl = sorted({num(r['floor']) for r in rows})
        grid = np.full((len(fl), len(xs)), np.nan)
        for r in rows:
            grid[fl.index(num(r['floor'])), xs.index(num(r[xkey]))] = num(r['sse'])
        im = ax.pcolormesh(xs, fl, np.log10(grid), cmap=SEQ.reversed(), shading='nearest')
        i, j = np.unravel_index(np.nanargmin(grid), grid.shape)
        ax.scatter([xs[j]], [fl[i]], s=40, facecolor='white', edgecolor='#0b0b0b', zorder=3)
        ax.set_xlabel(xlabel)
        ax.set_ylabel('Nitrogen floor')
        ax.set_title('{}  {}'.format(letter, title), loc='left', fontsize=8, fontweight='bold')
        ax.grid(False)
        fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02, label='log10 SSE')
    save(fig, 'figS1_objective_surfaces')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suffix', default='_unmodelled', help='cross-validation output suffix')
    SUFFIX = parser.parse_args().suffix
    np.random.seed(1)
    for f in (fig2, fig_percentile_schematic, fig3, fig4, fig5, fig6, fig7, fig8, fig9, figS1):
        try:
            f()
        except Exception as exc:  # keep going; report which figure failed
            import traceback
            traceback.print_exc()
            print('{} failed: {}'.format(f.__name__, exc))
