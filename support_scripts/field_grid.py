"""Sub-field spatial grid for the Crop simulation feature.

Builds a field's 2m x 2m grid - the same construction "Create irrigation
year" already uses (see import_data/handle_irrigation.py's
``create_grid_year`` and database_scripts/create_new_farm.py's
``makegrid_2d`` PostGIS function, which steps that many metres
geodesically) - and lets a caller match each cell against whatever
spatially-located data already exists for the field: imported
soil/plant/ferti tables' Voronoi polygons (see
import_data/handle_text_data.py's ``create_polygons``, which already gives
every imported point a "closest sample wins" coverage area clipped to the
field), the same way database_scripts/mean_analyse.py already joins
harvest points to other schemas' polygons via ``st_intersects``.

There is deliberately no "draw a zone" step here - this only reads data
that's already there. A cell with nothing overlapping it simply gets no
match; callers fall back to the field-wide ``.manual`` value (see
database_scripts/crop_simulation.py).
"""
import math
from dataclasses import dataclass

from psycopg2 import sql as pgsql

from . import db_rows

__author__ = 'Axel Horteborn'

CELL_SIZE_M = 2
# Above this many cells, build_grid coarsens the cell size instead of
# handing back a fine grid a caller might be tempted to thin out by
# stride-sampling it (e.g. cells[::N]) - makegrid_2d lays cells out
# row-major, so a fixed stride over the flat list samples a diagonal
# streak across the field rather than shrinking every cell, leaving most
# of a rendered heatmap blank instead of a smaller, still-complete mosaic.
# Coarsening the cell size instead keeps every returned cell meaningful:
# small/medium fields still get the full 2m resolution; only a very large
# field trades resolution for a grid that stays whole.
_TARGET_MAX_CELLS = 2500
# A plain (non-temp) scratch table: this DB wrapper pools connections and
# commits per call (see database_scripts/db.py's execute_sql), so a real
# Postgres TEMP TABLE wouldn't reliably survive between the build_grid()
# call and the join queries that follow it on a different pooled
# connection - a plain table, built/queried/dropped within one simulation
# run, is the same workaround import_data/handle_text_data.py's
# create_polygons already uses (its "temp_tbl2").
_GRID_TABLE = 'crop_sim_grid'


@dataclass(frozen=True)
class GridCell:
    cell_id: int
    polygon_wkt: str


def build_grid(db, field_name):
    """(Re)builds the field's grid into the scratch table
    ``public.crop_sim_grid``, replacing whatever was there before (from a
    previous field/run). Cells are ``CELL_SIZE_M`` metres square (the same
    construction "Create irrigation year" uses) unless that would produce
    more than :data:`_TARGET_MAX_CELLS` cells, in which case the cell size
    is scaled up just enough to stay near that budget - see
    :data:`_TARGET_MAX_CELLS` for why this beats returning a fine grid and
    thinning it after the fact.

    Returns
    -------
    list[GridCell]
        Empty if the field can't be found.
    """
    rows = db_rows(db.execute_and_return(
        "SELECT st_astext(polygon), st_area(polygon::geography)"
        " FROM fields WHERE field_name = %s", params=(field_name,)))
    if not rows or not rows[0][0]:
        return []
    polygon_wkt, area_m2 = rows[0][0], rows[0][1] or 0.0
    cell_size = CELL_SIZE_M
    max_area = _TARGET_MAX_CELLS * CELL_SIZE_M * CELL_SIZE_M
    if area_m2 > max_area:
        # makegrid_2d's width_step/height_step are declared integer.
        cell_size = max(CELL_SIZE_M, int(math.ceil(math.sqrt(area_m2 / _TARGET_MAX_CELLS))))
    tbl = pgsql.Identifier(_GRID_TABLE)
    db.execute_sql(pgsql.SQL("DROP TABLE IF EXISTS public.{tbl}").format(tbl=tbl))
    db.execute_sql(
        pgsql.SQL(
            "CREATE TABLE public.{tbl} AS"
            " SELECT row_number() OVER () AS cell_id, cell AS polygon FROM ("
            " SELECT (st_dump(makegrid_2d(st_geomfromtext(%s, 4326), %s, %s))).geom AS cell"
            " ) g WHERE st_intersects(cell, st_geomfromtext(%s, 4326))"
        ).format(tbl=tbl),
        params=(polygon_wkt, cell_size, cell_size, polygon_wkt))
    cells = db_rows(db.execute_and_return(
        pgsql.SQL("SELECT cell_id, st_astext(polygon) FROM public.{tbl} ORDER BY cell_id")
        .format(tbl=tbl)))
    return [GridCell(cell_id=r[0], polygon_wkt=r[1]) for r in cells]


def drop_grid(db):
    """Drops the scratch grid table - call once a simulation run is done
    with it, so it doesn't linger between fields/runs."""
    db.execute_sql(pgsql.SQL("DROP TABLE IF EXISTS public.{tbl}").format(
        tbl=pgsql.Identifier(_GRID_TABLE)))


def join_grid_to_table(db, schema, table, columns):
    """Matches every grid cell (see :func:`build_grid` - must be called
    first) to whichever row(s) of ``schema.table`` cover its centroid.

    A cell's centroid rather than the cell polygon itself is used to avoid
    a cell picking up two candidate rows just because it straddles a
    shared edge between two adjacent Voronoi polygons - each cell gets
    (at most) one row per candidate table.

    Parameters
    ----------
    columns: list[str]
        Extra columns to select from ``table`` (e.g. ``['date_', 'clay']``)
        alongside ``cell_id``.

    Returns
    -------
    list[dict]
        One dict per matched (cell, row) pair, with keys ``cell_id`` plus
        every name in ``columns``. A cell with nothing overlapping it is
        simply absent - callers fall back to a field-wide value.
    """
    select = pgsql.SQL(', ').join(
        [pgsql.SQL('t.') + pgsql.Identifier(c) for c in columns])
    query = pgsql.SQL(
        "SELECT g.cell_id, {select} FROM public.{grid} g"
        " JOIN {schema}.{tbl} t"
        " ON t.polygon IS NOT NULL"
        " AND st_intersects(t.polygon, st_centroid(g.polygon))"
    ).format(select=select, grid=pgsql.Identifier(_GRID_TABLE),
             schema=pgsql.Identifier(schema), tbl=pgsql.Identifier(table))
    rows = db_rows(db.execute_and_return(query))
    return [dict(zip(['cell_id'] + columns, row)) for row in rows]
