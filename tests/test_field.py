import pytest
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature)

from . import gdf, GeoDataFarm

@pytest.mark.depends(scope='session', name='add_field')
def test_add_field(gdf: GeoDataFarm):
    gdf.add_field.clicked_define_field()
    gdf.add_field.AFD.LEFieldName.setText('test_field')
    feat = QgsFeature(gdf.add_field.field.fields()) # Create the features
    pointxys = []
    coords = [[55.39658060, 13.55289676], [55.39478077, 13.55261314], [55.39429053, 13.55921056], [55.39625846, 13.55940787]]
    for coord in coords:
        pointxys.append(QgsPointXY(coord[1], coord[0])) 
    geom = QgsGeometry.fromPolygonXY([pointxys])
    feat.setGeometry(geom)
    gdf.add_field.field.addFeature(feat)
    gdf.add_field.field.endEditCommand() # Stop editing
    gdf.add_field.field.commitChanges() # Save changes
    gdf.add_field.save()

@pytest.mark.depends(scope='session', on=['remove_text'], name='remove_field')
def test_remove_field(gdf: GeoDataFarm):
    gdf.add_field.clicked_define_field()
    gdf.dock_widget.LWFields.item(0).setCheckState(2)
    gdf.add_field.remove_field()
