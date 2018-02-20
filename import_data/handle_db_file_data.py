from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QFileDialog, QAbstractItemView, QComboBox
from PyQt5.QtGui import QStandardItemModel, QStandardItem
import sqlite3
import os
from operator import xor
from collections import OrderedDict
# Import the code for the dialog
from widgets.import_db_file_dialog import ImportDBFileDialog
from support_scripts.rain_dancer import MyRainDancer
from database_scripts.db import DB
from support_scripts.create_layer import CreateLayer
__author__ = 'Axel Andersson'


class DBFileHandler:
    def __init__(self, iface, dock_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
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
        self.col_types = None
        self.add_to_Param_row_count = 0
        self.params_to_evaluate = []
        self.combo = []
        self.col_types = []
        self.col_names = []
        self.db_dict = None
        # Create the dialog (after translation) and keep reference
        self.IDB = ImportDBFileDialog()
        self.docked_widget = dock_widget

    def _get_db_dict(self):
        conn = sqlite3.connect("C:\\dev\\potatoes\\Sattdata\\2017\\pm-hmi.db")
        self.cursor = conn.cursor()
        res = self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        res1 = res.fetchall()
        tbls = OrderedDict()
        for table in res1:
            tbl_name = str(table[0])
            data = self.cursor.execute(
                "select * from {tbl} limit 10".format(tbl=tbl_name))
            data1 = data.fetchall()
            if len(data1) == 0:
                continue
            else:
                cols = self.cursor.execute(
                    "PRAGMA table_info({tbl})".format(tbl=tbl_name))
                cols1 = cols.fetchall()
                tbls[tbl_name] = {'col': [], 'data': []}
                for col_temp in cols1:
                    tbls[tbl_name]['col'].append(str(col_temp[1]))
                for row in data1:
                    tbls[tbl_name]['data'].append(row)
        self.db_dict = tbls

    def _change_example(self, mi):
        self.IDB.TWExamples.setRowCount(0)
        row = mi.row()
        data_example = self.db_dict[self.tbl_names[row]]['data']
        colums = self.db_dict[self.tbl_names[row]]['col']
        self.IDB.TWExamples.setRowCount(10)
        self.IDB.TWExamples.setColumnCount(len(colums))
        self.IDB.TWExamples.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.IDB.TWExamples.setHorizontalHeaderLabels([str(x) for x in colums])
        for i, row in enumerate(data_example):
            for j, col in enumerate(row):
                item = QTableWidgetItem(str(col))
                self.IDB.TWExamples.setItem(i, j, item)

    def fill_first_tlb(self):
        self.IDB.TWTableNames.setRowCount(len(self.tbl_names))
        self.IDB.TWTableNames.setColumnCount(1)
        self.IDB.TWTableNames.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        for i, row in enumerate(self.tbl_names):
            item1 = QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), Qt.ItemIsEditable))
            self.IDB.TWTableNames.setItem(i, 0, item1)
            #self.combo[i].view().pressed.connect(self.change_col_type)
            self.IDB.TWTableNames.itemDoubleClicked.connect(self._change_example)
        self.add_to_DB_row_count = i

    def _selected_main(self, mi):
        tbl = mi.row()
        colums = self.db_dict[self.tbl_names[tbl]]['col']
        data_example = self.db_dict[self.tbl_names[tbl]]['data']
        self.IDB.TWFinalExample.setRowCount(len(data_example) + 3)
        self.IDB.TWFinalExample.setColumnCount(len(colums))
        self.IDB.TWFinalExample.setSelectionBehavior(
            QAbstractItemView.SelectRows)
        self.IDB.TWFinalExample.setHorizontalHeaderLabels([str(x) for x in colums])
        other_tbls = self.tbl_names
        other_tbls.remove(self.tbl_names[tbl])
        for i in range(len(colums)):
            c_box = QComboBox()
            for j, tbl_name in enumerate(other_tbls):
                c_box.addItem(tbl_name, (i, j))
            c_box.currentIndexChanged[str].connect(self._change_2nd_row)
            self.IDB.TWFinalExample.setCellWidget(0, i, c_box)
        self.other_tbls = other_tbls
        for i, row in enumerate(data_example):
            for j, col in enumerate(row):
                item = QTableWidgetItem()
                item.setText(str(col))
                self.IDB.TWFinalExample.setItem(i + 3, j, item)

    @pyqtSlot(int)
    def _change_2nd_row(self, mi):
        combo = self.IDB.sender()
        row, tbl = combo.itemData(self.other_tbls.index(mi))
        colums = self.db_dict[self.tbl_names[tbl]]['col']
        c_box = QComboBox()
        c_box2 = QComboBox()
        for j, tbl_name in enumerate(colums):
            c_box.addItem(tbl_name, (row, tbl, j))
            c_box2.addItem(tbl_name, (row, tbl, j))
        self.IDB.TWFinalExample.setCellWidget(2, row, c_box2)
        c_box2.currentIndexChanged[str].connect(self._update_joins)
        self.IDB.TWFinalExample.setCellWidget(1, row, c_box)
        self.temp_col = colums

    @pyqtSlot(int)
    def _update_joins(self, mi):
        combo = self.IDB.sender()
        row, col, new_col = combo.itemData(self.temp_col.index(mi))
        print(row, col, new_col)
        first_row = self.IDB.TWFinalExample.cellWidget(1, row).currentText()
        sub_colum_id = self.temp_col.index(first_row)
        sub_new_name = new_col
        old_row = row
        current_data = []
        errors_found = []
        for i in range(3, 13):
            try:
                current_data.append(int(self.IDB.TWFinalExample.item(i, old_row).text()))
            except ValueError:
                errors_found.append(i)
                pass
        if len(current_data) == 0:
            print('no list')
        data = self.cursor.execute("select * from {tbl}".format(tbl=self.other_tbls[int(col)]))
        data1 = data.fetchall()
        matching_ids = []
        matching_values = []
        for row in data1:
            matching_ids.append(row[sub_colum_id])
            matching_values.append(row[sub_new_name])
        j = -1
        for i in range(3, 13):
            if i in errors_found:
                continue
            j += 1
            idx = current_data[j]
            item = QTableWidgetItem()
            new_name = matching_values[matching_ids.index(idx)]
            item.setText(str(new_name))
            self.IDB.TWFinalExample.setItem(i, old_row, item)

    def start_up(self):
        self._get_db_dict()
        self.tbl_names = list(self.db_dict.keys())
        self.tbl_names.sort()
        self.IDB.show()
        #self.fill_first_tlb()
        self.IDB.pButContinue.clicked.connect(self._change_example)
        self.IDB.ComBMainTable.addItems(self.tbl_names)
        self.IDB.ComBMainTable.view().pressed.connect(self._selected_main)
        quit = self.IDB.exec_()
        print('end')
