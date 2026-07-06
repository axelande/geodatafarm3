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
    matched = [text for text in items if text == field_name]
    print(f"\n[{field_name}] LWFields before removal: {items}")
    print(f"[{field_name}] Matched (will be checked): {matched}")
    for i, text in enumerate(items):
        if text == field_name:
            gdf.dock_widget.LWFields.item(i).setCheckState(_check_state('Checked'))
    gdf.add_field.remove_field()
    remaining_lw = [gdf.dock_widget.LWFields.item(i).text() for i in range(gdf.dock_widget.LWFields.count())]
    print(f"[{field_name}] LWFields after removal: {remaining_lw}")
    remaining_db = gdf.db.execute_and_return(
        "SELECT COUNT(*) FROM fields WHERE field_name = %s", params=(field_name,))
    print(f"[{field_name}] DB count after removal: {remaining_db}")
    assert field_name not in remaining_lw, f"Field {field_name!r} still in LWFields after removal: {remaining_lw}"
    assert isinstance(remaining_db, list) and remaining_db[0][0] == 0, (
        f"Field {field_name!r} still present in DB after removal")
