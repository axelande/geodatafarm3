# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeoDataFarm
                                 A QGIS plugin
 This is a plugin that aims to determine the yield impact of different parameters
                             -------------------
        begin                : 2016-10-24
        copyright            : (C) 2016 by Axel Andersson
        email                : axel.n.c.andersson@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load GeoDataFarm class from file GeoDataFarm.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .GeoDataFarm import GeoDataFarm
    from . import resources
    from .GeoDataFarm_dockwidget import GeoDataFarmDockWidget
    return GeoDataFarm(iface)
