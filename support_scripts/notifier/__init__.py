# -*- coding: utf-8 -*-
"""
***************************************************************************

 GeoDataFarm error-reporting subsystem

 This package gives GeoDataFarm a single, user friendly way to surface
 errors and warnings and to let users report them in one click.

 It is a port -- adapted to the GeoDataFarm code style -- of the
 ``let_us_know`` helper and ``MessageBarNotifier`` from NextGIS'
 qgis_devtools (https://github.com/nextgis/qgis_devtools), which is
 licensed under the GNU General Public License v2 or later. That license
 is compatible with GeoDataFarm's GNU Affero General Public License, under
 which this adaptation is distributed.

***************************************************************************
"""
from .exceptions import (
    GeoDataFarmError,
    GeoDataFarmWarning,
    UiLoadError,
)
from .notifier import (
    MessageBarNotifier,
    NotifierInterface,
    let_us_know,
    report_exception,
    report_message,
    report_info,
    report_success,
    report_warning,
    report_error,
    set_active_notifier,
    active_notifier,
    show_errors,
)

__all__ = [
    'GeoDataFarmError',
    'GeoDataFarmWarning',
    'UiLoadError',
    'MessageBarNotifier',
    'NotifierInterface',
    'let_us_know',
    'report_exception',
    'report_message',
    'report_info',
    'report_success',
    'report_warning',
    'report_error',
    'set_active_notifier',
    'active_notifier',
    'show_errors',
]
