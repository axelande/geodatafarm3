import os
from types import SimpleNamespace

import pytest
from qgis.PyQt.QtWidgets import (QApplication, QSpinBox, QDoubleSpinBox,
                                 QLineEdit, QComboBox, QPushButton)

from geodatafarm.support_scripts.pyagriculture.generate_taskdata_widgets import (
    distance,
    GenerateTaskDataWidget,
)


def ensure_qapp():
    app = QApplication.instance()
    if app is None:
        QApplication([])


def test_distance_returns_positive_float():
    p1 = SimpleNamespace(x=10.0, y=50.0)
    p2 = SimpleNamespace(x=10.1, y=50.1)
    d = distance(p1, p2)
    assert isinstance(d, float)
    assert d > 0.0


def test_get_value_from_widget_various_types():
    ensure_qapp()
    widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)

    # SpinBox
    sb = QSpinBox()
    sb.setValue(42)
    assert widget.get_value_from_widget(sb) == '42'

    # DoubleSpinBox
    db = QDoubleSpinBox()
    db.setDecimals(2)
    db.setValue(3.14)
    assert abs(float(widget.get_value_from_widget(db)) - 3.14) < 1e-6

    # LineEdit
    le = QLineEdit()
    le.setText('hello')
    assert widget.get_value_from_widget(le) == 'hello'

    # ComboBox (returns index)
    cb = QComboBox()
    cb.addItems(['a', 'b', 'c'])
    cb.setCurrentIndex(2)
    assert widget.get_value_from_widget(cb) == 2

    # QPushButton with custom `value` attribute
    btn = QPushButton()
    btn.value = 'file.bin'
    assert widget.get_value_from_widget(btn) == 'file.bin'


def test_load_schemas_with_repo_schemas():
    ensure_qapp()
    # Locate repository-level `schemas` directory relative to tests folder
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    # schemas live under support_scripts/schemas in this repo
    schemas_dir = os.path.join(repo_root, 'support_scripts', 'schemas')

    if not os.path.isdir(schemas_dir) or len(os.listdir(schemas_dir)) == 0:
        pytest.skip("No schemas directory available for tests")

    widget = GenerateTaskDataWidget(parent=None, parent_gdf=None)
    # start with empty and load from explicit dir
    widget.schemas = {}
    widget.load_schemas(schemas_dir=schemas_dir)

    # Expect at least one schema was loaded
    assert len(widget.schemas) >= 1
