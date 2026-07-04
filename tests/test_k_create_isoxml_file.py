import os
import shutil

import pytest

from ..GeoDataFarm import GeoDataFarm
from . import gdf

TASKDATA_DIR = "./tests/TASKDATA"


def test_create_isoxml_file(gdf: GeoDataFarm):
    clean_up()
    gdf.create_guide()
    # Select the field first (Step 1) so the available-attribute list is
    # filtered to this field's tables. Otherwise the unfiltered list is keyed
    # on table name and row 0 may be an unrelated/empty table left in the
    # shared database, which makes the grid query return no data.
    idx = gdf.guide.CGF.IsoCBFields.findText('test_field')
    gdf.guide.CGF.IsoCBFields.setCurrentIndex(idx)
    gdf.guide.iso_possible_attr('plant')
    # Find the row for the plant table imported in test_import_plant_text.
    expected_table = 'plant.test_field_plant_2023_04_15'
    tw = gdf.guide.CGF.IsoTWColumnNames
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
    gdf.guide.iso_add_to_param_list(2, target_row)
    gdf.guide.iso_add_to_param_list(3, target_row)
    gdf.guide.CGF.IsoTWSelected.selectRow(1)
    gdf.guide.iso_remove_from_param_list()
    gdf.guide.iso_update_max_min()
    gdf.guide.iso_set_output_path()
    gdf.guide.iso_create_file()
    assert os.path.isfile(os.path.join(TASKDATA_DIR, "TASKDATA.XML"))
    assert os.path.isfile(os.path.join(TASKDATA_DIR, "GRD00000.BIN"))
    import time
    time.sleep(0.5)
    clean_up()


def clean_up():
    if os.path.isdir(TASKDATA_DIR):
        shutil.rmtree(TASKDATA_DIR, ignore_errors=True)
