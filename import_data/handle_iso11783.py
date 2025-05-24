from typing import TYPE_CHECKING, Self
if TYPE_CHECKING:
    import pandas.core.frame
import numpy as np
from operator import xor
import pandas as pd
from PyQt5 import QtWidgets, QtCore
from qgis.core import QgsTask

from ..database_scripts.db import DB
from ..import_data.handle_text_data import create_table, create_polygons
from ..support_scripts.__init__ import (TR, check_text)
from ..support_scripts.create_layer import CreateLayer, add_background
from ..support_scripts.radio_box import RadioComboBox
from ..support_scripts.pyagriculture.agriculture import PyAgriculture
from ..widgets.import_xml_bin import ImportXmlBin


class Iso11783:
    def __init__(self: Self, parent_widget, type_: str) -> None:
        """For supporting the read of iso XML/Bin files"""
        self.py_agri = None
        self.db = parent_widget.db
        self.populate = parent_widget.populate
        self.parent = parent_widget
        self.data_type = type_
        self.sender = QtWidgets.QWidget().sender
        self.IXB = ImportXmlBin()
        self.py_agri = None
        translate = TR('ImportXmlBin')
        self.tr = translate.tr
        self.combo = []
        self.tasks = []
        self.checkboxes1 = []
        self.checkboxes2 = []
        self.checkboxes3 = []
        self.checkboxes4 = []
        self.unit_boxes = {}

    def initiate_pyAgriculture(self: Self, path: str) -> None:
        """Connects the plugin to pyAgriculture."""
        self.py_agri = PyAgriculture(path)

    def run(self: Self) -> None:
        """Presents the sub widget ImportXmlBin and connects the different
        buttons to their function."""
        self.IXB.show()
        self.IXB.PBAddInputFolder.clicked.connect(self.open_input_folder)
        self.IXB.PBFindFields.clicked.connect(self.populate_second_table)
        self.IXB.PBAddParam.clicked.connect(self.add_to_param_list)
        self.IXB.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.IXB.PBInsert.clicked.connect(self.add_to_database)
        if not self.parent.test_mode:
            self.IXB.exec_()

    def add_to_canvas(self, schema, tbl, focus_cols):
        """At the end add the layers to the canvas, one layer for 
        each of the columns in the focus_cols"""
        add_background()
        create_layer = CreateLayer(self.db)
        for param_layer in focus_cols[0]:
            param_layer = check_text(param_layer)
            target_field = param_layer
            if self.data_type == 'harvest':
                layer = self.db.add_postgis_layer(tbl, 'pos', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))
            else:
                layer = self.db.add_postgis_layer(tbl, 'polygon', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))

            create_layer.create_layer_style(layer, check_text(target_field), tbl, schema)

    def close(self, result, values):
        """Disconnects buttons and closes the widget when all tasks are completed, 
        also makes the call to add them to the canvas"""
        if values[0]:
            self.add_to_canvas(values[1], values[2], values[3])
        else:
             if values[1]:
                QtWidgets.QMessageBox.information(None, self.tr("Warning:"),
                                            values[2])
        self.added_nbrs += 1
        if self.added_nbrs == self.tasks_to_run:
            self.IXB.PBAddInputFolder.clicked.disconnect()
            self.IXB.PBFindFields.clicked.disconnect()
            self.IXB.PBAddParam.clicked.disconnect()
            self.IXB.PBRemParam.clicked.disconnect()
            self.IXB.PBInsert.clicked.disconnect()
            self.IXB.TWISODataSelect.itemChanged.disconnect(self.update_time_stamp)
            self.IXB.TWISODataAll.clear()
            self.IXB.TWISODataSelect.clear()
            self.IXB.TWColumnNames.clear()
            self.IXB.TWtoParam.clear()
            self.IXB.done(0)
            self.py_agri = None
            return True

    def open_input_folder(self: Self) -> None:
        """Opens a dialog and let the user select the folder where Taskdata are stored."""
        if self.parent.test_mode:
            if self.data_type == 'harvest':
                path = './tests/test_data/TASKDATA2/'
        else:
            path = QtWidgets.QFileDialog.getExistingDirectory(None, self.tr("Open a folder"), '',
                                                              QtWidgets.QFileDialog.ShowDirsOnly)
        if path != '':
            self.initiate_pyAgriculture(path)
            self.populate_first_table()      

    def get_task_data(self: Self) -> dict:
        """For those tasks that are marked with include the script will gather their data.
        The function will return a dict[task_nr] = [[field, timestamp]]"""
        task_names = {}
        for task_nr, data_set in enumerate(self.py_agri.tasks):  # type: pd.DataFrame
            try:
                if 'time_stamp' in data_set.columns:
                    time_stamp = data_set['time_stamp']
                else:
                    time_stamp = pd.Series(['1970-01-01'] * len(data_set))
                    data_set['time_stamp'] = time_stamp
                if 'geometry' in data_set.columns and 'longitude' not in data_set.columns:
                    try:
                        # Ensure the geometry column contains valid geometries
                        if not data_set['geometry'].isnull().all():
                            # Calculate centroids and create latitude and longitude columns
                            data_set['centroid'] = data_set['geometry'].apply(lambda geom: geom.centroid if geom else None)
                            data_set['latitude'] = data_set['centroid'].apply(lambda centroid: centroid.y if centroid else None)
                            data_set['longitude'] = data_set['centroid'].apply(lambda centroid: centroid.x if centroid else None)
                    except Exception as e:
                        print(f"Error calculating centroids: {e}")
                else:
                    lat = data_set['latitude']
                    lon = data_set['longitude']
                    if lat is None or lon is None:
                        continue
            except Exception as e:
                print(f'error: {e}')
                return
            fields = []
            sql = "with start_sel as ("
            for index, row in data_set.iloc[::int(len(data_set)/10)].iterrows():
                sql +=f"""select field_name from fields where st_intersects(polygon, st_geomfromtext('Point({row["longitude"]} {row["latitude"]})', 4326))
UNION """
            sql = sql[:-6] + ") select field_name from start_sel group by field_name"
            fields_ = self.db.execute_and_return(sql)
            if len(fields_) == 0 and not self.parent.test_mode:
                QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                              self.tr('At least one of the tasked was placed outside the field at approximate: ') + 
                                                      f'{round(lat, 4)}, {round(lon, 4)}')
            for field in fields_:
                fields.append([field[0], time_stamp.values[-1]])
            task_names[task_nr] = fields
        return task_names

    def populate_first_table(self: Self) -> None:
        """Populates the task list."""
        self.checkboxes1 = []
        task_names, file_names = self.py_agri.gather_task_names()
        self.IXB.TWISODataAll.setRowCount(len(task_names))
        self.IXB.TWISODataAll.setColumnCount(3)
        self.IXB.TWISODataAll.setHorizontalHeaderLabels([self.tr('Get more info'), self.tr('Task name'), self.tr('File name')])
        self.IXB.TWISODataAll.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        for i, row in enumerate(task_names):
            item1 = QtWidgets.QTableWidgetItem('Include')
            item1.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item1.setCheckState(QtCore.Qt.Unchecked)
            self.checkboxes1.append([item1, row, file_names[i]])
            item2 = QtWidgets.QTableWidgetItem(row)
            item2.setFlags(xor(item2.flags(), QtCore.Qt.ItemIsEditable))
            item3 = QtWidgets.QTableWidgetItem(file_names[i])
            item3.setFlags(xor(item3.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWISODataAll.setItem(i, 0, item1)
            self.IXB.TWISODataAll.setItem(i, 1, item2)
            self.IXB.TWISODataAll.setItem(i, 2, item3)

    def populate_second_table(self: Self) -> None:
        """Populates the list that is marked as include in the first table.
        Also calls py_agri to decode the binary data, this is done in a separate
        task."""
        self.tasks_to_include = []
        most_importants = []
        for row in self.checkboxes1:
            if row[0].checkState() == 2:
                self.tasks_to_include.append(row[2])
        if len(self.tasks_to_include) == 0:
            QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                              self.tr('You need to select at least one of the tasks'))
            return
        self.py_agri.tasks = []
        self.combo = []
        self.checkboxes2 = []
        self.checkboxes3 = []
        self.checkboxes4 = []
        if self.parent.test_mode is False:
            task = QgsTask.fromFunction('Decode binary data', self.py_agri.gather_data, 
                                        self.tasks_to_include, 
                                        most_importants,
                                        on_finished=self.populate2)
            self.parent.tsk_mngr.addTask(task)
        else:
            self.py_agri.gather_data("debug", self.tasks_to_include, 
                                     most_importants)
            self.populate2()

    def update_time_stamp(self, item: QtWidgets.QTableWidgetItem) -> None:
        """Updates the time_stamp in self.py_agri.tasks when the table is edited."""
        if item.column() == 1:  # Assuming the 'time_stamp' column is at index 1
            row = item.row()
            new_value = item.text()
            try:
                # Update the corresponding value in self.py_agri.tasks
                self.py_agri.tasks[row]['time_stamp'] = new_value
                print(f"Updated time_stamp for task {row} to {new_value}")
            except Exception as e:
                print(f"Error updating time_stamp: {e}")

    def populate2(self: Self, res: str="", values: str="") -> None:
        """The end of populate the second table when all data is decoded 
        from the qtask"""
        task_names = self.get_task_data()
        self.IXB.TWISODataSelect.setRowCount(len(self.tasks_to_include))
        self.IXB.TWISODataSelect.setColumnCount(4)
        self.IXB.TWISODataSelect.setHorizontalHeaderLabels([self.tr('To include'), self.tr('Date'), self.tr('Field'),
                                                            self.tr('Crops')])
        header = self.IXB.TWISODataSelect.horizontalHeader()       
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.IXB.TWISODataSelect.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        j = -1  # How may checkboxes that is added
        for i, row in enumerate(task_names.values()):
            j += 1
            item1 = QtWidgets.QTableWidgetItem('Include')
            item1.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            item1.setCheckState(QtCore.Qt.Checked)
            self.checkboxes2.append([i, j, item1])
            item2 = QtWidgets.QTableWidgetItem(row[0][1])
            item2.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable)
            field_column = RadioComboBox()
            self.combo.append(field_column)
            for field, _ in row:
                field_column.addItem(field)
            field_column.setCurrentIndex(1)
            crops = QtWidgets.QComboBox()
            self.populate.reload_crops(crops)
            self.IXB.TWISODataSelect.setItem(i, 0, item1)
            self.IXB.TWISODataSelect.setItem(i, 1, item2)
            self.IXB.TWISODataSelect.setCellWidget(i, 2, field_column)
            self.IXB.TWISODataSelect.setCellWidget(i, 3, crops)
            self.checkboxes3.append(field_column)
            self.checkboxes4.append(crops)
            self.tasks.append(self.rename_duplicate_columns(self.py_agri.tasks[i]))
        self.IXB.TWISODataSelect.itemChanged.connect(self.update_time_stamp)
        self.set_column_list()

    def add_to_param_list(self: Self) -> None:
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
                index = self.IXB.TWColumnNames.selectedIndexes()[i].row()
                unit = self.IXB.TWColumnNames.cellWidget(index, 4).currentText()
                if unit != item.text():
                    items_to_add.append(f'{item.text()}_{check_text(unit)}')
                else:
                    items_to_add.append(f'{check_text(item.text())}')
        for i, item in enumerate(items_to_add):
            self.IXB.TWtoParam.setRowCount(rows_in_table + i + 1)
            item1 = QtWidgets.QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWtoParam.setItem(i + rows_in_table, 0, item1)
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

    def set_column_list(self: Self) -> None:
        """A function that retrieves the name of the columns from the first tasks."""
        self.IXB.TWColumnNames.clear()  # Clear the table
        self.IXB.TWColumnNames.setRowCount(0)  # Reset row count
        self.IXB.TWColumnNames.setColumnCount(6)  # Set the number of columns

        # Set the horizontal header labels
        self.IXB.TWColumnNames.setHorizontalHeaderLabels([
            self.tr('Column name'),
            self.tr('Mean value'),
            self.tr('Min value'),
            self.tr('Max value'),
            self.tr('Unit'),
            self.tr('Scale')
        ])

        # Check if there are tasks to populate the table
        if self.tasks is None or len(self.tasks) == 0:
            return
        valid_columns = []
        for column in self.tasks[0].columns:
            if column not in ['latitude', 'longitude', 'geometry']:
                # Check if the column contains any non-null data
                if not self.tasks[0][column].isnull().all():
                    if len(self.tasks[0].attrs['unit_row']) > len(valid_columns):
                        valid_columns.append(column)

        # Populate the table with data
        self.IXB.TWColumnNames.setRowCount(len(valid_columns))
        self.unit_boxes = {}
        self.IXB.TWColumnNames.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        for i, row in enumerate(valid_columns):
            item1 = QtWidgets.QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), QtCore.Qt.ItemIsEditable))
            self.IXB.TWColumnNames.setItem(i, 0, item1)

            try:
                mean = str(round(self.tasks[0][row].mean(), 2))
            except:
                mean = ''
            item2 = QtWidgets.QTableWidgetItem(mean)
            self.IXB.TWColumnNames.setItem(i, 1, item2)

            try:
                _min = str(self.tasks[0][row].min())
            except:
                _min = ''
            item3 = QtWidgets.QTableWidgetItem(_min)
            self.IXB.TWColumnNames.setItem(i, 2, item3)

            try:
                _max = str(self.tasks[0][row].max())
            except:
                _max = ''
            item4 = QtWidgets.QTableWidgetItem(_max)
            self.IXB.TWColumnNames.setItem(i, 3, item4)

            unit = self.tasks[0].attrs['unit_row'][i]
            unit_col = self.get_units_option(unit)
            self.unit_boxes[len(self.unit_boxes)] = {'box': unit_col, 'org_item': unit}
            unit_col.__setattr__('index', i)
            unit_col.__setattr__('org_item', unit)
            unit_col.currentTextChanged.connect(self.change_unit_type)
            self.IXB.TWColumnNames.setCellWidget(i, 4, unit_col)

            item6 = QtWidgets.QTableWidgetItem("1")
            self.IXB.TWColumnNames.setItem(i, 5, item6)

    @staticmethod
    def rename_duplicate_columns(df):
        cols = pd.Series(df.columns)
        for dup in cols[cols.duplicated()].unique():
            cols[cols[cols == dup].index.values.tolist()] = [dup + '_' + str(i) if i != 0 else dup for i in range(sum(cols == dup))]
        df.columns = cols
        return df

    def change_unit_type(self):
        index = self.sender().index
        org_item = self.sender().org_item
        new_unit = self.IXB.TWColumnNames.cellWidget(index, 4).currentText()
        if org_item == new_unit:
            return
        new_value = None
        if org_item == 'ft':
            if new_unit == 'in':
                new_value = 12
            if new_unit == 'cm':
                new_value = 30.48
            if new_unit == 'm':
                new_value = 0.3048
        if org_item == 'in':
            if new_unit == 'in':
                new_value = 1 / 12
            if new_unit == 'cm':
                new_value = 2.54
            if new_unit == 'm':
                new_value = 0.0254
        if org_item == 'lb/bu':
            if new_unit == 'kg/m3':
                new_value = 12.87
        if org_item == 'lb/h':
            if new_unit =='kg/h':
                new_value = 0.453592
        if org_item == 'ac/h':
            if new_unit == 'ha/h':
                new_value = 0.404686
        if new_unit == 'kg/ha':
            if org_item == 'bu/ac':
                new_value = 67
            if org_item == 'lb/ac':
                new_value = 1.12085
        if org_item == 'gal/h':
            if new_unit == 'l/h':
                new_value = 3.7854
        if new_unit == 'C':
            new_value = 'C'
        if new_unit == 'F':
            new_value = 'F'
        if new_value is not None:
            self.IXB.TWColumnNames.item(index, 5).setText(str(new_value))

    @staticmethod
    def get_units_option(org_unit: str) -> RadioComboBox:
        unit_col = RadioComboBox()
        unit_col.addItem(org_unit)
        if org_unit == 'C':
            unit_col.addItem('F')
        if org_unit == 'F':
            unit_col.addItem('C')
        if org_unit == 'ft':
            unit_col.addItem('in')
            unit_col.addItem('cm')
            unit_col.addItem('m')
        if org_unit == 'in':
            unit_col.addItem('ft')
            unit_col.addItem('cm')
            unit_col.addItem('m')
        if org_unit == 'lb/bu':
            unit_col.addItem('kg/m3')
        if org_unit == 'lb/h':
            unit_col.addItem('kg/h')
        if org_unit == 'ac/h':
            unit_col.addItem('ha/h')
        if org_unit in ['bu/ac', 'lb/ac']:
            unit_col.addItem('kg/ha')
        if org_unit == 'gal/h':
            unit_col.addItem('l/h')
        return unit_col

    @staticmethod
    def cel2far(celsius) -> float:
        fahrenheit = 9.0 / 5.0 * celsius + 32
        return fahrenheit

    @staticmethod
    def far2cel(fahrenheit) -> float:
        celsius = (fahrenheit - 32) * 5.0 / 9.0
        return  celsius

    def prep_data(self: Self) -> list:
        """Gather data from the combo-checkboxes and check that they are valid."""
        fields = []
        crops = []
        dates = []
        focus_cols = []
        focus_col = []
        idxs = []
        rows_in_table = self.IXB.TWtoParam.rowCount()
        for i in range(rows_in_table):
            focus_col.append(check_text(self.IXB.TWtoParam.item(i, 0).text().strip()))
        found = False
        for tbl_idx, check_idx,  cbox in self.checkboxes2:
            if cbox.checkState() == 2:
                found = True
                if self.IXB.TWISODataSelect.item(tbl_idx, 1) is None:
                    continue
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
                focus_cols.append(focus_col)
                idxs.append(tbl_idx)
        if not found:
            QtWidgets.QMessageBox.information(None, self.tr("Error:"),
                                              self.tr('You need to select at least one of the tasks'))
            return [False]
        return [True, fields, crops, dates, focus_cols, idxs]

    def scale_dfs(self: Self, df: "pandas.core.frame.DataFrame") -> list:
        col_id = -1
        for col in df.attrs['columns']:
            if col in ['latitude', 'longitude', 'geometry']:
                continue
            col_id += 1
            scale_f = self.IXB.TWColumnNames.item(col_id, 5).text()
            if scale_f == 'C':
                df[col] = self.far2cel(df[col])
                continue
            elif scale_f == 'F':
                df[col] = self.cel2far(df[col])
                continue
            try:
                value = float(scale_f)
                df[col] = df[col] * value
            except ValueError:
                QtWidgets.QMessageBox(None, self.tr('Error'), self.tr('The number must only contain numbers and .'))
                return [False]
            except TypeError:
                pass
        return [True, df]

    def get_col_types(self: Self) -> list:
        """Gather the column types (0=int, 1=float, 2=string)"""
        col_types = []
        for dtype in self.py_agri.tasks[0].dtypes:
            if dtype == np.int64:
                col_types.append(0)
            elif dtype == np.float64:
                col_types.append(1)
            elif dtype == np.str_:
                col_types.append(2)
            else:
                col_types.append(2)
        return col_types

    def get_col_units(self: Self) -> dict:
        """returns a list with the unit of all columns, if None '' is added."""
        col_units = {}
        for index in range(self.IXB.TWColumnNames.rowCount()):
            column = self.IXB.TWColumnNames.item(index, 0).text()
            new_unit = self.IXB.TWColumnNames.cellWidget(index, 4).currentText()
            if new_unit == column:
                col_units[column] = '' 
            elif new_unit != '':
                col_units[column] = f'_{check_text(new_unit)}'
            else:
                col_units[column] = ''
        return col_units

    def add_to_database(self: Self) -> bool:
        """Initiate the insertion of data to the database."""
        col_types = self.get_col_types()
        col_units = self.get_col_units()
        prep_data = self.prep_data()
        if not prep_data[0]:
            return
        fields = prep_data[1]
        crops = prep_data[2]
        dates = prep_data[3]
        focus_cols = prep_data[4]
        self.added_nbrs = 0
        self.tasks_to_run = len(fields)
        for i, field in enumerate(fields):
            try:
                df = self.tasks[i]
                success = self.scale_dfs(df)
                if not success[0]:
                    return False
                
                crop = crops[i]
                date = dates[i]
                columns = []
                table = f'{check_text(field)}_{check_text(crop)}_{check_text(date)}'
                for col in df.columns:
                    columns.append(check_text(col.strip()))
                suc, insert_sql, _ = create_table(self.db, self.data_type, columns, 
                                                'latitude', 'longitude', 'time_stamp', '',
                                                col_types, column_units=col_units, table=table, 
                                                ask_replace=False, test_mode=self.parent.test_mode,
                                                task_nr=i)
                if not suc:
                    return False
                
                if not self.parent.test_mode:
                    db = DB(self.parent.dock_widget, path=self.parent.plugin_dir, test_mode=self.parent.test_mode)
                    connected = db.set_conn(False)
                    task = QgsTask.fromFunction(f'Adding field: {field}{prep_data[5][i]}', insert_data,
                                                db, df, self.data_type, 
                                                insert_sql, table, field, focus_cols, 
                                                col_types, i, on_finished=self.close)
                    self.parent.tsk_mngr.addTask(task)
                else:
                    res = insert_data(None, self.db, df, self.data_type, 
                                                insert_sql, table, field, focus_cols, 
                                                col_types, i)
                    # self.close(True, res)
                    return res[0]
            except Exception as e:
                print(e)

def insert_data(qtask: None, db: DB, data: pd.DataFrame, schema: str, insert_sql: str, tbl_name: str, 
                field: str, focus_col: list, col_types: list, tsk_nr:int) -> tuple[bool, str, str, list[list[str]]]:
    """Makes the actual insertion to the database (first to a temp table and then to the correct table)."""
    try:
        sql = insert_sql + '('
        count_db_insert = 0
        for row_nr, row in data.iterrows():
            lat_lon_insert = False
            lat_lon_c = 0
            for col_nr, col in enumerate(data.columns):
                if col in ['latitude', 'longitude']:
                    lat_lon_c += 1
                    if not lat_lon_insert:
                        sql += f"ST_PointFromText('POINT({row['longitude']} {row['latitude']})', 4326), "
                        lat_lon_insert = True
                    continue
                if col == 'time_stamp':
                    sql += f"'{row['time_stamp']}', "
                    continue
                if str(row[col]) == 'nan':
                    sql += f"Null, "
                elif str(row[col]).lower() == 'none':
                    sql += f"Null, "
                elif col_types[col_nr-lat_lon_c] == 2:
                    sql += f"'{row[col]}', "
                else:
                    sql += f"{row[col]}, "
            sql = sql[:-2] + '), ('
            if count_db_insert > 1_000:
                db.execute_sql(sql[:-3], return_failure=True)
                if qtask is not None:
                    qtask.setProgress(row_nr / len(data) * 80)
                sql = insert_sql + '('
                count_db_insert = 0
            else:
                count_db_insert += 1
            if qtask is not None:
                if qtask.isCanceled():
                    return False, False, "was cancelled"
        if count_db_insert > 0:
            db.execute_sql(sql[:-3])
        if qtask is not None:
            qtask.setProgress(80)

        sql = f"""SELECT * INTO {schema}.{tbl_name} 
        from {schema}.temp_table{tsk_nr}
        where st_intersects(pos, (select polygon 
        from fields where field_name = '{field}'))
        """
        suc = db.execute_sql(sql, return_failure=True, return_row_count=True)
        if qtask is not None:
            qtask.setProgress(85)
        if not suc[0]:
            return False, True, suc[1]
        if suc[2] == 0:
            return False, True, 'No data was found on that field.'
        if schema != 'harvest':
            create_polygons(db, schema, tbl_name, field)
        db.execute_sql(f"DROP TABLE {schema}.temp_table{tsk_nr}")
        if qtask is not None:
            qtask.setProgress(90)
        for j, col in enumerate(focus_col):
            db.create_indexes(tbl_name, col, schema, primary_key=False)
            if qtask is not None:
                qtask.setProgress(90 + j / len(focus_col) * 10)
        return True, schema, tbl_name, focus_col
    except Exception as e:
        return False, e