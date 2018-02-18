import support_scripts.shapefile as shp
from support_scripts.__init__ import check_text
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSignal, QThread, QObject, pyqtSlot
from qgis.core import QgsMapLayerRegistry
from support_scripts.create_layer import CreateLayer
from widgets.waiting import Waiting
import time
__author__ = 'Axel Andersson'


class InsertHarvestData:
    def __init__(self, IH, iface, dock_widget, polygon, db, tr):
        self.IH = IH
        self.iface = iface
        self.dock_widget = dock_widget
        self.polygon = polygon
        self.db = db
        self.CreateLayer = CreateLayer(db)
        self.tr = tr

    def insert_to_db(self):
        self.waiting_thread = QThread()
        self.waiting_thread.start()
        wait_msg = 'Please wait while data is being prosecuted'
        self.wait = Waiting(wait_msg)
        self.wait.moveToThread(self.waiting_thread)
        self.worker2 = InsertHarvestToDB(self.IH, self.iface,
                                         self.polygon, self.db)
        #self.worker2.insert_to_db()
        self.worker_thread_work = QThread()
        self.worker_thread_work.start()
        time.sleep(1)
        self.worker2.moveToThread(self.worker_thread_work)
        self.worker2.starts.connect(self.worker2.insert_to_db)
        self.worker2.starts.emit('run')
        self.wait.start.connect(self.wait.start_work)
        self.wait.start.emit('run')
        self.dock_widget.PBAddFieldToDB.setEnabled(False)
        while not self.worker2.finished:
            time.sleep(1)
        self.CreateLayer.create_layer_style(self.worker2.layer,
                                            check_text(self.worker2.harvest_yield_col),
                                            self.worker2.tbl_name.lower(), 'harvest')
        QgsMapLayerRegistry.instance().addMapLayer(self.worker2.layer)
        QgsMapLayerRegistry.instance().removeMapLayer(self.IH.input_layer.id())
        self.wait.stop_work()



class InsertHarvestToDB(QObject):
    signalStatus = pyqtSignal(str)

    def __init__(self, IH, iface, polygon, db):
        super(InsertHarvestToDB, self).__init__()
        """
        This class adds the data from the shapefile, created in the
        IH widget, into the database
        :param IH: widget
        :param iface: the qgis interface
        :param parent_widget: the docked widget
        :return:
        """

        self.DB = db
        self.iface = iface
        self.IH = IH
        self.finished = False
        self.defined_field = polygon

    starts = pyqtSignal(str)
    @QtCore.pyqtSlot()
    def insert_to_db(self):
        """
        Insert the data into the database, gathering all necessary data from
        "self".
        :return:
        """
        columns_to_add = self.IH.columns_to_add
        column_types = self.IH.column_types
        heading_row = self.IH.heading_row
        tbl_name = self.IH.file_name
        harvest_yield_col = str(self.IH.params_to_evaluate[0])
        print(str(self.IH.params_to_evaluate[0]))
        self.longitude_col = self.IH.longitude_col
        self.latitude_col = self.IH.latitude_col
        if self.defined_field ==  None:
            sql = "CREATE TABLE harvest.{tbl}(field_row_id integer PRIMARY KEY, ".format(tbl=tbl_name)
        else:
            sql = "CREATE TABLE harvest.temp_table (field_row_id integer PRIMARY KEY, "
        lat_lon_inserted = False
        lat_lon_col_number = []
        for i, key in enumerate(columns_to_add.keys()):
            if not lat_lon_inserted and (key == self.longitude_col or key == self.latitude_col):
                sql += "pos geometry(POINT,4326), "
                lat_lon_inserted = True
            if column_types[heading_row.index(key)] == 0:
                sql += str(check_text(key)) + " INT, "
            if column_types[heading_row.index(key)] == 1:
                if key == self.longitude_col or key == self.latitude_col:
                    lat_lon_col_number.append(i)
                    continue
                else:
                    sql += str(check_text(key)) + " REAL, "
            if column_types[heading_row.index(key)] == 2:
                sql += str(check_text(key)) + " CHARACTER VARYING(20), "
        sql = sql[:-2]
        sql += ")"
        if self.defined_field is None:
            self.DB.create_table(sql, 'harvest.' + tbl_name)
        else:
            self.DB.create_table(sql, 'harvest.temp_table')
        with shp.Reader(self.IH.input_file_path + "shapefiles/" + self.IH.file_name + '.shp') as shpfile:
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
                        col = "'" + check_text(col) + "'"
                    data_dict[field_names[i]].append(col)
                data_dict['pos'].append("ST_PointFromText('POINT({p1} {p2})',4326 )".format(p1=shapes[k].shape.points[0][0], p2=shapes[k].shape.points[0][1]))
                data_dict['field_row_id'].append(k)
            cols = []
            for key in columns_to_add.keys():
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
            for i in range(0, len(data_dict['field_row_id']), 10000):
                if self.defined_field is None:
                    sql_raw = "INSERT INTO harvest.{tbl} ({cols}) VALUES".format(tbl=tbl_name, cols=", ".join(str(e).replace("'","") for e in key_list))
                else:
                    sql_raw = "INSERT INTO harvest.temp_table ({cols}) VALUES".format(cols=", ".join(str(e).replace("'","") for e in key_list))
                for j in range(0, 10000):
                    if (i+j+1) > len(data_dict['field_row_id']):
                        break
                    value = [data_dict[key][i + j] for key in key_list]
                    sql_raw += "({vals_str}), ".format(vals_str=", ".join(str(e) for e in value))
                sql = sql_raw[:-2]
                if self.defined_field is None:
                    self.DB.execute_sql(sql)
                else:
                    self.DB.execute_sql(sql)
        if self.defined_field is not None:
            coord = str(self.defined_field)[1:-1].replace(',', ' ').replace(')  (', ',')
            sql = """DROP TABLE IF EXISTS harvest.{tbl};
SELECT * INTO harvest.{tbl} 
FROM harvest.temp_table 
WHERE st_intersects(pos, ST_GeomFromText('POLYGON({coord})',4326))""".format(
                tbl=tbl_name, coord=coord)
            time.sleep(0.1)
            self.DB.execute_sql(sql)
            self.DB.execute_sql("DROP TABLE harvest.temp_table")
        self.DB.create_indexes(tbl_name.lower(), params_to_eval=[check_text(harvest_yield_col)], schema='harvest')
        self.layer = self.DB.addPostGISLayer(tbl_name.lower(), 'pos', 'harvest', 'harvest')
        self.harvest_yield_col = harvest_yield_col
        self.tbl_name = tbl_name
        self.finished = True
