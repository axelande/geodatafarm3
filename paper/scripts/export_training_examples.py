"""Export one training example per field-year from a GeoDataFarm farm.

Runs the plugin's own farm-wide "Teach the model" scan
(``CropSimulation._compute_teach_scan``) headlessly and writes:

* ``<out>/<farm_id>_training_examples.pkl`` - the full TrainingExample list
  (weather slice, events, soil, irrigation) that ``cross_validate.py`` needs.
  Field names inside are already anonymised.
* ``<out>/<farm_id>_training_examples.csv`` - one anonymised summary row per
  field-year for Table 2 and the data-inventory figure.
* ``<out>/<farm_id>_skip_reasons.csv`` - why field-years were excluded.

Usage (from the repository root)::

    set GDF_PASSWORD=...
    paper\\scripts\\run_in_qgis_env.bat paper\\scripts\\export_training_examples.py ^
        --farm myfarm --user me --farm-id farm01
"""
import argparse
import csv
import dataclasses
import os
import pickle

import paper_common as pc


def summarise(example, farm_id, field_id):
    rain = sum((w.precipitation_mm or 0.0) for w in example.weather)
    temps = [w.temp_mean_c for w in example.weather if w.temp_mean_c is not None]
    return {
        'farm': farm_id,
        'field': field_id,
        'year': example.year,
        'crop': example.crop,
        'variety': example.variety or '',
        'season_from': example.season_from,
        'season_to': example.season_to,
        'planting_date_logged': int(bool(example.planting_date_logged)),
        'season_days': len(example.weather),
        'season_rain_mm': round(rain, 1),
        'season_mean_temp_c': round(sum(temps) / len(temps), 2) if temps else '',
        'clay_pct': example.clay,
        'organic_matter_pct': example.organic_matter,
        'n_applied_kg_ha': round(sum(example.fertilizer_kg_n_by_date.values()), 1),
        'k_applied_kg_ha': round(sum(example.fertilizer_kg_k_by_date.values()), 1),
        'n_events': len(example.fertilizer_kg_n_by_date),
        'irrigation_mm': round(sum(example.irrigation_by_date.values()), 1),
        'spacing_mm': example.spacing_mm or '',
        'predicted_default_t_ha': round(example.predicted_yield_t_ha, 2),
        'actual_t_ha': round(example.actual_yield_t_ha, 2),
        'limiting_factor': example.limiting_factor or '',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    pc.add_farm_arguments(parser)
    parser.add_argument('--allow-multiyear-crops', action='store_true')
    args = parser.parse_args()

    app = pc.start_qgis()
    db = pc.connect_db(args)
    CropSimulation = pc.import_plugin_module('database_scripts.crop_simulation').CropSimulation

    class Parent:
        pass
    parent = Parent()
    parent.db = db
    sim = CropSimulation(parent)

    print('Scanning farm {} ...'.format(args.farm))
    examples, skip_reasons = sim._compute_teach_scan(
        allow_multiyear_crops=args.allow_multiyear_crops)
    print('  {} training examples, {} skip reasons'.format(
        len(examples), sum(skip_reasons.values())))

    anon = pc.Anonymiser(args.farm_id)
    out = pc.ensure_dir(args.out)
    rows = []
    anonymised = []
    for ex in examples:
        field_id = anon.field_id(ex.field_name)
        rows.append(summarise(ex, args.farm_id, field_id))
        anonymised.append(dataclasses.replace(ex, field_name=field_id))
    anon.save()

    with open(os.path.join(out, '{}_training_examples.pkl'.format(args.farm_id)), 'wb') as handle:
        pickle.dump({'farm': args.farm_id, 'examples': anonymised}, handle)
    if rows:
        with open(os.path.join(out, '{}_training_examples.csv'.format(args.farm_id)),
                  'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    with open(os.path.join(out, '{}_skip_reasons.csv'.format(args.farm_id)),
              'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(['reason', 'count'])
        for reason, count in skip_reasons.most_common():
            writer.writerow([reason, count])

    # Raw fertiliser journal rows per exported field-year, for diagnosing
    # why nitrogen rates did not parse (the product name and rate text are
    # kept verbatim; the field name is anonymised).
    seen = {(ex.field_name, ex.season_from, ex.season_to) for ex in examples}
    ferti_rows = []
    columns = db.get_all_columns('manual', 'ferti')
    wanted = [c for c in columns if c not in ('field_row_id', 'polygon', 'pos', 'field')]
    for field_name, season_from, season_to in sorted(seen):
        rows = db.execute_and_return(
            'SELECT {} FROM ferti.manual WHERE field = %s AND date_ >= %s AND date_ <= %s '
            'ORDER BY date_'.format(', '.join('"{}"'.format(c) for c in wanted)),
            params=(field_name, season_from, season_to))
        for row in rows:
            ferti_rows.append(dict({'field': anon.field_id(field_name)},
                                   **{c: ('' if v is None else v) for c, v in zip(wanted, row)}))
    if ferti_rows:
        with open(os.path.join(out, '{}_ferti_rows.csv'.format(args.farm_id)),
                  'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ferti_rows[0]))
            writer.writeheader()
            writer.writerows(ferti_rows)
    anon.save()
    print('Wrote exports to', out)
    app.exitQgis()


if __name__ == '__main__':
    main()
