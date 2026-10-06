"""Objective O3 export: per-field grid cells with one yield column per
harvest year and the soil sources, using the plugin's own 2 m grid.

Writes ``<out>/<farm_id>_cells_<field_id>.csv`` with columns
``cell_id, x, y, harvest_<year>..., clay, humus, ph`` (soil columns only
when a soil table with that attribute exists for the field). Cell values
are the mean of the source features intersecting the cell, exactly as
``fertility_index_service.source_values`` computes them.

Run through ``run_in_qgis_env.bat`` with the same farm arguments as
``export_training_examples.py``.
"""
import argparse
import csv
import os
import re

from psycopg2 import sql as pgsql

import paper_common as pc

CLAY_PREFIXES = ('clay', 'total_lerhalt', 'lerhalt')
HUMUS_PREFIXES = ('humus', 'mullhalt')
PH_PREFIXES = ('ph',)
YIELD_PATTERNS = ('yield', 'skord', 'skörd', 'avkast', 'wet_mass', 'dry_mass')


def pick_column(columns, prefixes):
    lowered = {c.lower(): c for c in columns}
    for prefix in prefixes:
        for low, original in lowered.items():
            if low.startswith(prefix):
                return original
    return None


def pick_yield_column(columns):
    lowered = {c.lower(): c for c in columns}
    for pattern in YIELD_PATTERNS:
        for low, original in lowered.items():
            if pattern in low:
                return original
    return None


def tables_in_schema(db, schema):
    rows = db.execute_and_return(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = %s "
        "AND table_name <> 'manual' ORDER BY table_name", params=(schema,))
    return [r[0] for r in rows]


def table_touches_field(db, schema, table, geom_col, field_name):
    rows = db.execute_and_return(
        pgsql.SQL('SELECT count(*) FROM {schema}.{table} t, fields f WHERE f.field_name = %s '
                  'AND st_intersects(t.{geom}, f.polygon)').format(
            schema=pgsql.Identifier(schema), table=pgsql.Identifier(table),
            geom=pgsql.Identifier(geom_col)),
        params=(field_name,))
    return rows and rows[0][0] > 0


def table_year(db, schema, table):
    """Year from the table name when it carries one (the import names
    tables that way), otherwise the most common year of ``date_``. The
    max(date_) used before picked up stray rows dated 2000 or 2026."""
    match = re.search(r'(19|20)\d{2}', table)
    if match:
        return int(match.group(0))
    rows = db.execute_and_return(
        pgsql.SQL('SELECT extract(year FROM date_)::int AS y, count(*) FROM {schema}.{table} '
                  'WHERE date_ IS NOT NULL GROUP BY y ORDER BY count(*) DESC LIMIT 1').format(
            schema=pgsql.Identifier(schema), table=pgsql.Identifier(table)))
    if rows and rows[0][0]:
        return int(rows[0][0])
    return None


def numeric_columns(db, schema, table):
    rows = db.execute_and_return(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = %s "
        "AND table_name = %s AND data_type IN ('integer', 'bigint', 'numeric', 'real', "
        "'double precision', 'smallint') ORDER BY ordinal_position", params=(schema, table))
    return [r[0] for r in rows]


def cell_means(db, schema, table, attribute, geometry_column, field_grid):
    totals = {}
    for row in field_grid.join_grid_to_table(db, schema, table, [attribute],
                                             geometry_column=geometry_column):
        value = row[attribute]
        if value is None:
            continue
        total, count = totals.get(row['cell_id'], (0.0, 0))
        totals[row['cell_id']] = (total + float(value), count + 1)
    return {cid: t / c for cid, (t, c) in totals.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    pc.add_farm_arguments(parser)
    args = parser.parse_args()
    app = pc.start_qgis()
    db = pc.connect_db(args)
    field_grid = pc.import_plugin_module('support_scripts.field_grid')
    from shapely import wkt as shapely_wkt

    anon = pc.Anonymiser(args.farm_id)
    out = pc.ensure_dir(args.out)
    fields = [r[0] for r in db.execute_and_return('SELECT field_name FROM fields ORDER BY 1')]
    harvest_tables = tables_in_schema(db, 'harvest')
    soil_tables = tables_in_schema(db, 'soil')

    for field_name in fields:
        field_id = anon.field_id(field_name)
        cells = field_grid.build_grid(db, field_name)
        if not cells:
            print('{}: no grid'.format(field_id))
            continue
        columns = {}
        sources = {}  # column -> source table (kept in the private mapping only)
        for table in harvest_tables:
            cols = db.get_all_columns(table, 'harvest')
            geom = 'polygon' if 'polygon' in cols else 'pos'
            ycol = pick_yield_column(cols)
            if not ycol or not table_touches_field(db, 'harvest', table, geom, field_name):
                continue
            year = table_year(db, 'harvest', table)
            if year is None:
                continue
            key = 'harvest_{}'.format(year)
            values = cell_means(db, 'harvest', table, ycol, geom, field_grid)
            if key in columns:  # several tables for one year: average them
                for cid, v in values.items():
                    columns[key][cid] = (columns[key].get(cid, v) + v) / 2
                sources[key] += ' + ' + table + '.' + ycol
            else:
                columns[key] = values
                sources[key] = table + '.' + ycol
        for table in soil_tables:
            cols = db.get_all_columns(table, 'soil')
            geom = 'polygon' if 'polygon' in cols else 'pos'
            if not table_touches_field(db, 'soil', table, geom, field_name):
                continue
            # The named trio first (the crop model's inputs), then every
            # other numeric column the laboratory returned (K-AL, P-AL,
            # Mg-AL, ...), so the index validation can use all of them.
            taken = set()
            for name, prefixes in (('clay', CLAY_PREFIXES), ('humus', HUMUS_PREFIXES),
                                   ('ph', PH_PREFIXES)):
                col = pick_column(cols, prefixes)
                if col and name not in columns:
                    columns[name] = cell_means(db, 'soil', table, col, geom, field_grid)
                    sources[name] = table + '.' + col
                    taken.add(col)
            for col in numeric_columns(db, 'soil', table):
                if col in taken or col.lower() in ('id', 'gid', 'field_row_id', 'row_id',
                                                  'lat', 'lon', 'latitude', 'longitude'):
                    continue
                key = 'soil_' + re.sub(r'[^a-z0-9]+', '_', col.lower()).strip('_')
                if key not in columns:
                    values = cell_means(db, 'soil', table, col, geom, field_grid)
                    if values:
                        columns[key] = values
                        sources[key] = table + '.' + col
        if not any(k.startswith('harvest_') for k in columns):
            print('{}: no harvest data, skipped'.format(field_id))
            continue
        keys = sorted(k for k in columns if k.startswith('harvest_')) + \
            [k for k in ('clay', 'humus', 'ph') if k in columns] + \
            sorted(k for k in columns if k.startswith('soil_'))
        path = os.path.join(out, '{}_cells_{}.csv'.format(args.farm_id, field_id))
        with open(path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(['cell_id', 'x', 'y'] + keys)
            for cell in cells:
                centroid = shapely_wkt.loads(cell.polygon_wkt).centroid
                writer.writerow([cell.cell_id, round(centroid.x, 6), round(centroid.y, 6)] +
                                [columns[k].get(cell.cell_id, '') for k in keys])
        print('{}: {} cells, sources {}'.format(field_id, len(cells), keys))
        anon.mapping.setdefault('cell_sources', {})[
            '{}/{}'.format(args.farm_id, field_id)] = sources
        field_grid.drop_grid(db)
    anon.save()
    app.exitQgis()


if __name__ == '__main__':
    main()
