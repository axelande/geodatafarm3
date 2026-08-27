"""Tests for support_scripts.field_grid.

Uses the shared ``gdf``/database fixture like tests/test_import_data.py, so
it must run as part of the full suite (`pytest tests`), not on its own -
see tests/conftest.py and the project's stateful/order-dependent test setup.
"""
from ..GeoDataFarm import GeoDataFarm
from ..support_scripts import field_grid
from . import gdf


def test_build_grid_returns_many_fine_cells_for_a_real_field(gdf: GeoDataFarm):
    cells = field_grid.build_grid(gdf.db, 'test_field')

    # test_field is a real ~150-200m-across quadrilateral (see
    # tests/test_field.py) - a 2m grid over it should be hundreds of cells,
    # not a handful, confirming this is a fine grid and not a coarse zone
    # split.
    assert len(cells) > 100
    assert all(c.polygon_wkt.startswith('POLYGON') for c in cells)
    assert len(set(c.cell_id for c in cells)) == len(cells)  # all unique

    field_grid.drop_grid(gdf.db)


def test_build_grid_returns_empty_for_an_unknown_field(gdf: GeoDataFarm):
    cells = field_grid.build_grid(gdf.db, 'no_such_field_at_all')

    assert cells == []


def test_drop_grid_removes_the_scratch_table(gdf: GeoDataFarm):
    field_grid.build_grid(gdf.db, 'test_field')
    assert 'crop_sim_grid' in gdf.db.get_tables_in_db('public')

    field_grid.drop_grid(gdf.db)

    assert 'crop_sim_grid' not in gdf.db.get_tables_in_db('public')


def test_join_grid_to_table_matches_cells_inside_a_polygon_only(gdf: GeoDataFarm):
    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells

    # A coarse "west half" polygon covering roughly half the field's own
    # bounding box, built directly from the field's extent rather than a
    # hand-picked WKT literal, so this stays correct if the fixture
    # geometry in tests/test_field.py ever changes.
    bbox = gdf.db.execute_and_return(
        "SELECT st_xmin(polygon), st_xmax(polygon), st_ymin(polygon),"
        " st_ymax(polygon) FROM fields WHERE field_name = 'test_field'")[0]
    xmin, xmax, ymin, ymax = bbox
    xmid = (xmin + xmax) / 2

    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_grid_join_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE soil.test_field_grid_join_synthetic (row_id serial"
        " PRIMARY KEY, date_ date, clay real, polygon geometry)")
    gdf.db.execute_sql(
        "INSERT INTO soil.test_field_grid_join_synthetic (date_, clay, polygon)"
        " VALUES ('2024-01-01', 22.0,"
        " st_makeenvelope(%s, %s, %s, %s, 4326))",
        params=(xmin - 1, ymin - 1, xmid, ymax + 1))

    matches = field_grid.join_grid_to_table(
        gdf.db, 'soil', 'test_field_grid_join_synthetic', ['date_', 'clay'])

    assert matches
    assert all(m['clay'] == 22.0 for m in matches)
    matched_ids = {m['cell_id'] for m in matches}
    assert matched_ids.issubset({c.cell_id for c in cells})
    # Not every cell should match a polygon covering only half the field.
    assert len(matched_ids) < len(cells)

    gdf.db.execute_sql("DROP TABLE IF EXISTS soil.test_field_grid_join_synthetic")
    field_grid.drop_grid(gdf.db)


def test_join_grid_to_table_matches_points_inside_cells(gdf: GeoDataFarm):
    cells = field_grid.build_grid(gdf.db, 'test_field')
    assert cells
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_grid_point_join_synthetic")
    gdf.db.execute_sql(
        "CREATE TABLE harvest.test_field_grid_point_join_synthetic (row_id serial"
        " PRIMARY KEY, yield_value real, pos geometry(Point, 4326))")
    gdf.db.execute_sql(
        "INSERT INTO harvest.test_field_grid_point_join_synthetic (yield_value, pos)"
        " SELECT 123.0, st_centroid(polygon) FROM public.crop_sim_grid LIMIT 1")

    matches = field_grid.join_grid_to_table(
        gdf.db, 'harvest', 'test_field_grid_point_join_synthetic',
        ['yield_value'], geometry_column='pos')

    assert len(matches) == 1
    assert matches[0]['yield_value'] == 123.0
    gdf.db.execute_sql("DROP TABLE IF EXISTS harvest.test_field_grid_point_join_synthetic")
    field_grid.drop_grid(gdf.db)
