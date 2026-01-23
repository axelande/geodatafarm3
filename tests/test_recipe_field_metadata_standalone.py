"""
Standalone tests for recipe loading with GRD field selector and metadata combobox population.

Run from the parent directory of geodatafarm:
    cd c:\\dev
    python -m pytest geodatafarm/tests/test_recipe_field_metadata_standalone.py -v
"""

import os
import sys
from types import SimpleNamespace

# This test file does not rely on tests/__init__.py imports
# Ensure we can import the module properly
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

import pytest
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QComboBox, QListWidget, QListWidgetItem

from geodatafarm.support_scripts.pyagriculture.generate_taskdata_widgets import GenerateTaskDataWidget


def ensure_qapp():
    app = QApplication.instance()
    if app is None:
        QApplication([])


class TestMetadataComboboxPopulation:
    """Tests for metadata combobox population with existing items from XML files."""

    def test_get_existing_metadata_items_returns_frm_entries(self):
        """Test that _get_existing_metadata_items loads FRM entries from FRMs.xml."""
        ensure_qapp()
        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()

        items = widget._get_existing_metadata_items('FRM')

        # Should return at least the entries from FRMs.xml
        assert len(items) > 0
        # Items should be tuples of (id, display_name)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in items)
        # Check that FRM1 exists (from the test data)
        ids = [item[0] for item in items]
        assert 'FRM1' in ids or 'FRM3' in ids or 'FRM4' in ids

    def test_get_existing_metadata_items_returns_wkr_entries(self):
        """Test that _get_existing_metadata_items loads WKR entries from WRKs.xml."""
        ensure_qapp()
        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()

        items = widget._get_existing_metadata_items('WKR')

        # Should return at least WRK1 from WRKs.xml
        # Note: schema key is 'WKR' but XML elements are 'WRK1', 'WRK2', etc.
        assert len(items) > 0
        ids = [item[0] for item in items]
        assert 'WRK1' in ids

    def test_get_existing_metadata_items_returns_empty_for_unknown_schema(self):
        """Test that _get_existing_metadata_items returns empty list for unknown schema."""
        ensure_qapp()
        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()

        items = widget._get_existing_metadata_items('UNKNOWN')
        assert items == []

    def test_get_existing_metadata_items_returns_empty_for_task_specific_schemas(self):
        """Test that TZN and PFD return empty (they are task-specific, not global)."""
        ensure_qapp()
        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()

        assert widget._get_existing_metadata_items('TZN') == []
        assert widget._get_existing_metadata_items('PFD') == []

    def test_update_ref_ids_populates_combobox_with_existing_metadata(self, monkeypatch):
        """Test that update_ref_ids populates IDREF comboboxes with existing metadata."""
        ensure_qapp()
        recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_frm_wrk_grd.recipe')
        if not os.path.isfile(recipe_path):
            pytest.skip('test_frm_wrk_grd.recipe not available')

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()
        widget.load_recipe()

        # Find IDREF widgets for FRM and WKR
        frm_widgets = [w for w, ref in widget.idref_widgets.items() if ref == 'FRM']
        wkr_widgets = [w for w, ref in widget.idref_widgets.items() if ref == 'WKR']

        # Check that FRM combobox has existing metadata items
        if frm_widgets:
            frm_cb = frm_widgets[0]
            frm_items = [frm_cb.itemText(i) for i in range(frm_cb.count())]
            # Should have at least one entry with " - " (from existing metadata)
            has_existing = any(' - ' in item for item in frm_items)
            assert has_existing, f"FRM combobox should have existing metadata items, got: {frm_items}"

        # Check that WKR combobox has existing metadata items
        if wkr_widgets:
            wkr_cb = wkr_widgets[0]
            wkr_items = [wkr_cb.itemText(i) for i in range(wkr_cb.count())]
            # Should have at least one entry with " - " (from existing metadata)
            has_existing = any(' - ' in item for item in wkr_items)
            assert has_existing, f"WKR combobox should have existing metadata items, got: {wkr_items}"


class TestGrdFieldSelectorPopulation:
    """Tests for GRD field selector combobox population from main tab fields."""

    def test_grd_field_selector_created_for_grd_element(self, monkeypatch):
        """Test that a field selector combobox is created for GRD elements."""
        ensure_qapp()
        recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_frm_wrk_grd.recipe')
        if not os.path.isfile(recipe_path):
            pytest.skip('test_frm_wrk_grd.recipe not available')

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()
        widget.load_recipe()

        # Search for field selector widgets in the layout
        def find_field_selectors(layout, depth=0):
            """Recursively find widgets with is_field_selector attribute."""
            selectors = []
            if depth > 10:  # Prevent infinite recursion
                return selectors
            for row in range(layout.rowCount()):
                for col in range(layout.columnCount()):
                    item = layout.itemAtPosition(row, col)
                    if item is None:
                        continue
                    # Check if it's a layout
                    sub_layout = None
                    try:
                        sub_layout = item.layout()
                    except Exception:
                        pass
                    if sub_layout is not None:
                        # Check widgets in sub-layout
                        for i in range(sub_layout.count()):
                            child = sub_layout.itemAt(i)
                            if child is None:
                                continue
                            w = child.widget()
                            if w is not None and hasattr(w, 'is_field_selector'):
                                selectors.append(w)
                    # Check if it's a widget with its own layout
                    try:
                        w = item.widget()
                        if w is not None:
                            child_layout = w.layout()
                            if child_layout is not None:
                                selectors.extend(find_field_selectors(child_layout, depth + 1))
                    except Exception:
                        pass
            return selectors

        field_selectors = find_field_selectors(widget.q_layout)
        assert len(field_selectors) > 0, "GRD element should create a field selector combobox"

    def test_grd_field_selector_populated_from_dock_widget(self, monkeypatch):
        """Test that GRD field selector is populated with fields from dock widget."""
        ensure_qapp()
        recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_frm_wrk_grd.recipe')
        if not os.path.isfile(recipe_path):
            pytest.skip('test_frm_wrk_grd.recipe not available')

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

        # Create a mock dock widget with LWFields
        mock_dock_widget = SimpleNamespace()
        mock_lw_fields = QListWidget()
        mock_lw_fields.addItem(QListWidgetItem('Field1'))
        mock_lw_fields.addItem(QListWidgetItem('Field2'))
        mock_lw_fields.addItem(QListWidgetItem('TestField'))
        mock_dock_widget.LWFields = mock_lw_fields

        # Create a mock parent_gdf with dock_widget
        mock_parent_gdf = SimpleNamespace()
        mock_parent_gdf.dock_widget = mock_dock_widget

        widget = GenerateTaskDataWidget(parent=None, parent_gdf=mock_parent_gdf)
        widget.load_schemas()
        widget.load_recipe()

        # Find field selector widgets
        def find_field_selectors(layout, depth=0):
            selectors = []
            if depth > 10:
                return selectors
            for row in range(layout.rowCount()):
                for col in range(layout.columnCount()):
                    item = layout.itemAtPosition(row, col)
                    if item is None:
                        continue
                    sub_layout = None
                    try:
                        sub_layout = item.layout()
                    except Exception:
                        pass
                    if sub_layout is not None:
                        for i in range(sub_layout.count()):
                            child = sub_layout.itemAt(i)
                            if child is None:
                                continue
                            w = child.widget()
                            if w is not None and hasattr(w, 'is_field_selector'):
                                selectors.append(w)
                    try:
                        w = item.widget()
                        if w is not None:
                            child_layout = w.layout()
                            if child_layout is not None:
                                selectors.extend(find_field_selectors(child_layout, depth + 1))
                    except Exception:
                        pass
            return selectors

        field_selectors = find_field_selectors(widget.q_layout)
        assert len(field_selectors) > 0, "Should have field selectors"

        # Check that at least one field selector has the mock fields
        found_fields = False
        for fs in field_selectors:
            items = [fs.itemText(i) for i in range(fs.count())]
            if 'Field1' in items and 'Field2' in items and 'TestField' in items:
                found_fields = True
                break

        assert found_fields, "Field selector should be populated with fields from dock widget"


class TestGetValueFromWidget:
    """Tests for get_value_from_widget method handling IDREF comboboxes."""

    def test_get_value_extracts_id_from_display_text(self, monkeypatch):
        """Test that get_value_from_widget extracts the ID from 'FRM1 - hörte' format."""
        ensure_qapp()
        recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_frm_wrk_grd.recipe')
        if not os.path.isfile(recipe_path):
            pytest.skip('test_frm_wrk_grd.recipe not available')

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()
        widget.load_recipe()

        # Find an IDREF widget
        if widget.idref_widgets:
            cb = list(widget.idref_widgets.keys())[0]
            # Set a value with display name
            cb.clear()
            cb.addItem('FRM1 - Test Farm')
            cb.setCurrentIndex(0)

            value = widget.get_value_from_widget(cb)
            assert value == 'FRM1', f"Should extract 'FRM1' from 'FRM1 - Test Farm', got: {value}"

    def test_get_value_handles_plain_id(self, monkeypatch):
        """Test that get_value_from_widget handles plain ID without display name."""
        ensure_qapp()
        recipe_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_frm_wrk_grd.recipe')
        if not os.path.isfile(recipe_path):
            pytest.skip('test_frm_wrk_grd.recipe not available')

        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (recipe_path, ''))

        widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
        widget.load_schemas()
        widget.load_recipe()

        # Find an IDREF widget
        if widget.idref_widgets:
            cb = list(widget.idref_widgets.keys())[0]
            # Set a value without display name
            cb.clear()
            cb.addItem('WKR2')
            cb.setCurrentIndex(0)

            value = widget.get_value_from_widget(cb)
            assert value == 'WKR2', f"Should return plain 'WKR2', got: {value}"
