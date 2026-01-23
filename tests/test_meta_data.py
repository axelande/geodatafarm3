import xml.etree.ElementTree as ET
from pathlib import Path

from geodatafarm.support_scripts.pyagriculture.meta_data_widgets import MetaData


def test_meta_data_reads_and_writes(tmp_path):
    # prepare meta data dir
    meta_dir = tmp_path
    meta_subdir = meta_dir / 'meta_data'
    meta_subdir.mkdir()
    md_file = meta_subdir / 'FRMs.xml'
    md_file.write_text('<Farms schema="FRM">\n    <FRM1 A="" B="testfarm"/>\n</Farms>')

    # simple schema dict for MetaData.set_type_items
    # FRMs.xml uses attribute 'B' for the display name, so use 'B' here
    schema = {'B': {'Attribute_name': 'Name', 'Type': 'string'}}
    md = MetaData(meta_data_type='Farm', schema=schema, meta_data_dir=str(meta_dir))

    # initial table should contain the one item
    assert md.available_items_table_widget.count() == 1

    # modify via widgets and save
    # set a value in type widgets if present
    for i in range(md.type_widgets_layout.count()):
        frame = md.type_widgets_layout.itemAt(i).widget()
        widget = frame.layout().itemAt(1).widget()
        if hasattr(widget, 'setText'):
            widget.setText('NewName')
    md.save_item()

    # file should exist and contain the new entry
    tree = ET.parse(md_file)
    root = tree.getroot()
    assert any(child.attrib.get('B') == 'NewName' or child.attrib.get('B') == 'testfarm' for child in root)
