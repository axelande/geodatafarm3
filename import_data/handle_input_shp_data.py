__author__ = 'Axel Andersson'
from qgis.core import QgsProject, QgsVectorLayer
import processing
from PyQt5 import QtCore
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog, QAbstractItemView, QMessageBox
from osgeo import osr
import matplotlib.path as mplPath
import time
import support_scripts.shapefile as shp
import os
from string import ascii_letters, digits as str_digits
from operator import xor
# Import the code for the dialog
from import_data.insert_input_to_db import InsertInputToDB
from widgets.import_shp_dialog import ImportShpDialog
from support_scripts.radio_box import RadioComboBox
from database_scripts.db import DB
from support_scripts.create_layer import CreateLayer
from support_scripts.__init__ import check_text


class InputShpHandler:
    def __init__(self, iface, parent_widget, defined_field):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.iface = iface
        self.col_types = None
        self.add_to_param_row_count = 0
        self.params_to_evaluate = []
        self.combo = []
        self.col_types = []
        self.col_names = []
        # Create the dialog (after translation) and keep reference
        self.ISD = ImportShpDialog()
        self.DB = parent_widget.DB
        self.tr = parent_widget.tr
        self.dock_widget = parent_widget.dock_widget
        self.CreateLayer = CreateLayer(self.DB)
        self._q_replace_db_data = parent_widget._q_replace_db_data
        self.defined_field = defined_field
        self.fields_to_DB = False

    def add_input(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.ISD.show()
        self.ISD.add_input_file.clicked.connect(self.open_input_file)
        self.ISD.pButAdd_Param.clicked.connect(self.add_to_param_list)
        self.ISD.pButRem_Param.clicked.connect(self.remove_from_param_list)
        self.ISD.pButContinue.clicked.connect(self.prepere_data_to_be_inserted)
        self.ISD.pButInsertDataIntoDB.clicked.connect(self.prepere_shp_file)

    def add_to_param_list(self):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""
        row_count = self.add_to_param_row_count
        self.ISD.TWtoParam.setColumnCount(1)
        items_to_add = []
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append(self.ISD.TWtoParam.item(i,0).text())
        for item in self.ISD.TWColumnNames.selectedItems():
            if item.column() == 0 and item.text() not in existing_values:
                items_to_add.append(item.text())
        for i, item in enumerate(items_to_add, self.add_to_param_row_count):
            row_count += 1
            self.ISD.TWtoParam.setRowCount(row_count)
            item1 = QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(),QtCore.Qt.ItemIsEditable))
            self.ISD.TWtoParam.setItem(i, 0, item1)
        self.add_to_param_row_count = row_count
        self.ISD.pButContinue.setEnabled(True)

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        row_count = self.add_to_param_row_count
        if self.ISD.TWtoParam.selectedItems() == None:
            QMessageBox.information(None, self.tr("Error:"), message=('No row selected!'))
            return
        for item in self.ISD.TWtoParam.selectedItems():
            self.ISD.TWtoParam.removeRow(item.row())
            row_count -= 1
        self.add_to_param_row_count = row_count

    def get_columns_names(self):
        """A function that retrieves the name of the columns from the .csv file
        and returns a list with name"""
        self.ISD.TWColumnNames.clear()
        shp_file = shp.Reader(self.file_name_with_path + '.shp')
        f_row = True
        try:
            if len(shp_file.shapes()[0].points) > 1:
                self.isPolyon = True
            else:
                self.isPolyon = False
        except:
            QMessageBox.information(None, self.tr("Error:"), self.tr('No shapes was found in the file'))
        _types = []
        for name, type_, length, precision in shp_file.fields:
            if f_row:
                f_row = False
                continue
            self.col_names.append(name)
            _types.append(type_)
            if type_ == 'N':
                self.col_types.append(0)
            if type_ == 'F':
                self.col_types.append(1)
            if type_ == 'C':
                self.col_types.append(2)
        second_row = shp_file.iterRecords().next()
        combo_box_options = ["Integer", "Decimal value", "Character"]
        self.ISD.TWColumnNames.setRowCount(len(self.col_names))
        self.ISD.TWColumnNames.setColumnCount(3)
        self.ISD.TWColumnNames.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, row in enumerate(self.col_names):
            item1 = QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            item2 = QTableWidgetItem(str(second_row[i]))
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
            self.ISD.TWColumnNames.setItem(i, 0, item1)
            self.ISD.TWColumnNames.setItem(i, 1, item2)
            self.ISD.TWColumnNames.setCellWidget(i, 2, self.combo[i])
        self.add_to_DB_row_count = i

    def open_input_file(self):
        """
        Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function get_columns_names
        are being called.
        :return:
        """
        filters = "Shape files (*.shp)"
        self.file_name_with_path = QFileDialog.getOpenFileName(None, " File dialog ",'', filters)[0:-4]
        temp_var = self.file_name_with_path.split("/")
        self.file_name = temp_var[-1]
        if str(self.file_name_with_path) == '':
            return
        self.input_file_path = self.file_name_with_path[0:self.file_name_with_path.index(self.file_name)]
        if self._q_replace_db_data(tbl=self.file_name):
            self.get_columns_names()

    def _find_prj(self):
        """A little function that checks if a prj is in the same folder as the 
        input shp
        :return bool"""
        files_in_path = os.listdir(self.input_file_path)
        if self.file_name[:-4] + '.prj' in files_in_path:
            return True
        else:
            return False

    def prepere_data_to_be_inserted(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the shapefile, determining date and time columns """
        columns_to_add = []
        for i in range(self.add_to_DB_row_count + 1):
            columns_to_add.append(self.ISD.TWColumnNames.item(i, 0).text())
        shp_file = shp.Reader(self.file_name_with_path + '.shp')
        no_prj = self._find_prj()
        if -180 > shp_file.shapeRecord(0).shape.points[0][0] > 180 and no_prj and self.ISD.EPSG.text == '4326':
            QMessageBox.information(None, self.tr("Error:"), self.tr('The projection is probably wrong, please change from 4326'))
            return
        self.ISD.pButInsertDataIntoDB.setEnabled(True)
        self.ISD.RBNoDate.setEnabled(True)
        self.ISD.RBYearOnly.setEnabled(True)
        self.ISD.RBDateOnly.setEnabled(True)
        self.ISD.RBDateDiffTime.setEnabled(True)
        self.ISD.RBDateAndTime.setEnabled(True)
        self.ISD.year_only.setEnabled(True)
        self.ISD.ComBDateOnly.setEnabled(True)
        self.ISD.ComBDateOnly.addItems(columns_to_add)
        self.ISD.ComBDate.setEnabled(True)
        self.ISD.ComBDate.addItems(columns_to_add)
        self.ISD.ComBTime.setEnabled(True)
        self.ISD.ComBTime.addItems(columns_to_add)
        self.ISD.ComBDateTime.setEnabled(True)
        self.ISD.ComBDateTime.addItems(columns_to_add)

    def prepere_shp_file(self):
        """
        Preparing the data, by setting the correct type (including the date and
        time format), creating a shp file and finally ensure that the
        coordinates is in EPSG:4326
        :return:
        """
        columns_to_add = {}
        for i in range(self.add_to_DB_row_count + 1):
            text = self.ISD.TWColumnNames.item(i,0).text()
            only_char = check_text(text)
            columns_to_add[only_char] = []
        column_types = self.col_types
        if self.ISD.RBYearOnly.isChecked():
            self.time_dict['no_time'] = False
            self.time_dict['Year'] = str(self.ISD.year_only.text())
            self.time_dict['year_only'] = True
            columns_to_add[u'Year'] = []
            column_types.append(0)
        if self.ISD.RBDateOnly.isChecked():
            self.time_dict['no_time'] = False
            self.time_dict['ignore_col'].append(str(self.ISD.ComBDateOnly.currentText()))
            self.time_dict['date'] = str(self.ISD.ComBDateOnly.currentText())
            self.time_dict['date_only'] = True
            columns_to_add[u'Date'] = []
            column_types.append(2)
        if self.ISD.RBDateDiffTime.isChecked():
            self.time_dict['no_time'] = False
            self.time_dict['ignore_col'].append(str(self.ISD.ComBDate.currentText()))
            self.time_dict['ignore_col'].append(str(self.ISD.ComBTime.currentText()))
            self.time_dict['date'] = str(self.ISD.ComBDate.currentText())
            self.time_dict['time_'] = str(self.ISD.ComBTime.currentText())
            self.time_dict['date_time_diff'] = True
            columns_to_add[u'Date'] = []
            column_types.append(2)
        if self.ISD.RBDateAndTime.isChecked():
            self.time_dict['no_time'] = False
            self.time_dict['ignore_col'].append(str(self.ISD.ComBDateTime.currentText()))
            self.time_dict['text'] = str(self.ISD.ComBDateTime.currentText())
            self.time_dict['date_and_time'] = True
            columns_to_add[u'Date'] = []
            column_types.append(2)
        for i in range(self.add_to_param_row_count):
            self.params_to_evaluate.append(self.ISD.TWtoParam.item(i,0).text())
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(self.ISD.EPSG.text()))
        esri_output = srs.ExportToWkt()
        with open(str(self.input_file_path) + 'temp.prj', 'w') as prj_file:
            prj_file.write(esri_output)
        vlayer = QgsVectorLayer(str(self.input_file_path) + 'temp.shp', 'temp', "ogr")
        QgsProject.instance().addMapLayer(vlayer)
        only_char = check_text(self.file_name)
        self.file_name = only_char
        file_name = str(self.input_file_path) + self.ISD.data_prefix.text() + "_" + str(self.file_name)
        processing.runalg('qgis:reprojectlayer', str(self.input_file_path) + "temp.shp",'EPSG:4326', file_name + '.shp')
        QgsProject.instance().removeMapLayer(vlayer.id())
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        esri_output = srs.ExportToWkt()
        with open(file_name +'.prj', 'a') as prj_file:
            prj_file.write(esri_output)
        self.data_prefix = self.ISD.data_prefix.text()
        self.heading_row = self.col_names
        self.longitude_col = None
        self.latitude_col = None
        self.column_types = column_types
        schema = self.dock_widget.CBDataType.currentText()
        if schema != 'harvest':
            iitdb = InsertInputToDB(self, self.iface, dock_widget=self.dock_widget, defined_field=self.defined_field, db=self.DB)
            iitdb.import_data_to_db(schema=schema, convert2polygon=self.isPolyon, is_shp=True)
        self.reset_input_handler_widget()

    def reset_input_handler_widget(self):
        """
        Resets the input handler widget
        :return:
        """
        self.ISD.data_prefix.setText('')
        self.ISD.EPSG.setText('4326')
        self.ISD.TWColumnNames.setRowCount(0)
        self.ISD.TWtoParam.setRowCount(0)
        self.ISD.pButContinue.setEnabled(False)
        self.ISD.RBNoDate.setEnabled(False)
        self.ISD.RBYearOnly.setEnabled(False)
        self.ISD.RBDateOnly.setEnabled(False)
        self.ISD.RBDateDiffTime.setEnabled(False)
        self.ISD.year_only.setEnabled(False)
        self.ISD.year_only.setText('')
        self.ISD.ComBDate.clear()
        self.ISD.ComBDateOnly.clear()
        self.ISD.ComBDateTime.clear()
        self.ISD.ComBTime.clear()
        self.ISD.RBDateAndTime.setEnabled(False)
        self.ISD.pButInsertDataIntoDB.setEnabled(False)
        self.ISD.add_to_param_row_count = 0
        self.ISD.add_input_file.clicked.disconnect()
        self.ISD.pButAdd_Param.clicked.disconnect()
        self.ISD.pButRem_Param.clicked.disconnect()
        self.ISD.pButInsertDataIntoDB.clicked.disconnect()
        self.ISD.pButContinue.clicked.disconnect()
        self.ISD.done(0)