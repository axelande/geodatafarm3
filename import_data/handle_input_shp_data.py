__author__ = 'Axel Horteborn'
from qgis.core import QgsTask, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import Qt, QDate
import traceback
from qgis.PyQt.QtWidgets import (QTableWidgetItem, QFileDialog, QAbstractItemView,
                             QMessageBox)
from osgeo import osr, ogr
import os
from operator import xor
# Import the code for the dialog
from ..widgets.import_shp_dialog import ImportShpDialog
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts.__init__ import check_text, check_date_format, TR
from ..support_scripts.qt_data import _enum_select_rows, _item_flag
from psycopg2 import sql as pgsql
from ..import_data.insert_manual_from_file import ManualFromFile
from ..support_scripts.notifier import report_warning, report_error

#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)
class InputShpHandler:
    def __init__(self, parent_widget, schema, spec_columns):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.param_row_count = 0
        self.params_to_evaluate = []
        self.combo = []
        self.col_types = []
        self.col_names = []
        self.sample_data = []
        # Create the dialog (after translation) and keep reference
        self.ISD = ImportShpDialog()
        self.db = parent_widget.db
        translate = TR('InputShpHandler')
        self.tr = translate.tr
        self.tsk_mngr = parent_widget.tsk_mngr
        self.dock_widget = parent_widget.dock_widget
        self.populate = parent_widget.populate
        self.mff = ManualFromFile(parent_widget.db, self.ISD, spec_columns)
        self.CreateLayer = CreateLayer(self.db)
        self._q_replace_db_data = parent_widget._q_replace_db_data
        self.schema = schema
        self.fields_to_db = False
        self.isPolygon = False
        self.input_file_path = ''
        self.file_name_with_path = ''
        self.file_name = ''
        self.field = ''
        self.column_count = 0

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.ISD.show()
        self.ISD.add_input_file.clicked.connect(self.open_input_file)
        self.ISD.pButAdd_Param.clicked.connect(self.add_to_param_list)
        self.ISD.pButRem_Param.clicked.connect(self.remove_from_param_list)
        self.ISD.pButContinue.clicked.connect(self.prepare_data_to_be_inserted)
        self.ISD.pButInsertDataIntoDB.clicked.connect(self.prepare_shp_file)
        self.populate.reload_fields(self.ISD.CBField)
        self.populate.reload_crops(self.ISD.CBCrop)
        self.ISD.exec()

    def open_input_file(self):
        """Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function define_separator,
        set_sep_radio_but and set_column_list are being called."""
        filters = "Text files (*.shp)"
        self.file_name_with_path = QFileDialog.getOpenFileName(None,
                                                               " File dialog ",
                                                               '', filters)[0]
        path = self.file_name_with_path
        if self.file_name_with_path == '':
            return
        temp_var = self.file_name_with_path.split("/")
        self.tbl_name = temp_var[len(temp_var)-1][0:-4]
        self.input_file_path = path[0:path.index(self.tbl_name)]
        # If a .prj file with the same base name exists, read it and populate EPSG
        prj_path = str(self.file_name_with_path)[:-4] + '.prj'
        try:
            if os.path.exists(prj_path):
                with open(prj_path, 'r', encoding='utf-8', errors='ignore') as f:
                    prj_wkt = f.read()
                srs = osr.SpatialReference()
                try:
                    srs.ImportFromWkt(prj_wkt)
                    # Prefer PROJCS authority code (projected CRS) then fallback
                    epsg = None
                    try:
                        epsg = srs.GetAuthorityCode('PROJCS')
                    except Exception:
                        epsg = None
                    if not epsg:
                        try:
                            epsg = srs.GetAuthorityCode(None)
                        except Exception:
                            epsg = None
                    if not epsg:
                        try:
                            epsg = srs.GetAttrValue("AUTHORITY", 1)
                        except Exception:
                            epsg = None
                    if epsg:
                        try:
                            self.ISD.EPSG.setText(str(int(epsg)))
                        except Exception:
                            self.ISD.EPSG.setText(str(epsg))
                except Exception:
                    pass
        except Exception:
            # ignore PRJ parsing errors and continue
            pass
        self.get_columns_names()

    def get_columns_names(self):
        """A function that retrieves the name of the columns from the .csv file
        and returns a list with name"""
        self.ISD.TWColumnNames.clear()
        ogr_file = ogr.Open(self.file_name_with_path, 1)
        gk_lyr = ogr_file.GetLayer()
        if len(gk_lyr) == 0:
            report_warning(self.tr('No shapes was found in the file\n'))
            return
        _types = []
        for i in range(gk_lyr[0].GetFieldCount()):
            name = gk_lyr[0].GetFieldDefnRef(i).GetName()
            type_ = gk_lyr[0].GetFieldDefnRef(i).GetTypeName()
            self.col_names.append(name)
            _types.append(type_)
            if type_ in ['Integer', 'Integer64', 'Date', 'Time', 'DateTime']:
                self.col_types.append(0)
            elif type_ == 'Real':
                self.col_types.append(1)
            elif 'String' in type_:
                self.col_types.append(2)
            else:
                raise ValueError(self.tr('Unknown type found in shp file'))
        self.sample_data = []
        sec_row = True
        c_i = 0
        for row in gk_lyr:
            row = list(row.items().values())
            if sec_row:
                second_row = row
                sec_row = False
            if c_i < 1000:
                c_i += 1
                self.sample_data.append(row)
            else:
                break
        self.ISD.TWColumnNames.setRowCount(len(self.col_names))
        self.ISD.TWColumnNames.setColumnCount(2)
        self.ISD.TWColumnNames.setSelectionBehavior(
            _enum_select_rows())
        for i, row in enumerate(self.col_names):
            item1 = QTableWidgetItem(row)
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            # Safely obtain a sample value for this column; fall back to other rows or empty
            try:
                if 'second_row' in locals() and i < len(second_row):
                    sample_val = second_row[i]
                elif len(self.sample_data) > 0 and i < len(self.sample_data[0]):
                    sample_val = self.sample_data[0][i]
                else:
                    sample_val = ''
            except Exception:
                sample_val = ''
            item2 = QTableWidgetItem(str(sample_val))
            item2.setFlags(xor(item2.flags(), _item_flag('ItemIsEditable')))
            self.ISD.TWColumnNames.setItem(i, 0, item1)
            self.ISD.TWColumnNames.setItem(i, 1, item2)
        # store last index (used elsewhere as inclusive last index)
        self.column_count = i
        del gk_lyr, ogr_file

    def add_to_param_list(self):
        """Adds the selected columns to the list of fields that should be
        treated as "special" in the database both to work as a parameter that
        could be evaluated and as a layer that is added to the canvas"""
        row_count = self.param_row_count
        self.ISD.TWtoParam.setColumnCount(1)
        items_to_add = []
        existing_values = []
        if row_count != 0:
            for i in range(row_count):
                existing_values.append(self.ISD.TWtoParam.item(i, 0).text())
        for item in self.ISD.TWColumnNames.selectedItems():
            if item.column() == 0 and item.text() not in existing_values:
                items_to_add.append(item.text())
        for i, item in enumerate(items_to_add, self.param_row_count):
            row_count += 1
            self.ISD.TWtoParam.setRowCount(row_count)
            item1 = QTableWidgetItem(item)
            item1.setFlags(xor(item1.flags(), _item_flag('ItemIsEditable')))
            self.ISD.TWtoParam.setItem(i, 0, item1)
        self.param_row_count = row_count
        self.ISD.pButContinue.setEnabled(True)

    def remove_from_param_list(self):
        """Removes the selected columns from the list of fields that should be
        treated as "special" in the database"""
        row_count = self.param_row_count
        if self.ISD.TWtoParam.selectedItems() is None:
            report_warning(self.tr('No row selected!'))
            return
        for item in self.ISD.TWtoParam.selectedItems():
            self.ISD.TWtoParam.removeRow(item.row())
            row_count -= 1
        self.param_row_count = row_count

    def _find_prj(self):
        """A little function that checks if a prj is in the same folder as the 
        input shp
        :return bool"""
        files_in_path = os.listdir(self.input_file_path)
        if self.tbl_name[:-4] + '.prj' in files_in_path:
            return True
        else:
            return False

    def prepare_data_to_be_inserted(self):
        """A function that prepares the last parts of the widget with the data
        to be inserted into the shapefile, determining date and time columns """
        columns_to_add = []
        self.field = self.ISD.CBField.currentText()
        if self.field == self.tr('--- Select field ---'):
            report_warning(self.tr('In order to save the data you must select a field'))
            return
        for i in range(self.column_count + 1):
            columns_to_add.append(self.ISD.TWColumnNames.item(i, 0).text())
        ogr_file = ogr.Open(self.file_name_with_path, 1)
        lyr = ogr_file.GetLayer()
        # Robustly determine the EPSG code from the layer's spatial ref
        epsg = ''
        try:
            srs = lyr.GetSpatialRef()
            try:
                epsg = srs.GetAuthorityCode('PROJCS') or ''
            except Exception:
                epsg = ''
            if not epsg:
                try:
                    epsg = srs.GetAuthorityCode(None) or ''
                except Exception:
                    epsg = ''
            if not epsg:
                try:
                    epsg = srs.GetAttrValue('AUTHORITY', 1) or ''
                except Exception:
                    epsg = ''
        except Exception:
            epsg = ''
        if self.ISD.EPSG.text() and self.ISD.EPSG.text() != str(epsg):
            report_warning(self.tr(f'Projection mismatch: detected EPSG {epsg}, please set the EPSG field accordingly'))
            return
        self.ISD.pButInsertDataIntoDB.setEnabled(True)
        self.ISD.ComBDate.setEnabled(True)
        self.ISD.ComBDate.addItems(columns_to_add)
        self.mff.prepare_data(columns_to_add)

    def prepare_shp_file(self):
        """
        Preparing the data before adding it to a QgsTask. and ensure that the
        coordinates is in EPSG:4326
        :return:
        """
        columns_to_add = {}
        for i in range(self.column_count + 1):
            text = self.ISD.TWColumnNames.item(i,0).text()
            only_char = check_text(text)
            columns_to_add[only_char] = []
        for i in range(self.param_row_count):
            self.params_to_evaluate.append(self.ISD.TWtoParam.item(i,0).text())
        if not self._find_prj():
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(self.ISD.EPSG.text()))
            esri_output = srs.ExportToWkt()
            with open(str(self.file_name_with_path)[:-4] + '.prj', 'w') as f:
                f.write(esri_output)
        if self.db.check_table_exists(self.tbl_name, self.schema):
            return
        date_dict = {}
        if self.ISD.RBDateOnly.isChecked():
            is_ok, first_date = check_date_format(self.sample_data, check_text(self.ISD.ComBDate.currentText()),
                                                  self.ISD.ComBDate_2.currentText())
            if not is_ok:
                report_warning(self.tr("The date format didn't match the selected format, please change"))
                return
            manual_date = 'date_'
            date_dict['date_row'] = check_text(self.ISD.ComBDate.currentText())
            date_dict['date_format'] = self.ISD.ComBDate_2.currentText()
            table_date = first_date

        else:
            date_dict['simple_date'] = self.ISD.DE.text()
            manual_date = 'c_' + self.ISD.DE.text()
            table_date = self.ISD.DE.text()
        self.tbl_name = check_text(self.tbl_name + '_' + table_date)
        if self.schema != 'soil':
            self.mff.insert_manual_data(manual_date, self.ISD.CBField.currentText(),
                                        self.tbl_name, self.schema)
        task = QgsTask.fromFunction('Run import text data', self.import_data,
                                    date_dict, on_finished=self.show_data)
        self.tsk_mngr.addTask(task)

        # Debug
        #res = self.import_data('debug', date_dict)
        #self.show_data('a', res)

    def create_tbl(self, date_dict):
        """Creates a "temp" table in the database

        Returns
        -------
        If works:
            [True]
        else:
            return [False, e, traceback.format_exc()]
        """
        try:
            col_defs = "field_row_id integer PRIMARY KEY, "
            lat_lon_inserted = False
            date_inserted = False
            for i, col_name in enumerate(self.col_names):
                if not lat_lon_inserted:
                    col_defs += """pos geometry(POINT, 4326),
                    polygon geometry(POLYGON, 4326),
                    """
                    lat_lon_inserted = True
                # Normalize column name to safe lowercase identifier
                only_char = check_text(col_name)[:10]
                if 'date_row' in date_dict.keys() and check_text(col_name) == date_dict['date_row']:
                    col_defs += "date_ TIMESTAMP, "
                    continue
                elif 'simple_date' in date_dict.keys() and not date_inserted:
                    col_defs += "date_ TIMESTAMP, "
                    date_inserted = True
                if self.col_types[i] == 0:
                    col_defs += f"{only_char} INT, "
                if self.col_types[i] == 1:
                    col_defs += f"{only_char} REAL, "
                if self.col_types[i] == 2:
                    col_defs += f"{only_char} TEXT, "
            # If simple_date was requested but not inserted (e.g., no columns looped), ensure Date_ exists
            if 'simple_date' in date_dict.keys() and not date_inserted:
                col_defs += "date_ TIMESTAMP, "
                date_inserted = True
            col_defs = col_defs[:-2]
            sql = pgsql.SQL("CREATE TABLE {schema}.temp_table ({cols})").format(
                schema=pgsql.Identifier(self.schema),
                cols=pgsql.SQL(col_defs))
            # CREATE TABLE will be executed
            self.db.create_table(sql, f'{self.schema}.temp_table')
            return [True]
        except Exception as e:
            return [False, e, traceback.format_exc()]

    def get_shp_data(self):
        """Read data from the shp file

        Returns
        -------
        if works:
            [True, shapes, fields, data_as_points]
        else:
            [False, e, traceback.format_exc()]
        """
        try:
            ogr_file = ogr.Open(self.file_name_with_path, 1)
            gk_lyr = ogr_file.GetLayer()
            first = True
            data_dict = {}
            count = 0
            for feature in gk_lyr:
                geom = feature.GetGeometryRef()
                if first:
                    if geom.GetGeometryType() == 1:
                        data_as_points = True
                        geom_type = 'pos'
                    elif geom.GetGeometryType() == 3:
                        data_as_points = False
                        geom_type = 'polygon'
                    else:
                        report_warning(self.tr('Unknown shapetype (not point or polygon)'))
                        return [False, 'Wrong format', traceback.format_exc()]
                    data_dict[geom_type] = []
                    items = feature.items()
                    for key in items.keys():
                        key_name = check_text(key)[:10]
                        data_dict[key_name] = []
                    data_dict['field_row_id'] = []
                    first = False
                if geom.GetGeometryType() == 6:
                    report_warning(self.tr('Some shapes are of multipolygon type please convert them to single polygons.'))
                    return [False, 'Wrong format', traceback.format_exc()]
                geom_wkt = geom.ExportToWkt()
                if self.ISD.EPSG.text() == '4326':
                    data_dict[geom_type].append("ST_geomfromtext('{p}', 4326)".format(p=geom_wkt))
                else:
                    data_dict[geom_type].append("ST_transform(ST_geomfromtext('{p}',{epsg}), 4326)".format(p=geom_wkt, epsg=self.ISD.EPSG.text()))
                items = feature.items()

                for key in items.keys():
                    key_name = check_text(key)[:10]
                    if isinstance(items[key], str):
                        col = "'" + items[key] + "'"
                    else:
                        col = items[key]
                    data_dict[key_name].append(col)
                count += 1
                data_dict['field_row_id'].append(count)
            del ogr_file
            return [True, data_dict, data_as_points]
        except Exception as e:
            return [False, e, traceback.format_exc()]

    def import_data(self, task, date_dict):
        failure = False
        res = self.create_tbl(date_dict)
        if res[0] is False:
            failure = True
        if task != 'debug' and not failure:
            task.setProgress(5)
        res = self.get_shp_data()
        if res[0] is False:
            failure = True
        if not failure:
            data_dict = res[1]
            data_as_points = res[2]
        if task != 'debug':
            task.setProgress(25)
        if not failure:
            cols = []
            for key in self.col_names:
                cols.append(key.encode('ascii').decode('utf-8'))
            if 'simple_date' in date_dict.keys():
                data_dict['date_'] = []
                for i in range(len(data_dict['field_row_id'])):
                    data_dict['date_'].append("'" + str(date_dict['simple_date']) + "'")
            key_list = list(data_dict.keys())
            col_ids = pgsql.SQL(", ").join(
                pgsql.Identifier(str(e).replace("'", "")) for e in key_list)
            sql_prefix = pgsql.SQL("INSERT INTO {schema}.temp_table ({cols}) VALUES").format(
                schema=pgsql.Identifier(self.schema),
                cols=col_ids)
            values_parts = []
            for i in range(len(data_dict['field_row_id'])):
                value = [data_dict[key][i] for key in key_list]
                values_parts.append(f"({', '.join(str(e) for e in value)})")
            sql = sql_prefix + pgsql.SQL(", ".join(values_parts))
            # INSERT will be executed
            #print(sql)
            self.db.execute_sql(sql)
            if self.ISD.EPSG.text() != '4326':
                query = pgsql.SQL("UPDATE {schema}.temp_table SET pos = st_transform(pos, 4326)").format(
                    schema=pgsql.Identifier(self.schema))
                self.db.execute_sql(query)
            # temp_table and field geometry inspection skipped in normal operation
            if task != 'debug':
                task.setProgress(50)
            if data_as_points:
                geom_col = 'pos'
            else:
                geom_col = 'polygon'
            # Determine field polygon SRID so we can compare geometries in the same CRS
            try:
                fs_q = pgsql.SQL("SELECT ST_SRID(polygon) FROM fields WHERE field_name = %s")
                fs_res = self.db.execute_and_return(fs_q, params=(self.field,), return_failure=True)
                field_srid = None
                if isinstance(fs_res, list) and fs_res[0] is True:
                    data = fs_res[1]
                else:
                    data = fs_res
                if data and len(data) > 0 and len(data[0]) > 0:
                    try:
                        field_srid = int(data[0][0])
                    except Exception:
                        field_srid = None
            except Exception:
                field_srid = None

            # detected field_srid logged during development
            if field_srid and field_srid != 4326:
                # transform temp_table geometry into field_srid for intersection test
                intersects_sql = pgsql.SQL(
                    "SELECT * INTO {schema}.{tbl} FROM {schema}.temp_table WHERE st_intersects(st_transform({geom_col}, %s), (SELECT polygon FROM fields WHERE field_name = %s))"
                ).format(schema=pgsql.Identifier(self.schema), tbl=pgsql.Identifier(self.tbl_name), geom_col=pgsql.Identifier(geom_col))
                params = (field_srid, self.field)
            else:
                intersects_sql = pgsql.SQL(
                    "SELECT * INTO {schema}.{tbl} FROM {schema}.temp_table WHERE st_intersects({geom_col}, (SELECT polygon FROM fields WHERE field_name = %s))"
                ).format(schema=pgsql.Identifier(self.schema), tbl=pgsql.Identifier(self.tbl_name), geom_col=pgsql.Identifier(geom_col))
                params = (self.field,)

            # Ensure destination table does not already exist to avoid conflicts
            try:
                drop_query = pgsql.SQL("DROP TABLE IF EXISTS {schema}.{tbl}").format(
                    schema=pgsql.Identifier(self.schema), tbl=pgsql.Identifier(self.tbl_name))
                self.db.execute_sql(drop_query)
            except Exception:
                pass

            try:
                self.db.execute_sql(intersects_sql, params=params)
            except Exception as e:
                # Log exception to QGIS message log for visibility
                try:
                    from qgis.core import QgsMessageLog, Qgis
                    QgsMessageLog.logMessage(f"execute_sql for intersects failed: {e}", 'GeoDataFarm', Qgis.Warning)
                except Exception:
                    pass
            if task != 'debug':
                task.setProgress(70)
            if self.schema != 'harvest' and data_as_points:
                # self.db.execute_sql(
                #    "DROP TABLE {schema}.temp_table".format(schema=self.schema))

                query = pgsql.SQL(
                    "DROP TABLE IF EXISTS {schema}.temp_tbl2;"
                    " WITH voronoi_temp2 AS ("
                    " SELECT ST_dump(ST_VoronoiPolygons(ST_Collect(pos))) AS vor"
                    " FROM {schema}.{tbl})"
                    " SELECT (vor).path, (vor).geom INTO {schema}.temp_tbl2 FROM voronoi_temp2;"
                    " CREATE INDEX temp_index ON {schema}.temp_tbl2 USING gist(geom);"
                    " UPDATE {schema}.{tbl}"
                    " SET polygon = ST_Intersection(geom, (SELECT polygon FROM fields WHERE field_name = %s))"
                    " FROM {schema}.temp_tbl2"
                    " WHERE st_intersects(pos, geom)"
                ).format(
                    schema=pgsql.Identifier(self.schema),
                    tbl=pgsql.Identifier(self.tbl_name))
                self.db.execute_sql(query, params=(self.field,))
            if task != 'debug':
                task.setProgress(90)
            redone_param_list = []
            for param in self.params_to_evaluate:
                only_char = check_text(param)
                redone_param_list.append(only_char)
            self.db.execute_sql(
                pgsql.SQL("DROP TABLE IF EXISTS {schema}.temp_tbl2").format(
                    schema=pgsql.Identifier(self.schema)))
            self.db.create_indexes(self.tbl_name, redone_param_list, self.schema)
            return [True]
        if failure:
            return res

    def show_data(self, result, values):
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
            report_error(self.tr('Following error occurred: {m}\n\n Traceback: {t}'.format(m=values[1],
                                                                                                      t=values[2])))
            return
        tbl = self.tbl_name
        length = self.db.execute_and_return(
            pgsql.SQL("SELECT field_row_id FROM {s}.{t} LIMIT 2").format(
                s=pgsql.Identifier(self.schema), t=pgsql.Identifier(tbl)))
        if len(length) == 0:
            report_warning(self.tr('No data were found in the field, '
                                            'are you sure that the data is in the correct field?'))
            return
        create_layer = CreateLayer(self.db)
        for param_layer in self.params_to_evaluate:
            param_layer = check_text(param_layer)
            target_field = param_layer
            if self.schema == 'harvest':
                layer = self.db.add_postgis_layer(tbl, 'pos', '{schema}'.format(
                    schema=self.schema),
                                                  check_text(
                                                      param_layer.lower()))
            else:
                layer = self.db.add_postgis_layer(tbl, 'polygon',
                                                  '{schema}'.format(
                                                      schema=self.schema),
                                                  check_text(
                                                      param_layer.lower()))

            create_layer.create_layer_style(layer, check_text(target_field),
                                            tbl, self.schema)
        self.reset_input_handler_widget()

    def reset_input_handler_widget(self):
        """
        Resets the input handler widget
        :return:
        """
        self.ISD.EPSG.setText('4326')
        self.ISD.TWColumnNames.setRowCount(0)
        self.ISD.TWtoParam.setRowCount(0)
        self.ISD.pButContinue.setEnabled(False)
        self.ISD.RBDateOnly.setEnabled(False)
        self.ISD.DE.setDate(QDate.fromString('2000-01-01', 'yyyy-MM-dd'))
        self.ISD.ComBDate.clear()
        self.ISD.pButInsertDataIntoDB.setEnabled(False)
        self.ISD.param_row_count = 0
        self.ISD.add_input_file.clicked.disconnect()
        self.ISD.pButAdd_Param.clicked.disconnect()
        self.ISD.pButRem_Param.clicked.disconnect()
        self.ISD.pButInsertDataIntoDB.clicked.disconnect()
        self.ISD.pButContinue.clicked.disconnect()
        self.ISD.done(0)
