import sys
import types

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
