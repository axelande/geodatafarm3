from qgis.core import QgsProject, QgsVectorLayer, QgsTask
import processing
from PyQt5 import QtCore
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog, QAbstractItemView, \
    QMessageBox
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
from ..support_scripts.__init__ import check_text, isfloat, isint
from ..support_scripts import shapefile as shp
__author__ = 'Axel Andersson'


class InputTextHandler(object):
    def __init__(self, iface, parent_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'GeoDataFarm_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        #print "** INITIALIZING GeoDataFarm"
        self.col_types = None
        self.file_name_with_path = None
        self.file_name = None
        self.input_file_path = None
        self.add_to_param_row_count = 0
        self.add_to_DB_row_count = 0
        # Create the dialog (after translation) and keep reference
        self.ITD = ImportTextDialog()
        self.dock_widget = parent_widget.dock_widget
        self.tr = parent_widget.tr
        self.iface = parent_widget.iface
        self.parent_widget = parent_widget
        self.tsk_mngr = parent_widget.tsk_mngr
        self.rb_pressed = False
        self.fields_to_DB = False
        self.combo = None
        self.sep = None
        self.encoding = 'utf-8'
        self.longitude_col = None
        self.latitude_col = None

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.ITD.show()
        self.ITD.PBAddInputFile.clicked.connect(self.open_input_file)
        self.ITD.pButAdd_Param.clicked.connect(self.add_to_param_list)
        self.ITD.pButRem_Param.clicked.connect(self.remove_from_param_list)
        self.ITD.pButInsertDataIntoDB.clicked.connect(self.insert_input_data_into_shp_file)
        self.ITD.pButContinue.clicked.connect(self.prepare_data_to_be_inserted)
        self.ITD.RBComma.clicked.connect(self.get_sep)
        self.ITD.RBSemi.clicked.connect(self.get_sep)
        self.ITD.RBTab.clicked.connect(self.get_sep)
        self.ITD.RBOwnSep.clicked.connect(self.get_sep)
        if self.dock_widget.CBDataType.currentText() == 'harvest':
            self.ITD.LParams.setText('Harvest Column')
            self.ITD.LMaxYield.setEnabled(True)
            self.ITD.LMinYield.setEnabled(True)
            self.ITD.LEMaximumYield.setEnabled(True)
            self.ITD.LEMinimumYield.setEnabled(True)
        if self.dock_widget.CBDataType.currentText() == 'soil':
            self.ITD.CombTime.setEnabled(False)
        self.ITD.exec_()

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
            if self.dock_widget.CBDataType.currentText() == 'harvest' and len(existing_values) > 0:
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
        self.ITD.pButContinue.setEnabled(True)

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        row_count = self.add_to_param_row_count
        if self.ITD.TWtoParam.selectedItems() is None:
            QMessageBox.information(None, "Error:", message=self.tr('No row selected!'))
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
        self.add_to_DB_row_count = i

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
        file_name = self.file_name + '.shp'
        if 'shapefiles' not in os.listdir(self.input_file_path):
            os.makedirs(self.input_file_path + "shapefiles/")
        files = os.listdir(self.input_file_path + "shapefiles/")
        if file_name in files:
            qm = QMessageBox()
            ret = qm.question(None, 'Message',
                              self.tr("The shape file already exist on your computer, would you like to replace it?"),
                              qm.Yes, qm.No)
            if ret == qm.No:
                return
            else:
                for ending in ['shp', 'shx', 'dbf', 'prj']:
                    try:
                        os.remove(
                            self.input_file_path) + "shapefiles/{f}.{e}".format(
                                f=file_name[:-4], e=ending)
                    except:
                        pass
        self.get_separator()
        self.set_radio_but()
        self.get_columns_names()

    def prepare_data_to_be_inserted(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the shapefile, determining date and time columns """
        columns_to_add = []
        for i in range(self.add_to_DB_row_count + 1):
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
        self.ITD.pButInsertDataIntoDB.setEnabled(True)
        if self.dock_widget.CBDataType.currentText() == 'harvest' or \
                (self.ITD.CombTime.currentText() == 'Yearly operations' and
                         self.dock_widget.CBDataType.currentText() !='soil'):
            self.ITD.LEYearOnly.setEnabled(True)
        if self.ITD.CombTime.currentText() == 'Time influenced operation':
            self.ITD.RBDateOnly.setEnabled(True)
            self.ITD.RBDateDiffTime.setEnabled(True)
            self.ITD.RBDateAndTime.setEnabled(True)
            self.ITD.ComBDateOnly.setEnabled(True)
            self.ITD.ComBDateOnly.addItems(columns_to_add)
            self.ITD.ComBDate.setEnabled(True)
            self.ITD.ComBDate.addItems(columns_to_add)
            self.ITD.ComBTime.setEnabled(True)
            self.ITD.ComBTime.addItems(columns_to_add)
            self.ITD.ComBDateTime.setEnabled(True)
            self.ITD.ComBDateTime.addItems(columns_to_add)

    def determine_column_type(self):
        """
        A function that retrieves the types of the columns from the .csv file
        :return: a list with with 0=int, 1=float, 2=char
        """
        row_types = []
        with open(self.file_name_with_path, encoding=self.encoding) as f:
            read_all = f.readlines()
            first_row = True
            max_rows = len(read_all)
            if max_rows > 1000:
                max_rows = 1000
            for row in read_all[:max_rows]:
                row = re.split((self.sep + ' |' + self.sep), row)
                if first_row:
                    heading_row = row
                    first_row = False
                    for col in heading_row:
                        row_types.append(0)
                    continue
                else:
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

    def insert_input_data_into_shp_file(self):
        """
        Preparing the data, by setting the correct type (including the date and
        time format), creating a shp file and finally ensure that the
        coordinates is in EPSG:4326
        :return:
        """
        self.latitude_col = check_text(self.ITD.ComBNorth.currentText())
        self.longitude_col = check_text(self.ITD.ComBEast.currentText())
        end_method = EndMethod()
        task1 = QgsTask.fromFunction('running script', end_method.run,
                                     self.parent_widget, self.ITD,
                                     self.add_to_DB_row_count, self.sep,
                                     self.col_types,
                                     self.add_to_param_row_count,
                                     self.file_name_with_path,
                                     self.input_file_path,
                                     self.encoding,
                                     on_finished=self.finish)
        self.tsk_mngr.addTask(task1)
        ##Debugg
        #values = end_method.run(1, self.parent_widget, self.ITD,
        #                        self.add_to_DB_row_count, self.sep,
        #                        self.col_types,
        #                        self.add_to_param_row_count,
        #                        self.file_name_with_path,
        #                        self.input_file_path,
        #                        self.encoding)
        #self.finish(1, values)

    def finish(self, result, values):
        [columns_to_add, column_types, heading_row, time_dict,
         params] = values
        self.params_to_evaluate = params
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(self.ITD.LEEPSG.text()))
        esri_output = srs.ExportToWkt()
        with open(self.input_file_path + 'shapefiles/temp.prj', 'a') as prj_file:
            prj_file.write(esri_output)
        vlayer = QgsVectorLayer(self.input_file_path + 'shapefiles/temp.shp','temp', "ogr")
        QgsProject.instance().addMapLayer(vlayer)
        text = self.file_name
        only_char = check_text(text)
        self.file_name = only_char
        file_name_with_path = self.input_file_path + "shapefiles/" + self.file_name
        para = {'INPUT': self.input_file_path + "shapefiles/temp.shp",
                'TARGET_CRS': 'EPSG:4326',
                'OUTPUT': file_name_with_path + '.shp'}
        processing.run('native:reprojectlayer', para)
        QgsProject.instance().removeMapLayer(vlayer.id())
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        esri_output = srs.ExportToWkt()
        with open(file_name_with_path + '.prj', 'a') as prj_file:
            prj_file.write(esri_output)
        self.point_layer = QgsVectorLayer(file_name_with_path + ".shp", self.file_name, "ogr")
        QgsProject.instance().addMapLayer(self.point_layer)
        os.remove(self.input_file_path + "shapefiles/temp.shp")
        os.remove(self.input_file_path + "shapefiles/temp.shx")
        os.remove(self.input_file_path + "shapefiles/temp.dbf")
        os.remove(self.input_file_path + "shapefiles/temp.prj")
        self.input_layer = self.point_layer
        self.file_name_with_path = file_name_with_path
        if self.dock_widget.CBDataType.currentText() != 'soil':
            columns_to_add['year'] = 0
            column_types.append(0)
            heading_row.append('year')
        self.columns_to_add = columns_to_add
        self.column_types = column_types
        self.heading_row = heading_row
        self.time_dict = time_dict
        self.dock_widget.PBAddFieldToDB.setEnabled(True)
        self.ITD.PBAddInputFile.clicked.disconnect()
        self.ITD.pButAdd_Param.clicked.disconnect()
        self.ITD.pButRem_Param.clicked.disconnect()
        self.ITD.pButInsertDataIntoDB.clicked.disconnect()
        self.ITD.pButContinue.clicked.disconnect()
        self.ITD.done(0)


class EndMethod:
    def __init__(self):
        self = self

    def run(self, task, parent_widget, ITD, add_to_DB_row_count, sep,
            col_types, add_to_param_row_count, file_name_with_path,
            input_file_path, encoding):
        super(EndMethod, self).__init__()
        self.iface = parent_widget.iface
        self.dock_widget = parent_widget.dock_widget
        self.ITD = ITD
        self.sep = sep
        self.col_types = col_types
        self.add_to_DB_row_count = add_to_DB_row_count
        self.add_to_param_row_count = add_to_param_row_count
        self.file_name_with_path = file_name_with_path
        self.input_file_path = input_file_path
        self.encoding = encoding
        only_char = check_text(self.ITD.ComBNorth.currentText())
        self.latitude_col = only_char
        only_char = check_text(self.ITD.ComBEast.currentText())
        self.longitude_col = only_char
        columns_to_add = {}
        for i in range(self.add_to_DB_row_count + 1):
            text = self.ITD.TWColumnNames.item(i, 0).text()
            only_char = check_text(text)
            columns_to_add[only_char] = []
        column_types = self.col_types
        self.params_to_evaluate = []
        ignore_col = []
        time_dict = {}
        time_dict['no_time'] = True
        time_dict['date_and_time'] = False
        time_dict['year_only'] = False
        time_dict['date_only'] = False
        time_dict['date_time_diff'] = False
        time_dict['time_'] = "Not correct column name"
        time_dict['Year'] = "Not correct column name"
        if self.dock_widget.CBDataType == 'Input (Yearly) like planting data':
            time_dict['no_time'] = False
            time_dict['Year'] = str(self.ITD.LEYearOnly.text())
            time_dict['year_only'] = True
            columns_to_add[u'Year'] = []
            column_types.append(0)
        if self.ITD.RBDateOnly.isChecked():
            time_dict['no_time'] = False
            ignore_col.append(str(self.ITD.ComBDateOnly.currentText()))
            time_dict['date'] = str(self.ITD.ComBDateOnly.currentText())
            time_dict['date_only'] = True
            columns_to_add[u'Date'] = []
            column_types.append(2)
        if self.ITD.RBDateDiffTime.isChecked():
            time_dict['no_time'] = False
            time_dict['date'] = str(self.ITD.ComBDate.currentText())
            time_dict['time_'] = str(self.ITD.ComBTime.currentText())
            time_dict['date_time_diff'] = True
            columns_to_add[u'Date'] = []
            ignore_col.append(str(self.ITD.ComBDate.currentText()))
            ignore_col.append(str(self.ITD.ComBTime.currentText()))
            column_types.append(2)
        if self.ITD.RBDateAndTime.isChecked():
            time_dict['no_time'] = False
            ignore_col.append(str(self.ITD.ComBDateTime.currentText()))
            time_dict['text'] = str(self.ITD.ComBDateTime.currentText())
            time_dict['date_and_time'] = True
            columns_to_add[u'Date'] = []
            column_types.append(2)
        for i in range(self.add_to_param_row_count):
            self.params_to_evaluate.append(self.ITD.TWtoParam.item(i, 0).text())
        start_date = datetime.strptime("2015-04-01", "%Y-%m-%d")
        if self.dock_widget.CBDataType.currentText() == 'harvest':
            min_yield = float(self.ITD.LEMinimumYield.text())
            max_yield = float(self.ITD.LEMaximumYield.text())
            if min_yield > max_yield:
                QMessageBox.information(None, "Error:",
                                        self.tr('Min value is greater than the '
                                                'maximum value'))
                return
            yield_row = check_text(self.params_to_evaluate[0])
            harvest = True
        else:
            harvest = False
        with open(self.file_name_with_path, encoding=self.encoding) as f:
            read_all = f.readlines()
            first_row = True
            some_wrong_len = 0
            for row_count, row in enumerate(read_all):
                row = re.split((self.sep + ' |' + self.sep), row)
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
                if task != 1:
                    task.setProgress(2 + row_count / len(read_all) * 45)
                for key in columns_to_add.keys():
                    col_data = row[heading_row.index(key)]
                    if float(row[heading_row.index(self.latitude_col)]) < 0.1 or float(row[heading_row.index(self.longitude_col)]) < 0.1:
                        break
                    if harvest:
                        if float(row[heading_row.index(yield_row)]) > max_yield:
                            break
                        if float(row[heading_row.index(yield_row)]) < min_yield:
                            break
                    if key == 'Year':
                        columns_to_add['Year'].append(time_dict['Year'])
                    elif key == 'Date':
                        if time_dict['date_only']:
                            try:
                                format_date = datetime.strftime(parse(col_data), '%Y-%m-%d')
                            except ValueError:
                                format_date = start_date
                            columns_to_add['Date'].append(format_date)
                        elif time_dict['date_time_diff']:
                            try:
                                format_date = datetime.strftime((parse(str(col_data) + " " + str(row[heading_row.index(time_dict['time_'])])), '%Y-%m-%d %H:%M:%d'))
                            except ValueError:
                                format_date = start_date
                            columns_to_add['Date'].append(format_date)
                        elif time_dict['date_and_time'] and key == time_dict['text']:
                            try:
                                format_date = datetime.strftime(parse(col_data), '%Y-%m-%d %H:%M:%d')
                            except ValueError:
                                format_date = start_date
                            columns_to_add['Date'].append(format_date)

                    elif column_types[heading_row.index(key)] == 0:
                        try: # Trying to add a int
                            columns_to_add[key].append(int(float(col_data)))
                        except (ValueError, OverflowError):
                            columns_to_add[key].append(0)
                    elif column_types[heading_row.index(key)] == 1:
                        try: # Trying to add a float
                            col_data = col_data.replace(',', '.')
                            if math.isnan(float(col_data)):
                                columns_to_add[key].append(0)
                            elif col_data == 'inf':
                                columns_to_add[key].append(999999)
                            else:
                                columns_to_add[key].append(float(col_data))
                        except (ValueError, OverflowError):
                            columns_to_add[key].append(0)
                    else:
                        columns_to_add[key].append(check_text(col_data))
            if some_wrong_len > 0:
                QMessageBox.information(None, "Information:",
                                        str(some_wrong_len) + self.tr(' rows were skipped '
                                                              'since the row'
                                                              ' did not match '
                                                              'the heading.'))
        if time_dict['year_only']:
            heading_row.append('Year')
        elif not time_dict['no_time']:
            heading_row.append('Date')
        ignore_col.append(self.longitude_col)
        ignore_col.append(self.latitude_col)
        with shp.Writer(shp.POINT) as w:
            w.autoBalance = 1 #ensures gemoetry and attributes match
            for i, key in enumerate(columns_to_add.keys()):
                if key in ignore_col:
                    continue
                if column_types[heading_row.index(key)] == 0:
                    w.field(str(key)[:10], 'N', max(10, len(str(key))), 0)
                if column_types[heading_row.index(key)] == 1:
                    w.field(str(key)[:10], 'F', max(10, len(str(key))), 8)
                if column_types[heading_row.index(key)] == 2:
                    w.field(str(key)[:10], 'C', 20)
            if self.dock_widget.CBDataType.currentText() != 'soil':
                w.field('year', 'N', 4)
            #loop through the data and write the shapefile
            for j, k in enumerate(columns_to_add[self.longitude_col]):
                if task != 1:
                    task.setProgress(50 + j/len(columns_to_add[self.longitude_col])*40)
                w.point(k, columns_to_add[self.latitude_col][j])
                data_row = []
                for key in columns_to_add.keys():
                    if key in ignore_col:
                        continue
                    data_row.append(columns_to_add[key][j])
                if self.dock_widget.CBDataType.currentText() != 'soil':
                    data_row.append(int(self.ITD.LEYearOnly.text()))
                w.record(*data_row) #write the attributes
            w.save(str(self.input_file_path) + "shapefiles/temp")
        del(w)
        return [columns_to_add, column_types, heading_row, time_dict,
                    self.params_to_evaluate]
