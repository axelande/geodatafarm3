# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CheckHarvestDependentDialog
                                 A QGIS plugin
 A simple program that calculate the impact on the harvest of different factors
                             -------------------
        begin                : 2016-03-04
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Axel Horteborn
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
from typing import Self

import os
import io
import csv
from qgis.PyQt import QtWidgets, uic, QtCore, QtGui

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'Run_analyse_base.ui'))


class RunAnalyseDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self: Self, parent: None=None) -> None:
        """Constructor."""
        super(RunAnalyseDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect

        self.setupUi(self)
        self.TVValues.installEventFilter(self)

    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.KeyPress and
            event.matches(QtGui.QKeySequence.Copy)):
            self.copySelection()
            return True
        return super(RunAnalyseDialog, self).eventFilter(source, event)

    def copySelection(self):
        selection = self.TVValues.selectedIndexes()
        if selection:
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[''] * colcount for _ in range(rowcount)]
            for index in selection:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream).writerows(table)
            QtWidgets.qApp.clipboard().setText(stream.getvalue())

