import os

import pytest

from ..GeoDataFarm import GeoDataFarm
from . import gdf

def test_create_guide_file(gdf: GeoDataFarm):
    clean_up()
    gdf.create_guide()
    # Select the field first so the attribute list is filtered to tables linked
    # to this field.  Without filtering, stale tables left in the shared
    # database from earlier runs may land at row 0 with no numeric columns,
    # making cellWidget(0, 1) return None.
    idx = gdf.guide.CGF.CBFields.findText('test_field')
    gdf.guide.CGF.CBFields.setCurrentIndex(idx)
    gdf.guide.possible_attr('plant')
    # Find the row for the plant table imported in test_import_plant_text.
    # Using a name-based lookup rather than assuming row 0 makes the test
    # resilient to stale tables from previous CI/CD runs appearing first.
    expected_table = 'plant.test_field_plant_2023_04_15'
    tw = gdf.guide.CGF.TWColumnNames
    target_row = next(
        (r for r in range(tw.rowCount())
         if tw.item(r, 0) is not None and tw.item(r, 0).text() == expected_table),
        0)
    # column 1 of the target row is the QComboBox listing numeric attributes.
    # setCurrentIndex(2) picks the third attribute alphabetically (index 2).
    widget = tw.cellWidget(target_row, 1)
    if widget is None:
        plant_tables = gdf.db.get_tables_in_db('plant')
        field_tables = gdf.guide._get_tables_for_field('plant', 'test_field')
        print(f"\nDEBUG plant_tables={plant_tables}")
        print(f"DEBUG field_tables={field_tables}")
        print(f"DEBUG rowCount={tw.rowCount()}")
    assert widget is not None, (
        f"No attribute combo found for {expected_table} "
        f"(rowCount={tw.rowCount()})")
    widget.setCurrentIndex(2)
    gdf.guide.add_to_param_list(2, target_row)  # add attribute at combo-index 2
    gdf.guide.add_to_param_list(3, target_row)  # add attribute at combo-index 3
    gdf.guide.CGF.TWSelected.selectRow(1)
    gdf.guide.remove_from_param_list()
    gdf.guide.update_max_min()
    gdf.guide.set_output_path()
    gdf.guide.create_file()
    assert os.path.isfile("./tests/guide_file.shp")
    import time
    time.sleep(0.5)
    clean_up()

def clean_up():
    for ending in ['shp', 'prj', 'dbf', 'shx']:
        try:
            os.remove(f'./tests/guide_file.{ending}')
        except FileNotFoundError:
            pass

