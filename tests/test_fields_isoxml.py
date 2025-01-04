import sys
import os
from PyQt5 import QtWidgets

#from ..GeoDataFarm import GeoDataFarm
from ..support_scripts.find_iso_field import FindIsoField
from . import gdf

def test_import_par_field_from_isoxml(gdf):
    W = FindIsoField(gdf, test_path='./tests/test_data/TASKDATA3/TASKDATA.XML')
    W.zoom_level = 10
    W.fifw.PBAddFolder.click()
    W.on_item_clicked(W.fifw.LWFields.item(0))
    W.fifw.LEFieldName.setText('test_iso_added_field')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_iso_added_field":
            field_added = True
    W.disconnect()
    assert field_added

def test_import_task_field_from_isoxml(gdf):
    W = FindIsoField(gdf, test_path='./tests/test_data/TASKDATA2/TASKDATA.XML')
    W.fifw.PBAddFolder.click()
    W.fifw.PBGetAdditionalData.click()
    W.on_item_clicked(W.fifw.LWFields.item(0))
    W.fifw.LEFieldName.setText('test_iso_added_field2')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_iso_added_field2":
            field_added = True
    W.disconnect()
    assert field_added


if __name__ == '__main__':
    test_import_field_from_isoxml()