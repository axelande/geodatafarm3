from qgis.PyQt.QtWidgets import QAbstractItemView, QFileDialog, QHeaderView, QMessageBox, QSizePolicy
from qgis.PyQt.QtGui import QFont, QKeySequence
from qgis.PyQt.QtCore import Qt, QEvent


def _size_policy(policy_name: str):
    """Return a QSizePolicy enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6 style
        return getattr(QSizePolicy.Policy, policy_name)
    except AttributeError:
        # PyQt5 style
        return getattr(QSizePolicy, policy_name)

def _font_weight_bold():
    """Return correct enum for Bold weight for PyQt5/PyQt6."""
    try:
        # PyQt6
        return QFont.Weight.Bold  
    except AttributeError:
        # PyQt5
        return QFont.Bold  


def _enum_select_rows():
    """Return the correct enum value for SelectRows for PyQt5/PyQt6."""
    try:
        # PyQt6
        return QAbstractItemView.SelectionBehavior.SelectRows
    except AttributeError:
        # PyQt5
        return QAbstractItemView.SelectRows

def _item_flag(name: str):
    """Return a Qt item flag compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: nested under Qt.ItemFlag
        return getattr(Qt.ItemFlag, name)
    except AttributeError:
        # PyQt5: direct attribute on Qt
        return getattr(Qt, name)
    

def _check_state(name: str):
    """Return a Qt CheckState enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6
        return getattr(Qt.CheckState, name)  
    except AttributeError:
        # PyQt5
        return getattr(Qt, name)
    


def _scroll_bar_policy(name: str):
    """Return a Qt ScrollBarPolicy enum compatible with PyQt5/PyQt6."""
    try:
        return getattr(Qt.ScrollBarPolicy, name)  # PyQt6
    except AttributeError:
        return getattr(Qt, name)  # PyQt5


def _alignment(name: str):
    """Return a Qt Alignment enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: AlignmentFlag namespace
        return getattr(Qt.AlignmentFlag, name)
    except AttributeError:
        # PyQt5: direct attribute on Qt
        return getattr(Qt, name)


def _widget_attribute(name: str):
    """Return a Qt WidgetAttribute enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: WidgetAttribute namespace
        return getattr(Qt.WidgetAttribute, name)
    except AttributeError:
        # PyQt5: direct attribute on Qt
        return getattr(Qt, name)


def _match_flag(name: str):
    """Return a Qt MatchFlag enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: MatchFlag namespace
        return getattr(Qt.MatchFlag, name)
    except AttributeError:
        # PyQt5: direct attribute on Qt
        return getattr(Qt, name)


def _file_dialog_option(name: str):
    """Return a QFileDialog option compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: Option namespace
        return getattr(QFileDialog.Option, name)
    except AttributeError:
        # PyQt5: direct attribute on QFileDialog
        return getattr(QFileDialog, name)


def _header_view_resize_mode(name: str):
    """Return a QHeaderView ResizeMode enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: ResizeMode namespace
        return getattr(QHeaderView.ResizeMode, name)
    except AttributeError:
        # PyQt5: direct attribute on QHeaderView
        return getattr(QHeaderView, name)


def _item_data_role(name: str):
    """Return a Qt ItemDataRole enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: ItemDataRole namespace
        return getattr(Qt.ItemDataRole, name)
    except AttributeError:
        # PyQt5: direct attribute on Qt
        return getattr(Qt, name)


def _message_box_button(name: str):
    """Return a QMessageBox standard button compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: StandardButton namespace
        return getattr(QMessageBox.StandardButton, name)
    except AttributeError:
        # PyQt5: direct attribute on QMessageBox
        return getattr(QMessageBox, name)


def _event_type(name: str):
    """Return a QEvent type enum compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: Type namespace
        return getattr(QEvent.Type, name)
    except AttributeError:
        # PyQt5: direct attribute on QEvent
        return getattr(QEvent, name)


def _key_sequence(name: str):
    """Return a QKeySequence standard key compatible with PyQt5/PyQt6."""
    try:
        # PyQt6: StandardKey namespace
        return getattr(QKeySequence.StandardKey, name)
    except AttributeError:
        # PyQt5: direct attribute on QKeySequence
        return getattr(QKeySequence, name)
