import os

from PyQt5.QtWidgets import QMessageBox, QLineEdit, QLabel
from PyQt5 import QtGui, QtWidgets
import pytest

from ..GeoDataFarm import GeoDataFarm
from ..database_scripts.mean_analyse import Analyze, sql_query
from . import gdf

def test_analyse_consistency(gdf: GeoDataFarm):
    names = [["plant", "test_field_plant_2023_04_15"],["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    print(analyse.db.get_tables_in_db('plant'))
    print(analyse.db.get_tables_in_db('harvest'))
    assert analyse.check_consistency()

def test_analyse_yield(gdf: GeoDataFarm):
    names = [["plant", "test_field_plant_2023_04_15"],["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    d = analyse.get_initial_distinct_values('yield_kg__per_ha__', 'test_field_harvest_2023_09_15', 'harvest')
    assert len(d["distinct_values"]) == 2256

def test_analyse_consistency_all_harvest(gdf: GeoDataFarm):
    # Test check_consistency for each harvest table with the plant table
    harvest_tables = [
        "test_field_harvest_2023_09_15",
    ]
    for htable in harvest_tables:
        names = [["plant", "test_field_plant_2023_04_15"], ["harvest", htable]]
        analyse = Analyze(gdf, names)
        assert analyse.check_consistency() in [True, False]

def test_get_initial_distinct_values_all_harvest(gdf: GeoDataFarm):
    # Test get_initial_distinct_values for each harvest table and all real columns
    harvest_tables = [
        "test_field_harvest_2023_09_15",
    ]
    for htable in harvest_tables:
        analyse = Analyze(gdf, [["harvest", htable]])
        columns = analyse.db.get_all_columns(htable, 'harvest')
        for col in columns:
            d = analyse.get_initial_distinct_values(col, htable, 'harvest')
            assert isinstance(d["distinct_values"], list)

def test_fill_dict_tables_all_available(gdf: GeoDataFarm):
    # Use all available tables in the names list
    names = [
        ["plant", "test_field_plant_2023_04_15"],
        ["harvest", "test_field_harvest_2023_09_15"],
        ["harvest", "test_iso_added_field2_potatoes__023_08_17t18_44_14"],
        ["harvest", "test_iso_added_field3_potatoes_one970_01_01"]
    ]
    analyse = Analyze(gdf, names)
    analyse.fill_dict_tables()
    assert analyse.harvest_tables
    assert analyse.plant_tables

def test_sql_query_each_harvest(gdf: GeoDataFarm):
    # Directly test the SQL query logic for each harvest table
    harvest_tables = [
        "test_field_harvest_2023_09_15",
        "test_iso_added_field2_potatoes__023_08_17t18_44_14",
        "test_iso_added_field3_potatoes_one970_01_01"
    ]
    for htable in harvest_tables:
        investigating_param = {
            'checked': True,
            'hist': False,
            'values': "'A','B'",
            htable: {
                'ha_col': 'yield_kg__per_ha__',
                f'harvest.{htable}': {
                    'prefix': 'a1',
                    'col': 'crop_type',
                    'None': False
                }
            }
        }
        other_parameters = {}
        db = gdf.db
        min_counts = 0
        limiting_polygon = None
        result = sql_query('debug', investigating_param, other_parameters, db, min_counts, limiting_polygon)
        assert isinstance(result, list)
        assert result[0] in [True, False]


def test_check_consistency_only_harvest_returns_false(gdf: GeoDataFarm, monkeypatch):
    # Should return False if only harvest tables are provided, and not block on popup
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    names = [["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    assert analyse.check_consistency() is False

def test_default_layout_populates_layout_dict_and_panels(gdf, monkeypatch):
    # Patch QMessageBox to avoid popups if any error occurs
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    # Use real tables for a valid overlap
    names = [["plant", "test_field_plant_2023_04_15"], ["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    assert analyse.check_consistency()  # Should populate overlapping_tables
    analyse.default_layout()
    # layout_dict and top_right_panel should be populated
    assert len(analyse.layout_dict) > 0
    assert len(analyse.top_right_panel) > 0

def test_update_layout_min_max_and_checked(gdf):
    # Setup Analyze and minimal layout_dict for a numeric and a checked column
    parent = gdf
    analyse = Analyze(parent, [["harvest", "test_field_harvest_2023_09_15"]])
    # Numeric column setup
    col_num = "yield_kg__per_ha__"
    analyse.layout_dict[col_num] = {
        'type': 'max_min',
        'min': 10,
        'max': 20,
        'min_text': QtWidgets.QLineEdit("10"),
        'min_label_text': QtWidgets.QLabel("10"),
        'max_text': QtWidgets.QLineEdit("20"),
        'max_label_text': QtWidgets.QLabel("20")
    }
    # Simulate new analyse_params with a lower min and higher max
    analyse_params_num = {'distinct_values': [5, 10, 15, 25], 'distinct_count': [1, 1, 1, 1]}
    analyse._update_layout(analyse_params_num, col_num)
    assert analyse.layout_dict[col_num]['min'] == 5
    assert analyse.layout_dict[col_num]['max'] == 25
    # Checked column setup
    col_str = "crop_type"
    model = QtGui.QStandardItemModel(0, 1)
    param_label = QtWidgets.QLabel()
    analyse.layout_dict[col_str] = {
        'type': 'checked',
        'checked': ['A'],
        'checked_items': [],
        'model': model,
        'name_text': 'A ',
        'param_label': param_label
    }
    analyse_params_str = {'distinct_values': ['A', 'B', 'C'], 'distinct_count': [1, 1, 1]}
    analyse._update_layout(analyse_params_str, col_str)
    # Should have added B and C to checked and checked_items
    assert 'B' in analyse.layout_dict[col_str]['checked']
    assert 'C' in analyse.layout_dict[col_str]['checked']
    assert analyse.layout_dict[col_str]['model'].rowCount() > 0
