import sys
import os

from PyQt5 import QtWidgets
import pytest
from shapely.geometry import Polygon
from shapely import wkt

#from ..GeoDataFarm import GeoDataFarm
from ..support_scripts.find_iso_field import FindIsoField
from . import gdf

def test_import_par_field_from_isoxml(gdf):
    W = FindIsoField(gdf, test_path='./tests/test_data/TASKDATA3/TASKDATA.XML')
    W.zoom_level = 10
    W.fifw.PBAddFolder.click()
    W.on_item_clicked(W.fifw.LWFields.item(0))
    W.fifw.LEFieldName.setText('test_iso_added_field')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_iso_added_field":
            field_added = True
    W.disconnect()
    assert field_added

def test_import_task_field_from_isoxml(gdf):
    W = FindIsoField(gdf, test_path='./tests/test_data/TASKDATA2/TASKDATA.XML')
    W.fifw.PBAddFolder.click()
    W.fifw.PBGetAdditionalData.click()
    W.on_item_clicked(W.fifw.LWFields.item(0))
    W.fifw.LEFieldName.setText('test_iso_added_field2')
    W.save_field()
    field_added = False
    for index in range(gdf.dock_widget.LWFields.count()):
        if gdf.dock_widget.LWFields.item(index).text() == "test_iso_added_field2":
            field_added = True
    W.disconnect()
    assert field_added

@pytest.fixture
def find_iso_field():
    """Fixture to set up the FindIsoField instance."""
    parent = type('test', (object,), {'test_mode': True, 'db': None, 'tr': lambda x: x})
    find_iso_field = FindIsoField(parent)
    # find_iso_field.fifw = FindIsoFieldWidget()
    yield find_iso_field

def test_polygon_coordinates_consistency(find_iso_field: FindIsoField):
    """Test that the polygon coordinates remain consistent before and after saving."""
    # Create a sample polygon
    original_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    original_wkt = original_polygon.wkt

    # Plot the polygon
    find_iso_field.fields['Test Field'] = original_wkt
    find_iso_field.load_wkt(original_wkt)
    find_iso_field.current_polygon = original_wkt

    # Save the polygon
    find_iso_field.save_updated_polygon()

    # Get the saved polygon WKT
    saved_wkt = find_iso_field.current_polygon

    # Load the saved polygon
    saved_polygon = wkt.loads(saved_wkt)

    # Compare the coordinates
    assert original_polygon.equals_exact(saved_polygon, tolerance=1e-7), "The polygon coordinates should remain consistent before and after saving."


if __name__ == '__main__':
    test_import_field_from_isoxml()