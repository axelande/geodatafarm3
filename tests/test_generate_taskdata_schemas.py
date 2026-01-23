import json
import tempfile
import os

from geodatafarm.support_scripts.pyagriculture.generate_taskdata import GenerateTaskDataWidget


def test_load_schemas_from_custom_dir(tmp_path):
    # create a fake schema file
    dir_ = tmp_path / "schemas"
    dir_.mkdir()
    schema = {"Name": "Test", "A": {"Attribute_name": "A"}}
    file_path = dir_ / "TST.schema"
    file_path.write_text(json.dumps(schema))

    gtd = GenerateTaskDataWidget(parent=None)
    gtd.load_schemas(str(dir_))

    assert 'TST' in gtd.schemas
    assert gtd.schemas['TST']['Name'] == 'Test'
