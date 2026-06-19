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
    widget = gdf.guide.CGF.IsoTWColumnNames.cellWidget(0, 1)
    widget.setCurrentIndex(2)
    gdf.guide.iso_add_to_param_list(2, 0)
    gdf.guide.iso_add_to_param_list(3, 0)
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
