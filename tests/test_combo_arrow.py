"""Tests for support_scripts.combo_arrow.

The bug these guard against is invisible to an ordinary widget test: the
combo box is constructed correctly, holds the right items and reports the
right size - it just paints no arrow, because the plugin's stylesheet
styles ``::drop-down`` without supplying an image (see the module
docstring). So the check has to be on pixels, not on the widget's state.

Needs no database, unlike the rest of the journal-field tests.
"""
import os

from qgis.PyQt.QtCore import QDir
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QComboBox

from ..support_scripts import combo_arrow

# The stylesheet every .ui file in the plugin carries, reduced to the part
# that matters here. Kept as a literal rather than parsed out of a .ui so
# that a test failure points at the rule itself.
_DROP_DOWN = """QComboBox {
  border: 1px solid palette(mid);
  border-radius: 3px;
  padding: 2px 4px;
  background: palette(base);
}
QComboBox::drop-down {
  border: none;
  width: 20px;
}
"""
_ARROW = """QComboBox::down-arrow {
  image: url(%s:%s);
  width: 14px;
  height: 14px;
}
""" % (combo_arrow.SEARCH_PREFIX, combo_arrow.FILE_NAME)


def _combo(qtbot, stylesheet):
    combo = QComboBox()
    combo.addItems(['--- Select field ---', 'Home field'])
    combo.setFixedSize(220, 30)
    combo.setStyleSheet(stylesheet)
    if hasattr(qtbot, 'addWidget'):
        qtbot.addWidget(combo)
    return combo


def _arrow_area_ink(combo):
    """How many pixels in the drop-down area differ from the field's own
    background - i.e. whether anything at all was drawn there."""
    image = combo.grab().toImage()
    width, height = image.width(), image.height()
    # The stylesheet reserves 20px on the right for the drop-down. Sample
    # inside it, clear of the rounded border on either side.
    background = QColor(image.pixel(width // 2, height // 2)).rgb()
    ink = 0
    for x in range(width - 18, width - 3):
        for y in range(4, height - 4):
            if QColor(image.pixel(x, y)).rgb() != background:
                ink += 1
    return ink


def test_install_writes_the_arrow_and_registers_the_search_path(tmp_path):
    path = combo_arrow.install(str(tmp_path))

    assert path is not None
    assert os.path.exists(path)
    # The .ui stylesheets name the file through this prefix, so the search
    # path is as much a part of the contract as the image is.
    assert str(tmp_path) in QDir.searchPaths(combo_arrow.SEARCH_PREFIX)[0]


def test_install_survives_a_directory_it_cannot_create(tmp_path):
    """A missing arrow must cost the user nothing more than the arrow - the
    plugin still has to load, so install() reports failure rather than
    raising."""
    blocker = tmp_path / 'not_a_directory'
    blocker.write_text('')

    assert combo_arrow.install(str(blocker / 'inside')) is None


def test_the_styled_combo_paints_nothing_without_the_arrow_rule(qtbot, tmp_path):
    """Characterises the bug: this is what every combo box in the plugin
    looked like."""
    combo_arrow.install(str(tmp_path))

    combo = _combo(qtbot, _DROP_DOWN)

    assert _arrow_area_ink(combo) == 0


def test_the_arrow_rule_makes_the_drop_down_visible(qtbot, tmp_path):
    combo_arrow.install(str(tmp_path))

    combo = _combo(qtbot, _DROP_DOWN + _ARROW)

    # A chevron is three strokes in a 14px box; anything above a handful of
    # pixels means it actually rendered rather than the url quietly failing.
    assert _arrow_area_ink(combo) > 20


def test_an_editable_combo_gets_the_arrow_too(qtbot, tmp_path):
    """The journal history fields are editable combos - they are the ones
    most easily mistaken for a text box, so they matter most here."""
    combo_arrow.install(str(tmp_path))
    combo = _combo(qtbot, _DROP_DOWN + _ARROW)
    combo.setEditable(True)

    assert _arrow_area_ink(combo) > 20


def test_the_arrow_is_drawn_in_the_palette_colour(tmp_path):
    """A fixed dark arrow would vanish against a dark QGIS theme."""
    from qgis.PyQt.QtGui import QGuiApplication, QImage, QPalette

    expected = QGuiApplication.instance().palette().color(
        QPalette.ColorRole.WindowText)
    color = combo_arrow._arrow_color()

    assert (color.red(), color.green(), color.blue()) == (
        expected.red(), expected.green(), expected.blue())

    drawn = QImage(combo_arrow.install(str(tmp_path)))
    painted = [drawn.pixelColor(x, y)
               for x in range(drawn.width()) for y in range(drawn.height())
               if drawn.pixelColor(x, y).alpha() > 0]
    assert painted, 'the arrow image is entirely transparent'


def test_every_ui_file_that_styles_the_drop_down_also_styles_the_arrow():
    """The rule has to be in all of them or the fix is partial - and a new
    .ui copied from an old one is exactly how that would regress."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    missing = []
    for folder, _, names in os.walk(root):
        parts = os.path.relpath(folder, root).split(os.sep)
        if parts and parts[0] in ('old', 'build', 'zip_build', '.git'):
            continue
        for name in names:
            if not name.endswith('.ui'):
                continue
            path = os.path.join(folder, name)
            text = open(path, encoding='utf-8').read()
            if 'QComboBox::drop-down' in text and 'QComboBox::down-arrow' not in text:
                missing.append(os.path.relpath(path, root))
    assert missing == []
