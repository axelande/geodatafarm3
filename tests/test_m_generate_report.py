from datetime import datetime
import pytest
from . import gdf

@pytest.fixture
def dummy_data(gdf):
    # Use the GeoDataFarm instance and its report_generator
    return {
        "db": gdf.db,
        "tr": gdf.tr,
        "year": 2023
    }

def test_collect_data_basic(dummy_data, gdf):
    result = gdf.report_generator.collect_data('debug', dummy_data)
    assert result[0] is True
    data_dict = result[1]
    # For each operation, check that the structure is present and at least one of simple/advanced is True if data exists
    for op in ["planting", "fertilizing", "spraying", "harvesting", "plowing", "harrowing", "soil"]:
        assert op in data_dict
        # Accept either simple or advanced as True, and check data presence accordingly
        if data_dict[op]["simple"]:
            assert "simple_data" in data_dict[op]
            assert isinstance(data_dict[op]["simple_data"], list)
        if data_dict[op]["advanced"]:
            assert "advance_dat" in data_dict[op]
            assert isinstance(data_dict[op]["advance_dat"], list)
    # Additionally, check that at least one operation has data
    assert any(data_dict[op]["simple"] or data_dict[op]["advanced"] for op in data_dict)

def test_collect_data_no_data(gdf):
    class EmptyDB:
        def execute_and_return(self, sql, return_failure=False):
            return []
    dummy_data = {
        "db": EmptyDB(),
        "tr": gdf.tr,
        "year": 2023
    }
    result = gdf.report_generator.collect_data('debug', dummy_data)
    assert result[0] is True
    data_dict = result[1]
    for op in data_dict:
        if op == "year":
            continue  # The Year is an integer, skip it
        assert data_dict[op]["simple"] is False
        assert data_dict[op]["advanced"] is False