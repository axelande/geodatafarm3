from PyQt5 import QtCore
from qgis.core import QgsProject, QgsTask
import time
from ..support_scripts.__init__ import check_text
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts import shapefile as shp
__author__ = 'Axel Andersson'


class InsertInputToDB:
    def __init__(self, IH, iface, dock_widget, defined_field, tsk_mngr, db):
        """
        This class adds the data from the shapefile, created in the
        InputHandler widget, into the database
        :param InputHandler: widget
        :param iface: the qgis interface
        :param parent_widget: the docked widget
        :return:
        """
        self.db = db
        self.iface = iface
        self.IH = IH
        self.dock_widget = dock_widget
        self.defined_field = defined_field
        self.tsk_mngr = tsk_mngr
        self.CreateLayer = CreateLayer(db)

    def import_data_to_db(self, schema, convert2polygon=True, is_shp=False):
        """Imports the data into the database.
        :param schema str, what kind of data is it
        :param convert2polygon bool, is the data in the shp file already 
        polygons?
        :param is_shp bool, is the data from a shp file?
        """
        self.is_shp = is_shp
        self.schema = schema
        insert_data = InsertData()
        ##Debugg
        #insert_data.import_data_to_db('test', self.IH, self.defined_field, self.db,
        #                             schema, convert2polygon, is_shp)
        #self.end_method(1,2)
        task1 = QgsTask.fromFunction('running script', insert_data.import_data_to_db,
                                     self.IH, self.defined_field, self.db,
                                     schema, convert2polygon, is_shp,
                                     on_finished=self.end_method)
        wait_msg = 'Please wait while data is being prosecuted'
        self.tsk_mngr.addTask(task1)

    def end_method(self, result, values):
        schema = self.schema
        self.dock_widget.PBAddFieldToDB.setEnabled(False)
        if not self.is_shp:
            QgsProject.instance().removeMapLayer(
                self.IH.point_layer.id())
        for param_layer in self.IH.params_to_evaluate:
            param_layer = check_text(param_layer)
            target_field = param_layer
            layer = self.db.addPostGISLayer(str(self.IH.file_name).lower(), 'polygon', '{schema}'.format(schema=schema), check_text(param_layer.lower()))
            self.CreateLayer.create_layer_style(layer, check_text(target_field), str(self.IH.file_name).lower(), schema)
            QgsProject.instance().addMapLayer(layer)


class InsertData(QtCore.QObject):
    def __init__(self):
        self.IH = None
        self.db = None

    def import_data_to_db(self, task, IH, defined_field, db,
                                     schema, convert2polygon, is_shp):
        """Imports the data into the database.
        """
        self.IH = IH
        self.db = db
        column_types = self.IH.column_types
        heading_row = self.IH.heading_row
        params_to_eval = self.IH.params_to_evaluate
        tbl_name = str(self.IH.file_name)
        self.longitude_col = self.IH.longitude_col
        self.latitude_col = self.IH.latitude_col
        file_name_with_path = self.IH.file_name_with_path
        sql = "CREATE TABLE {schema}.temp_table (field_row_id integer PRIMARY KEY, ".format(schema=schema)
        lat_lon_inserted = False
        for i, col_name in enumerate(heading_row):
            if not lat_lon_inserted and (
                    col_name == self.longitude_col or col_name == self.latitude_col or is_shp):
                sql += "pos geometry(POINT, 4326), polygon geometry(POLYGON, 4326), "
                lat_lon_inserted = True
            if lat_lon_inserted and (
                    col_name == self.longitude_col or col_name == self.latitude_col):
                continue
            if col_name == "Date":
                sql += "Date TIMESTAMP, "
                continue
            if column_types[i] == 0:
                sql += str(col_name) + " INT, "
            if column_types[i] == 1:
                sql += str(col_name) + " REAL, "
            if column_types[i] == 2:
                sql += str(col_name) + " CHARACTER VARYING(20), "
        sql = sql[:-2]
        sql += ")"
        self.db.create_table(sql, '{schema}.temp_table'.format(schema=schema))
        if task != 1:
            task.setProgress(5)
        with shp.Reader(file_name_with_path + '.shp') as shpfile:
            # records = shpfile.records()
            shapes = shpfile.shapeRecords()
            fields = shpfile.fields
            data_dict = {"pos": [], 'field_row_id': []}
            field_names = []
            if task != 1:
                task.setProgress(25)
            for name, type, int1, int2 in fields:
                if name == 'DeletionFlag':
                    continue
                field_names.append(name)
                data_dict[name] = []
            for k, row in enumerate(shapes):
                for i, col in enumerate(row.record):
                    if col == b'                    ':
                        col = "' '"
                    elif isinstance(col, str):
                        col = "'" + col + "'"
                    data_dict[field_names[i]].append(col)
                data_dict['pos'].append(
                    "ST_PointFromText('POINT({p1} {p2})',4326 )".format(
                        p1=shapes[k].shape.points[0][0],
                        p2=shapes[k].shape.points[0][1]))
                data_dict['field_row_id'].append(k)
            cols = []
            for key in heading_row:
                cols.append(key.encode('ascii').decode('utf-8'))
            for j, name in enumerate(field_names):
                found = False
                for col in cols:
                    if col[:10] == name:
                        data_dict[col] = data_dict.pop(name)
                        found = True
                if not found:
                    #cols.remove(name) ?
                    del data_dict[name]
            key_list = list(data_dict.keys())
            sql_raw = "INSERT INTO {schema}.temp_table ({cols}) VALUES".format(schema=schema, cols=", ".join(str(e).replace("'","") for e in key_list))
            for i in range(len(data_dict['field_row_id'])):
                value = [data_dict[key][i] for key in key_list]
                sql_raw += "({vals_str}), ".format(
                    vals_str=", ".join(str(e) for e in value))
            sql = sql_raw[:-2]
            redone_param_list = []
            for param in params_to_eval:
                only_char = check_text(param)
                redone_param_list.append(only_char)
            self.db.insert_data(sql, '{schema}.temp_table'.format(schema=schema), redone_param_list)
            if defined_field is not None:
                sql = """SELECT * INTO {schema}.{tbl} 
from {schema}.temp_table
where st_intersects(pos, ST_GeomFromText('{field}',4326))""".format(schema=schema, tbl=tbl_name, field=defined_field)
            else:
                sql = """SELECT * INTO {schema}.{tbl} 
                from {schema}.temp_table""".format(schema=schema, tbl=tbl_name)
            time.sleep(0.1)
            if task != 1:
                task.setProgress(50)
            self.db.execute_sql(sql)
        if task != 1:
            task.setProgress(70)
        if convert2polygon:
            self.db.execute_sql("DROP TABLE {schema}.temp_table".format(schema=schema))

            sql = """drop table if exists {schema}.temp_tbl2;
WITH voronoi_temp2 AS (
    SELECT ST_dump(ST_VoronoiPolygons(ST_Collect(pos))) as vor
    FROM {schema}.{tbl})
SELECT (vor).path, (vor).geom into {schema}.temp_tbl2
FROM voronoi_temp2  ;
 create index temp_index on {schema}.temp_tbl2 Using gist(geom);
update {schema}.{tbl}
SET polygon = ST_Intersection(geom,ST_GeomFromText('{field}',4326))
FROM {schema}.temp_tbl2
WHERE st_intersects(pos, geom)""".format(schema=schema, tbl=tbl_name, field=defined_field)

            self.db.execute_sql(sql)
        if task != 1:
            task.setProgress(90)
        self.db.execute_sql("drop table if exists {schema}.temp_tbl2;".format(schema=schema))
        self.db.create_indexes(tbl_name, redone_param_list, schema)
        return 1
