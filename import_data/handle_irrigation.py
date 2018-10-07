from PyQt5.QtWidgets import QMessageBox
# Import the code for the dialog
from ..widgets.import_irrigation_dialog import ImportIrrigationDialog
from ..support_scripts.rain_dancer import MyRainDancer
from ..support_scripts.__init__ import check_text
__author__ = 'Axel Hörteborn'


class IrrigationHandler:
    def __init__(self, parent_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.db = parent_widget.db
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
        self.IIR.PBCreateYear.clicked.connect(self.create_grid_year)
        self.IIR.PBGetData.clicked.connect(self.get_grid_data)
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
        self.client_id = self.IIR.LEClientId.text()
        self.user_name = self.IIR.LEUserName.text()
        self.password = self.IIR.LEPassword.text()
        self.dancer = MyRainDancer(client=self.client_id,
                                   username=self.user_name,
                                   password=self.password)

    def find_operation_table(self):
        if not hasattr(self, 'dancer'):
            self._connect()
        try:
            test_data = self.db.execute_and_return(sql="select * from weather.raindancer_operation limit 1")
            return True
        except:
            return False

    def create_grid_year(self):
        """Creates a 2x2 grid over all fields"""
        sql = """create table weather.irrigation_{year} (row_id serial, 
                                                         polygon geometry, 
                                                         precipitation double precision)
              """.format(year=self.IIR.DECreateYear.text())
        #self.db.execute_sql(sql)
        sql = "select field_name, st_astext(polygon) from fields"
        fields = self.db.execute_and_return(sql)
        for field_name, polygon in fields:
            sql = """with first as(select (st_dump(makegrid_2d(st_geomfromtext('{polygon}', 4326), 2, 2))).geom as grid)
            insert into weather.irrigation_{year} (polygon, precipitation)
            select grid, 0 
            from first where st_intersects(grid, st_geomfromtext('{polygon}', 4326))
            """.format(polygon=polygon, field=check_text(field_name), year=self.IIR.DECreateYear.text())
            self.db.execute_sql(sql)
        self.db.execute_sql("""ALTER TABLE weather.irrigation_{year}
    ADD CONSTRAINT p_key_irrigation{year} PRIMARY KEY (row_id);""")

    def get_grid_data(self):
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
            if finished < '{year}-01-01'.format(year=self.IIR.DECreateYear.text()):
                continue
            if finished > '{year}-01-01'.format(year=int(self.IIR.DECreateYear.text()) + 1):
                continue
            line = 'LINESTRING({long1} {lat1}, {long2} {lat2})'.format(long1=data["destination"]["lng"], lat1=data["destination"]["lat"], long2=data["origin"]["lng"], lat2=data["origin"]["lat"])
            sql = """Update weather.irrigation_{year}
            set precipitation = precipitation + {p}
            where st_intersects(polygon, ST_Buffer(CAST(ST_SetSRID(ST_geomfromtext('{line}'),4326) AS geography),
                                                  30, 'endcap=flat join=round')::geometry)
            """.format(line=line, p=data["precipitation"], year=self.IIR.DECreateYear.text())#, d=finished)
            self.db.execute_sql(sql)
            print('inserted')

    def reset_tables(self):
        pass
        #self.db.execute_sql("drop table if exists weather.raindancer_operation; Create table weather.raindancer_operation(field_row_id SERIAL, polygon GEOMETRY, precipitation REAL, date_irrigation TIMESTAMP )")
        #self.db.execute_sql("drop table if exists weather.raindancer_total; Create table weather.raindancer_total(row_id SERIAL, polygon GEOMETRY, precipitation REAL)")

    def update_total_irrigation(self):
        operations = self.db.execute_and_return("select * from weather.raindancer_operation where date_irrigation::date>'2018-01-01'")
        for row_id, geom, percept, dat in operations:
            print(row_id)
            sql= """select row_id, precipitation, st_intersection(polygon, st_buffer('{g}',0.000001)) as inter_geom
            from weather.raindancer_total
            where not ST_IsEmpty(st_intersection(polygon,st_buffer('{g}',0.000001)))""".format(g=geom)
            try:
                intersections = self.db.execute_and_return(sql)
            except:
                print('intersection Error:' + str(self.db.execute_and_return("select st_astext('{g}')".format(g=geom))[0]))
                continue
            if len(intersections) == 0:
                sql = """Insert into weather.raindancer_total(polygon,precipitation) VALUES ('{g}', {p})
                """.format(g=geom, p=percept)
                self.db.execute_sql(sql)
            else:
                for row_id2, precipitation, inter_geom in intersections:
                    sql = """UPDATE weather.raindancer_total t
                    SET polygon = st_difference(t.polygon, '{g}')
                    WHERE row_id = {r}""".format(g=inter_geom, r=row_id2)
                    self.db.execute_sql(sql)
                    new_p = precipitation + percept
                    sql = """Insert into weather.raindancer_total(polygon, precipitation) Values('{g}', {p})
                    """.format(g=inter_geom, p=new_p)
                    self.db.execute_sql(sql)
                try:
                    sql = """Insert into weather.raindancer_total(polygon, precipitation) Values(st_difference('{ng}', (select st_union(polygon) from weather.raindancer_total)), {p})
                                        """.format(ng=geom, g=inter_geom, p=percept)
                    self.db.execute_sql(sql)
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
            if finished < '2018-06-01':
                continue
            line = 'LINESTRING({long1} {lat1}, {long2} {lat2})'.format(long1=data["destination"]["lng"], lat1=data["destination"]["lat"], long2=data["origin"]["lng"], lat2=data["origin"]["lat"])
            sql="""INSERT INTO weather.raindancer_operation(polygon, precipitation, date_irrigation) 
            select ST_Buffer(CAST(ST_SetSRID(ST_geomfromtext('{line}'),4326) AS geography),30, 'endcap=flat join=round')::geometry, {p}, '{d}'
            """.format(line=line, p=data["precipitation"], d=finished)
            self.db.execute_sql(sql)