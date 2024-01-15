import pytest
from . import gdf, GeoDataFarm

# @pytest.mark.depends(scope='session', name='add_crop')
def test_add_crop(gdf:GeoDataFarm):
    gdf.dock_widget.LECropName.setText('Potatoes')
    gdf.dock_widget.PBAddCrop.click()
