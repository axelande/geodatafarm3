from qgis.core import *
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QTableWidgetItem, QFileDialog, QAbstractItemView
from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox
# Import the code for the dialog
from database_scripts.db import DB
import support_scripts.shapefile as shp
import os
from operator import xor
from widgets.import_harvest_dialog import ImportHarvestDialog
from support_scripts.__init__ import check_text, isint, isfloat
from support_scripts.radio_box import RadioComboBox
__author__ = 'Axel Andersson'


class InputHarvestHandler:
    def __init__(self, iface, parent_widget):
        """A widget that enables the possibility to insert harvest data from a
        text file into a shapefile
        :param iface: Interface from Qgis
        :param parent_widget: the docked widget
        :return:
        """
        self.iface = iface

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
        self.dockwidget = None
        self.IHD = ImportHarvestDialog()
        self.DB = DB(parent_widget)
        self.parent_widget = parent_widget
        connected = self.DB.get_conn()
        self.rb_pressed = False
        if not connected:
            QMessageBox.information(None, "Error:", 'No farm is created, please create a farm to continue')
            return
        # Create the dialog (after translation) and keep reference


    def add_input(self):
        """
        Function that connects buttons to the widget and also that displaying
        the widget
        :return:
        """
        self.IHD.show()
        self.IHD.add_input_file.clicked.connect(self.open_input_file)
        self.IHD.pButInsertDataIntoDB.clicked.connect(self.insert_input_data_into_shp)
        self.IHD.RBComma.clicked.connect(self.get_sep)
        self.IHD.RBSemi.clicked.connect(self.get_sep)
        self.IHD.RBTab.clicked.connect(self.get_sep)
        self.IHD.RBOwnSep.clicked.connect(self.get_sep)

    def get_columns_names(self):
        """
        A function that retrieves the name of the columns from the .csv file
        and returns a list with name
        :return:
        """
        self.IHD.TWColumnNames.clear()
        with open(self.input_file) as f:
            read_all = f.readlines()
            first_row_bo = True
            if not self.rb_pressed:
                c = read_all[0].count(",")
                sc = read_all[0].count(";")
                if c > sc:
                    self.sep = ","
                else:
                    self.sep = ";"
            for row in read_all:
                row = row.split(self.sep)
                if first_row_bo:
                    first_row = row
                    first_row_bo = False
                else:
                    second_row = row
                    break
        headingrow = []
        for col in first_row:
            only_char = check_text(col)
            headingrow.append(only_char)
        self.col_types = self.determine_coloumn_type()
        combo_box_options = ["Integer","Decimal value","Character"]
        self.combo = []
        self.IHD.TWColumnNames.setRowCount(len(headingrow))
        self.IHD.TWColumnNames.setColumnCount(3)
        self.IHD.TWColumnNames.setSelectionBehavior(QAbstractItemView.SelectRows)
        for i, col in enumerate(headingrow):
            item1 = QTableWidgetItem(col)
            item1.setFlags(xor(item1.flags(),QtCore.Qt.ItemIsEditable))
            item2 = QTableWidgetItem(second_row[i])
            item2.setFlags(xor(item2.flags(),QtCore.Qt.ItemIsEditable))
            self.combo.append(RadioComboBox())
            for nr, t in enumerate(combo_box_options):
                self.combo[i].addItem(t)
                item = self.combo[i].model().item(nr, 0)
                if self.col_types[i] == nr:
                    item.setCheckState(QtCore.Qt.Checked)
                    self.combo[i].setCurrentIndex(nr)
                else:
                    item.setCheckState(QtCore.Qt.Unchecked)
            self.IHD.TWColumnNames.setItem(i, 0, item1)
            self.IHD.TWColumnNames.setItem(i, 1, item2)
            self.IHD.TWColumnNames.setCellWidget(i, 2, self.combo[i])
            self.combo[i].view().pressed.connect(self.change_col_type)
        first_row_checked = []
        for name in first_row:
            first_row_checked.append(check_text(name))
        self.IHD.ComBHarvestCol.addItems(first_row_checked)
        self.heading_row = first_row_checked
        self.IHD.pButInsertDataIntoDB.setEnabled(True)

    def change_col_type(self):
        combo_box_options = ["Integer", "Decimal value", "Character"]
        self.col_types = []
        for cbox in self.combo:
            self.col_types.append(cbox.currentIndex())

    def open_input_file(self):
        """
        Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function get_columns_names
        are being called.
        :return:
        """
        filters = "Text files (*.txt *.csv)"
        self.input_file = QFileDialog.getOpenFileName(None, " File dialog ",'', filters)
        temp_var = self.input_file.split("/")
        self.input_file_name = temp_var[len(temp_var)-1][0:-4]
        self.input_file_path = self.input_file[0:self.input_file.index(self.input_file_name)]
        self.get_columns_names()
        self.set_rb()

    def set_rb(self):
        if self.sep == ',':
            self.IHD.RBComma.setChecked(True)
        if self.sep == ';':
            self.IHD.RBSemi.setChecked(True)
        if self.sep == '\t':
            self.IHD.RBTab.setChecked(True)

    def get_sep(self):
        self.rb_pressed = True
        if self.IHD.RBComma.isChecked():
            self.sep = ','
        if self.IHD.RBSemi.isChecked():
            self.sep = ';'
        if self.IHD.RBTab.isChecked():
            self.sep = '\t'
        if self.IHD.RBOwnSep.isChecked():
            self.sep = self.IHD.LEOwnSep.text().encode('utf-8')
        self.get_columns_names()

    def determine_coloumn_type(self):
        """
        A function that retrieves the types of the columns from the .csv file
        :return: a list with with 0=int, 1=float, 2=char
        """

        row_types = []
        with open(self.input_file) as f:
            read_all = f.readlines()
            first_row = True
            for row in read_all[:1000]:
                row = row.split(self.sep)
                if first_row:
                    self.heading_row = row
                    first_row = False
                    for i, col in enumerate(self.heading_row):
                        row_types.append([])
                    continue
                else:
                    for j, col in enumerate(row):
                        if isint(col):
                            row_types[j].append(0)
                        elif isfloat(col):
                            row_types[j].append(1)
                        else:
                            row_types[j].append(2)
        row_type_return = []
        for col_value in range(len(row_types)):
            row_value = 0
            int_count = row_types[col_value].count(0)
            float_count = row_types[col_value].count(1)
            char_count = row_types[col_value].count(2)
            if float_count > int_count and float_count > char_count:
                row_value = 1
            if char_count > int_count and float_count < char_count:
                row_value = 2
            row_type_return.append(row_value)
        return row_type_return

    def insert_input_data_into_shp(self):
        """
        Preparing the data, by setting the correct type and creating a shp file
        :return:
        """
        lat_check, lon_check = False, False
        for word in self.heading_row:
            if "latitude" in word or "Latitude" in word:
                lat_check = True
                only_char = check_text(word)
                self.latitude_col = only_char
            if "longitude" in word or "Longitude" in word:
                lon_check = True
                only_char = check_text(word)
                self.longitude_col = only_char
        if not lat_check:
            QMessageBox.information(None, "Error:", 'There needs to be a latitude (wgs84) column')
            return
        if not lon_check:
            QMessageBox.information(None, "Error:", 'There needs to be a longitude (wgs84) column')
            return

        min_yield = float(self.IHD.minimum_yield.text())
        max_yield = float(self.IHD.maximum_yield.text())
        yield_row = self.IHD.ComBHarvestCol.currentText()
        columns_to_add = {}
        for name in self.heading_row:
            columns_to_add[check_text(name)] = []
        dict_order = []
        for key in columns_to_add.keys():
            dict_order.append(key)
        self.columns_to_add = columns_to_add
        column_types = self.col_types
        with open(self.input_file) as f:
            read_all = f.readlines()
            first_row = True
            for row in read_all:
                comma_count = row.count(',')
                semi_comma_count = row.count(';')
                if comma_count > semi_comma_count:
                    row = row.split(",")
                else:
                    row = row.split(";")
                if first_row:
                    heading_row =[]
                    headingrow = row
                    for col in headingrow:
                        only_char = check_text(col)
                        heading_row.append(only_char)
                    first_row = False
                    continue
                elif len(row) != len(heading_row):
                    continue

                for i, key in enumerate(heading_row):
                    if float(row[heading_row.index(self.latitude_col)]) < 1 or float(row[heading_row.index(self.longitude_col)]) < 1:
                        break
                    if float(row[heading_row.index(yield_row)]) > max_yield:
                        break
                    if float(row[heading_row.index(yield_row)]) < min_yield:
                        break
                    elif column_types[i] == 0:
                        try: # Trying to add a int
                            columns_to_add[key].append(int(row[i]))
                        except (ValueError, OverflowError):
                            columns_to_add[key].append(0)
                    elif column_types[i] == 1:
                        try: # Trying to add a float
                            columns_to_add[key].append(float(row[i]))
                        except (ValueError, OverflowError):
                            columns_to_add[key].append(0)
                    else:
                        only_char = check_text(row[i])
                        columns_to_add[key].append(only_char)
        w = shp.Writer(shp.POINT)
        w.autoBalance = 1 #ensures gemoetry and attributes match
        for i, key in enumerate(columns_to_add.keys()):
            if column_types[heading_row.index(key)] == 0:
                w.field(str(key)[:10], 'N', max(10, len(str(key))), 0)
            if column_types[heading_row.index(key)] == 1:
                w.field(str(key)[:10], 'F', max(10, len(str(key))), 8)
            if column_types[heading_row.index(key)] == 2:
                w.field(str(key)[:10], 'C', 20)
        #loop through the data and write the shapefile
        for j,k in enumerate(columns_to_add[self.longitude_col]):

            w.point(k, columns_to_add[self.latitude_col][j])
            list = []
            for key in columns_to_add.keys():
                list.append(columns_to_add[key][j])
            w.record(*list) #write the attributes

        #Save shapefile
        text = self.input_file_name
        only_char = check_text(text)
        self.input_file_name = self.IHD.LEYear.text() + "_" + only_char
        self.file_name = str(self.input_file_path) +"shapefiles/" + self.input_file_name

        w.save(self.file_name + ".shp")
        text_file = open(self.file_name + ".prj", "w")
        text_file.write('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["'
                        'WGS_1984",6378137,298.257223563]],PRIMEM["Greenwich",'
                        '0],UNIT["Degree",0.017453292519943295]]')
        text_file.close()

        input_layer = self.iface.addVectorLayer(self.file_name + ".shp", self.IHD.LEYear.text() + str(self.input_file_name), "ogr")
        QgsMapLayerRegistry.instance().addMapLayer(input_layer)
        self.input_layer = input_layer
        self.columns_to_add = columns_to_add
        self.column_types = column_types
        self.heading_row = heading_row
        self.parent_widget.dockwidget.pb_add_harvest_file_2.setEnabled(True)
        self.parent_widget.dockwidget.pb_move_harvest_points.setEnabled(True)
        self.IHD.done(0)
