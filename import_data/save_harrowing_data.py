from typing import Self
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate
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
            if depth == '':
                depth = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into other.harrowing_manual(field, date_, depth, other) 
            VALUES ('{field}', '{date_}','{depth}','{other}')""".format(field=field, date_=date_, depth=depth,
                                                                        other=other)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))
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
