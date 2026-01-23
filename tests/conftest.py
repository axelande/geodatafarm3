import sys
import types
import os

# Add project root to sys.path and create 'geodatafarm' package alias
# This allows tests to use 'from geodatafarm.xxx import yyy' without installing the package
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Create a 'geodatafarm' module that points to the project root
# This enables imports like 'from geodatafarm.support_scripts.xxx import yyy'
if 'geodatafarm' not in sys.modules:
    import importlib.util
    _init_path = os.path.join(_project_root, '__init__.py')
    # Create __init__.py if it doesn't exist (for package discovery)
    if not os.path.exists(_init_path):
        # Use a spec with submodule_search_locations to make it a package
        _spec = importlib.util.spec_from_file_location(
            'geodatafarm',
            None,
            submodule_search_locations=[_project_root]
        )
        _geodatafarm = importlib.util.module_from_spec(_spec)
        _geodatafarm.__path__ = [_project_root]
        sys.modules['geodatafarm'] = _geodatafarm
    else:
        _spec = importlib.util.spec_from_file_location('geodatafarm', _init_path)
        _geodatafarm = importlib.util.module_from_spec(_spec)
        _geodatafarm.__path__ = [_project_root]
        sys.modules['geodatafarm'] = _geodatafarm

# Provide a minimal `qgis` package for tests by mapping `qgis.PyQt` to available PySide6/PyQt5
# This avoids import errors when the real QGIS Python API isn't present.
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except Exception:
    # pytest-qt / CI should install PySide6; if not available tests will fail explicitly
    QtWidgets = None
    QtCore = None
    QtGui = None

if 'qgis' not in sys.modules:
    qgis = types.ModuleType('qgis')
    pyqt_namespace = types.SimpleNamespace()
    if QtWidgets is not None:
        pyqt_namespace.QtWidgets = QtWidgets
        pyqt_namespace.QtCore = QtCore
        pyqt_namespace.QtGui = QtGui
    qgis.PyQt = pyqt_namespace
    sys.modules['qgis'] = qgis
    # Also expose qgis.PyQt.QtWidgets at the top-level import path
    sys.modules['qgis.PyQt'] = pyqt_namespace

# Silence QMessageBox exec during tests unless explicitly handling GUI tests
from qgis.PyQt.QtWidgets import QMessageBox
_orig_exec = QMessageBox.exec

def _dummy_exec(self=None):
    # Return immediately for headless tests
    return 0

# Patch only when running non-qt tests; qt tests can restore if needed
QMSGBOX_PATCHED = False
try:
    QMessageBox.exec = _dummy_exec
    QMSGBOX_PATCHED = True
except Exception:
    pass


# Ensure there is a running QApplication for widget tests
try:
    from qgis.PyQt.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])
except Exception:
    pass

# Ensure a default locale is present for tests (some tests set this in tests/__init__.py,
# but ensure it's present early in headless runs or when import order differs).
try:
    from qgis.PyQt.QtCore import QSettings
    if QSettings().value('locale/userLocale') is None:
        QSettings().setValue('locale/userLocale', 'se')
except Exception:
    # If QSettings isn't available, skip setting locale (tests will handle missing value)
    pass


import pytest


@pytest.fixture
def qtbot(request):
    """Provide a qtbot-compatible fixture. In pytest-qt environments the real
    `qtbot` will already exist; if not, try to fall back to pytest-qgis's
    `qgis_bot` fixture (which exists when pytest-qgis is installed). If neither
    is present, return a minimal dummy that supports `addWidget`.
    """
    try:
        return request.getfixturevalue('qgis_bot')
    except Exception:
        # if pytest-qt is present, the real `qtbot` would be registered already;
        # otherwise, provide a minimal dummy
        class _DummyQtBot:
            def addWidget(self, widget):
                return None

        return _DummyQtBot()
