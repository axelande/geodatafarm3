from typing import Self
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate
from ..support_scripts.__init__ import TR


class SaveHarrowing:
    def __init__(self: Self, parent) -> None:
        """
        A class for storing harrowing data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SaveHarrowing')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the harrowing tab"""
        self.parent.dock_widget.PBHwSaveManual.clicked.connect(self.save_manual_data)

    def save_manual_data(self):
        """Saves the manual data."""
        if self.check_input():
            field = self.dw.CBHwField.currentText()
            date_ = self.dw.DEHarrowing.selectedDate().toString("yyyy-MM-dd")
            depth = self.dw.LEHwDepth.text()
            other = self.dw.LEHwOther.toPlainText()
            depth = depth or None
            other = other or None
            sql = ("INSERT INTO other.harrowing_manual (field, date_, depth, other)"
                   " VALUES (%s, %s, %s, %s)")
            try:
                self.parent.db.execute_sql(sql, params=(field, date_, depth, other))
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr(f'Following error occurred: {e}'))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBHwField.setCurrentIndex(0)
        self.dw.LEHwDepth.setText('')
        self.dw.LEHwOther.setPlainText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBHwField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DEHarrowing.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        return True
