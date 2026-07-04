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
    # TWColumnNames row 0, column 1 is the QComboBox listing numeric attributes
    # of the first available plant table.  setCurrentIndex(2) picks the third
    # attribute alphabetically (index 2) before it is added to the selected list.
    widget = gdf.guide.CGF.TWColumnNames.cellWidget(0, 1)
    widget.setCurrentIndex(2)
    gdf.guide.add_to_param_list(2, 0)  # add attribute at combo-index 2, table row 0
    gdf.guide.add_to_param_list(3, 0)  # add attribute at combo-index 3, table row 0
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

