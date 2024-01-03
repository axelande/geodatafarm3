import pytest
from PyQt5.QtCore import QDate

from ..GeoDataFarm import GeoDataFarm
from . import gdf


@pytest.mark.depends(name='import_text', on=['add_crop'])
def test_import_text(gdf:GeoDataFarm):
    gdf.dock_widget.CBPFileType.setCurrentIndex(1)
    gdf.dock_widget.PBPAddFile.click()
    gdf.save_planting.importer.ITD.PBAddInputFile.click()
    gdf.save_planting.importer.ITD.CBField.setCurrentIndex(1)
    gdf.save_planting.importer.ITD.CBCrop.setCurrentIndex(1)
    for i in [6, 13, 16, 19]:
        gdf.save_planting.importer.ITD.TWColumnNames.selectRow(i)
        gdf.save_planting.importer.ITD.PBAddParam.click()
    gdf.save_planting.importer.ITD.PBContinue.click()
    gdf.save_planting.importer.ITD.GLSpecific.itemAt(1).widget().setCurrentIndex(18)
    gdf.save_planting.importer.ITD.DE.setDate(QDate.fromString('2015-04-15', "yyyy-MM-dd"))
    suc = gdf.save_planting.importer.trigger_insection()
    assert suc[0]

@pytest.mark.depends(on=['import_text'], name='remove_text')
def test_remove_dataset(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    gdf.tabel_mgmt.TMD.SATables.itemAt(0, 0).setCheckState(2)
    gdf.tabel_mgmt.TMD.pButRemove.click()