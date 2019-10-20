import webbrowser
from qgis.core import QgsTask
import traceback
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QTableWidgetItem, QFileDialog, QAbstractItemView, \
                             QMessageBox)
import re
import math
import time
from operator import xor, itemgetter
from datetime import datetime
# Import the code for the dialog
from ..widgets.import_text_dialog import ImportTextDialog
from ..support_scripts.radio_box import RadioComboBox
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts.__init__ import (TR, check_text, isfloat, isint,
                                        check_date_format)
from ..import_data.insert_manual_from_file import ManualFromFile
__author__ = 'Axel Horteborn'


class InputTextHandler(object):
    def __init__(self, parent_widget, data_type, columns=None):
        """A widget that enables the possibility to insert data from a text
        file into a postgres database.
        Parameters
        ----------
        parent_widget: GeoDataFarm
        data_type: str
            the name of the schema to add the data to
        columns: list
            list of str (the name) which columns to create a special
            request for the user to specify data/columns"""
        # initialize plugin directory
        self.data_type = data_type

        self.add_to_param_row_count = 0
        self.add_to_db_row_count = 0
        # Create the dialog (after translation) and keep reference
        self.ITD = ImportTextDialog()
        self.dock_widget = parent_widget.dock_widget
        translate = TR('InputTextHandler')
        self.tr = translate.tr
        self.plugin_dir = parent_widget.plugin_dir
        self.iface = parent_widget.iface
        self.populate = parent_widget.populate
        self.db = parent_widget.db
        self.parent_widget = parent_widget
        self.tsk_mngr = parent_widget.tsk_mngr
        self.mff = ManualFromFile(parent_widget.db, self.ITD, columns)
        self.rb_pressed = False
        self.fields_to_db = False
        self.combo = None
        self.sep = None
        self.col_types = None
        self.file_name_with_path = None
        self.file_name = None
        self.input_file_path = None
        self.longitude_col = None
        self.latitude_col = None
        self.heading_row = None
        self.sample_data = None
        self.tbl_name = ''
        self.encoding = 'utf-8'

    def run(self):
        """Presents the sub widget ImportTextDialog and connects the different
        buttons to their function"""
        self.ITD.show()
        self.ITD.PBAddInputFile.clicked.connect(self.open_input_file)
        self.ITD.PBHelp.clicked.connect(
            lambda: webbrowser.open('http://www.geodatafarm.com/add_data/'))
        self.ITD.PBAddParam.clicked.connect(self.add_to_param_list)
        self.ITD.PBRemParam.clicked.connect(self.remove_from_param_list)
        self.ITD.PBInsertDataIntoDB.clicked.connect(self.trigger_insection)
        self.ITD.PBContinue.clicked.connect(self.prepare_last_choices)
        self.ITD.PBAbbreviations.clicked.connect(self.show_abbreviations)
        self.ITD.RBComma.clicked.connect(self.change_sep)
        self.ITD.RBSemi.clicked.connect(self.change_sep)
        self.ITD.RBTab.clicked.connect(self.change_sep)
        self.ITD.RBOwnSep.clicked.connect(self.change_sep)
        self.populate.reload_fields(self.ITD.CBField)
        self.populate.reload_crops(self.ITD.CBCrop)
        if self.data_type == 'harvest':
            self.ITD.LParams.setText('Harvest Column')
            self.ITD.LMaxYield.setEnabled(True)
            self.ITD.LMinYield.setEnabled(True)
            self.ITD.LEMaximumYield.setEnabled(True)
            self.ITD.LEMinimumYield.setEnabled(True)
            self.ITD.LMoveX.setEnabled(True)
            self.ITD.LMoveY.setEnabled(True)
            self.ITD.LEMoveX.setEnabled(True)
            self.ITD.LEMoveY.setEnabled(True)
        if self.data_type == 'soil':
            self.ITD.CBCrop.setEnable(False)
        self.ITD.exec_()

    def show_abbreviations(self):
        """Shows a messageBox with the time abbreviations"""
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

    def define_separator(self):
        """Define the file encoding and the separator of the file"""
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

    def set_column_list(self):
        """A function that retrieves the name of the columns from the text file
        and fills the TWColumnName list with the name, first value and data type"""
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
        self.determine_column_type()
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

    def set_sep_radio_but(self):
        """Sets the radioButton indicating the separator of the file"""
        if self.sep == ',':
            self.ITD.RBComma.setChecked(True)
        if self.sep == ';':
            self.ITD.RBSemi.setChecked(True)
        if self.sep == '\t':
            self.ITD.RBTab.setChecked(True)

    def change_sep(self):
        """Change the separator and reload the column list"""
        if self.ITD.RBComma.isChecked():
            self.sep = ','
        if self.ITD.RBSemi.isChecked():
            self.sep = ';'
        if self.ITD.RBTab.isChecked():
            self.sep = '\t'
        if self.ITD.RBOwnSep.isChecked():
            self.sep = self.ITD.LEOwnSep.text().encode('utf-8')
        self.set_column_list()

    def change_col_type(self):
        """Updates the values (in self.col_types) of the data types for each 
        column in the data set"""
        self.col_types = []
        for c_box in self.combo:
            if c_box.currentText() == "Integer":
                self.col_types.append(0)
            if c_box.currentText() == "Decimal value":
                self.col_types.append(1)
            if c_box.currentText() == "Character":
                self.col_types.append(2)

    def open_input_file(self):
        """Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function define_separator,
        set_sep_radio_but and set_column_list are being called."""
        filters = "Text files (*.txt *.csv)"
        self.file_name_with_path = QFileDialog.getOpenFileName(None, " File dialog ", '',
                                                      filters)[0]
        if self.file_name_with_path == '':
            return
        temp_var = self.file_name_with_path.split("/")
        self.file_name = temp_var[len(temp_var)-1][0:-4]
        self.input_file_path = self.file_name_with_path[0:self.file_name_with_path.index(self.file_name)]
        self.define_separator()
        self.set_sep_radio_but()
        self.set_column_list()

    def prepare_last_choices(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the database"""
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
        self.mff.prepare_data(columns_to_add)

    def determine_column_type(self):
        """
        A function that retrieves the types of the columns from the .csv file
        and sets col_types as a list where with 0=int, 1=float, 2=char
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
        self.col_types = row_type_return

    def trigger_insection(self):
        """Preparing the data, by setting the correct type (including the date and
        time format), creating a shp file and finally ensure that the
        coordinates is in EPSG:4326
        """
        params = {}
        params['schema'] = self.data_type
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
        if self.ITD.RBDateOnly.isChecked():
            is_ok, first_date = check_date_format(self.sample_data, check_text(self.ITD.ComBDate.currentText()),
                                                  self.ITD.ComBDate_2.currentText())
            if not is_ok:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr("The date format didn't match the selected format, please change"))
                return
            params['date_row'] = check_text(self.ITD.ComBDate.currentText())
            params['date_format'] = self.ITD.ComBDate_2.currentText()
            params['all_same_date'] = ''
            manual_date = 'date_'
            table_date = first_date
        else:
            params['all_same_date'] = self.ITD.DE.text()
            manual_date = 'c_' + self.ITD.DE.text()
            table_date = self.ITD.DE.text()
            params['date_row'] = ''
        self.tbl_name = check_text(self.ITD.CBField.currentText() + '_' + self.data_type + '_' + table_date)
        params['tbl_name'] = self.tbl_name
        if self.db.check_table_exists(self.tbl_name, self.data_type):
            return
        for i in range(self.add_to_param_row_count):
            params['focus_col'].append(check_text(self.ITD.TWtoParam.item(i, 0).text()))
        self.focus_cols = params['focus_col']
        if params['schema'] == 'harvest':
            params['yield_row'] = params['focus_col'][0]
            params['max_yield'] = float(self.ITD.LEMaximumYield.text())
            params['min_yield'] = float(self.ITD.LEMinimumYield.text())
        self.mff.insert_manual_data(manual_date, self.ITD.CBField.currentText(),
                                    self.tbl_name, self.data_type)
        params['sep'] = self.sep
        params['tr'] = self.tr
        params['epsg'] = self.ITD.LEEPSG.text()
        if float(self.ITD.LEMoveX.text()) != 0.0 or float(self.ITD.LEMoveY.text()) != 0.0:
            params['move'] = True
            params['move_x'] = float(self.ITD.LEMoveX.text())
            params['move_y'] = float(self.ITD.LEMoveY.text())
        else:
            params['move'] = False
        #a = insert_data_to_database('debug', self.db, params)
        #print(a)
        task = QgsTask.fromFunction('Run import text data', insert_data_to_database, self.db, params,
                                    on_finished=self.finish)
        self.tsk_mngr.addTask(task)

    def finish(self, result, values):
        """Checks that all data is uploaded to the postgres database and adds
        the data to the canvas and closes the widget

        Parameters
        ----------
        result: object
            The result object
        values: list
            list with [bool, bool, int]
        """
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
        tbl = self.tbl_name
        if isint(tbl[0]):
            tbl = '_' + self.tbl_name
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
                layer = self.db.add_postgis_layer(tbl, 'pos', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))
            else:
                layer = self.db.add_postgis_layer(tbl, 'polygon', '{schema}'.format(schema=schema),
                                                check_text(param_layer.lower()))

            create_layer.create_layer_style(layer, check_text(target_field), tbl, schema)
        self.close()

    def close(self):
        """Disconnects buttons and closes the widget"""
        self.ITD.PBAddInputFile.clicked.disconnect()
        self.ITD.PBAddParam.clicked.disconnect()
        self.ITD.PBRemParam.clicked.disconnect()
        self.ITD.PBInsertDataIntoDB.clicked.disconnect()
        self.ITD.PBContinue.clicked.disconnect()
        self.ITD.PBAbbreviations.clicked.disconnect()
        self.ITD.RBComma.clicked.disconnect()
        self.ITD.RBSemi.clicked.disconnect()
        self.ITD.RBTab.clicked.disconnect()
        self.ITD.RBOwnSep.clicked.disconnect()
        self.ITD.done(0)


def check_row_failed(row, heading_row, n_coord, e_coord, yield_col, max_yield, min_yield):
    if len(row) != len(heading_row) and len(row) < 3:
        return True
    try:
        if float(row[heading_row.index(n_coord)]) < 0.1 or float(
                row[heading_row.index(e_coord)]) < 0.1:
            return True
    except ValueError:
        return True
    if yield_col:
        try:
            if float(row[heading_row.index(yield_col)]) > max_yield:
                return True
            elif float(row[heading_row.index(yield_col)]) < min_yield:
                return True
        except ValueError:
            return True
    return False


def move_points(db, move_x, move_y, tbl_name, task):
    try:
        # TODO: Check what happens when calling a non existing table
        min_row_id = db.execute_and_return("select min(field_row_id) from harvest.{tbl}".format(tbl=tbl_name))[0][0]
        max_row_id = db.execute_and_return("select max(field_row_id) from harvest.{tbl}".format(tbl=tbl_name))[0][0]
        if min_row_id is None:
            # If the user choose the wrong field and this part cant be used.
            return [False, 'Wrong field']
        distance = math.sqrt(move_x * move_x + move_y * move_y)
        if move_x > 0:
            p_bearing = 90 - math.degrees(math.atan(move_y / move_x))
        elif move_x < 0:
            p_bearing = 270 - math.degrees(math.atan(move_y / move_x))
        else:
            if move_y > 0:
                p_bearing = 0
            else:
                p_bearing = 180
        for i in range(min_row_id, max_row_id, 2000):
            if task != 'debug':
                task.setProgress(50 + (i - min_row_id) / (max_row_id - min_row_id) * 40)
            sql = """
                    WITH first_selected as
                        (SELECT field_row_id, pos, st_azimuth(pos,
                            (SELECT pos
                            FROM {tbl} new
                            WHERE org.field_row_id+1=new.field_row_id)
                            ) as bearing
                        FROM {tbl} org
                    where org.field_row_id >= {i1} - 3
                    and org.field_row_id < {i3} + 3
                    ),
                    sub_section as(SELECT field_row_id, st_project(pos::geography, 
                                                                   {dist}, 
                                                                   (select atan2(avg(sin(bearing)), avg(cos(bearing))) 
                                                                    from first_selected fs 
                                                                    where fs.field_row_id > (ss.field_row_id -3) 
                                                                    and fs.field_row_id < (ss.field_row_id +3)
                                                                    ) + radians({p_bearing})
                                                                  )::geometry as new_pos
                    FROM first_selected ss
                    )
                    update {tbl}
                    set pos=new_pos
                    from sub_section
                    where {tbl}.field_row_id = sub_section.field_row_id
                    and {tbl}.field_row_id >= {i1}
                    and {tbl}.field_row_id < {i3}""".format(tbl='harvest.' + tbl_name, i1=i, i2=i + 1,
                                                            i3=i + 2000, dist=distance,
                                                            p_bearing=p_bearing)
            db.execute_sql(sql)
            # print(sql)
        return [True, task]
    except Exception as e:
        return [False, e]


def create_table(db, schema, heading_row, latitude_col, longitude_col, date_row, all_same_date, column_types):
    inserting_text = 'INSERT INTO {schema}.temp_table ('.format(schema=schema)
    sql = "CREATE TABLE {schema}.temp_table (field_row_id serial PRIMARY KEY, ".format(
        schema=schema)
    lat_lon_inserted = False
    date_inserted = False
    for i, col_name in enumerate(heading_row):
        if isint(col_name[0]):
            col_name = '_' + col_name
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
            sql += str(col_name) + " text, "
        inserting_text += str(col_name) + ', '
    sql = sql[:-2]
    sql += ")"
    inserting_text = inserting_text[:-2] + ') VALUES '
    insert_org_sql = inserting_text
    db.create_table(sql, '{schema}.temp_table'.format(schema=schema))
    return inserting_text, insert_org_sql


def create_polygons(db, schema, tbl_name, field):
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


def insert_data_to_database(task, db, params):
    """Walks though the text files and adds data to the database
    Parameters
    ----------
    task: QgsTask
    db: object
    params: dict

    Returns
    -------
    list
        if no error: [bool, bool, int, str]
        else: [False, e, traceback.format_exc()]
    """
    try:
        schema = params['schema']
        tbl_name = params['tbl_name']
        column_types = params['column_types']
        encoding = params['encoding']
        file_name_with_path = params['file_name_with_path']
        field = params['field']
        longitude_col = params['longitude_col']
        latitude_col = params['latitude_col']
        if schema == 'harvest':
            yield_row = params['yield_row']
            max_yield = params['max_yield']
            min_yield = params['min_yield']
        else:
            yield_row = False
            max_yield = 1
            min_yield = 0
        date_row = params['date_row']
        if date_row != '':
            date_format = params['date_format']
        all_same_date = params['all_same_date']
        sep = params['sep']
        epsg = params['epsg']
        focus_col = params['focus_col']
        if isint(tbl_name[0]):
            tbl_name = '_' + tbl_name
        inserting_text, insert_org_sql = create_table(db, schema, params['heading_row'], latitude_col, longitude_col, date_row, all_same_date, column_types)
        if task != 'debug':
            task.setProgress(2)
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
                if check_row_failed(row, heading_row, latitude_col, longitude_col, yield_row,
                                    max_yield, min_yield):
                            some_wrong_len += 1
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
        no_miss_heading = True
        if some_wrong_len > 0:
            no_miss_heading = False

        sql = """SELECT * INTO {schema}.{tbl} 
        from {schema}.temp_table
        where st_intersects(pos, (select polygon 
        from fields where field_name = '{field}'))
        """.format(schema=schema, tbl=tbl_name, field=field)
        time.sleep(0.1)
        if task != 'debug':
            task.setProgress(50)
        db.execute_sql(sql)
        db.execute_sql("DROP TABLE {schema}.temp_table".format(schema=schema))
        suc = db.reset_row_id(schema, tbl_name)
        if not suc[0]:
            return suc
        if task != 'debug':
            task.setProgress(70)
        if schema != 'harvest':
            create_polygons(db, schema, tbl_name, field)
        db.create_indexes(tbl_name, focus_col, schema, primary_key=False)
        if params['move']:
            suc = move_points(db, params['move_x'], params['move_y'], tbl_name, task)
            if not suc[0]:
                True, no_miss_heading, some_wrong_len, sql
            else:
                task = suc[1]
        if task != 'debug':
            task.setProgress(90)
        return [True, no_miss_heading, some_wrong_len, sql]
    except Exception as e:
        return [False, e, traceback.format_exc()]
