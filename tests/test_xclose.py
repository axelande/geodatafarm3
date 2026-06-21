import pytest
from . import gdf, GeoDataFarm
from geodatafarm.support_scripts.qt_data import _check_state

# @pytest.mark.depends(on=['remove_sec_field'], scope='session')
def test_remove_crop(gdf: GeoDataFarm):
    gdf.dock_widget.LWCrops.itemAt(0, 0).setCheckState(_check_state('Checked'))
    gdf.dock_widget.PBRemoveCrop.click()

# @pytest.mark.depends(on=['import_text'], name='remove_text')
def test_remove_test_field_datasets(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(i).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    found = False
    for i, text in enumerate(items):
        if 'test_field' in text or 'tabbehus' in text:
            gdf.tabel_mgmt.TMD.SATables.item(i).setCheckState(_check_state('Checked'))
            found = True
    gdf.tabel_mgmt.TMD.pButRemove.click()
    assert found

# @pytest.mark.depends(on=['import_harvest_text'], name='remove_iso')
def test_remove_iso_dataset(gdf: GeoDataFarm):
    gdf.dock_widget.PBEditTables.click()
    items = [gdf.tabel_mgmt.TMD.SATables.item(i).text() for i in range(gdf.tabel_mgmt.TMD.SATables.count())]
    found = False
    for i, text in enumerate(items):
        if 'test_iso' in text:
            gdf.tabel_mgmt.TMD.SATables.item(i).setCheckState(_check_state('Checked'))
            found = True
    gdf.tabel_mgmt.TMD.pButRemove.click()
    assert found
fields = ['test_field', 'test_iso_field', 'test_iso_added_field', 'test_iso_added_field2', 'test_iso_added_field3', 'test_shape_added_field', 'Tabbehus'] #, 'test_iso_field2']
# @pytest.mark.depends(scope='session', on=['remove_text'], name='remove_field')
@pytest.mark.parametrize('field_name', fields)
def test_remove_xfield(gdf: GeoDataFarm, field_name):
    gdf.add_field.clicked_define_field()
    items = [gdf.dock_widget.LWFields.item(i).text() for i in range(gdf.dock_widget.LWFields.count())]
    for i, text in enumerate(items):
        if field_name in text:
            gdf.dock_widget.LWFields.item(i).setCheckState(_check_state('Checked'))
    gdf.add_field.remove_field()
    assert field_name not in [gdf.dock_widget.LWFields.item(i).text() for i in range(gdf.dock_widget.LWFields.count())]
