import xml.etree.ElementTree as ET
from pathlib import Path

from qgis.PyQt.QtWidgets import QTableWidgetItem
from geodatafarm.support_scripts.pyagriculture.create_recipe import CreateRecipe, CheckableComboBox


class DummyParent:
    def __init__(self):
        # minimal schema needed by CreateRecipe.continue_to_attributes
        self.schemas = {
            'TST': {
                'Name': 'Test',
                'A': {'Attribute_name': 'SomeName', 'Use': 'o'},
                'B': {'Attribute_name': 'RequiredAttr', 'Use': 'r'},
                'includes': {}
            }
        }


def test_store_data_writes_recipe(tmp_path):
    parent = DummyParent()
    cr = CreateRecipe(parent=parent)
    # populate a single row in available_attributes_list that will be used to create XML
    cr.available_attributes_list.setRowCount(1)
    item = QTableWidgetItem('Test | TST')
    cr.available_attributes_list.setItem(0, 0, item)
    # add a CheckableComboBox with one required attribute (B)
    cb = CheckableComboBox()
    cb.addItem('SomeName | A', checked=False)
    cb.addItem('RequiredAttr | B', checked=True)
    cr.available_attributes_list.setCellWidget(0, 1, cb)

    # Instead, create a simple xml to write
    path = tmp_path / "out.recipe"
    # ensure storage reads our attributes
    # (clear unrelated UI widgets to avoid interference)
    cr.included_schemas_list.clear()
    # call store_data with a path (should not show dialog)
    cr.store_data(path=str(path))

    assert path.exists()
    tree = ET.parse(str(path))
    root = tree.getroot()
    assert root.tag == 'ISO11783_TaskData'
    # verify our TST element and attr B is present
    tsts = root.findall('TST')
    assert len(tsts) == 1
    assert 'B' in tsts[0].attrib
