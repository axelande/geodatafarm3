import os

import pytest

from ..GeoDataFarm import GeoDataFarm
from ..database_scripts.mean_analyse import Analyze
from . import gdf

def test_analyse_consistency(gdf: GeoDataFarm):
    names = [["plant", "test_field_plant_2023_04_15"],["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    assert analyse.check_consistency()

def test_analyse_yield(gdf: GeoDataFarm):
    names = [["plant", "test_field_plant_2023_04_15"],["harvest", "test_field_harvest_2023_09_15"]]
    analyse = Analyze(gdf, names)
    d = analyse.get_initial_distinct_values('yield_kg__ha__', 'test_field_harvest_2023_09_15', 'harvest')
    assert len(d["distinct_values"]) == 2256
