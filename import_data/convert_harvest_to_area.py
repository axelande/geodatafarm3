import webbrowser
from qgis.core import QgsTask
import traceback
from PyQt5 import QtCore
from qgis.PyQt.QtWidgets import (QTableWidgetItem, QFileDialog, QAbstractItemView, QMessageBox)
import re
import math
from operator import xor, itemgetter
# Import the code for the dialog
from ..widgets.import_interpolate_harvest_dialog import ImportInterpolateHarvestDialog
from ..support_scripts.radio_box import RadioComboBox
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts import (TR, check_text, isfloat, isint, error_in_sign)
from ..import_data.insert_manual_from_file import ManualFromFile
__author__ = 'Axel Horteborn'


def check_row_failed(row, heading_row, param):
    if len(row) != len(heading_row) and len(row) < 3:
        return True
    try:
        if float(row[heading_row.index(param['n_coord'])]) < 0.1 or float(
                row[heading_row.index(param['e_coord'])]) < 0.1:
            return True
    except ValueError:
        return True
    try:
        if float(row[heading_row.index(param['yield_col'])]) > param['max_yield']:
            return True
        elif float(row[heading_row.index(param['yield_col'])]) < param['min_yield']:
            return True
    except ValueError:
        return True
    return False


class ConvertToAreas:
    def __init__(self, parent):
        """This class uses a text file as input and interpolate the harvest from a combiner."""
        self.db = parent.db
        self.populate = parent.populate
        self.tsk_mngr = parent.tsk_mngr
        self.IIHD = ImportInterpolateHarvestDialog()
        self.mff = ManualFromFile(parent.db, self.IIHD, [])
        translate = TR('ConvertToAreas')
        self.tr = translate.tr
        self.encoding = 'utf-8'

    def run(self):
        """Presents the sub widget ImportTextDialog and connects the different
        buttons to their function"""
        self.IIHD.show()
        self.IIHD.PBAddInputFile.clicked.connect(self.open_input_file)
        self.IIHD.PBSave.clicked.connect(self.run_import_step1)
        self.IIHD.PBHelp.clicked.connect(lambda: webbrowser.open('http://www.geodatafarm.com/combiner_harvest/'))
        self.IIHD.RBComma.clicked.connect(self.change_sep)
        self.IIHD.RBSemi.clicked.connect(self.change_sep)
        self.IIHD.RBTab.clicked.connect(self.change_sep)
        self.IIHD.RBOwnSep.clicked.connect(self.change_sep)
        self.populate.reload_fields(self.IIHD.CBField)
        self.populate.reload_crops(self.IIHD.CBCrop)
        self.IIHD.exec()

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
        self.prepare_last_choices()

    def set_sep_radio_but(self):
        """Sets the radioButton indicating the separator of the file"""
        if self.sep == ',':
            self.IIHD.RBComma.setChecked(True)
        if self.sep == ';':
            self.IIHD.RBSemi.setChecked(True)
        if self.sep == '\t':
            self.IIHD.RBTab.setChecked(True)

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

    def change_sep(self):
        """Change the separator and reload the column list"""
        if self.IIHD.RBComma.isChecked():
            self.sep = ','
        if self.IIHD.RBSemi.isChecked():
            self.sep = ';'
        if self.IIHD.RBTab.isChecked():
            self.sep = '\t'
        if self.IIHD.RBOwnSep.isChecked():
            self.sep = self.IIHD.LEOwnSep.text().encode('utf-8')
        self.set_column_list()
        self.prepare_last_choices()

    def set_column_list(self):
        """A function that retrieves the name of the columns from the text file
        and fills the TWColumnName list with the name, first value and data type"""
        self.IIHD.TWColumnNames.clear()
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
        self.IIHD.TWColumnNames.setRowCount(len(heading_row))
        self.IIHD.TWColumnNames.setColumnCount(3)
        self.IIHD.TWColumnNames.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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
            self.IIHD.TWColumnNames.setItem(i, 0, item1)
            self.IIHD.TWColumnNames.setItem(i, 1, item2)
            self.IIHD.TWColumnNames.setCellWidget(i, 2, self.combo[i])
        self.add_to_db_row_count = i

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

    def prepare_last_choices(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the database"""
        columns = []
        for i in range(self.add_to_db_row_count + 1):
            columns.append(self.IIHD.TWColumnNames.item(i, 0).text())
        self.IIHD.ComBNorth.clear()
        self.IIHD.ComBEast.clear()
        self.IIHD.ComBNorth.addItems(columns)
        self.IIHD.ComBEast.addItems(columns)
        self.IIHD.ComBYield.clear()
        self.IIHD.ComBMoisture.clear()
        self.IIHD.ComBYield.addItems(columns)
        self.IIHD.ComBMoisture.addItems(columns)
        for word in columns:
            for part in word.split(' '):
                if part.lower() in "latitude lat y":
                    index = self.IIHD.ComBNorth.findText(word)
                    self.IIHD.ComBNorth.setCurrentIndex(index)
                if part.lower() in "longitude lat x":
                    index = self.IIHD.ComBEast.findText(word)
                    self.IIHD.ComBEast.setCurrentIndex(index)
                if 'yield' in part.lower():
                    index = self.IIHD.ComBYield.findText(word)
                    self.IIHD.ComBYield.setCurrentIndex(index)
                if 'moisture' in part.lower():
                    index = self.IIHD.ComBMoisture.findText(word)
                    self.IIHD.ComBMoisture.setCurrentIndex(index)
        self.IIHD.PBSave.setEnabled(True)

    def gather_user_data(self):
        if self.IIHD.CBField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('In order to save the data you must select a field'))
            return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        else:
            field = self.IIHD.CBField.currentText()
        if self.IIHD.CBCrop.currentText() == self.tr('--- Select crop ---'):
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('In order to save the data you must select a crop'))
            return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        else:
            crop = self.IIHD.CBCrop.currentText()
        n_coord = self.IIHD.ComBNorth.currentText()
        e_coord = self.IIHD.ComBEast.currentText()
        yield_col = self.IIHD.ComBYield.currentText()
        if not self.IIHD.CBMoistureNA.isChecked():
            moisture_col = self.IIHD.ComBMoisture.currentText()
        else:
            moisture_col = None
        try:
            min_yield = float(self.IIHD.LEMinimumYield.text())
            max_yield = float(self.IIHD.LEMaximumYield.text())
            move_x = float(self.IIHD.LEMoveX.text())
            move_y = float(self.IIHD.LEMoveY.text())
        except Exception as e:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Yield and move values must be integer or a float number {e}'.format(e=e)))
            return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        date_text = self.IIHD.DE.text()
        if self.IIHD.CBRecalcYield.isChecked():
            yield_sign = self.IIHD.LEYieldSign.text()
            if error_in_sign(yield_sign):
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Sign must be "+", "-", "*" or "/"'))
                return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
            yield_value = self.IIHD.LEYieldValue.text()
            if not isfloat(yield_value):
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Yield value must be an integer or a float number'))
                return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        else:
            yield_sign = ''
            yield_value = ''
        if self.IIHD.CBRecalcMoisture.isChecked():
            moisture_sign = self.IIHD.LEMoistureSign.text()
            if error_in_sign(moisture_sign):
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Sign must be "+", "-", "*" or "/"'))
                return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
            moisture_value = self.IIHD.LEMoistureValue.text()
            if not isfloat(moisture_value):
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Moisture value must be an integer or a float number'))
                return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        else:
            moisture_sign = ''
            moisture_value = ''
        harvester_width = self.IIHD.LEHarvesterWidth.text()
        if not isfloat(harvester_width):
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Harvester width must be an integer or a float number'))
            return [False, '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        return [True, field, crop, n_coord, e_coord, yield_col, moisture_col, min_yield, max_yield,
                move_x, move_y, date_text, yield_sign, yield_value, moisture_sign, moisture_value,
                harvester_width]

    def run_import_step1(self):
        [bool_val, field, crop, n_coord, e_coord, yield_col, moisture_col, min_yield, max_yield,
         move_x, move_y, date_text, yield_sign, yield_value, moisture_sign, moisture_value,
         harvester_width] = self.gather_user_data()
        if bool_val is False:
            return
        param = {'db': self.db, 'field': field, 'e_coord': e_coord, 'n_coord': n_coord,
                 'yield_col': yield_col, 'moisture_col': moisture_col, 'min_yield': min_yield,
                 'max_yield': max_yield, 'encoding': self.encoding, 'sep': self.sep,
                 'file_name_with_path': self.file_name_with_path,
                 'harvester_width': harvester_width,
                 'date_text': date_text, 'yield_value': yield_value, 'yield_sign': yield_sign,
                 'moisture_value': moisture_value, 'moisture_sign': moisture_sign, 'move_x': move_x,
                 'move_y': move_y, 'tsk_mngr': self.tsk_mngr, 'crop': crop,
                 'run_import_step2': self.run_import_step2, 'final_method': self.final_method}
        self.all_parms = param
        task = QgsTask.fromFunction('First step of importing', self.create_temp_tbl1, param,
                                    on_finished=self.start_step2)
        #self.create_temp_tbl1('debug', param)
        self.tsk_mngr.addTask(task)

    @staticmethod
    def create_temp_tbl1(task, param):
        try:
            param['db'].execute_sql('DROP TABLE IF EXISTS harvest.temp_table')
            param['db'].execute_sql(
                'CREATE TABLE harvest.temp_table (field_row_id serial PRIMARY KEY, pos geometry(POINT, 4326), yield real, moisture real)')
            inserting_text = 'INSERT INTO harvest.temp_table (pos, yield, moisture)  VALUES '
            insert_org_sql = inserting_text
            count_db_insert = 0
            with open(param['file_name_with_path'], encoding=param['encoding']) as f:
                read_all = f.readlines()
                first_row = True
                some_wrong_len = 0
                for row_count, row in enumerate(read_all):
                    row_value = [None, 'Null', 'Null']
                    row = re.split((param['sep'] + ' |' + param['sep']), row)
                    lat_lon_inserted = False
                    if first_row:
                        heading_row = []
                        for col in row:
                            heading_row.append(col)
                        first_row = False
                        continue
                    if check_row_failed(row, heading_row, param):
                        some_wrong_len += 1
                        continue
                    if task != 'debug':
                        task.setProgress(row_count / len(read_all) * 35)
                    for key in heading_row:
                        col_data = row[heading_row.index(key)]
                        if not lat_lon_inserted and (
                                key == param['e_coord'] or key == param['n_coord']):
                            row_value[0] = "ST_PointFromText('POINT({p1} {p2})', 4326)".format(
                                p1=row[heading_row.index(param['e_coord'])],
                                p2=row[heading_row.index(param['n_coord'])])
                            lat_lon_inserted = True
                        if key == param['yield_col']:
                            try:
                                row_value[1] = str(float(col_data))
                            except (ValueError, OverflowError):
                                row_value[1] = 'Null'
                        if param['moisture_col'] is not None and key == param['moisture_col']:
                            try:
                                row_value[2] = str(float(col_data))
                            except (ValueError, OverflowError):
                                row_value[2] = 'Null'
                    inserting_text += "({p}, {y}, {m}),".format(p=row_value[0], y=row_value[1],
                                                                m=row_value[2])
                    if count_db_insert > 10000:
                        insert_ok = param['db'].execute_sql(inserting_text[:-1], return_failure=True)
                        if not insert_ok[0]:
                            return [False, insert_ok[2]]
                        inserting_text = insert_org_sql
                        count_db_insert = 0
                    else:
                        count_db_insert += 1
            insert_ok = param['db'].execute_sql(inserting_text[:-1], return_failure=True)
            if not insert_ok[0]:
                return [False, insert_ok[2]]
            param['db'].execute_sql('DROP table if exists harvest.temp_table2')
            sql = """SELECT * INTO harvest.temp_table2 
                        from harvest.temp_table
                        where st_intersects(pos, (select polygon 
                        from fields where field_name = '{field}'));
                        DROP table harvest.temp_table
                        """.format(field=param['field'])
            insert_ok = param['db'].execute_sql(sql, return_failure=True)
            if not insert_ok[0]:
                return [False, insert_ok[2]]
            if task != 'debug':
                task.setProgress(40)
            return [True, param]
        except Exception as e:
            return [False, e, traceback.format_exc()]

    def start_step2(self, result, values):
        if values[0]:
            try:
                task = QgsTask.fromFunction('Second step of importing', self.run_import_step2,
                                            self.all_parms, on_finished=self.start_step3)
                self.tsk_mngr.addTask(task)
            except Exception as e:
                print(e)
        else:
            print(values[1], values[2])

    @staticmethod
    def run_import_step2(task, param):
        try:
            if task != 'debug':
                task.setProgress(40)
            grid_size = int(int(param['harvester_width'])/2)
            tbl = check_text(param['field'] + '_harvest_' + param['date_text'])
            sql = """with pts as (SELECT st_centroid((st_dump(makegrid_2d(polygon, {g_s}, {g_s}))).geom) as the_geom from fields where field_name = '{field}'
                ), 
                v_pts as(select the_geom, st_buffer(the_geom, 0.0005) as buffered
                         from pts
                         where st_intersects((select polygon from fields where field_name = '{field}'), the_geom)
                        -- limit 10
                 ),
                 yield_data as(select pos, yield{y_sign}{y_eq} as yield, moisture{m_sign}{m_eq} as moisture
                               from harvest.temp_table2)
            select ROW_NUMBER() OVER() as field_row_id, the_geom as pos, avg(yield) as yield, avg(moisture) as moisture, '{d}'::TIMESTAMP AS Date_ into harvest.{tbl}
            from v_pts, yield_data
            where  pos && buffered --LEFT JOIN LATERAL (select * from yield_data where st_intersects(buffered, pos)) a On True
            group by the_geom
        """.format(field=param['field'], g_s=grid_size, y_sign=param['yield_sign'],
                   y_eq=param['yield_value'], m_sign=param['moisture_sign'],
                   m_eq=param['moisture_value'], d=param['date_text'], tbl=tbl)
            param['db'].execute_sql(sql)
            param['db'].execute_sql('DROP table harvest.temp_table2')
            if task != 'debug':
                task.setProgress(60)
            param['db'].create_indexes(tbl, ['yield', 'moisture'], 'harvest')
            if task != 'debug':
                task.setProgress(70)
            param['tbl'] = tbl
            return [True, param]
        except Exception as e:
            return [False, e,  traceback.format_exc()]

    def start_step3(self, result, values):
        if values[0]:
            if int(values[1]['move_x']) != 0 or int(values[1]['move_y'] != 0):
                try:
                    task = QgsTask.fromFunction('Second step of importing', self.run_move_points,
                                                values[1], on_finished=self.final_method)
                    self.tsk_mngr.addTask(task)
                except Exception as e:
                    print(e)
        else:
            print(values[1], values[2])

    @staticmethod
    def run_move_points(task, param):
        move_x = param['move_x']
        move_y = param['move_y']
        tbl = param['tbl']
        min_row_id = param['db'].execute_and_return("select min(field_row_id) from harvest.{tbl}".format(tbl=tbl))[0][0]
        max_row_id = param['db'].execute_and_return("select max(field_row_id) from harvest.{tbl}".format(tbl=tbl))[0][0]
        distance = math.sqrt(move_x * move_x + move_y * move_y)
        if move_x > 0:
            p_bearing = 90 - math.degrees(math.atan(move_y/move_x))
        elif move_x < 0:
            p_bearing = 270 - math.degrees(math.atan(move_y/move_x))
        else:
            if move_y > 0:
                p_bearing = 0
            else:
                p_bearing = 180
        for i in range(min_row_id, max_row_id, 2000):
            if task != 'debug':
                task.setProgress(70 + (i - min_row_id) / (max_row_id - min_row_id) * 20)
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
        and {tbl}.field_row_id < {i3}""".format(tbl='harvest.'+tbl, i1=i, i2=i + 1, i3=i + 2000, dist=distance, p_bearing=p_bearing)
            param['db'].execute_sql(sql)

    def check_failure(self, result, values):
        if values[0] is False:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return

    def final_method(self, result, values):
        if values[0]:
            param = values[1]
            print(param)
            self.mff.insert_manual_data(param['date_text'], param['field'], param['tbl'], 'harvest')
            create_layer = CreateLayer(self.db)
            print('ja')
            layer = self.db.add_postgis_layer(param['tbl'], 'pos', 'harvest', 'yield')
            create_layer.create_layer_style(layer, 'yield', param['tbl'], 'harvest')
            self.close()
        else:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Following error occurred: {m}'.format(m=values[1])))
            return

    def close(self):
        """Disconnects buttons and closes the widget"""
        self.IIHD.PBAddInputFile.clicked.disconnect()
        self.IIHD.PBSave.clicked.disconnect()
        self.IIHD.PBHelp.clicked.disconnect()
        self.IIHD.RBComma.clicked.disconnect()
        self.IIHD.RBSemi.clicked.disconnect()
        self.IIHD.RBTab.clicked.disconnect()
        self.IIHD.RBOwnSep.clicked.disconnect()
        self.IIHD.done(0)
