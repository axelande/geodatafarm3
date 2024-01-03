import pytest
from . import gdf, GeoDataFarm

@pytest.mark.depends(scope='session',name='add_crop', on=['add_field'])
def test_add_crop(gdf:GeoDataFarm):
    gdf.dock_widget.LECropName.setText('Potatoes')
    gdf.dock_widget.PBAddCrop.click()

@pytest.mark.depends(on=['remove_field'], scope='session')
def test_remove_crop(gdf: GeoDataFarm):
    try:
        gdf.dock_widget.LWCrops.itemAt(0, 0).setCheckState(2)
    except AttributeError:
        test_add_crop(gdf)
        gdf.dock_widget.LWCrops.itemAt(0, 0).setCheckState(2)
    gdf.dock_widget.PBRemoveCrop.click()