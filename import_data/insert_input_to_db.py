from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from qgis.core import QgsProject
import time
from widgets.waiting import Waiting
from support_scripts.__init__ import check_text
from support_scripts.create_layer import CreateLayer
import support_scripts.shapefile as shp
__author__ = 'Axel Andersson'


class InsertInputToDB:
    def __init__(self, IH, iface, dock_widget, defined_field, db):
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
        self.CreateLayer = CreateLayer(db)

    def import_data_to_db(self, schema, convert2polygon=True, is_shp=False):
        """Imports the data into the database.
        :param schema str, what kind of data is it
        :param convert2polygon bool, is the data in the shp file already 
        polygons?
        :param is_shp bool, is the data from a shp file?
        """
        #TODO: fix the treading!
        self.is_shp = is_shp
        self.schema = schema
        self.idata = InsertData(self.IH, self.defined_field, self.db, schema, convert2polygon, is_shp)
        worker_thread_work = QThread()
        self.idata.moveToThread(worker_thread_work)
        worker_thread_work.started.connect(self.idata.import_data_to_db)
        worker_thread_work.start()
        waiting_thread = QThread()
        waiting_thread.start()
        wait_msg = 'Please wait while data is being prosecuted'
        self.wait = Waiting(wait_msg)
        self.wait.moveToThread(waiting_thread)
        self.wait.start.connect(self.wait.start_work)
        self.wait.start.emit('run')
        while not self.idata.finish:
            time.sleep(1)
        self.end_method()

    def end_method(self):
        schema = self.schema
        self.dock_widget.PBAddFieldToDB.setEnabled(False)
        if not self.is_shp:
            QgsProject.instance().removeMapLayer(
                self.IH.point_layer.id())

        for param_layer in self.idata.redone_param_list:
            target_field = param_layer
            layer = self.db.addPostGISLayer(self.idata.tbl_name.lower(), 'polygon', '{schema}'.format(schema=schema), check_text(param_layer.lower()))
            self.CreateLayer.create_layer_style(layer, check_text(target_field), self.idata.tbl_name.lower(), schema)
            QgsProject.instance().addMapLayer(layer)
        self.wait.stop_work()


class InsertData(QtCore.QObject):
    signalStatus = pyqtSignal(str)

    def __init__(self, IH, defined_field, db, schema, convert2polygon, is_shp, *args, **kwargs):
        QtCore.QObject.__init__(self, *args, **kwargs)
        self.IH = IH
        self.defined_field = defined_field
        self.db = db
        self.schema = schema
        self.convert2polygon = convert2polygon
        self.is_shp = is_shp
        self.finish = False

    def import_data_to_db(self):
        """Imports the data into the database.
        """
        schema = self.schema
        convert2polygon = self.convert2polygon
        is_shp = self.is_shp
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
        with shp.Reader(file_name_with_path + '.shp') as shpfile:
            records = shpfile.records()
            shapes = shpfile.shapeRecords()
            fields = shpfile.fields
            data_dict = {"pos": [], 'field_row_id': []}
            field_names = []
            for name, type, int1, int2 in fields:
                if name == 'DeletionFlag':
                    continue
                field_names.append(name)
                data_dict[name] = []
            for k, row in enumerate(records):
                for i, col in enumerate(row):
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
                cols.append(key.encode('ascii'))
            for j, name in enumerate(field_names):
                found = False
                for col in cols:
                    if col[:10] == name:
                        data_dict[col] = data_dict.pop(name)
                        found = True
                if not found:
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
            if self.defined_field is not None:
                field_coord = str(self.defined_field)[1:-1].replace(',',' ').replace(')  (', ',')
                sql = """SELECT * INTO {schema}.{tbl} 
from {schema}.temp_table
where st_intersects(pos, ST_GeomFromText('POLYGON({field})',4326))""".format(schema=schema, tbl=tbl_name, field=field_coord)
            else:
                sql = """SELECT * INTO {schema}.{tbl} 
                from {schema}.temp_table""".format(schema=schema, tbl=tbl_name)
            time.sleep(0.1)
            self.db.execute_sql(sql)
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
SET polygon = ST_Intersection(geom,ST_GeomFromText('POLYGON({field})',4326))
FROM {schema}.temp_tbl2
WHERE st_intersects(pos, geom)""".format(schema=schema, tbl=tbl_name, field=field_coord)
            self.db.execute_sql(sql)
        self.db.execute_sql("drop table if exists {schema}.temp_tbl2;".format(schema=schema))
        self.db.create_indexes(tbl_name, redone_param_list, schema)
        self.redone_param_list = redone_param_list
        self.tbl_name = tbl_name
        self.finish = True