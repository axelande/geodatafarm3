from typing import Self
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate
from ..support_scripts.__init__ import TR
from ..support_scripts.notifier import report_success, report_warning, report_error


class SavePlowing:
    def __init__(self: Self, parent) -> None:
        """A class for storing plowing data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SavePlowing')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the plowing tab"""
        self.parent.dock_widget.PBPloSaveManual.clicked.connect(self.save_manual_data)

    def save_manual_data(self):
        """Saves manual data."""
        if self.check_input():
            field = self.dw.CBPloField.currentText()
            date_ = self.dw.DEPlowing.selectedDate().toString("yyyy-MM-dd")
            depth = self.dw.LEPloDepth.text()
            other = self.dw.LEPloOther.toPlainText()
            depth = depth or None
            other = other or None
            sql = ("INSERT INTO other.plowing_manual (field, date_, depth, other)"
                   " VALUES (%s, %s, %s, %s)")
            try:
                self.parent.db.execute_sql(sql, params=(field, date_, depth, other))
                report_success(self.tr('The data was stored correctly'))
            except Exception as e:
                report_error(self.tr(f'Following error occurred: {e}'), detail=str(e))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBPloField.setCurrentIndex(0)
        self.dw.LEPloDepth.setText('')
        self.dw.LEPloOther.setPlainText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBPloField.currentText() == self.tr('--- Select field ---'):
            report_warning(self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DEPlowing.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            report_warning(self.tr('In order to save the data you must select a date'))
            return False
        return True
