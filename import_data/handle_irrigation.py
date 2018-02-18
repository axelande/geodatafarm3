#from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
#from PyQt4.QtGui import QMessageBox
import os
# Import the code for the dialog
#from widgets.import_shp_dialog import ImportShpDialog
from support_scripts.rain_dancer import MyRainDancer
#from test.test_db_con import DB
#from database_scripts.db import DB
#from support_scripts.create_layer import CreateLayer
__author__ = 'Axel Andersson'


class IrrigationHandler:
    def __init__(self):#, iface, parent_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        #self.iface = iface
        self.DB = DB()
        self.DB.get_conn()
        self.col_types = None
        self.add_to_Param_row_count = 0
        self.params_to_evaluate = []
        self.combo = []
        self.col_types = []
        self.col_names = []
        # Create the dialog (after translation) and keep reference
        #self.ISD = ImportShpDialog()
        self.client_id = 160003
        self.user_name = 'axel'
        self.password = 'axelaxel'

    def run(self):
        self._connect()
        if not self.find_operation_table():
            self.create_operation_table()
        self.insert_operation_data()

    def _connect(self):
        self.dancer = MyRainDancer(client=self.client_id, username=self.user_name, password=self.password)

    def find_operation_table(self):
        try:
            test_data = self.DB.execute_and_return(sql="select * from weather.raindancer_operation limit 1")
            return True
        except:
            return False

    def reset_tables(self):
        #self.DB.execute_sql("drop table if exists weather.raindancer_operation; Create table weather.raindancer_operation(field_row_id SERIAL, polygon GEOMETRY, precipitation REAL)")
        self.DB.execute_sql("drop table if exists weather.raindancer_total; Create table weather.raindancer_total(row_id SERIAL, polygon GEOMETRY, precipitation REAL)")

    def update_total_irrigation(self):

        operations = self.DB.execute_and_return("select * from weather.raindancer_operation")
        for row_id, geom, percept in operations:
            print(row_id)
            sql= """select row_id, precipitation, st_intersection(polygon, st_buffer('{g}',0.000001)) as inter_geom
            from weather.raindancer_total
            where not ST_IsEmpty(st_intersection(polygon,st_buffer('{g}',0.000001)))""".format(g=geom)
            try:
                intersections = self.DB.execute_and_return(sql)
            except:
                print('intersection Error:' + str(self.DB.execute_and_return("select st_astext('{g}')".format(g=geom))[0]))
                continue
            if len(intersections) == 0:
                sql = """Insert into weather.raindancer_total(polygon,precipitation) VALUES ('{g}', {p})
                """.format(g=geom, p=percept)
                self.DB.execute_sql(sql)
            else:
                for row_id2, precipitation, inter_geom in intersections:
                    sql = """UPDATE weather.raindancer_total t
                    SET polygon = st_difference(t.polygon, '{g}')
                    WHERE row_id = {r}""".format(g=inter_geom, r=row_id2)
                    self.DB.execute_sql(sql)
                    new_p = precipitation + percept
                    sql = """Insert into weather.raindancer_total(polygon, precipitation) Values('{g}', {p})
                    """.format(g=inter_geom, p=new_p)
                    self.DB.execute_sql(sql)
                try:
                    sql = """Insert into weather.raindancer_total(polygon, precipitation) Values(st_difference('{ng}', (select st_union(polygon) from weather.raindancer_total)), {p})
                                        """.format(ng=geom, g=inter_geom, p=percept)
                    self.DB.execute_sql(sql)
                except:
                    pass
                a=1

    def insert_operation_data(self):
        operations = self.dancer.get_operation_data()
        for data in operations:
            line = 'LINESTRING({long1} {lat1}, {long2} {lat2})'.format(long1=data["destination"]["lng"], lat1=data["destination"]["lat"], long2=data["origin"]["lng"], lat2=data["origin"]["lat"])
            sql="""INSERT INTO weather.raindancer_operation(polygon, precipitation) 
            select ST_Buffer(CAST(ST_SetSRID(ST_geomfromtext('{line}'),4326) AS geography),30, 'endcap=flat join=round')::geometry, {d}
            """.format(line=line, d=data["precipitation"])
            print(sql)
            self.DB.execute_sql(sql)

if __name__ == "__main__":
    r = IrrigationHandler()
    r.reset_tables()
    #r.insert_operation_data()
    r.update_total_irrigation()
