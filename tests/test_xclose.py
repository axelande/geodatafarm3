import pytest
from . import gdf, GeoDataFarm

# @pytest.mark.depends(on=['remove_sec_field'], scope='session')
def test_remove_crop(gdf: GeoDataFarm):
    gdf.dock_widget.LWCrops.itemAt(0, 0).setCheckState(2)
    gdf.dock_widget.PBRemoveCrop.click()

# @pytest.mark.depends(on=['import_text'], name='remove_text')
def test_remove_test_field_datasets(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(i).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    found = False
    for i, text in enumerate(items):
        if 'test_field' in text:
            gdf.tabel_mgmt.TMD.SATables.item(i).setCheckState(2)
            found = True
    gdf.tabel_mgmt.TMD.pButRemove.click()
    assert found

# @pytest.mark.depends(on=['import_harvest_text'], name='remove_iso')
def test_remove_iso_dataset(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(i).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    found = False
    for i, text in enumerate(items):
        if 'test_iso_field' in text:
            gdf.tabel_mgmt.TMD.SATables.item(i).setCheckState(2)
            found = True
    gdf.tabel_mgmt.TMD.pButRemove.click()
    assert found
fields = ['test_field', 'test_iso_field'] #, 'test_iso_field2']
# @pytest.mark.depends(scope='session', on=['remove_text'], name='remove_field')
@pytest.mark.parametrize('field_name', fields)
def test_remove_xfield(gdf: GeoDataFarm, field_name):
    gdf.add_field.clicked_define_field()
    items = [gdf.dock_widget.LWFields.item(i).text() for i in range(gdf.dock_widget.LWFields.count())]
    for i, text in enumerate(items):
        if field_name in text:
            gdf.dock_widget.LWFields.item(i).setCheckState(2)
    gdf.add_field.remove_field()
