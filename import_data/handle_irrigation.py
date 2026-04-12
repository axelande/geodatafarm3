from psycopg2 import sql as pgsql
from qgis.PyQt.QtWidgets import QMessageBox
from datetime import datetime
# Import the code for the dialog
from ..widgets.import_irrigation_dialog import ImportIrrigationDialog
from ..support_scripts.rain_dancer import MyRainDancer
from ..support_scripts.__init__ import check_text, TR
__author__ = 'Axel Horteborn'


class IrrigationHandler:
    def __init__(self, parent_widget):
        """A widget that enables the possibility to insert data from a text
        file into a shapefile"""
        self.db = parent_widget.db
        translate = TR('IrrigationHandler')
        self.tr = translate.tr
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
        self.IIR.exec()

    def _connect(self):
        self.client_id = self.IIR.LEClientId.text()
        self.user_name = self.IIR.LEUserName.text()
        self.password = self.IIR.LEPassword.text()
        self.dancer = MyRainDancer(client=self.client_id,
                                   username=self.user_name,
                                   password=self.password)

    def create_grid_year(self):
        """Creates a 2x2 grid over all fields"""
        year = self.IIR.DECreateYear.text()
        tbl_id = pgsql.Identifier(f"irrigation_{year}")
        pkey_id = pgsql.Identifier(f"p_key_irrigation{year}")
        self.db.execute_sql(
            pgsql.SQL(
                "CREATE TABLE weather.{tbl} (field_row_id serial,"
                " polygon geometry, irrigation_mm double precision)"
            ).format(tbl=tbl_id))
        fields = self.db.execute_and_return(
            "SELECT field_name, st_astext(polygon) FROM fields")
        for field_name, polygon in fields:
            query = pgsql.SQL(
                "WITH first AS ("
                " SELECT (st_dump(makegrid_2d(st_geomfromtext(%s, 4326), 2, 2))).geom AS grid)"
                " INSERT INTO weather.{tbl} (polygon, irrigation_mm)"
                " SELECT grid, 0 FROM first"
                " WHERE st_intersects(grid, st_geomfromtext(%s, 4326))"
            ).format(tbl=tbl_id)
            self.db.execute_sql(query, params=(polygon, polygon))
        self.db.execute_sql(
            pgsql.SQL("ALTER TABLE weather.{tbl} ADD CONSTRAINT {pkey} PRIMARY KEY (field_row_id)").format(
                tbl=tbl_id, pkey=pkey_id))

    def get_grid_data(self):
        """
        Function that loops though all irrigation operations during the selected year.
        It adds the precipitation amount to each 2x2 cell that the operation "covers".
        Returns
        -------
        """
        from_date = datetime.strptime(self.IIR.CWFrom.selectedDate().toString("yyyy-MM-dd"), '%Y-%m-%d')
        to_date = datetime.strptime(self.IIR.CWTo.selectedDate().toString("yyyy-MM-dd"), '%Y-%m-%d')
        if from_date >= to_date:
            QMessageBox.information(None, "Error:",
                                    self.tr(
                                        'The "to date" must be larger than the "from date"'))
            return
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
            finished = f"{data['finished']['year']}-{data['finished']['month']}-{data['finished']['day']}"
            fin = datetime.strptime(finished, '%Y-%m-%d')
            before_start = fin - from_date
            after_last = to_date - fin
            if before_start.days < 0:
                continue
            if after_last.days < 0:
                continue
            line = (f"LINESTRING({data['destination']['lng']} {data['destination']['lat']},"
                    f" {data['origin']['lng']} {data['origin']['lat']})")
            query = pgsql.SQL(
                "UPDATE weather.{tbl} SET irrigation_mm = irrigation_mm + %s"
                " WHERE st_intersects(polygon,"
                " ST_Buffer(CAST(ST_SetSRID(ST_geomfromtext(%s), 4326) AS geography),"
                " 30, 'endcap=flat join=round')::geometry)"
            ).format(tbl=pgsql.Identifier(f"irrigation_{finished[:4]}"))
            self.db.execute_sql(query, params=(data["precipitation"], line))
