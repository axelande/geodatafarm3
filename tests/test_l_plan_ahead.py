import pytest
from ..database_scripts.plan_ahead import PlanAhead
from . import gdf

# test_plan_ahead.py


def test_update_fields(gdf):
    pa = PlanAhead(gdf)
    pa.update_fields()
    # Check that the table was updated
    assert gdf.dock_widget.TWPlan.rowCount() > 0
    assert gdf.dock_widget.TWPlan.columnCount() == 7

def test_update_sum(gdf):
    pa = PlanAhead(gdf)
    pa.update_sum()
    # Check that the summary list widget was updated
    assert gdf.dock_widget.LWPlanSummary.count() > 0
    assert 'Plan summary' in gdf.dock_widget.LPlanSummaryLabel.text()

def test_save_data(gdf):
    pa = PlanAhead(gdf)
    pa.update_fields()
    pa.save_data()
    # Check that the database was updated (requires known test data)
    # Example: assert gdf.db.execute_and_return("select ...") == expected

def test_view_year(gdf):
    pa = PlanAhead(gdf)
    pa.view_year()
    # Check that the layer was added (requires known test data)
    # Example: assert gdf.db.layer_exists('fields', extra_name=str(gdf.dock_widget.DEPlanYear.text()))