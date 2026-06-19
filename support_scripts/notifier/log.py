# -*- coding: utf-8 -*-
"""
***************************************************************************

 Thin logging helpers writing to the QGIS message log under the
 'GeoDataFarm' tag. Kept separate so the notifier and the rest of the
 plugin share one place that decides how things are logged.

***************************************************************************
"""
import traceback

from qgis.core import QgsMessageLog, Qgis

LOG_TAG = 'GeoDataFarm'


def log(message: str, level: 'Qgis.MessageLevel' = Qgis.Info) -> None:
    """Write a single message to the QGIS log.

    Parameters
    ----------
    message: str
    level: Qgis.MessageLevel
    """
    QgsMessageLog.logMessage(message, LOG_TAG, level)


def warning(message: str) -> None:
    """Write a warning to the QGIS log."""
    QgsMessageLog.logMessage(message, LOG_TAG, Qgis.Warning)


def exception(message: str, exc: BaseException = None) -> None:
    """Write an error and, when available, its traceback to the QGIS log.

    Parameters
    ----------
    message: str
        The message to log.
    exc: BaseException, optional
        The exception whose traceback should be included.
    """
    if exc is not None:
        tb = ''.join(
            traceback.format_exception(type(exc), exc, exc.__traceback__))
        message = f'{message}\n{tb}'
    QgsMessageLog.logMessage(message, LOG_TAG, Qgis.Critical)
