import os
import gdal
from osgeo import osr
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from functools import partial
import subprocess
from qgis.core import (QgsTask, QgsProcessingAlgRunnerTask, QgsApplication,
                       QgsProcessingContext,
                       QgsMessageLog, Qgis)
from ..support_scripts.create_layer import CreateLayer
from ..support_scripts.__init__ import TR

MESSAGE_CATEGORY = 'AlgRunnerTask'


class ImportRaster:
    """With this module the user can add Raster data"""
    def __init__(self, parent, date_dialog, field_dialog, schema):
        """

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.db = parent.db
        translate = TR('ImportRaster')
        self.tr = translate.tr
        self.tsk_mngr = parent.tsk_mngr
        self.plugin_dir = parent.plugin_dir
        self.date_dialog = date_dialog
        self.field_dialog = field_dialog
        self.schema = schema
        self.parent = parent
        self.s_tbl = ''
        self.file_name = ''
        self.file_name_with_path = ''

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
        if self.db.check_table_exists(self.file_name, self.schema):
            return
        self.run_import_command()

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
        self.file_name = self.file_name.lower()
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
        """Adds the polygonize script to a QgsTask"""
        self.s_tbl = "{schema}.{file_name}".format(file_name=self.file_name,
                                                   schema=self.schema)
        input_ = self.file_name_with_path
        params = {'INPUT': input_, 'BAND': 1, 'OUTPUT': self.plugin_dir + '/temp.shp',
                  'FIELD': 'raster_value'}
        alg = QgsApplication.processingRegistry().algorithmById(
                                      u'gdal:polygonize')
        d = gdal.Open(input_)
        proj = osr.SpatialReference(wkt=d.GetProjection())
        self.epsg = proj.GetAttrValue('AUTHORITY', 1)
        context = QgsProcessingContext()
        task = QgsProcessingAlgRunnerTask(alg, params, context)
        task.executed.connect(partial(self.task_finished, context))
        self.tsk_mngr.addTask(task)

    def task_finished(self, context, successful, results):
        """Function that is called after polygonize is complete, starts the next
        task with importing the data to the database,

        Parameters
        ----------
        context: QgsProcessingContext
        successful: bool
        results: Unused

        Returns
        -------

        """
        if not successful:
            QgsMessageLog.logMessage('Task finished unsucessfully',
                                     MESSAGE_CATEGORY, Qgis.Warning)
        else:
            #task = QgsTask.fromFunction('Importing data to storage',
            #                            self.import_to_db,
            #                            on_finished=self.run_sql_commands)
            #self.tsk_mngr.addTask(task)
            from ..import_data.handle_input_shp_data import InputShpHandler
            ish = InputShpHandler(self.parent, schema=self.schema, spec_columns=[])
            ish.tbl_name = self.file_name
            ish.col_names = ['raster_val']
            ish.col_types = [1]
            ish.file_name_with_path = self.plugin_dir + '/temp.shp'
            ish.ISD.EPSG.setText(self.epsg)
            ish.field = self.field_dialog.currentText()
            ish.params_to_evaluate = ['raster_val']
            res = ish.import_data('debug', date_dict={'simple_date': self.date_dialog.text()})
            # print(res)

    def import_to_db(self, task):
        """Imports the shapefile with a ogr2ogr command in a shell script

        Parameters
        ----------
        task: QgsTask

        Returns
        -------
        bool
        """
        cmd = """ogr2ogr -f PostgreSQL PG:"host='{host}' port='{port}' dbname='{dbname}' user='{username}' password='{password}'" "{shp_path}" -nln {s_tbl}""".format(host=self.db.dbhost, port=self.db.dbport,
                               dbname=self.db.dbname, username=self.db.dbuser,
                               password=self.db.dbpass, s_tbl=self.s_tbl,
                               shp_path=self.plugin_dir + '/temp.shp')
        res = subprocess.call(cmd, shell=True)
        if res == 0:
            return True
        else:
            return False

    def run_sql_commands(self, result, values):
        """Changes the names of some columns and change the srid to 4326, adds
        the column pos as the centroid of the polygon"""
        sql = """ALTER TABLE {s_tbl} 
              RENAME COLUMN ogc_fid TO field_row_id""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        sql = """ALTER TABLE {s_tbl} 
              RENAME COLUMN wkb_geometry TO polygon""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        srid = self.db.execute_and_return("""select st_srid(polygon) 
                                          from {s_tbl} limit 1
                                          """.format(s_tbl=self.s_tbl))[0][0]
        sql = """ALTER TABLE {s_tbl}
        ALTER COLUMN polygon TYPE geometry(POLYGON, 4326) 
          USING ST_Transform(ST_SetSRID(polygon,{srid}),4326);
        """.format(s_tbl=self.s_tbl, srid=srid)
        self.db.execute_sql(sql)
        sql = """ALTER TABLE {s_tbl}
        ADD pos geometry(POINT, 4326);""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        sql = """UPDATE {s_tbl} 
        SET pos=st_centroid(polygon)""".format(s_tbl=self.s_tbl)
        self.db.execute_sql(sql)
        cols = self.db.get_all_columns(self.file_name, self.schema,
                                       "'field_row_id', 'pos', 'polygon', 'cmin', 'cmax', 'xmin', 'xmax', 'ctid', 'tableoid'")
        cols_to_add = []
        for col in cols:
            col_ = col[0]
            cols_to_add.append(col_)
        self.db.create_indexes(self.file_name, cols_to_add, self.schema,
                               primary_key=False)
        layer = self.db.add_postgis_layer(self.file_name, 'polygon',
                                          self.schema)
        create_layer = CreateLayer(self.db)
        create_layer.create_layer_style(layer, 'raster_val', self.file_name,
                                        self.schema)
        os.remove(self.plugin_dir + '/temp.shp')
        os.remove(self.plugin_dir + '/temp.shx')
        os.remove(self.plugin_dir + '/temp.dbf')
        os.remove(self.plugin_dir + '/temp.prj')
