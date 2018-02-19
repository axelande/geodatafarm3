# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CheckHarvestDependentDialog
                                 A QGIS plugin
 A simple program that calculate the impact on the harvest of different factors
                             -------------------
        begin                : 2016-03-04
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Axel Andersson
        email                : axel.n.c.andersson@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os

from PyQt5 import QtWidgets, uic

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'create_farm_popup_base.ui'))


class CreateFarmPopup(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(CreateFarmPopup, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
