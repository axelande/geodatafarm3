import os
import pytest
from shapely.geometry import Polygon
from shapely import wkt

from . import gdf

def test_import_field_from_shapefile(gdf):
    gdf.add_shape_field()
    W = gdf.find_shape_field
    W.path='./tests/test_data/tabbehus.shp'
    W.zoom_level = 10
    W.fsfw.PBAddShapeFile.click()
    # Select the first field name column
    if W.fsfw.CBFieldNames.count() > 0:
        W.fsfw.CBFieldNames.setCurrentIndex(0)
    W.populate_field_list()
    # Select the first field in the list
    item = W.fsfw.LWFields.item(0)
    W.on_item_clicked(item)
    W.fsfw.LEFieldName.setText('test_shape_added_field')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_shape_added_field":
            field_added = True
    assert field_added

def test_polygon_coordinates_consistency_shapefile(gdf):
    gdf.add_shape_field()
    W = gdf.find_shape_field
    W.path = './tests/test_data/tabbehus.shp'
    W.fsfw.PBAddShapeFile.click()
    if W.fsfw.CBFieldNames.count() > 0:
        W.fsfw.CBFieldNames.setCurrentIndex(0)
    W.populate_field_list()
    item = W.fsfw.LWFields.item(0)
    W.on_item_clicked(item)
    original_wkt = W.current_polygon
    W.save_field()
    saved_wkt = W.current_polygon
    original_polygon = wkt.loads(original_wkt)
    saved_polygon = wkt.loads(saved_wkt)
    assert original_polygon.equals_exact(saved_polygon, tolerance=1e-7), "Polygon coordinates should remain consistent before and after saving."