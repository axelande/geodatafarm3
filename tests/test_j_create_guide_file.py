import os

import pytest

from ..GeoDataFarm import GeoDataFarm
from . import gdf

def test_create_guide_file(gdf: GeoDataFarm):
    clean_up()
    gdf.create_guide()
    gdf.guide.possible_attr('plant')
    widget = gdf.guide.CGF.TWColumnNames.cellWidget(0, 1)
    widget.setCurrentIndex(2)
    gdf.guide.add_to_param_list(2, 0)
    gdf.guide.add_to_param_list(3, 0)
    gdf.guide.CGF.TWSelected.selectRow(1)
    gdf.guide.remove_from_param_list()
    gdf.guide.CGF.CBFields.setCurrentIndex(1)
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

