from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate
from ..support_scripts.__init__ import TR


class SavePlowing:
    def __init__(self, parent):
        """A class for storing plowing data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SavePlowing')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self):
        """A simple function that sets the buttons on the plowing tab"""
        self.parent.dock_widget.PBPloSaveManual.clicked.connect(self.save_manual_data)

    def save_manual_data(self):
        """Saves manual data."""
        if self.check_input():
            field = self.dw.CBPloField.currentText()
            date_ = self.dw.DEPlowing.selectedDate().toString("yyyy-MM-dd")
            depth = self.dw.LEPloDepth.text()
            other = self.dw.LEPloOther.toPlainText()
            if depth == '':
                depth = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into other.plowing_manual(field, date_, depth, other) 
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
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DEPlowing.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        return True
