# -*- coding: utf-8 -*-
"""
***************************************************************************

 GeoDataFarm message-bar notifier

 Adapted, in the GeoDataFarm code style, from the ``let_us_know`` helper and
 ``MessageBarNotifier`` of NextGIS' qgis_devtools (GNU GPL v2 or later).

 The notifier is the single entry point for telling the user that something
 happened. ``display_message`` shows neutral information; ``display_exception``
 turns any exception into a message bar entry and, for errors, adds buttons
 that let the user retry, open the details, open the QGIS log or report the
 problem straight to the issue tracker ('Let us know').

***************************************************************************
"""
from abc import ABCMeta, abstractmethod
import configparser
import functools
import os
import re
import uuid
from typing import Any, Callable, List, Optional, Self
from urllib.parse import quote

from qgis.core import Qgis
from qgis.PyQt.QtCore import QObject, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QMessageBox, QPushButton, QWidget

from .exceptions import GeoDataFarmError, GeoDataFarmWarning
from . import log as gdf_log
from ..__init__ import TR

PLUGIN_NAME = 'GeoDataFarm'
_tr = TR('GeoDataFarm').tr

# The currently installed notifier, so any module can report an exception
# without holding a reference to the plugin object (see report_exception).
_ACTIVE_NOTIFIER: Optional['NotifierInterface'] = None


def _plugin_metadata() -> configparser.SectionProxy:
    """Read and return the ``[general]`` section of the plugin metadata.txt."""
    plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # interpolation=None so a stray '%' in metadata.txt (e.g. changelog) never
    # raises when we just want to read the tracker URL.
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(os.path.join(plugin_root, 'metadata.txt'), encoding='utf-8')
    return parser['general']


def let_us_know() -> None:
    """Open the GeoDataFarm issue tracker so the user can report a problem.

    The tracker URL is taken from metadata.txt. A non GitHub tracker gets a
    set of UTM query tags appended so reports can be traced back to the
    plugin; the GitHub tracker is opened as is.
    """
    try:
        tracker_url = _plugin_metadata().get(
            'tracker', 'https://github.com/axelande/geodatafarm3/issues')
    except Exception:
        tracker_url = 'https://github.com/axelande/geodatafarm3/issues'

    if 'github' in tracker_url:
        QDesktopServices.openUrl(QUrl(tracker_url))
    else:
        QDesktopServices.openUrl(QUrl(f'{tracker_url}/?{_utm_tags("error")}'))


def _utm_tags(medium: str) -> str:
    """Build a UTM query string for non GitHub trackers."""
    try:
        version = _plugin_metadata().get('version', '')
    except Exception:
        version = ''
    return (f'utm_source=qgis_plugin&utm_medium={quote(medium)}'
            f'&utm_campaign=geodatafarm&utm_term={quote(version)}')


def active_notifier() -> Optional['NotifierInterface']:
    """Return the notifier currently installed for the plugin, if any."""
    return _ACTIVE_NOTIFIER


def set_active_notifier(notifier: Optional['NotifierInterface']) -> None:
    """Install ``notifier`` as the plugin wide notifier used by helpers."""
    global _ACTIVE_NOTIFIER
    _ACTIVE_NOTIFIER = notifier


def report_exception(error: BaseException) -> Optional[str]:
    """Show ``error`` through the active notifier, falling back to the log.

    This is the convenience entry point for code that does not hold a
    reference to the plugin: ``from ..support_scripts.notifier import
    report_exception``.

    Returns
    -------
    str or None
        The id of the shown message, or None when no notifier is installed.
    """
    notifier = active_notifier()
    if notifier is not None:
        return notifier.display_exception(error)
    gdf_log.exception('Unhandled exception (no notifier installed)', error)
    return None


def report_message(message: str, *,
                   level: 'Qgis.MessageLevel' = Qgis.Info,
                   widgets: Optional[List[QWidget]] = None) -> Optional[str]:
    """Show a neutral message through the active notifier (else log it).

    Module level entry point so widgets that do not hold the plugin object can
    notify the user with a single import.

    Parameters
    ----------
    message: str
    level: Qgis.MessageLevel
    widgets: list of QWidget, optional

    Returns
    -------
    str or None
        The id of the shown message, or None when no notifier is installed.
    """
    notifier = active_notifier()
    if notifier is not None:
        return notifier.display_message(message, level=level, widgets=widgets)
    gdf_log.log(message, level)
    return None


def report_info(message: str) -> Optional[str]:
    """Show a neutral, informational message."""
    return report_message(message, level=Qgis.Info)


def report_success(message: str) -> Optional[str]:
    """Show a success (green) message."""
    return report_message(message, level=Qgis.Success)


def report_warning(message: str) -> Optional[str]:
    """Show a warning (yellow) message, e.g. for input validation.

    Use this for "you forgot to fill in X" / "name already exists" cases: the
    user caused it and there is nothing to report, so no buttons are added.
    """
    return report_message(message, level=Qgis.Warning)


def report_error(message: str, *, detail: Optional[str] = None) -> Optional[str]:
    """Show an error (red) message with report buttons.

    Use this for genuine failures (a caught exception, an operation that did
    not work). The user gets 'Open logs' and 'Let us know' buttons.

    Parameters
    ----------
    message: str
        Plain language description shown to the user.
    detail: str, optional
        Extra technical text shown behind a 'Details' button.
    """
    return report_exception(
        GeoDataFarmError(user_message=message, detail=detail))


def show_errors(func: Callable) -> Callable:
    """Decorator that routes any exception raised by ``func`` to the notifier.

    Wrap a slot/callback with this to make sure a failure is reported to the
    user (with a 'Let us know' button) instead of vanishing into the QGIS
    Python console.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - reported to the user
            report_exception(error)
            return None
    return wrapper


class _QObjectABCMeta(ABCMeta, type(QObject)):
    """Metaclass mixing ``ABCMeta`` with QObject's metaclass.

    Needed so an abstract base can also be a QObject (the two metaclasses
    would otherwise clash).
    """


class NotifierInterface(QObject, metaclass=_QObjectABCMeta):
    """Interface for showing and dismissing messages to the user."""

    @abstractmethod
    def display_message(self: Self, message: str, *,
                        level: 'Qgis.MessageLevel' = Qgis.Info,
                        widgets: Optional[List[QWidget]] = None) -> str:
        """Show ``message`` and return an id identifying it."""
        ...

    @abstractmethod
    def display_exception(self: Self, error: BaseException) -> str:
        """Show ``error`` as a message and return an id identifying it."""
        ...

    @abstractmethod
    def dismiss_message(self: Self, message_id: str) -> None:
        """Remove the message with the given id."""
        ...

    @abstractmethod
    def dismiss_all(self: Self) -> None:
        """Remove every message shown by this notifier."""
        ...


class MessageBarNotifier(NotifierInterface):
    """Show GeoDataFarm messages and exceptions in the QGIS message bar.

    Parameters
    ----------
    iface: QgisInterface
        The QGIS interface, used to reach the message bar and the log.
    parent: QObject, optional
        Parent object for Qt ownership.
    """

    _ITEM_NAME = 'GeoDataFarmMessageBarItem'
    _ID_PROPERTY = 'GeoDataFarmMessageId'

    def __init__(self: Self, iface, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.iface = iface

    def __del__(self: Self) -> None:
        """Dismiss everything this notifier put on screen."""
        try:
            self.dismiss_all()
        except Exception:
            pass

    def _message_bar(self):
        """Return the QGIS message bar, or None when unavailable (tests)."""
        try:
            return self.iface.messageBar()
        except Exception:
            return None

    @staticmethod
    def _supports_widgets(bar) -> bool:
        """Whether ``bar`` exposes the rich widget API.

        The real QGIS ``QgsMessageBar`` supports ``createMessage``/
        ``pushWidget``; lightweight test doubles (e.g. pytest-qgis'
        ``MockMessageBar``) only offer ``pushMessage``. Fall back to the
        plain message API for those.
        """
        return hasattr(bar, 'createMessage') and hasattr(bar, 'pushWidget')

    def display_message(self: Self, message: str, *,
                        level: 'Qgis.MessageLevel' = Qgis.Info,
                        widgets: Optional[List[QWidget]] = None) -> str:
        """Show a neutral message in the message bar.

        Parameters
        ----------
        message: str
        level: Qgis.MessageLevel
        widgets: list of QWidget, optional
            Extra widgets (e.g. buttons) added next to the message.

        Returns
        -------
        str
            The id of the shown message.
        """
        message_id = str(uuid.uuid4())
        bar = self._message_bar()
        gdf_log.log(message, level)
        if bar is None:
            return message_id
        if not self._supports_widgets(bar):
            bar.pushMessage(PLUGIN_NAME, message, level, 0)
            return message_id
        widget = bar.createMessage(PLUGIN_NAME, message)
        for custom_widget in (widgets or []):
            custom_widget.setParent(widget)
            widget.layout().addWidget(custom_widget)
        item = bar.pushWidget(widget, level)
        item.setObjectName(self._ITEM_NAME)
        item.setProperty(self._ID_PROPERTY, message_id)
        return message_id

    def display_exception(self: Self, error: BaseException) -> str:
        """Show ``error`` in the message bar, wrapping plain exceptions.

        Anything that is not already a :class:`GeoDataFarmError` /
        :class:`GeoDataFarmWarning` is wrapped in one (keeping the original
        as ``__cause__``) so it gets a user message and report buttons.

        Returns
        -------
        str
            The ``error_id`` of the shown exception.
        """
        if not isinstance(error, (GeoDataFarmError, GeoDataFarmWarning)):
            original = error
            wrapped = (GeoDataFarmWarning() if isinstance(error, Warning)
                       else GeoDataFarmError())
            wrapped.__cause__ = original
            error = wrapped

        is_warning = isinstance(error, GeoDataFarmWarning)
        message = error.user_message.rstrip('.') + '.'
        level = Qgis.Warning if is_warning else Qgis.Critical

        if is_warning:
            gdf_log.warning(error.user_message)
        else:
            gdf_log.exception(error.log_message, error)

        bar = self._message_bar()
        if bar is None:
            return error.error_id
        if not self._supports_widgets(bar):
            bar.pushMessage(PLUGIN_NAME, message, level, 0)
            return error.error_id
        widget = bar.createMessage(PLUGIN_NAME, message)
        if not is_warning:
            self._add_error_buttons(error, widget)
        item = bar.pushWidget(widget, level)
        item.setObjectName(self._ITEM_NAME)
        item.setProperty(self._ID_PROPERTY, error.error_id)
        return error.error_id

    def dismiss_message(self: Self, message_id: str) -> None:
        """Remove a single message by its id."""
        bar = self._message_bar()
        if bar is None:
            return
        for item in bar.items():
            if (item.objectName() == self._ITEM_NAME
                    and item.property(self._ID_PROPERTY) == message_id):
                bar.popWidget(item)

    def dismiss_all(self: Self) -> None:
        """Remove every message this notifier has shown."""
        bar = self._message_bar()
        if bar is None:
            return
        for item in bar.items():
            if item.objectName() == self._ITEM_NAME:
                bar.popWidget(item)

    def _open_logs(self: Self) -> None:
        """Open the QGIS message log panel."""
        try:
            self.iface.openMessageLog()
        except Exception:
            pass

    def _add_error_buttons(self: Self, error: GeoDataFarmError,
                           widget: QWidget) -> None:
        """Attach the action buttons that belong to ``error`` to ``widget``."""
        def show_details() -> None:
            title = re.sub(r'</?(i|b)\b[^>]*?>', '',
                           error.user_message.rstrip('.'), flags=re.IGNORECASE)
            QMessageBox.information(
                self.iface.mainWindow(), title, error.detail or '')

        if error.try_again is not None:
            def try_again() -> None:
                error.try_again()
                bar = self._message_bar()
                if bar is not None:
                    bar.popWidget(widget)
            button = QPushButton(_tr('Try again'))
            button.pressed.connect(try_again)
            widget.layout().addWidget(button)

        for action_name, action_callback in error.actions:
            button = QPushButton(action_name)
            button.pressed.connect(action_callback)
            widget.layout().addWidget(button)

        if error.detail is not None:
            button = QPushButton(_tr('Details'))
            button.pressed.connect(show_details)
            widget.layout().addWidget(button)
        elif error.need_logs:
            button = QPushButton(_tr('Open logs'))
            button.pressed.connect(self._open_logs)
            widget.layout().addWidget(button)

        if type(error) is GeoDataFarmError:
            button = QPushButton(_tr('Let us know'))
            button.pressed.connect(let_us_know)
            widget.layout().addWidget(button)
