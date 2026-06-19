# -*- coding: utf-8 -*-
"""
***************************************************************************

 GeoDataFarm exception types

 Adapted, in the GeoDataFarm code style, from the exception framework of
 NextGIS' qgis_devtools (GNU GPL v2 or later). The classes here carry both
 a developer facing ``log_message`` and a user facing ``user_message`` so a
 single exception can be logged in full detail and, at the same time, shown
 to the user in plain language by the notifier.

***************************************************************************
"""
from typing import Any, Callable, List, Optional, Self, Tuple
import uuid

from qgis.core import QgsApplication


def _default_message() -> str:
    """The generic message used when no specific text is supplied."""
    return QgsApplication.translate(
        'GeoDataFarm', 'An error occurred while running GeoDataFarm')


class ExceptionInfoMixin:
    """Common fields and behaviour shared by GeoDataFarm errors and warnings.

    Every instance gets a unique ``error_id`` (handy for matching a message
    bar entry with its log line and for users to quote when reporting), a
    ``log_message`` for the QGIS log and a ``user_message`` for the message
    bar. Optionally an exception may also carry a ``detail`` text, a
    ``try_again`` callable and a list of extra ``actions`` (name, callback)
    that the notifier renders as buttons.
    """

    _error_id: str
    _log_message: str
    _user_message: str
    _detail: Optional[str]
    _try_again: Optional[Callable[[], Any]]
    _actions: List[Tuple[str, Callable[[], Any]]]
    _need_logs: bool

    def __init__(self: Self, log_message: Optional[str] = None, *,
                 user_message: Optional[str] = None,
                 detail: Optional[str] = None) -> None:
        """Constructor.

        Parameters
        ----------
        log_message: str, optional
            Technical message written to the QGIS log.
        user_message: str, optional
            Plain language message shown to the user. Falls back to the
            generic message when omitted.
        detail: str, optional
            Extra information shown behind a 'Details' button.
        """
        self._error_id = str(uuid.uuid4())
        default = _default_message()
        self._log_message = (log_message if log_message else default).strip()
        self._user_message = (user_message if user_message else default).strip()

        Exception.__init__(self, self._log_message)
        self.add_note('Message: ' + self._user_message)

        self._detail = detail.strip() if detail is not None else None
        if self._detail is not None:
            self.add_note('Details: ' + self._detail)

        self._try_again = None
        self._actions = []
        self._need_logs = True

    @property
    def error_id(self: Self) -> str:
        """The unique identifier of this exception."""
        return self._error_id

    @property
    def log_message(self: Self) -> str:
        """The technical message for the QGIS log."""
        return self._log_message

    @property
    def user_message(self: Self) -> str:
        """The plain language message for the user."""
        return self._user_message

    @property
    def detail(self: Self) -> Optional[str]:
        """Extra detail text, or None."""
        return self._detail

    @property
    def try_again(self: Self) -> Optional[Callable[[], Any]]:
        """A callable that retries the failed operation, or None."""
        return self._try_again

    @try_again.setter
    def try_again(self: Self, try_again: Optional[Callable[[], Any]]) -> None:
        self._try_again = try_again

    @property
    def actions(self: Self) -> List[Tuple[str, Callable[[], Any]]]:
        """Extra (name, callback) actions shown as buttons."""
        return self._actions

    def add_action(self: Self, name: str, callback: Callable[[], Any]) -> None:
        """Add an extra action button to this exception.

        Parameters
        ----------
        name: str
            Button label.
        callback: callable
            Function called when the button is pressed.
        """
        self._actions.append((name, callback))

    @property
    def need_logs(self: Self) -> bool:
        """Whether an 'Open logs' button is useful for this exception."""
        return self._need_logs


class GeoDataFarmError(ExceptionInfoMixin, Exception):
    """Base class for recoverable errors raised by GeoDataFarm.

    Raise this (or a subclass) instead of a bare ``Exception`` whenever the
    user should be told about a problem. The notifier turns it into a red
    message bar entry with 'Details'/'Open logs' and a 'Let us know' button.
    """

    def __init__(self: Self, log_message: Optional[str] = None, *,
                 user_message: Optional[str] = None,
                 detail: Optional[str] = None) -> None:
        ExceptionInfoMixin.__init__(
            self, log_message, user_message=user_message, detail=detail)
        Exception.__init__(self, self._log_message)


class GeoDataFarmWarning(ExceptionInfoMixin, UserWarning):
    """Base class for non critical issues raised by GeoDataFarm.

    Shown as a yellow (warning) message bar entry, without the report
    buttons that errors get.
    """

    def __init__(self: Self, log_message: Optional[str] = None, *,
                 user_message: Optional[str] = None,
                 detail: Optional[str] = None) -> None:
        ExceptionInfoMixin.__init__(
            self, log_message, user_message=user_message, detail=detail)
        Exception.__init__(self, self._log_message)


class UiLoadError(GeoDataFarmError):
    """Raised when a ``.ui`` file or widget fails to load."""

    def __init__(self: Self, log_message: Optional[str] = None, *,
                 user_message: Optional[str] = None,
                 detail: Optional[str] = None) -> None:
        default = QgsApplication.translate(
            'GeoDataFarm', 'Failed to load the user interface.')
        super().__init__(
            log_message=log_message if log_message else default,
            user_message=user_message if user_message else default,
            detail=detail)
