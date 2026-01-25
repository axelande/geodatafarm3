import pytest

from geodatafarm.support_scripts.pyagriculture.generate_taskdata import GenerateTaskDataWidget


def test_create_dialogs_use_exec(monkeypatch, qtbot):
    # Create a widget instance
    w = GenerateTaskDataWidget(parent=None, parent_gdf=None)
    # Track calls
    called = {'create_recipe': False}

    def fake_exec_create(self=None):
        called['create_recipe'] = True

    # Patch CreateRecipe.exec so we don't block tests
    monkeypatch.setattr('geodatafarm.support_scripts.pyagriculture.create_recipe.CreateRecipe.exec', fake_exec_create)

    # Call the method; it should call exec() and set our flag
    w.create_new_recipe()

    assert called['create_recipe']
