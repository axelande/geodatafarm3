import sys
import os
from PyQt5 import QtWidgets

from support_scripts.find_iso_field import FindIsoField
from . import gdf

def test_import_field_from_isoxml(gdf):
    app = QtWidgets.QApplication(sys.argv)
    W = FindIsoField(gdf)
    W.fifw.PBAddFolder.click()
    W.on_item_clicked(W.fifw.LWFields.item(0))
    W.fifw.LEFieldName.setText('test_iso_added_field')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_iso_added_field":
            field_added = True
    assert field_added

if __name__ == '__main__':
    test_import_field_from_isoxml()