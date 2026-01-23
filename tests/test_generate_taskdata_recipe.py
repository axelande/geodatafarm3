import os
from types import SimpleNamespace

import pytest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog

from geodatafarm.support_scripts.pyagriculture.generate_taskdata_widgets import GenerateTaskDataWidget


def ensure_qapp():
    app = QApplication.instance()
    if app is None:
        QApplication([])


def test_load_recipe_builds_layout(tmp_path, monkeypatch):
    ensure_qapp()
    recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test1.recipe')
    if not os.path.isfile(recipe_path):
        pytest.skip('test1.recipe not available')

    # Monkeypatch the file dialog to return our test recipe
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

    widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
    # Ensure schemas loaded (constructor calls load_schemas)
    widget.load_schemas()

    # Call load_recipe which should parse and create layouts
    widget.load_recipe()

    assert hasattr(widget, 'q_layout')
    assert widget.q_layout.rowCount() >= 1
    # Ensure middle_layout has a widget (the scroll area)
    assert widget.middle_layout.count() >= 1


def test_store_data_writes_xml(tmp_path, monkeypatch):
    ensure_qapp()
    recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test1.recipe')
    if not os.path.isfile(recipe_path):
        pytest.skip('test1.recipe not available')

    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))
    widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
    widget.load_schemas()
    widget.load_recipe()

    out_file = tmp_path / 'out.xml'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args, **kwargs: (str(out_file), ''))

    # Should not raise
    widget.store_data()

    assert out_file.exists()
    content = out_file.read_text()
    assert '<ISO11783_TaskData' in content
