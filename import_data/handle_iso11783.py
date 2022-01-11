import numpy as np
from operator import xor
import pandas as pd
from PyQt5 import QtWidgets, QtCore

from ..import_data.handle_text_data import create_table, create_polygons
from ..support_scripts.__init__ import (TR, check_text)
from ..support_scripts.radio_box import RadioComboBox
from ..support_scripts.pyagriculture.agriculture import PyAgriculture
from ..widgets.import_xml_bin import ImportXmlBin


class Iso11783:
    def __init__(self, parent_widget, type_: str):
        """For supporting the read of iso XML/Bin files"""
        self.py_agri = None
        self.db = parent_widget.db
        self.populate = parent_widget.populate
        self.data_type = type_
        self.IXB = ImportXmlBin()
        self.py_agri = None
        translate = TR('ImportXmlBin')
        self.tr = translate.tr
        self.combo = []
        self.checkboxes1 = []
        self.checkboxes2 = []
        self.checkboxes3 = []
        self.checkboxes4 = []

    def initiate_pyAgriculture(self, path: str):
        """Connects the plugin to pyAgriculture."""
        self.py_agri = PyAgriculture(path)
        self.py_agri.read_with_cython = False

    def run(self):
        """Presents the sub widget ImportXmlBin and connects the different
        buttons to their function."""
        self.IXB.show()
        self.IXB.PBAddInputFolder.clicked.connect(self.open_input_folder)
        self.IXB.PBFindFields.clicked.connect(self.populate_second_table)
        self.IXB.PBAddParam.clicked.connect(self.add_to_param_list)
        self.IXB.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.IXB.PBInsert.clicked.connect(self.add_to_database)
        self.IXB.exec_()

    def close(self):
        """Disconnects buttons and closes the widget"""
        self.IXB.PBAddInputFolder.clicked.disconnect()
        self.IXB.PBFindFields.clicked.disconnect()
        self.IXB.PBAddParam.clicked.disconnect()
        self.IXB.PBRemParam.clicked.disconnect()
        self.IXB.PBInsert.clicked.disconnect()
        self.IXB.done(0)

    def open_input_folder(self):
        """Opens a dialog and let the user select the folder where Taskdata are stored."""
        path = QtWidgets.QFileDialog.getExistingDirectory(None, self.tr("Open a folder"), '',
                                                          QtWidgets.QFileDialog.ShowDirsOnly)
        if path != '':
            self.initiate_pyAgriculture(path)
            self.populate_first_table()

    def get_task_data(self) -> dict:
        """For those tasks that are marked with include the script will gather their data."""
        task_names = {}
        for task_nr, data_set in enumerate(self.py_agri.tasks):  # type: pd.DataFrame
            try:
                print('data set')
                print(data_set)
                mid_rw = int(len(data_set) / 2)
                lat = data_set.iloc[mid_rw]['latitude']
                lon = data_set.iloc[mid_rw]['longitude']
                time_stamp = data_set.iloc[mid_rw]['time_stamp']
                if lat is None or lon is None or time_stamp is None:
                    continue
            except Exception as e:
                print(f'error: {e}')
                return
            fields = []
            fields_ = self.db.execute_and_return(f"""select field_name from fields where st_intersects(polygon, st_geomfromtext('Point({lon} {lat})', 4326))""")
            for field in fields_:
                fields.append([field, time_stamp])
            task_names[task_nr] = fields
        return task_names

    def populate_first_table(self):
        """Populates the task list."""
        self.checkboxes1 = []
        task_names = self.py_agri.gather_task_names()
        self.IXB.TWISODataAll.setRowCount(len(task_names))
        self.IXB.TWISODataAll.setColumnCount(2)
        self.IXB.TWISODataAll.setHorizontalHeaderLabels([self.tr('Get more info'), self.tr('Task name')])
        self.IXB.TWISODataAll.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        for i, row in enumerate(task_names):
            item1 = QtWidgets.QTableWidgetItem('Include')
            item1.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item1.setCheckState(QtCore.Qt.Unchecked)
            self.checkboxes1.append([item1, row])
            item2 = QtWidgets.QTableWidgetItem(row)
            item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWISODataAll.setItem(i, 0, item1)
            self.IXB.TWISODataAll.setItem(i, 1, item2)

    def populate_second_table(self):
        """Populates the list that is marked as include in the first table."""
        tasks_to_include = []
        for row in self.checkboxes1:
            if row[0].checkState() == 2:
                tasks_to_include.append(row[1])
        if len(tasks_to_include) is 0:
            QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                              self.tr('You need to select at least one of the tasks'))
            return
        self.py_agri.tasks = []
        self.combo = []
        self.checkboxes2 = []
        self.checkboxes3 = []
        self.checkboxes4 = []
        self.py_agri.gather_data(only_tasks=tasks_to_include)
        task_names = self.get_task_data()
        print(task_names)
        self.IXB.TWISODataSelect.setRowCount(len(self.py_agri.tasks))
        self.IXB.TWISODataSelect.setColumnCount(4)
        self.IXB.TWISODataSelect.setHorizontalHeaderLabels([self.tr('To include'), self.tr('Date'), self.tr('Field'),
                                                            self.tr('Crops')])
        self.IXB.TWISODataSelect.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        j = -1  # How may checkboxes that is added
        for i, row in enumerate(task_names.items()):
            if len(row[1]) == 0:
                continue
            j += 1
            item1 = QtWidgets.QTableWidgetItem('Include')
            item1.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item1.setCheckState(QtCore.Qt.Checked)
            self.checkboxes2.append([i, j, item1])
            item2 = QtWidgets.QTableWidgetItem(row[1][0][1])
            item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
            field_column = RadioComboBox()
            self.combo.append(field_column)
            self.populate.reload_fields(field_column)
            for nr in range(field_column.count()):
                if field_column.itemText(nr) == row[1][0][0][0]:
                    item = field_column.model().item(nr, 0)
                    item.setCheckState(QtCore.Qt.Checked)
                    field_column.setCurrentIndex(nr)
            crops = QtWidgets.QComboBox()
            self.populate.reload_crops(crops)
            self.IXB.TWISODataSelect.setItem(i, 0, item1)
            self.IXB.TWISODataSelect.setItem(i, 1, item2)
            self.IXB.TWISODataSelect.setCellWidget(i, 2, field_column)
            self.IXB.TWISODataSelect.setCellWidget(i, 3, crops)
            self.checkboxes3.append(field_column)
            self.checkboxes4.append(crops)
        self.set_column_list()

    def add_to_param_list(self):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""
        rows_in_table = self.IXB.TWtoParam.rowCount()
        self.IXB.TWtoParam.setColumnCount(1)
        items_to_add = []
        existing_values = []
        for i in range(rows_in_table):
            existing_values.append(self.IXB.TWtoParam.item(i, 0).text())
        for i, item in enumerate(self.IXB.TWColumnNames.selectedItems()):
            if item.column() == 0 and item.text() not in existing_values:
                items_to_add.append(item.text())
        for i, item in enumerate(items_to_add):
            self.IXB.TWtoParam.setRowCount(rows_in_table + i + 1)
            item1 = QtWidgets.QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWtoParam.setItem(i, 0, item1)
        self.IXB.PBInsert.setEnabled(True)

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        if self.IXB.TWtoParam.selectedItems() is None:
            QtWidgets.QMessageBox.information(None, self.tr("Error:"), self.tr('No row selected!'))
            return
        for item in self.IXB.TWtoParam.selectedItems():
            self.IXB.TWtoParam.removeRow(item.row())
        if self.IXB.TWtoParam.rowCount() == 0:
            self.IXB.PBInsert.setEnabled(False)

    def set_column_list(self):
        """A function that retrieves the name of the columns from the first tasks"""
        self.IXB.TWColumnNames.clear()
        self.combo = []
        self.IXB.TWColumnNames.setRowCount(len(self.py_agri.tasks[0].columns))
        self.IXB.TWColumnNames.setColumnCount(1)
        self.IXB.TWColumnNames.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        for i, row in enumerate(self.py_agri.tasks[0].columns):
            item1 = QtWidgets.QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWColumnNames.setItem(i, 0, item1)

    def prep_data(self) -> list:
        """Gather data from the combo-checkboxes and check that they are valid."""
        fields = []
        crops = []
        dates = []
        focus_cols = []
        focus_col = []
        idxs = []
        rows_in_table = self.IXB.TWtoParam.rowCount()
        for i in range(rows_in_table):
            focus_col.append(self.IXB.TWtoParam.item(i, 0).text())
        found = False
        for tbl_idx, check_idx,  cbox in self.checkboxes2:
            if cbox.checkState() == 2:
                found = True
                dates.append(self.IXB.TWISODataSelect.item(tbl_idx, 1).text())
                field = self.checkboxes3[check_idx].currentText()
                if field == self.tr('--- Select field ---'):
                    QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                                      self.tr('You need to select a crop'))
                    return [False]
                fields.append(field)
                crop = self.checkboxes4[check_idx].currentText()
                if crop == self.tr('--- Select crop ---'):
                    QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                                      self.tr('You need to select a crop'))
                    return [False]
                crops.append(crop)
                focus_cols.append(check_text(focus_col))
                idxs.append(tbl_idx)
        if not found:
            QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                              self.tr('You need to select at least one of the tasks'))
            return [False]
        return [True, fields, crops, dates, focus_cols, idxs]

    def get_col_types(self) -> list:
        """Gather the column types (0=int, 1=float, 2=string)"""
        col_types = []
        for dtype in self.py_agri.tasks[0].dtypes:
            if dtype == np.int64:
                col_types.append(0)
            elif dtype == np.float64:
                col_types.append(1)
            elif dtype == np.str:
                col_types.append(2)
            else:
                col_types.append(2)
        return col_types

    def add_to_database(self):
        """Initiate the insertion of data to the database."""
        col_types = self.get_col_types()
        prep_data = self.prep_data()
        if not prep_data[0]:
            return
        fields = prep_data[1]
        crops = prep_data[2]
        dates = prep_data[3]
        focus_cols = prep_data[4]
        idxs = prep_data[5]
        for i, field in enumerate(fields):
            crop = crops[i]
            date = dates[i]
            focus_col = focus_cols[i]
            columns = []
            for col in self.py_agri.tasks[idxs[i]].attrs['columns']:
                columns.append(check_text(col))
            insert_sql, _ = create_table(self.db, self.data_type, columns, 'latitude', 'longitude', 'time_stamp', '',
                                         col_types)
            insert_data(self.tr, self.db, self.py_agri.tasks[idxs[i]], self.data_type, insert_sql,
                        f'{check_text(field)}_{check_text(crop)}_{check_text(date)}', field, focus_col, col_types)
        self.close()


def insert_data(tr, db, data: pd.DataFrame, schema: str, insert_sql: str, tbl_name: str, field: str, focus_col: list,
                col_types: list):
    """Makes the actual insertion to the database (first to a temp table and then to the correct table)."""
    sql = insert_sql + '('
    count_db_insert = 0
    for row_nr, row in data.iterrows():
        lat_lon_insert = False
        for col_nr, col in enumerate(data.columns):
            if col in ['latitude', 'longitude']:
                if not lat_lon_insert:
                    sql += f"ST_PointFromText('POINT({row['longitude']} {row['latitude']})', 4326), "
                    lat_lon_insert = True
                continue
            if col == 'time_stamp':
                sql += f"'{row['time_stamp']}', "
                continue
            if str(row[col]) == 'nan':
                sql += f"Null, "
            elif col_types[col_nr] == 2:
                sql += f"'{row[col]}', "
            else:
                sql += f"{row[col]}, "
        sql = sql[:-2] + '), ('
        if count_db_insert > 10000:
            db.execute_sql(sql[:-3], return_failure=True)
            sql = insert_sql + '('
            count_db_insert = 0
        else:
            count_db_insert += 1
    if count_db_insert > 0:
        db.execute_sql(sql[:-3])

    sql = f"""SELECT * INTO {schema}.{tbl_name} 
    from {schema}.temp_table
    where st_intersects(pos, (select polygon 
    from fields where field_name = '{field}'))
    """
    suc = db.execute_sql(sql, return_failure=True)
    if not suc[0]:
        return suc
    if suc[2] == 0:
        QtWidgets.QMessageBox.information(None, tr("Warning:"),
                                          tr('No data was found on that field.'))
    if schema != 'harvest':
        create_polygons(db, schema, tbl_name, field)
    db.execute_sql(f"DROP TABLE {schema}.temp_table")
    db.create_indexes(tbl_name, focus_col, schema, primary_key=False)


class App:
    def __init__(self):
        self.dock_widget = GeoDataFarmDockWidget(None)
        self.db = DB(self.dock_widget)


if __name__ == '__main__':
    test_path = 'c:\\dev\\geodatafarm\\test_data\\TASKDATA\\'
    ap = None
    iso = Iso11783(ap)
    iso.initate_pyagriculture(test_path)
    iso.get_task_names()
