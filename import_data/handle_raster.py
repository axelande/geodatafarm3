import gdal
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import subprocess


class ImportRaster:
    """With this module the user can add Raster data"""
    def __init__(self, parent, date_dialog, schema):
        """

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.db = parent.db
        self.tr = parent.tr
        self.date_dialog = date_dialog
        self.schema = schema
        self.parent = parent
        self.s_tbl = ''

    def run(self):
        """Check that a date is filled in, open the file explorer, preforms
        some tests that the data is ok, import it to the database, renames and
        runs some sql commands"""
        if not self.check_date():
            return
        if not self.open_input_file():
            return
        if not self.check_file():
            return
        if not self.check_if_exist():
            return
        self.run_import_command()
        self.run_sql_commands()

    def open_input_file(self):
        """Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function define_separator,
        set_sep_radio_but and set_column_list are being called."""
        filters = "Geo referenced images files (*tiff *tif)"
        self.file_name_with_path = \
            QFileDialog.getOpenFileName(None, " File dialog ", '',
                                        filters)[0]
        if self.file_name_with_path == '':
            return False
        temp_var = self.file_name_with_path.split("/")
        self.file_name = temp_var[len(temp_var) - 1][0:-4]
        self.input_file_path = self.file_name_with_path[
                               0:self.file_name_with_path.index(self.file_name)]
        return True

    def check_date(self):
        """Checks that the user have filled in a manual date

        Returns
        -------
        bool
        """
        if self.date_dialog.text() == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        return True

    def check_if_exist(self):
        """Check if there is a table with the same name, if so this function
        checks weather the user wants to replace the data in the database or
        if the user want to stop importing the file."""

        if self.db.check_table_exists(self.file_name, self.schema):
            qm = QMessageBox()
            res = qm.question(None, self.tr('Message'),
                              self.tr(
                                  "The name of the data set already exist in your database, would you like to replace it? (If not please rename the file)"),
                              qm.Yes, qm.No)
            if res == qm.No:
                return False
            else:
                self.db.execute_sql("""DROP TABLE {schema}.{tbl};
                                       DELETE FROM {schema}.manual
                                       WHERE table_ = '{tbl}';
                                       """.format(schema=self.schema,
                                                  tbl=self.file_name))
                return True

    def check_file(self):
        """Tries to open the file

        Returns
        -------
        bool
        """
        ds = gdal.Open(self.file_name_with_path)
        if ds is None:
            QMessageBox.information(None, self.tr('Error'),
                                    self.tr('Unable to open the raster file.'))
            return False
        else:
            return True

    def run_import_command(self):
        """Imports the raster to the database"""
        self.s_tbl = "{schema}.{file_name}".format(file_name=self.file_name,
                                                   schema=self.schema)
        run_text = """gdal_polygonize.bat {file_w_path} -f PostgreSQL PG:"host='{host}' port='{port}' dbname='{dbname}' user='{username}' password='{password}'" {s_tbl}
            """.format(host=self.db.dbhost, port=self.db.dbport,
                       dbname=self.db.dbname, username=self.db.dbuser,
                       password=self.db.dbpass, s_tbl=self.s_tbl,
                       file_w_path=self.file_name_with_path)
        run = subprocess.Popen(run_text)
        run.wait()

    def run_sql_commands(self):
        """Changes the names of some columns and change the srid to 4326, adds
        the column pos as the centroid of the polygon"""
        sql = """ALTER TABLE {s_tbl} 
              RENAME COLUMN ogc_fid TO field_row_id""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        sql = """ALTER TABLE {s_tbl} 
              RENAME COLUMN wkb_geometry TO poly""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        srid = self.db.execute_and_return("""select st_srid(poly) 
                                          from {s_tbl} limit 1
                                          """.format(s_tbl=self.s_tbl))[0][0]
        sql = """ALTER TABLE {s_tbl}
        ALTER COLUMN poly TYPE geometry(POLYGON, 4326) 
          USING ST_Transform(ST_SetSRID(poly,{srid}),4326);
        """.format(s_tbl=self.s_tbl, srid=srid)
        self.db.execute_sql(sql)
        sql = """ALTER TABLE {s_tbl}
        ADD pos geometry(POINT, 4326);""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        sql = """UPDATE {s_tbl} 
        SET pos=st_centroid(poly)""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)


