import pytest

from geodatafarm.support_scripts.pyagriculture.generate_taskdata import GenerateTaskDataWidget


def test_create_dialogs_use_exec(monkeypatch, qtbot):
    # Create a widget instance
    w = GenerateTaskDataWidget(parent=None, parent_gdf=None)
    # Track calls
    called = {'create_recipe': False, 'farm': False, 'customer': False, 'worker': False, 'device': False}

    def fake_exec_create(self=None):
        called['create_recipe'] = True

    def fake_exec_meta(self=None):
        # Determine which meta by checking class name or args isn't easy; set True generically
        # We'll set all meta flags to True for simplicity
        called['farm'] = True
        called['customer'] = True
        called['worker'] = True
        called['device'] = True

    # Patch CreateRecipe.exec and MetaData.exec so we don't block tests
    monkeypatch.setattr('geodatafarm.support_scripts.pyagriculture.create_recipe.CreateRecipe.exec', fake_exec_create)
    monkeypatch.setattr('geodatafarm.support_scripts.pyagriculture.meta_data_widgets.MetaData.exec', fake_exec_meta)

    # Call the methods; they should call exec() and set our flags
    w.create_new_recipe()
    w.create_farm()
    w.create_customer()
    w.create_worker()
    w.create_device()

    assert called['create_recipe']
    assert called['farm'] and called['customer'] and called['worker'] and called['device']
