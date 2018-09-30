from qgis.core import QgsProject, QgsVectorLayer, QgsTask
import traceback
from PyQt5 import QtCore
from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog, QAbstractItemView, \
    QMessageBox, QLabel, QLineEdit, QComboBox, QCheckBox
from osgeo import osr
import os
import re
import math
import time

from operator import xor, itemgetter
from datetime import datetime
from dateutil.parser import parse
# Import the code for the dialog
from ..widgets.import_text_dialog import ImportTextDialog
from ..support_scripts.radio_box import RadioComboBox
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts.__init__ import check_text, isfloat, isint, check_date_format
__author__ = 'Axel Andersson'


class InputTextHandler(object):
    def __init__(self, parent_widget, data_type, columns=None):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        # initialize plugin directory
        self.data_type = data_type

        self.col_types = None
        self.file_name_with_path = None
        self.file_name = None
        self.input_file_path = None
        self.add_to_param_row_count = 0
        self.add_to_db_row_count = 0
        # Create the dialog (after translation) and keep reference
        self.ITD = ImportTextDialog()
        self.dock_widget = parent_widget.dock_widget
        self.tr = parent_widget.tr
        self.plugin_dir = parent_widget.plugin_dir
        self.iface = parent_widget.iface
        self.populate = parent_widget.populate
        self.db = parent_widget.db
        self.parent_widget = parent_widget
        self.tsk_mngr = parent_widget.tsk_mngr
        self.type_specific_cols = columns
        self.manual_values = {}
        self.rb_pressed = False
        self.fields_to_db = False
        self.combo = None
        self.sep = None
        self.encoding = 'utf-8'
        self.longitude_col = None
        self.latitude_col = None
        self.heading_row = None
        self.sample_data = None

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.ITD.show()
        self.ITD.PBAddInputFile.clicked.connect(self.open_input_file)
        self.ITD.PBAddParam.clicked.connect(self.add_to_param_list)
        self.ITD.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.ITD.PBInsertDataIntoDB.clicked.connect(self.trigger_insection)
        self.ITD.PBContinue.clicked.connect(self.prepare_last_choices)
        self.ITD.PBAbbreviations.clicked.connect(self.show_abbreviations)
        self.ITD.RBComma.clicked.connect(self.get_sep)
        self.ITD.RBSemi.clicked.connect(self.get_sep)
        self.ITD.RBTab.clicked.connect(self.get_sep)
        self.ITD.RBOwnSep.clicked.connect(self.get_sep)
        self.populate.reload_fields(self.ITD.CBField)
        self.populate.reload_crops(self.ITD.CBCrop)
        if self.data_type == 'harvest':
            self.ITD.LParams.setText('Harvest Column')
            self.ITD.LMaxYield.setEnabled(True)
            self.ITD.LMinYield.setEnabled(True)
            self.ITD.LEMaximumYield.setEnabled(True)
            self.ITD.LEMinimumYield.setEnabled(True)
        self.add_specific_columns()
        self.ITD.exec_()

    def show_abbreviations(self):
        QMessageBox.information(None, self.tr('Information'),
                                self.tr('%Y = Year (2010)\n'
                                        '%y = Year (98)\n'
                                        '%m = Month\n'
                                        '%d = Day\n'
                                        '%H = Hour (24h)\n'
                                        '%M = Minute\n'
                                        '%S = Second\n'
                                        'If you are missing any formats please contact geodatafarm@gmail.com'
                                        ))

    def add_to_param_list(self):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""
        row_count = self.add_to_param_row_count
        self.ITD.TWtoParam.setColumnCount(1)
        items_to_add = []
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append(self.ITD.TWtoParam.item(i, 0).text())
        for i, item in enumerate(self.ITD.TWColumnNames.selectedItems()):
            if self.data_type == self.tr('harvest') and len(existing_values) > 0:
                QMessageBox.information(None, self.tr("Error:"),
                                        self.tr('You can only select one yield column!'))
                return
            if item.column() == 0 and item.text() not in existing_values:
                items_to_add.append(item.text())
        for i, item in enumerate(items_to_add, self.add_to_param_row_count):
            row_count += 1
            self.ITD.TWtoParam.setRowCount(row_count)
            item1 = QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.ITD.TWtoParam.setItem(i, 0, item1)
        self.add_to_param_row_count = row_count
        self.ITD.PBContinue.setEnabled(True)

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        row_count = self.add_to_param_row_count
        if self.ITD.TWtoParam.selectedItems() is None:
            QMessageBox.information(None, self.tr("Error:"), self.tr('No row selected!'))
            return
        for item in self.ITD.TWtoParam.selectedItems():
            self.ITD.TWtoParam.removeRow(item.row())
            row_count -= 1
        self.add_to_param_row_count = row_count

    def get_separator(self):
        with open(self.file_name_with_path, 'rb') as f:
            # Join binary lines for specified number of lines
            try:
                dat = f.read()
                read_all = dat.decode('utf-8')
                self.encoding = 'utf-8'
            except:
                dat = f.read()
                read_all = dat.decode('ansi')
                self.encoding = 'ansi'
        with open(self.file_name_with_path, encoding=self.encoding) as f:
            read_all = f.readlines()
            c = read_all[0].count(",")
            c_s = read_all[0].count(", ")
            sc = read_all[0].count(";")
            sc_s = read_all[0].count("; ")
            tab = read_all[0].strip().count('\t')
            sep_list = [c, c_s, sc, sc_s, tab]
            max_index, max_val = max(enumerate(sep_list), key=itemgetter(1))
            if max_index == 0 or max_index == 1:
                self.sep = ","
            elif max_index == 2 or max_index == 3:
                self.sep = ";"
            else:
                self.sep = '\t'

    def get_columns_names(self):
        """A function that retrieves the name of the columns from the .csv file
        and returns a list with name"""
        self.ITD.TWColumnNames.clear()
        with open(self.file_name_with_path, encoding=self.encoding) as f:
            read_all = f.readlines()
            first_row = True
            for row in read_all:
                row = re.split((self.sep + ' |' + self.sep), row)
                if first_row:
                    heading_row = row
                    first_row = False
                else:
                    second_row = row
                    break
        self.col_types = self.determine_column_type()
        combo_box_options = ["Integer", "Decimal value", "Character"]
        self.combo = []
        self.ITD.TWColumnNames.setRowCount(len(heading_row))
        self.ITD.TWColumnNames.setColumnCount(3)
        self.ITD.TWColumnNames.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, row in enumerate(heading_row):
            item1 = QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            item2 = QTableWidgetItem(second_row[i])
            item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
            self.combo.append(RadioComboBox())
            for nr, t in enumerate(combo_box_options):
                self.combo[i].addItem(t)
                item = self.combo[i].model().item(nr, 0)
                if self.col_types[i] == nr:
                    item.setCheckState(QtCore.Qt.Checked)
                    self.combo[i].setCurrentIndex(nr)
                else:
                    item.setCheckState(QtCore.Qt.Unchecked)
            self.combo[i].currentTextChanged.connect(self.change_col_type)
            self.ITD.TWColumnNames.setItem(i, 0, item1)
            self.ITD.TWColumnNames.setItem(i, 1, item2)
            self.ITD.TWColumnNames.setCellWidget(i, 2, self.combo[i])
        self.add_to_db_row_count = i

    def add_specific_columns(self):
        self.manual_values = {}
        for i, column in enumerate(self.type_specific_cols):
            self.manual_values[i] = {}
            label = QLabel(column)
            self.ITD.GLSpecific.addWidget(label, i, 0)
            combo = QComboBox()
            combo.setEnabled(False)
            combo.setFixedWidth(220)
            self.manual_values[i]['Combo'] = combo
            self.ITD.GLSpecific.addWidget(combo, i, 1)
            line = QLineEdit()
            line.setEnabled(False)
            line.setFixedWidth(110)
            self.manual_values[i]['line_edit'] = line
            self.ITD.GLSpecific.addWidget(line, i, 2)
            check = QCheckBox(text=self.tr('Not Applicable'))
            check.setEnabled(False)
            check.setFixedWidth(110)
            self.manual_values[i]['checkbox'] = check
            self.ITD.GLSpecific.addWidget(check, i, 3)

    def set_radio_but(self):
        if self.sep == ',':
            self.ITD.RBComma.setChecked(True)
        if self.sep == ';':
            self.ITD.RBSemi.setChecked(True)
        if self.sep == '\t':
            self.ITD.RBTab.setChecked(True)

    def get_sep(self):
        if self.ITD.RBComma.isChecked():
            self.sep = ','
        if self.ITD.RBSemi.isChecked():
            self.sep = ';'
        if self.ITD.RBTab.isChecked():
            self.sep = '\t'
        if self.ITD.RBOwnSep.isChecked():
            self.sep = self.ITD.LEOwnSep.text().encode('utf-8')
        self.get_columns_names()

    def change_col_type(self):
        """Updates the values (in self.col_types) of the data types for each 
        column in the data set
        :return:
        """
        self.col_types = []
        for c_box in self.combo:
            if c_box.currentText() == "Integer":
                self.col_types.append(0)
            if c_box.currentText() == "Decimal value":
                self.col_types.append(1)
            if c_box.currentText() == "Character":
                self.col_types.append(2)

    def open_input_file(self):
        """
        Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function get_columns_names
        are being called.
        :return:
        """
        filters = "Text files (*.txt *.csv)"
        self.file_name_with_path = QFileDialog.getOpenFileName(None, " File dialog ", '',
                                                      filters)[0]
        if self.file_name_with_path == '':
            return
        temp_var = self.file_name_with_path.split("/")
        self.file_name = temp_var[len(temp_var)-1][0:-4]
        self.input_file_path = self.file_name_with_path[0:self.file_name_with_path.index(self.file_name)]
        self.get_separator()
        self.set_radio_but()
        self.get_columns_names()

    def prepare_last_choices(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the shapefile, determining date and time columns """
        columns_to_add = []
        for i in range(self.add_to_db_row_count + 1):
            columns_to_add.append(self.ITD.TWColumnNames.item(i, 0).text())
        self.ITD.ComBNorth.clear()
        self.ITD.ComBEast.clear()
        self.ITD.ComBNorth.addItems(columns_to_add)
        self.ITD.ComBEast.addItems(columns_to_add)
        lat_check, lon_check = False, False
        for word in columns_to_add:
            for part in word.split(' '):
                if part.lower() in "latitude lat y":
                    lat_check = True
                    only_char = check_text(word)
                    self.latitude_col = only_char
                    index = self.ITD.ComBNorth.findText(word)
                    self.ITD.ComBNorth.setCurrentIndex(index)
                if part.lower() in "longitude lat x":
                    lon_check = True
                    only_char = check_text(word)
                    self.longitude_col = only_char
                    index = self.ITD.ComBEast.findText(word)
                    self.ITD.ComBEast.setCurrentIndex(index)
        if self.ITD.LEEPSG.text() == '4326' and not lat_check:
            QMessageBox.information(None, self.tr("Error:"), self.tr('There needs to be a column called latitude (wgs84) or you need to change the EPSG system'))
            return
        if self.ITD.LEEPSG.text() == '4326' and not lon_check:
            QMessageBox.information(None, self.tr("Error:"), self.tr('There needs to be a column called longitude (wgs84) or you need to change the EPSG system'))
            return
        self.ITD.ComBNorth.setEnabled(True)
        self.ITD.ComBEast.setEnabled(True)
        self.ITD.ComBDate.setEnabled(True)
        self.ITD.ComBDate.addItems(columns_to_add)
        self.ITD.PBInsertDataIntoDB.setEnabled(True)

        for i, column in enumerate(self.type_specific_cols):
            self.manual_values[i]['Combo'].setEnabled(True)
            self.manual_values[i]['Combo'].addItems(columns_to_add)
            self.manual_values[i]['line_edit'].setEnabled(True)
            self.manual_values[i]['checkbox'].setEnabled(True)

    def determine_column_type(self):
        """
        A function that retrieves the types of the columns from the .csv file
        :return: a list with with 0=int, 1=float, 2=char
        """
        row_types = []
        self.sample_data = []
        with open(self.file_name_with_path, encoding=self.encoding) as f:
            read_all = f.readlines()
            first_row = True
            max_rows = len(read_all)
            if max_rows > 1000:
                max_rows = 1000
            for row in read_all[:max_rows]:
                row = re.split((self.sep + ' |' + self.sep), row)
                if first_row:
                    self.heading_row = row
                    first_row = False
                    h_row = []
                    for col in self.heading_row:
                        h_row.append(check_text(col))
                        row_types.append(0)
                    self.sample_data.append(h_row)
                    continue
                else:
                    self.sample_data.append(row)
                    for j, col in enumerate(row):
                        if isint(col):
                            row_types[j] += 0
                            continue
                        if isfloat(col):
                            row_types[j] += 1
                            continue
                        else:
                            row_types[j] += 2
        row_type_return = []
        for i, col_value in enumerate(row_types):
            row_type_return.append(int(col_value/(max_rows*0.7)))
        return row_type_return

    def insert_manual_data(self, date_):
        field = self.ITD.CBField.currentText()
        table = self.file_name
        date_ = "'{d}'".format(d=date_)
        if self.data_type == 'soil':
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
        crop = self.ITD.CBCrop.currentText()
        if self.data_type == 'plant':
            sql = """insert into plant.manual(field, crop, date_text, table_, variety) VALUES ('{f}', '{c}', {d}, '{t}', 
                """.format(f=field, c=crop, d=date_, t=table)
            if self.manual_values[0]['checkbox'].isChecked():
                sql += "'None')"
            elif self.manual_values[0]['Combo'].currentText() != '':
                sql += "'{t}')".format(t=check_text(self.manual_values[0]['Combo'].currentText()))
            else:
                sql += "'c_{t}')".format(t=self.manual_values[0]['line_edit'].text())
        elif self.data_type == 'ferti':
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
        elif self.data_type == 'spray':
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
        elif self.data_type == 'harvest':
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

    def trigger_insection(self):
        """
        Preparing the data, by setting the correct type (including the date and
        time format), creating a shp file and finally ensure that the
        coordinates is in EPSG:4326
        :return:
        """
        params = {}
        params['schema'] = self.data_type
        params['tbl_name'] = self.file_name
        params['column_types'] = self.col_types
        params['heading_row'] = []
        for col in self.heading_row:
            params['heading_row'].append(check_text(col))
        params['encoding'] = self.encoding
        params['file_name_with_path'] = self.file_name_with_path
        params['field'] = self.ITD.CBField.currentText()
        params['longitude_col'] = self.longitude_col
        params['latitude_col'] = self.latitude_col
        params['focus_col'] = []
        if self.db.check_table_exists(self.file_name, self.data_type):
            qm = QMessageBox()
            res = qm.question(None, self.tr('Message'),
                              self.tr(
                                  "The name of the data set already exist in your database, would you like to replace it? (If not please rename the file)"),
                              qm.Yes, qm.No)
            if res == qm.No:
                return
            else:
                self.db.execute_sql("""DROP TABLE {schema}.{tbl};
                                            DELETE FROM {schema}.manual
        	                                WHERE table_ = '{tbl}';""".format(schema=self.data_type, tbl=self.file_name))
        for i in range(self.add_to_param_row_count):
            params['focus_col'].append(check_text(self.ITD.TWtoParam.item(i, 0).text()))
        self.focus_cols = params['focus_col']
        if params['schema'] == 'harvest':
            params['yield_row'] = params['focus_col'][0]
            params['max_yield'] = float(self.ITD.LEMaximumYield.text())
            params['min_yield'] = float(self.ITD.LEMinimumYield.text())
        if self.ITD.RBDateOnly.isChecked():
            if not check_date_format(self.sample_data, check_text(self.ITD.ComBDate.currentText()), self.ITD.ComBDate_2.currentText()):
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr("The date format didn't match the selected format, please change"))
                return
            params['date_row'] = check_text(self.ITD.ComBDate.currentText())
            params['date_format'] = self.ITD.ComBDate_2.currentText()
            params['all_same_date'] = ''
            self.insert_manual_data('date_')
        else:
            params['all_same_date'] = self.ITD.DE.text()
            self.insert_manual_data('c_' + self.ITD.DE.text())
            params['date_row'] = ''
        params['sep'] = self.sep
        params['tr'] = self.tr
        params['epsg'] = self.ITD.LEEPSG.text()
        #a = insert_data_to_database('debug', self.db, params)
        #print(a)
        task = QgsTask.fromFunction('Run import text data', insert_data_to_database, self.db, params,
                                    on_finished=self.finish)
        self.tsk_mngr.addTask(task)

    def finish(self, result, values):
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        if not values[1]:
            QMessageBox.information(None, self.tr("Information:"),
                                    str(values[2]) + self.tr(' rows were skipped '
                                                             'since the row'
                                                             ' did not match '
                                                             'the heading.'))

        schema = self.data_type
        tbl = check_text(self.file_name)
        if isint(tbl[0]):
            tbl = '_' + tbl
        length = self.db.execute_and_return("select field_row_id from {s}.{t} limit 2".format(s=schema, t=tbl))
        if len(length) == 0:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('No data were found in the field, '
                                            'are you sure that the data is in the correct field?'))
            return
        create_layer = CreateLayer(self.db)
        for param_layer in self.focus_cols:
            param_layer = check_text(param_layer)
            target_field = param_layer
            if self.data_type == 'harvest':
                layer = self.db.addPostGISLayer(tbl, 'pos', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))
            else:
                layer = self.db.addPostGISLayer(tbl, 'polygon', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))

            create_layer.create_layer_style(layer, check_text(target_field), tbl, schema)

        self.ITD.PBAddInputFile.clicked.disconnect()
        self.ITD.PBAddParam.clicked.disconnect()
        self.ITD.PBRemParam.clicked.disconnect()
        self.ITD.PBInsertDataIntoDB.clicked.disconnect()
        self.ITD.PBContinue.clicked.disconnect()
        self.ITD.done(0)


def insert_data_to_database(task, db, params):
    try:
        schema = params['schema']
        tbl_name = params['tbl_name']
        column_types = params['column_types']
        heading_row = params['heading_row']
        encoding = params['encoding']
        file_name_with_path = params['file_name_with_path']
        field = params['field']
        longitude_col = params['longitude_col']
        latitude_col = params['latitude_col']
        if schema == 'harvest':
            yield_row = params['yield_row']
            max_yield = params['max_yield']
            min_yield = params['min_yield']
        date_row = params['date_row']
        if date_row != '':
            date_format = params['date_format']
        all_same_date = params['all_same_date']
        sep = params['sep']
        tr = params['tr']
        epsg = params['epsg']
        focus_col = params['focus_col']
        if isint(tbl_name[0]):
            tbl_name = '_' + tbl_name
        inserting_text = 'INSERT INTO {schema}.temp_table ('.format(schema=schema)
        sql = "CREATE TABLE {schema}.temp_table (field_row_id serial PRIMARY KEY, ".format(schema=schema)
        lat_lon_inserted = False
        date_inserted = False
        for i, col_name in enumerate(heading_row):
            if not lat_lon_inserted and (
                    col_name == longitude_col or col_name == latitude_col):
                sql += "pos geometry(POINT, 4326),"
                if schema != 'harvest':
                    sql += " polygon geometry(MULTIPOLYGON, 4326), "
                inserting_text += 'pos, '
                lat_lon_inserted = True
            if lat_lon_inserted and (
                    col_name == longitude_col or col_name == latitude_col):
                continue
            if col_name == date_row:
                sql += "Date_ TIMESTAMP, "
                inserting_text += 'Date_, '
                continue
            elif all_same_date and not date_inserted:
                sql += "Date_ TIMESTAMP, "
                inserting_text += 'Date_, '
                date_inserted = True
            if column_types[i] == 0:
                sql += str(col_name) + " INT, "
            elif column_types[i] == 1:
                sql += str(col_name) + " REAL, "
            elif column_types[i] == 2:
                sql += str(col_name) + " CHARACTER VARYING(20), "
            inserting_text += str(col_name) + ', '
        sql = sql[:-2]
        sql += ")"
        inserting_text = inserting_text[:-2] + ') VALUES '
        insert_org_sql = inserting_text
        db.create_table(sql, '{schema}.temp_table'.format(schema=schema))
        if task != 'debug':
            task.setProgress(5)
        count_db_insert = 0
        with open(file_name_with_path, encoding=encoding) as f:
            read_all = f.readlines()
            first_row = True
            some_wrong_len = 0
            for row_count, row in enumerate(read_all):
                row_value = '('
                row = re.split((sep + ' |' + sep), row)
                lat_lon_inserted = False
                if first_row:
                    heading_row = []
                    for col in row:
                        only_char = check_text(col)
                        heading_row.append(only_char)
                    first_row = False
                    continue
                elif len(row) != len(heading_row) and len(row) < 3:
                    some_wrong_len += 1
                    continue
                if float(row[heading_row.index(latitude_col)]) < 0.1 or float(
                        row[heading_row.index(longitude_col)]) < 0.1:
                    continue
                if schema == 'harvest':
                    if float(row[heading_row.index(yield_row)]) > max_yield:
                        continue
                    elif float(row[heading_row.index(yield_row)]) < min_yield:
                        continue
                if task != 'debug':
                    task.setProgress(2 + row_count / len(read_all) * 45)
                date_inserted = False
                for key in heading_row:
                    col_data = row[heading_row.index(key)]
                    if len(str(col_data)) == 0:
                        row_value += 'Null, '
                        continue
                    if not lat_lon_inserted and (
                            key == longitude_col or key == latitude_col):
                        row_value += "ST_Transform(ST_PointFromText('POINT({p1} {p2})',{epsg}), 4326), ".format(
                            p1=row[heading_row.index(longitude_col)],
                            p2=row[heading_row.index(latitude_col)],
                            epsg=epsg)
                        lat_lon_inserted = True
                    if lat_lon_inserted and (
                            key == longitude_col or key == latitude_col):
                        continue
                    if all_same_date and not date_inserted:
                        row_value += "'{s}', ".format(s=all_same_date)
                        date_inserted = True
                    if key == date_row:
                        in_date = datetime.strptime(row[heading_row.index(date_row)], date_format)
                        out_date = datetime.strftime(in_date, '%Y-%m-%d %H:%M:%S')
                        row_value += "'{s}', ".format(s=out_date)
                    elif column_types[heading_row.index(key)] == 0:
                        try:  # Trying to add a int
                            row_value += '{s}, '.format(s=int(float(col_data)))
                        except (ValueError, OverflowError):
                            row_value += '{s}, '.format(s=0)
                    elif column_types[heading_row.index(key)] == 1:
                        try:  # Trying to add a float
                            col_data = col_data.replace(',', '.')
                            if math.isnan(float(col_data)):
                                row_value += '{s}, '.format(s=0)
                            elif col_data == 'inf':
                                row_value += '{s}, '.format(s=999999)
                            else:
                                row_value += '{s}, '.format(s=float(col_data))
                        except (ValueError, OverflowError):
                            row_value += '{s}, '.format(s=0)
                    else:
                        row_value += "'{s}', ".format(s=check_text(col_data))
                inserting_text += row_value[:-2] + '),'
                if count_db_insert > 10000:
                    #print(inserting_text)
                    db.execute_sql(inserting_text[:-1])
                    inserting_text = insert_org_sql
                    count_db_insert = 0
                else:
                    count_db_insert += 1
            #print(inserting_text[:-1])
            db.execute_sql(inserting_text[:-1])
            if some_wrong_len > 0:
                no_miss_heading = False

        sql = """SELECT * INTO {schema}.{tbl} 
        from {schema}.temp_table
        where st_intersects(pos, (select polygon 
        from fields where field_name = '{field}'))
        """.format(schema=schema, tbl=tbl_name,field=field)
        time.sleep(0.1)
        if task != 'debug':
            task.setProgress(50)
        db.execute_sql(sql)
        db.execute_sql("DROP TABLE {schema}.temp_table".format(schema=schema))
        if task != 'debug':
            task.setProgress(70)
        ## TODO: Remove if data_type = harvest?
        if schema != 'harvest':
            sql = """drop table if exists {schema}.temp_tbl2;
        WITH voronoi_temp2 AS (
        SELECT ST_dump(ST_VoronoiPolygons(ST_Collect(pos))) as vor
        FROM {schema}.{tbl})
        SELECT (vor).path, (vor).geom into {schema}.temp_tbl2
        FROM voronoi_temp2;
        create index temp_index on {schema}.temp_tbl2 Using gist(geom);
        update {schema}.{tbl}
        SET polygon = st_multi(ST_Intersection(geom, (select polygon 
            from fields where field_name = '{field}')))
        FROM {schema}.temp_tbl2
        WHERE st_intersects(pos, geom)""".format(schema=schema, tbl=tbl_name, field=field)
            db.execute_sql(sql)
            db.execute_sql("drop table if exists {schema}.temp_tbl2;".format(schema=schema))

        if task != 'debug':
            task.setProgress(90)
        db.create_indexes(tbl_name, focus_col, schema)
        return [True, no_miss_heading, some_wrong_len]
    except Exception as e:
        return [False, e, traceback.format_exc()]
