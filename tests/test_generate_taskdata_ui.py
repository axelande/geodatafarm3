import pytest
from qgis.PyQt.QtWidgets import QWidget

from geodatafarm.support_scripts.pyagriculture.generate_taskdata_widgets import GenerateTaskDataWidget


def test_generate_widget_api():
    w = GenerateTaskDataWidget(parent=None)
    # The widget no longer creates its own menubar (GeoDataFarm provides it)
    assert not hasattr(w, 'generate_menu')
    # Ensure command-facing methods still exist
    expected_methods = {
        'create_new_recipe', 'load_schemas', 'reset_recipe'
    }
    for m in expected_methods:
        assert hasattr(w, m)
