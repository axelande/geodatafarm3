import pytest
from PyQt5.QtCore import QDate

from ..GeoDataFarm import GeoDataFarm
from . import gdf


# @pytest.mark.depends(name='import_text', on=['add_field'])
def test_import_plant_text(gdf:GeoDataFarm):
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
    gdf.save_planting.importer.ITD.DE.setDate(QDate.fromString('2023-04-15', "yyyy-MM-dd"))
    suc = gdf.save_planting.importer.trigger_insection()
    assert suc[0]


def test_import_harvest_text(gdf:GeoDataFarm):
    gdf.dock_widget.CBHvFileType.setCurrentIndex(1)
    gdf.dock_widget.PBHvAddFile.click()
    gdf.save_harvesting.importer.ITD.PBAddInputFile.click()
    gdf.save_harvesting.importer.ITD.CBField.setCurrentIndex(1)
    gdf.save_harvesting.importer.ITD.CBCrop.setCurrentIndex(1)
    for i in [2]:
        gdf.save_harvesting.importer.ITD.TWColumnNames.selectRow(i)
        gdf.save_harvesting.importer.ITD.PBAddParam.click()
    gdf.save_harvesting.importer.ITD.PBContinue.click()
    gdf.save_harvesting.importer.ITD.GLSpecific.itemAt(1).widget().setCurrentIndex(2)
    gdf.save_harvesting.importer.ITD.GLSpecific.itemAt(7).widget().setChecked(True)
    gdf.save_harvesting.importer.ITD.DE.setDate(QDate.fromString('2023-09-15', "yyyy-MM-dd"))
    suc = gdf.save_harvesting.importer.trigger_insection()
    assert suc[0]


# @pytest.mark.depends(name='import_harvest_text', on=['add_field2'])
def test_import_iso(gdf:GeoDataFarm):
    gdf.dock_widget.CBHvFileType.setCurrentIndex(2)
    gdf.dock_widget.PBHvAddFile.click()
    gdf.save_harvesting.importer.IXB.PBAddInputFolder.click()
    gdf.save_harvesting.importer.IXB.TWISODataAll.item(0, 0).setCheckState(2)
    gdf.save_harvesting.importer.IXB.PBFindFields.click()
    i = 0 #for i in range(gdf.save_harvesting.importer.IXB.TWISODataSelect.rowCount()):
    gdf.save_harvesting.importer.IXB.TWISODataSelect.cellWidget(i, 2).setCurrentIndex(0)
    gdf.save_harvesting.importer.IXB.TWISODataSelect.cellWidget(i, 3).setCurrentIndex(1)
    gdf.save_harvesting.importer.IXB.TWColumnNames.selectRow(3)
    gdf.save_harvesting.importer.IXB.PBAddParam.click()
    suc = gdf.save_harvesting.importer.add_to_database()
    assert suc
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(i).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    for text in items:
        if 'test_iso_field' in text:
            assert True
