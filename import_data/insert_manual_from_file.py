from PyQt5.QtWidgets import QLabel, QLineEdit, QComboBox, QCheckBox
from ..support_scripts import check_text
from ..support_scripts.__init__ import TR


class ManualFromFile:
    def __init__(self, db, widget, spec_columns):
        """Adds Manual data from file

        Parameters
        ----------
        db: database object
        tr: translation function
        widget: QtWidget, must contain following element: CBCrop, GLSpecific
        """
        self.db = db
        translate = TR('ManualFromFile')
        self.tr = translate.tr
        self.manual_values = {}
        self.spec_columns = spec_columns
        self.widget = widget
        self.add_specific_columns(widget, spec_columns)

    def prepare_data(self, columns_to_add):
        """Adds rows to the comboboxes

        Parameters
        ----------
        columns_to_add: list
        """
        for i, column in enumerate(self.spec_columns):
            self.manual_values[i]['Combo'].setEnabled(True)
            self.manual_values[i]['Combo'].addItems(columns_to_add)
            self.manual_values[i]['line_edit'].setEnabled(True)
            self.manual_values[i]['checkbox'].setEnabled(True)

    def add_specific_columns(self, widget, spec_columns):
        """Adds rows for the user to manual define which columns contains
        schema specific columns (or one single value / Not applicable)

        Parameters
        ----------
        widget: QtWidget
            A widget with a layout named "GLSpecific" where data type specific
            data is loaded
        spec_columns: list
            Each column gets three choices, one of the rows, spec value or NA
        """
        self.manual_values = {}
        for i, column in enumerate(spec_columns):
            self.manual_values[i] = {}
            label = QLabel(column)
            widget.GLSpecific.addWidget(label, i, 0)
            combo = QComboBox()
            combo.setEnabled(False)
            combo.setFixedWidth(220)
            self.manual_values[i]['Combo'] = combo
            widget.GLSpecific.addWidget(combo, i, 1)
            line = QLineEdit()
            line.setEnabled(False)
            line.setFixedWidth(110)
            self.manual_values[i]['line_edit'] = line
            widget.GLSpecific.addWidget(line, i, 2)
            check = QCheckBox(text=self.tr('Not Applicable'))
            check.setEnabled(False)
            check.setFixedWidth(110)
            self.manual_values[i]['checkbox'] = check
            widget.GLSpecific.addWidget(check, i, 3)

    def insert_manual_data(self, date_, field, table, data_type):
        """Inserts the manual data that is used to generate reports, rather long
        function since all schemas have separate attributes.

        Parameters
        ----------
        date_: str
            The column where the dates is listed or one date that is the same
            for all rows (than it starts with c\_)

        Returns
        -------
        bool
            If success or not
        """
        date_ = "'{d}'".format(d=date_)
        if data_type == 'soil':
            if self.manual_values[0]['checkbox'].isChecked():
                clay = 'None'
            elif self.manual_values[0]['Combo'].currentText() != '':
                clay = '{t}'.format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                clay = 'c_{t}'.format(t=self.manual_values[0]['line_edit'].text())
            if self.manual_values[1]['checkbox'].isChecked():
                humus = 'None'
            elif self.manual_values[1]['Combo'].currentText() != '':
                humus = '{t}'.format(t=check_text(self.manual_values[1]['Combo'].currentText()))
            else:
                humus = 'c_{t}'.format(t=self.manual_values[1]['line_edit'].text())
            if self.manual_values[2]['checkbox'].isChecked():
                ph = 'None'
            elif self.manual_values[2]['Combo'].currentText() != '':
                ph = '{t}'.format(t=check_text(self.manual_values[2]['Combo'].currentText()))
            else:
                ph = 'c_{t}'.format(t=self.manual_values[2]['line_edit'].text())
            if self.manual_values[3]['checkbox'].isChecked():
                rx = 'None'
            elif self.manual_values[3]['Combo'].currentText() != '':
                rx = '{t}'.format(t=check_text(self.manual_values[3]['Combo'].currentText()))
            else:
                rx = 'c_{t}'.format(t=self.manual_values[3]['line_edit'].text())
            sql = """insert into soil.manual(date_text, field, clay, humus, ph, rx, table_) 
                VALUES ({d}, '{f}', '{clay}', '{humus}', '{ph}', '{rx}', '{tbl}')""".format(f=field, d=date_,
                                                                                               clay=clay, humus=humus,
                                                                                               ph=ph, rx=rx, tbl=table)
            self.db.execute_sql(sql)
            return True
        crop = self.widget.CBCrop.currentText()
        if data_type == 'plant':
            sql = """insert into plant.manual(field, crop, date_text, table_, variety) VALUES ('{f}', '{c}', {d}, '{t}', 
                """.format(f=field, c=crop, d=date_, t=table)
            if self.manual_values[0]['checkbox'].isChecked():
                sql += "'None')"
            elif self.manual_values[0]['Combo'].currentText() != '':
                sql += "'{t}')".format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                sql += "'c_{t}')".format(t=self.manual_values[0]['line_edit'].text())
        elif data_type == 'ferti':
            if self.manual_values[0]['checkbox'].isChecked():
                variety = 'None'
            elif self.manual_values[0]['Combo'].currentText() != '':
                variety = '{t}'.format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                variety = 'c_{t}'.format(t=self.manual_values[0]['line_edit'].text())
            if self.manual_values[1]['checkbox'].isChecked():
                rate = 'None'
            elif self.manual_values[1]['Combo'].currentText() != '':
                rate = '{t}'.format(t=check_text(self.manual_values[1]['Combo'].currentText()))
            else:
                rate = 'c_{t}'.format(t=self.manual_values[1]['line_edit'].text())
            sql = """insert into ferti.manual(field, crop, table_, date_text,variety, rate) 
            VALUES ('{f}', '{c}', '{t}', {d}, '{v}', '{r}')""".format(f=field, c=crop, t=table,
                                                                      v=variety, r=rate, d=date_)
        elif data_type == 'spray':
            if self.manual_values[0]['checkbox'].isChecked():
                variety = 'None'
            elif self.manual_values[0]['Combo'].currentText() != '':
                variety = '{t}'.format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                variety = 'c_{t}'.format(t=self.manual_values[0]['line_edit'].text())
            if self.manual_values[1]['checkbox'].isChecked():
                rate = 'None'
            elif self.manual_values[1]['Combo'].currentText() != '':
                rate = '{t}'.format(t=check_text(self.manual_values[1]['Combo'].currentText()))
            else:
                rate = 'c_{t}'.format(t=self.manual_values[1]['line_edit'].text())
            sql = """insert into spray.manual(field, crop, table_, date_text, variety, rate) 
            VALUES ('{f}', '{c}', '{t}', {d}, '{v}', '{r}')""".format(f=field, c=crop, t=table,
                                                                      v=variety, r=rate, d=date_)
        elif data_type == 'harvest':
            if self.manual_values[0]['checkbox'].isChecked():
                yield_ = 'None'
            elif self.manual_values[0]['Combo'].currentText() != '':
                yield_ = '{t}'.format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                yield_ = 'c_{t}'.format(t=self.manual_values[0]['line_edit'].text())
            if self.manual_values[1]['checkbox'].isChecked():
                total_yield = 'None'
            elif self.manual_values[1]['Combo'].currentText() != '':
                total_yield = '{t}'.format(t=check_text(self.manual_values[1]['Combo'].currentText()))
            else:
                total_yield = 'c_{t}'.format(t=self.manual_values[1]['line_edit'].text())
            sql = """insert into harvest.manual(field, crop, table_, date_text, yield, total_yield) 
            VALUES ('{f}', '{c}', '{t}', {d}, '{y}', '{t_y}')""".format(f=field, c=crop, t=table, d=date_,
                                                                        y=yield_, t_y=total_yield)
        else:
            ## Should never happen!
            print('Unkown data source...')
            return False
        self.db.execute_sql(sql)
        return True