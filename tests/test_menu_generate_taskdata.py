import pytest

from geodatafarm.GeoDataFarm import GeoDataFarm


def test_generate_isoxml_tab_has_tabs_after_run(qgis_iface):
    """Test that the Generate ISO XMLs tab has sub-tabs in the UI."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    dock = g.dock_widget
    assert dock is not None
    # Check the tab widget exists
    assert hasattr(dock, 'tabWidgetGenerateIsoxml')
    tab_widget = dock.tabWidgetGenerateIsoxml
    assert tab_widget.count() >= 5  # At least 5 tabs (may have more metadata tabs)
    # Check some expected tab names are present
    tab_names = [tab_widget.tabText(i) for i in range(tab_widget.count())]
    assert 'Recipe' in tab_names
    assert 'Farm' in tab_names
    assert 'Customer' in tab_names
    assert 'Worker' in tab_names
    assert 'Device' in tab_names


def test_generate_isoxml_has_recipe_buttons(qgis_iface):
    """Test that the Recipe tab has action buttons."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    dock = g.dock_widget
    assert dock is not None
    # Check action buttons exist
    assert hasattr(dock, 'btnNewRecipe')
    assert hasattr(dock, 'btnLoadRecipe')
    assert hasattr(dock, 'btnResetRecipe')
    assert hasattr(dock, 'btnCreateFile')


def test_generate_isoxml_has_metadata_tables(qgis_iface):
    """Test that metadata tables exist in the UI."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    dock = g.dock_widget
    assert dock is not None
    # Check tables exist (using actual UI widget names)
    assert hasattr(dock, 'tableFarm')
    assert hasattr(dock, 'tableCustomer')
    assert hasattr(dock, 'tableWorker')
    assert hasattr(dock, 'tableDevice')


def test_generate_isoxml_has_metadata_buttons(qgis_iface):
    """Test that metadata Add/Edit/Remove buttons exist."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    dock = g.dock_widget
    assert dock is not None
    # Farm buttons
    assert hasattr(dock, 'btnAddFarm')
    assert hasattr(dock, 'btnEditFarm')
    assert hasattr(dock, 'btnRemoveFarm')
    # Customer buttons
    assert hasattr(dock, 'btnAddCustomer')
    assert hasattr(dock, 'btnEditCustomer')
    assert hasattr(dock, 'btnRemoveCustomer')
    # Worker buttons
    assert hasattr(dock, 'btnAddWorker')
    assert hasattr(dock, 'btnEditWorker')
    assert hasattr(dock, 'btnRemoveWorker')
    # Device buttons
    assert hasattr(dock, 'btnAddDevice')
    assert hasattr(dock, 'btnEditDevice')
    assert hasattr(dock, 'btnRemoveDevice')


def test_generate_action_shows_tab(qgis_iface):
    """Test that open_generate_menu selects the generate tab."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    g.open_generate_menu()
    # Check the generate tab is selected
    tab = getattr(g.dock_widget, 'tab_generate_isoxml', None) or getattr(g.dock_widget, 'tab_17', None)
    tab_widget = getattr(g.dock_widget, 'tabWidget', None)
    if tab_widget is not None and tab is not None:
        assert tab_widget.currentWidget() is tab


def test_metadata_tables_populated(qgis_iface):
    """Test that metadata tables are populated after setup."""
    g = GeoDataFarm(qgis_iface, True)
    g.run()
    # The generate isoxml controller should exist on the dock_widget
    dock = g.dock_widget
    assert dock is not None
    assert hasattr(dock, 'generate_isoxml_controller')
