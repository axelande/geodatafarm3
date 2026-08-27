"""Tests for the dock's left sidebar navigation (see
GeoDataFarm_dockwidget._setup_sidebar_nav).

The sidebar items live in GeoDataFarm_dockwidget_base.ui while the pages they
open live in ``_nav``, and the row number is the only thing tying the two
together. Anything that adds a page to one list without the other silently
shifts every row below it, so each row opens its neighbour's page - which is
what these tests guard against.

Uses the shared ``gdf`` fixture (already run() by the time any test sees it -
see tests/__init__.py) and only reads/selects sidebar rows, so it adds no
ordering dependency on the other test modules.
"""
import pytest

from ..GeoDataFarm import GeoDataFarm
from . import gdf

# (label keyword, top page attribute, inner tab widget attribute, inner index)
EXPECTED = [
    ('Farm', 'tab_4', None, None),
    ('Crop simulation', 'tabCropSimulation', None, None),
    ('Fertility index', 'fertility_index_page', None, None),
    ('Add data', 'tabAddData', None, None),
    ('Data sets', 'tabYourData', 'tabWidgetYourData', 0),
    ('Visualization', 'tabYourData', 'tabWidgetYourData', 1),
    ('Data tools', 'tabYourData', 'tabWidgetYourData', 2),
    ('Guide file', 'tabGuideFile', None, None),
    ('Satellite', 'tab_16', None, None),
    ('Reports', 'tabReportsPlanning', 'tabWidgetReportsPlanning', 0),
    ('Plan ahead', 'tabReportsPlanning', 'tabWidgetReportsPlanning', 1),
    ('ISO-XML', 'tab_generate_isoxml', None, None),
]


def _labels(dw):
    return [dw.navSidebar.item(row).text() for row in range(dw.navSidebar.count())]


def _row_of(dw, keyword):
    for row, text in enumerate(_labels(dw)):
        if keyword in text:
            return row
    raise AssertionError(f'no sidebar row labelled {keyword!r} in {_labels(dw)}')


def test_every_sidebar_item_has_a_page(gdf: GeoDataFarm):
    """The count invariant: one _nav entry per navSidebar item."""
    dw = gdf.dock_widget
    assert dw.navSidebar.count() == len(dw._nav), (
        f'{dw.navSidebar.count()} sidebar items vs {len(dw._nav)} _nav entries '
        f'- rows below the mismatch open the wrong page')
    assert all(page is not None for page, _inner, _idx in dw._nav)


def test_sidebar_labels_are_the_expected_pages(gdf: GeoDataFarm):
    """Each labelled row opens the page that label promises.

    The sidebar is untranslated in the test locale; if that ever changes the
    keyword lookup below is what will fail first.
    """
    dw = gdf.dock_widget
    assert len(_labels(dw)) == len(EXPECTED)
    for row, (keyword, page_attr, inner_attr, inner_idx) in enumerate(EXPECTED):
        assert keyword in _labels(dw)[row], (
            f'row {row} is {_labels(dw)[row]!r}, expected {keyword!r}')
        page, inner, idx = dw._nav[row]
        assert page is getattr(dw, page_attr), f'{keyword}: wrong page'
        assert inner is (None if inner_attr is None else getattr(dw, inner_attr))
        assert idx == inner_idx


def test_selecting_a_row_shows_its_page(gdf: GeoDataFarm):
    dw = gdf.dock_widget
    for row, (keyword, page_attr, inner_attr, inner_idx) in enumerate(EXPECTED):
        dw.navSidebar.setCurrentRow(row)
        assert dw.tabWidget.currentWidget() is getattr(dw, page_attr), (
            f'{keyword} row shows '
            f'{dw.tabWidget.tabText(dw.tabWidget.currentIndex())!r}')
        if inner_attr is not None:
            assert getattr(dw, inner_attr).currentIndex() == inner_idx


@pytest.mark.parametrize('keyword, page_attr', [
    ('Add data', 'tabAddData'),
    ('Guide file', 'tabGuideFile'),
])
def test_showing_a_page_from_elsewhere_moves_the_highlight(
        gdf: GeoDataFarm, keyword, page_attr):
    """Other code jumps straight to a page (e.g. crop_simulation's 'add the
    missing data' link -> tabAddData); the sidebar has to follow."""
    dw = gdf.dock_widget
    dw.navSidebar.setCurrentRow(0)
    dw.tabWidget.setCurrentWidget(getattr(dw, page_attr))
    assert dw.navSidebar.currentRow() == _row_of(dw, keyword)


def test_sub_tab_rows_of_a_shared_page_are_told_apart(gdf: GeoDataFarm):
    """Data sets, Visualization and Data tools share tabYourData, so the
    highlight has to follow the inner tab, not just the top page."""
    dw = gdf.dock_widget
    dw.navSidebar.setCurrentRow(_row_of(dw, 'Data sets'))
    for keyword, inner_idx in (('Visualization', 1), ('Data tools', 2),
                               ('Data sets', 0)):
        dw.tabWidgetYourData.setCurrentIndex(inner_idx)
        assert dw.navSidebar.currentRow() == _row_of(dw, keyword)


def test_add_data_row_returns_to_the_operation_picker(gdf: GeoDataFarm):
    """'Add data' is two steps deep - operation picker, then that operation's
    form (widgets/add_data_form.py) - so its sidebar row has to land on the
    picker whichever form was last left open. Without it, 'Add data' reopened
    on e.g. Harvest and there was no obvious way back out to add anything else.
    """
    dw = gdf.dock_widget
    row = _row_of(dw, 'Add data')
    form = gdf.add_data_form
    dw.navSidebar.setCurrentRow(row)

    # Clicking the row you are already on: currentRowChanged never fires, so
    # this is the itemClicked path in _setup_sidebar_nav.
    form.addStack.setCurrentIndex(1)
    dw.navSidebar.itemClicked.emit(dw.navSidebar.item(row))
    assert form.addStack.currentIndex() == 0

    # And coming back to the page from another row.
    form.addStack.setCurrentIndex(1)
    dw.navSidebar.setCurrentRow(0)
    dw.navSidebar.setCurrentRow(row)
    assert form.addStack.currentIndex() == 0


def test_jumping_straight_to_an_operation_form_is_not_reset(gdf: GeoDataFarm):
    """The crop-simulation gap links switch to Add data *in order to* open one
    operation's form (CropSimulation._open_add_data_for_gap), so the reset
    above must hang off the sidebar and not off tabWidget.currentChanged."""
    dw = gdf.dock_widget
    form = gdf.add_data_form
    dw.navSidebar.setCurrentRow(0)
    form.addStack.setCurrentIndex(1)
    dw.tabWidget.setCurrentWidget(dw.tabAddData)
    assert form.addStack.currentIndex() == 1
