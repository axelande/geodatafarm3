import pytest
from . import gdf, GeoDataFarm

# @pytest.mark.depends(on=['remove_sec_field'], scope='session')
def test_remove_crop(gdf: GeoDataFarm):
    gdf.dock_widget.LWCrops.itemAt(0, 0).setCheckState(2)
    gdf.dock_widget.PBRemoveCrop.click()

# @pytest.mark.depends(on=['import_text'], name='remove_text')
def test_remove_dataset(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(0).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    for i, text in enumerate(items):
        if 'test_field' in text:
            gdf.tabel_mgmt.TMD.SATables.itemAt(i, 0).setCheckState(2)
    gdf.tabel_mgmt.TMD.pButRemove.click()

# @pytest.mark.depends(on=['import_harvest_text'], name='remove_iso')
def test_remove_iso_dataset(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(0).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    for i, text in enumerate(items):
        if 'test_iso_field' in text:
            gdf.tabel_mgmt.TMD.SATables.itemAt(i, 0).setCheckState(2)
    gdf.tabel_mgmt.TMD.pButRemove.click()


# @pytest.mark.depends(scope='session', on=['remove_text'], name='remove_field')
def test_remove_field(gdf: GeoDataFarm):
    gdf.add_field.clicked_define_field()
    items = [gdf.dock_widget.LWFields.item(0).text() for i in range(gdf.dock_widget.LWFields.count())]
    for i, text in enumerate(items):
        if 'test_field' in text:
            gdf.dock_widget.LWFields.item(i).setCheckState(2)
    gdf.add_field.remove_field()

# @pytest.mark.depends(scope='session', on=['remove_iso'], name='remove_sec_field')
def test_remove_field2(gdf: GeoDataFarm):
    gdf.add_field.clicked_define_field()
    items = [gdf.dock_widget.LWFields.item(0).text() for i in range(gdf.dock_widget.LWFields.count())]
    for i, text in enumerate(items):
        if 'test_iso_field' in text:
            gdf.dock_widget.LWFields.item(i).setCheckState(2)
    gdf.add_field.remove_field()
