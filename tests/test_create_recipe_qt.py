import pytest
from qgis.PyQt.QtWidgets import QApplication

from geodatafarm.support_scripts.pyagriculture.create_recipe import CreateRecipe


@pytest.mark.qt
def test_create_recipe_ui_smoke(qtbot, tmp_path, monkeypatch):
    parent = type('P', (), {'schemas': {}})()
    # Mark parent as test-mode so CreateRecipe won't show blocking QMessageBox during save
    parent.test_mode = True
    app = QApplication.instance() or QApplication([])
    cr = CreateRecipe(parent=parent)
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(cr)
    else:
        cr.show()
    assert cr.isVisible()
    # clicking buttons should not raise
    cr.add_item_button.click()
    # Set a recipe name (the dialog now uses a line edit instead of file dialog)
    cr.recipe_name_edit.setText('test_recipe')
    # Use store_data with explicit path to skip recipe name prompt and file dialogs
    out = tmp_path / 'test.recipe'
    cr.store_data(path=str(out))
    cr.close()


def test_create_recipe_uses_parent_gdf_for_schemas(qtbot):
    # If no QWidget parent is provided, parent_gdf should still supply schemas
    parent_gdf = type('P', (), {})()
    parent_gdf.schemas = {
        'ABC': {'Name': 'AbcName', 'includes': {'ABC': {'Use': 'r'}}}
    }
    cr = CreateRecipe(parent=None, parent_gdf=parent_gdf)
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(cr)
    else:
        cr.show()
    # The available_schemas_list should be populated from parent_gdf
    assert cr.available_schemas_list.rowCount() == 1
    # The display code adds spaces ('Abc Name | ABC'), check for the display name
    assert 'Abc Name' in cr.available_schemas_list.item(0, 0).text()
    cr.close()
