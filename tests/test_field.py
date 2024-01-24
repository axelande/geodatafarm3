import pytest
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature)

from . import gdf, GeoDataFarm

test_data = [('test_field', [[55.39658060, 13.55289676], [55.39478077, 13.55261314], [55.39429053, 13.55921056], [55.39625846, 13.55940787]]),
             ('test_iso_field', [[55.39185207, 13.53883729], [55.39802257, 13.53983692], [55.39745005, 13.54726151], [55.39066160, 13.54608921]])
             ]
# @pytest.mark.depends(scope='session', name='add_field')
@pytest.mark.parametrize('name, coord_input', test_data)
def test_add_field(gdf: GeoDataFarm, name, coord_input):
    gdf.add_field.clicked_define_field()
    gdf.add_field.AFD.LEFieldName.setText(name)
    feat = QgsFeature(gdf.add_field.field.fields()) # Create the features
    pointxys = []
    coords = coord_input
    for coord in coords:
        pointxys.append(QgsPointXY(coord[1], coord[0])) 
    geom = QgsGeometry.fromPolygonXY([pointxys])
    feat.setGeometry(geom)
    gdf.add_field.field.addFeature(feat)
    gdf.add_field.field.endEditCommand() # Stop editing
    gdf.add_field.field.commitChanges() # Save changes
    save_suc = gdf.add_field.save()
    assert save_suc
