"""Generate Table 1 (default crop-model parameters) from the CropModel
dataclass in ``support_scripts/crop_models.py`` so the paper cannot drift
from the code. Writes ``paper/tables/table1_parameters.md`` (main text:
potato and wheat as the cereal archetype example) and
``paper/tables/tableS1_parameters_all.csv`` (supplement: every crop).

Run through ``run_in_qgis_env.bat``.
"""
import csv
import dataclasses
import os

import paper_common as pc

crop_models = pc.import_plugin_module('support_scripts.crop_models')

# (field, label, unit, source note) in the order Table 1 should list them.
ROWS = [
    ('gdd_base_c', 'Base temperature for growing degree days (GDD)', 'deg C', 'extension convention (potato 4.4, cereals 0)'),
    ('season_end_gdd', 'Season length', 'GDD', 'potato ~1100 GDD to harvest readiness; cereals crop-specific'),
    ('kc_ini_end_gdd', 'End of initial stage', 'GDD', 'FAO-56 Table 11 stage proportions'),
    ('kc_mid_end_gdd', 'End of development stage', 'GDD', 'FAO-56 Table 11 stage proportions'),
    ('kc_late_start_gdd', 'End of mid-season stage', 'GDD', 'FAO-56 Table 11 stage proportions'),
    ('kc_ini', 'Kc initial', '-', 'FAO-56 Table 12'),
    ('kc_mid', 'Kc mid-season', '-', 'FAO-56 Table 12'),
    ('kc_end', 'Kc end', '-', 'FAO-56 Table 12'),
    ('root_depth_min_cm', 'Root depth at emergence', 'cm', 'shape-consistent estimate'),
    ('root_depth_max_cm', 'Maximum root depth', 'cm', 'shape-consistent estimate'),
    ('root_depth_full_gdd', 'Root depth reaches maximum at', 'GDD', 'shape-consistent estimate'),
    ('ky_initial', 'Ky initial stage', '-', 'seasonal Ky (FAO-33 Table 24) x 0.105'),
    ('ky_development', 'Ky development stage', '-', 'seasonal Ky x 0.245'),
    ('ky_mid_season', 'Ky mid-season stage', '-', 'seasonal Ky x 0.6'),
    ('ky_late_season', 'Ky late stage', '-', 'seasonal Ky x 0.105'),
    ('season_n_demand_kg_ha', 'Season nitrogen demand', 'kg N/ha', 'CDFA-FREP guidelines'),
    ('n_uptake_midpoint_gdd', 'Nitrogen uptake midpoint', 'GDD', 'logistic placement'),
    ('n_uptake_steepness', 'Nitrogen uptake steepness', '1/GDD', 'logistic placement'),
    ('ky_nitrogen', '**Ky nitrogen (fitted)**', '-', 'planning estimate; calibrated in this study'),
    ('min_relative_yield_nitrogen', '**Nitrogen floor (fitted)**', '-', 'zero-N plots 30-60 % of fertilised yield; calibrated'),
    ('season_k_demand_kg_ha', 'Season potassium demand', 'kg K/ha', 'PDA offtake figures'),
    ('k_uptake_midpoint_gdd', 'Potassium uptake midpoint', 'GDD', 'logistic placement'),
    ('k_uptake_steepness', 'Potassium uptake steepness', '1/GDD', 'logistic placement'),
    ('ky_potassium', 'Ky potassium (active, not calibrated)', '-', 'planning estimate'),
    ('min_relative_yield_potassium', 'Potassium floor (active, not calibrated)', '-', 'mirrors nitrogen floor'),
    ('season_p_demand_kg_ha', 'Season phosphorus demand', 'kg P/ha', 'PDA/FAO offtake; flag only'),
    ('season_mg_demand_kg_ha', 'Season magnesium demand', 'kg Mg/ha', 'PDA offtake; flag only'),
    ('potential_yield_t_ha', '**Potential yield (fitted)**', 't/ha', 'attainable-yield ranges; calibrated in this study'),
    ('heat_stress_threshold_c', 'Heat-stress threshold', 'deg C', 'indicative; ky_heat = 0 disables'),
    ('ky_heat', 'Ky heat', '-', 'disabled by default'),
    ('reference_spacing_mm', 'Reference in-row spacing', 'mm', '0 = spacing effect disabled (as in this study)'),
    ('spacing_sensitivity', 'Spacing sensitivity', '-', '0 = disabled (as in this study)'),
]


def fmt(value):
    if isinstance(value, float):
        return ('{:.4g}'.format(value)).rstrip('0').rstrip('.') if value != int(value) else str(int(value))
    return str(value)


def main():
    out_dir = pc.ensure_dir(os.path.join(pc.PAPER_DIR, 'tables'))
    potato = crop_models.CROP_MODELS['potato']
    wheat = crop_models.CROP_MODELS['wheat']
    lines = ['Table 1. Default crop-model parameters for potato and for wheat as the '
             'cereal archetype (barley, rye and oats differ only in season length, '
             'seasonal Ky, Ky nitrogen and potential yield; see Table S1). '
             'Parameters in bold and marked (fitted) are the three calibrated by "Teach the model". '
             'The source labels are explained in Supplementary Note S1.',
             '',
             '| Parameter | Unit | Potato | Wheat | Source |',
             '|---|---|---|---|---|']
    for field, label, unit, source in ROWS:
        lines.append('| {} | {} | {} | {} | {} |'.format(
            label, unit, fmt(getattr(potato, field)), fmt(getattr(wheat, field)), source))
    with open(os.path.join(out_dir, 'table1_parameters.md'), 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')

    names = [f.name for f in dataclasses.fields(crop_models.CropModel)]
    with open(os.path.join(out_dir, 'tableS1_parameters_all.csv'), 'w', newline='',
              encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['parameter'] + list(crop_models.CROP_MODELS) + ['default'])
        for name in names:
            if name == 'name':
                continue
            writer.writerow([name] + [fmt(getattr(m, name)) for m in crop_models.CROP_MODELS.values()]
                            + [fmt(getattr(crop_models.DEFAULT_CROP_MODEL, name))])
    print('Wrote Table 1 and Table S1 to', out_dir)


if __name__ == '__main__':
    main()
