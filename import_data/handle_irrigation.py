from PyQt5.QtWidgets import QMessageBox
# Import the code for the dialog
from ..widgets.import_irrigation_dialog import ImportIrrigationDialog
from ..support_scripts.rain_dancer import MyRainDancer

__author__ = 'Axel Andersson'


class IrrigationHandler:
    def __init__(self, parent_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.DB = parent_widget.DB
        self.tr = parent_widget.tr
        self.col_types = None
        self.add_to_Param_row_count = 0
        self.params_to_evaluate = []
        self.combo = []
        self.col_types = []
        self.col_names = []
        # Create the dialog (after translation) and keep reference
        #self.ISD = ImportShpDialog()
        self.client_id = 0
        self.user_name = ''
        self.password = ''
        self.IIR = ImportIrrigationDialog()

    def run(self):
        self.IIR.show()
        self.IIR.PBAddRaindancer.clicked.connect(self.insert_data_from_raindancer)
        self.IIR.exec_()

    def insert_data_from_raindancer(self):
        try:
            self.client_id = int(self.IIR.LEClientId.text())
        except ValueError:
            QMessageBox.information(None, "Error:",
                                    self.tr("ClintID must be a number"))
            return
        self.user_name = self.IIR.LEUserName.text()
        self.password = self.IIR.LEPassword.text()
        if not self.find_operation_table():
            self.reset_tables()
        self.insert_operation_data()
        #self.update_total_irrigation()

    def _connect(self):
        self.dancer = MyRainDancer(client=self.client_id,
                                   username=self.user_name,
                                   password=self.password)

    def find_operation_table(self):
        if not hasattr(self, 'dancer'):
            self._connect()
        try:
            test_data = self.DB.execute_and_return(sql="select * from weather.raindancer_operation limit 1")
            return True
        except:
            return False

    def reset_tables(self):
        self.DB.execute_sql("drop table if exists weather.raindancer_operation; Create table weather.raindancer_operation(field_row_id SERIAL, polygon GEOMETRY, precipitation REAL, date_irrigation TIMESTAMP )")
        #self.DB.execute_sql("drop table if exists weather.raindancer_total; Create table weather.raindancer_total(row_id SERIAL, polygon GEOMETRY, precipitation REAL)")

    def update_total_irrigation(self):
        operations = self.DB.execute_and_return("select * from weather.raindancer_operation where date_irrigation::date>'2018-01-01'")
        for row_id, geom, percept, dat in operations:
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
        if not hasattr(self, 'dancer'):
            self._connect()
        operations = self.dancer.get_operation_data()
        if operations == 'Failed':
            QMessageBox.information(None, "Error:",
                                    self.tr("Wasn't able to fetch data from raindancer.\nAre you sure that id, username and password was correct?"))
            return
        for data in operations:
            if data['finished'] is None:
                continue
            finished = f"""{data['finished']['year']}-{data['finished']['month']}-{data['finished']['day']} {data['finished']['hour']}:{data['finished']['minute']}:{data['finished']['second']}"""
            line = 'LINESTRING({long1} {lat1}, {long2} {lat2})'.format(long1=data["destination"]["lng"], lat1=data["destination"]["lat"], long2=data["origin"]["lng"], lat2=data["origin"]["lat"])
            sql="""INSERT INTO weather.raindancer_operation(polygon, precipitation, date_irrigation) 
            select ST_Buffer(CAST(ST_SetSRID(ST_geomfromtext('{line}'),4326) AS geography),30, 'endcap=flat join=round')::geometry, {p}, '{d}'
            """.format(line=line, p=data["precipitation"], d=finished)
            self.DB.execute_sql(sql)
