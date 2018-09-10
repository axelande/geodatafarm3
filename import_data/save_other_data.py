from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate
from ..support_scripts.__init__ import check_text


class SaveOther:
    def __init__(self, parent):
        """
        A class for storing other data
        :param parent: GeoDataFarm "self"
        """
        self.dw = parent.dock_widget
        self.tr = parent.tr
        self.parent = parent

    def set_widget_connections(self):
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBSaveOther.clicked.connect(self.save_manual_data)

    def save_manual_data(self):
        if self.check_input():
            field = self.dw.CBOField.currentText()
            sql = "Select '{f}' as field, ".format(f=field)
            crop = self.dw.CBOCrop.currentText()
            if crop == self.tr('--- Select crop ---'):
                crop = 'Null'
            sql += "'{c}' as crop, ".format(c=crop)
            date_ = self.dw.DEOther.text()
            sql += "'{d}' as date_, ".format(d=date_)
            option1 = check_text(self.dw.LEOOption_1.text())
            if option1 != '':
                unit1 = check_text(self.dw.LEOUnit_1.text())
                if unit1 == '':
                    unit1 = 'Null'
                value1 = check_text(self.dw.LEOValue_1.text())
                if value1 != '':
                    # If the value is not set it is not worth saving the value.
                    sql += "'{v}' as {o}_{u}, ".format(v=value1, o=option1, u=unit1)
            option2 = check_text(self.dw.LEOOption_2.text())
            if option2 != '':
                unit2 = check_text(self.dw.LEOUnit_2.text())
                if unit2 == '':
                    unit2 = 'Null'
                value2 = check_text(self.dw.LEOValue_2.text())
                if value2 != '':
                    # If the value is not set it is not worth saving the value.
                    sql += "'{v}' as {o}_{u}, ".format(v=value2, o=option2, u=unit2)
            option3 = check_text(self.dw.LEOOption_3.text())
            if option3 != '':
                unit3 = check_text(self.dw.LEOUnit_3.text())
                if unit3 == '':
                    unit3 = 'Null'
                value3 = check_text(self.dw.LEOValue_3.text())
                if value3 != '':
                    # If the value is not set it is not worth saving the value.
                    sql += "'{v}' as {o}_{u}, ".format(v=value3, o=option3, u=unit3)
            option4 = check_text(self.dw.LEOOption_4.text())
            if option4 != '':
                unit4 = check_text(self.dw.LEOUnit_4.text())
                if unit4 == '':
                    unit4 = 'Null'
                value4 = check_text(self.dw.LEOValue_4.text())
                if value4 != '':
                    # If the value is not set it is not worth saving the value.
                    sql += "'{v}' as {o}_{u}, ".format(v=value4, o=option4, u=unit4)
            other = self.dw.LEOOther.toPlainText()
            if other == '':
                other = 'Null'
            sql += "'{o}' as other ".format(o=other)
            name = self.dw.LEOtherName.text()
            tbl = "{n}_{f}_{d}".format(n=check_text(name), d=check_text(date_), f=field)
            sql_t = """SELECT EXISTS (
               SELECT 1
               FROM   information_schema.tables 
               WHERE  table_schema = 'other'
               AND    table_name = '{tbl}'
               );""".format(tbl=tbl)
            if self.parent.db.execute_and_return(sql_t)[0][0]:
                QMessageBox.information(None, self.tr('Success'),
                                        self.tr('That operation, at that field on that day is already stored'))
                return
            sql += "into other.{tbl}".format(tbl=tbl)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBOField.setCurrentIndex(0)
        self.dw.CBOCrop.setCurrentIndex(0)
        self.dw.DEOther.setDate(QDate.fromString('2000-01-01', 'yyyy-MM-dd'))
        self.dw.LEOOption_1.setText('')
        self.dw.LEOValue_1.setText('')
        self.dw.LEOUnit_1.setText('')
        self.dw.LEOOption_2.setText('')
        self.dw.LEOValue_2.setText('')
        self.dw.LEOUnit_2.setText('')
        self.dw.LEOOption_3.setText('')
        self.dw.LEOValue_3.setText('')
        self.dw.LEOUnit_3.setText('')
        self.dw.LEOOption_4.setText('')
        self.dw.LEOValue_4.setText('')
        self.dw.LEOUnit_4.setText('')
        self.dw.LEOOther.setPlainText('')
        self.dw.LEOtherName.setText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.
        :return bool"""
        if self.dw.CBOField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DEOther.text() == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        return True
