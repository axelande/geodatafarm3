"""Companion to patch_review2.py: Table 3 restructured, Table 4 without the
class test, S4 and S5 extended, Table 5 and Figure S2 registered in the
Word builder."""
import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------ make_tables.py
p = os.path.join(HERE, 'make_tables.py')
s = open(p, encoding='utf-8').read()
start = s.index('def table3():')
end = s.index('def tableS3():')
new_t3 = '''def table3():
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
        handle.write('\\n'.join(lines) + '\\n')
    print('wrote table3')


'''
s = s[:start] + new_t3 + s[end:]
s = s.replace("that have a soil source. '\n             'Spearman rho: 1 means",
              "that have a soil layer. '\n             'Spearman rho over all cells: 1 means")
s = s.replace("'given for reference.', '',\n             '| Index variant | Pairs |",
              "'given for reference; the class-separation test is in Table S5.', '',\n             '| Index variant | Pairs |")
s = s.replace("'Table S5. Fertility index: sensitivity variants", "'Table S5. Productivity index: sensitivity variants")
s4_anchor = "    with open(os.path.join(OUT, 'tableS4_sensitivity.md'), 'w', encoding='utf-8') as handle:"
s4_add = '''    struct = read('structure_sensitivity.csv')
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
'''
assert s4_anchor in s
s = s.replace(s4_anchor, s4_add + s4_anchor)
s5_anchor = "    with open(os.path.join(OUT, 'tableS5_fertility_detail.md'), 'w', encoding='utf-8') as handle:"
s5_add = '''    src = read('fertility_sources.csv')
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
'''
assert s5_anchor in s
s = s.replace(s5_anchor, s5_add + s5_anchor)
ast.parse(s)
open(p, 'w', encoding='utf-8').write(s)
print('make_tables updated')

# ------------------------------------------------------------ build_docx.py
p = os.path.join(HERE, 'build_docx.py')
s = open(p, encoding='utf-8').read()
s = s.replace("'3': 'table3_cv_metrics.md', '4': 'table4_fertility.md'}",
              "'3': 'table3_cv_metrics.md', '4': 'table4_fertility.md',\n               '5': 'table5_reproducibility.md'}")
s = s.replace("    'S1': ('figS1_objective_surfaces.png',",
              "    'S2': ('figS2_predicted_vs_observed_examples.png',\n"
              "           'Figure S2. As Figure 3 but at the level of the 48 variety observations; grey lines '\n"
              "           'join the varieties of one field-year.'),\n"
              "    'S1': ('figS1_objective_surfaces.png',")
s = s.replace("    add_figure(doc, 'S1')\n", "    add_figure(doc, 'S1')\n    add_figure(doc, 'S2')\n")
old_f3 = s[s.index("    '3': ('fig3_predicted_vs_observed.png',"):s.index("    '4': ('fig4_learning_curve.png',")]
new_f3 = ("    '3': ('fig3_predicted_vs_observed.png',\n"
          "          'Figure 3. Predicted against observed potato yield for held-out field-years, post hoc '\n"
          "          'variant, one point per field-year (mean over its variety observations). (a) Literature '\n"
          "          'defaults. (b) Farm-calibrated, three crop-level parameters. (c) Farm-calibrated with '\n"
          "          'potential yield refitted per variety. (d) Training-set same-variety mean. Dashed line '\n"
          "          'is 1:1. The variety-observation level is Figure S2.'),\n")
s = s.replace(old_f3, new_f3)
s = s.replace("'fertility index, and the fields with a soil map (EM38 conductivity or laboratory '",
              "'productivity index, and the fields with a soil layer (EM38 conductivity or laboratory '")
s = s.replace("'Figure 6. (a) Limiting factor per training example by harvest year, defined as the '\n"
              "          'modelled term with the lowest relative yield when below 0.95.",
              "'Figure 6. (a) Model-attributed limiting factor per variety observation by harvest year, '\n"
              "          'defined as the modelled term with the lowest relative yield when below 0.95; not an '\n"
              "          'agronomically verified limitation.")
ast.parse(s)
open(p, 'w', encoding='utf-8').write(s)
print('build_docx updated')
