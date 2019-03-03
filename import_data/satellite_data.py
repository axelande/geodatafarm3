import webbrowser
import os
import shutil
from zipfile import ZipFile
import numpy as np
from osgeo import gdal
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QVBoxLayout, QPushButton
from PyQt5.QtCore import QVariant
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsGeometry,
                       QgsFeature,QgsProcessingFeedback, QgsRasterBandStats,
                       QgsExpression, QgsField)
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator, QgsZonalStatistics
import processing
from ..support_scripts import check_text
from ..import_data.handle_input_shp_data import InputShpHandler


class SatelliteData:
    def __init__(self, parent):
        self.parent = parent
        self.dlg = parent.dock_widget
        self.tr = parent.tr
        self.path = ''
        self.canvas = None
        self.show_calender = False
        self.y_values = []
        self.x_values = []
        self.rarray = []
        self.graph_area = QVBoxLayout(self.dlg.QWGraphArea)
        self.connect_buttons = False

    def set_widget_connections(self):
        """A simple function that sets the buttons on the satellite tab"""
        if self.connect_buttons:
            return
        self.dlg.PBListCropstat.clicked.connect(
            lambda: webbrowser.open('http://www.cropsat.se'))
        self.dlg.PBListEOBrowser.clicked.connect(
            lambda: webbrowser.open('https://apps.sentinel-hub.com/eo-browser/'))
        self.dlg.PBListGeoDataFarm.clicked.connect(
            lambda: webbrowser.open('http://www.geodatafarm.com'))
        self.dlg.CheckBPlanned.clicked.connect(self.change_calender_status)
        self.dlg.PBSelectZipFile.clicked.connect(self.select_zip_file)
        self.dlg.PBUpdateFieldList.clicked.connect(self.update_field_list)
        self.dlg.PBGenerateGuideFile.clicked.connect(self.generate_guide_file)
        self.dlg.PBUpdateGraph.clicked.connect(self.update_graph)
        self.connect_buttons = True

    def change_calender_status(self):
        """Changes the calender to either enable or disable"""
        if self.show_calender:
            self.dlg.CWPlannedDate.setEnabled(False)
            self.show_calender = False
        else:
            self.dlg.CWPlannedDate.setEnabled(True)
            self.show_calender = True

    def open_input_file(self):
        """Open the file dialog and let the user choose which file that should
        be inserted. In the end of this function the function define_separator,
        set_sep_radio_but and set_column_list are being called."""
        filters = "Text files (*.zip)"
        archive_file = QFileDialog.getOpenFileName(None, " File dialog ", '',
                                                   filters)[0]
        if archive_file == '':
            return
        path = archive_file[:archive_file.index(archive_file.split('/')[-1])]
        self.path = path + 'tmp_files123/'
        new_dir = path + 'tmp_files123/'
        band4 = band8 = None
        zf = ZipFile(archive_file, "r")
        zf.extractall(new_dir)
        for name in zf.namelist():
            if "B04.tiff" in name:
                name = new_dir + name
                date = name.split(",")[0].split("/")[-1]
                band = QgsRasterLayer(name, 'band4')
                band4 = self.crop_image(band, 'band4')
            elif "B08.tiff" in name:
                name = new_dir + name
                date = name.split(",")[0].split("/")[-1]
                band = QgsRasterLayer(name, 'band8')
                band8 = self.crop_image(band, 'band8')
        return band4, band8

    def select_zip_file(self):
        """Calls to open the input file and runs the base calculation on band 4
        and band 8, when the base calculation have finished, the text and the
        graph is upadted, and the last push buttons is enabled."""
        band4, band8 = self.open_input_file()
        if band4 is None or band8 is None:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'Either is raster band 4 or 8 missing from the ZIP file.'))
            return
        self.do_base_calculation(band4, band8)
        self.update_texts()
        self.dlg.PBUpdateGraph.setEnabled(True)
        self.dlg.PBGenerateGuideFile.setEnabled(True)
        self.update_graph()

    def crop_image(self, raster_layer, name):
        """Crops the raster image to the field

        Parameters
        ----------
        raster_layer: QgsRasterLayer
            The raster layer
        name: str,
            needs the name of the raster in order to create the QgsRasterLayer

        Returns
        -------
        QgsRasterLayer
        """
        field_name = self.dlg.CBFieldList.currentText()
        field_wkt = self.parent.db.execute_and_return("select st_astext(polygon) from fields where field_name ='{name}'".format(name=field_name))[0][0]
        field_vector = QgsGeometry.fromWkt(field_wkt)
        mask_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "temp_field", "memory")
        pr = mask_layer.dataProvider()
        fet = QgsFeature()
        fet.setGeometry(field_vector)
        pr.addFeatures([fet])
        mask_layer.updateExtents()
        alg_name = 'gdal:cliprasterbymasklayer'
        #self.file_name_with_path = self.file_name_with_path.replace('/','\\')
        params = {'INPUT': raster_layer,
                  'MASK': mask_layer,
                  'NODATA': 255.0,
                  'ALPHA_BAND': False,
                  'CROP_TO_CUTLINE': True,
                  'KEEP_RESOLUTION': True,
                  'OPTIONS': 'COMPRESS=LZW',
                  'DATA_TYPE': 0,  # Byte
                  'OUTPUT': self.path + name + "clipped.tif",
                  }
        processing.run(alg_name, params)
        return QgsRasterLayer(self.path + name + "clipped.tif", name)

    def do_base_calculation(self, band4, band8):
        """Calculates either the NDVI or MSAVI2 index, based on band 4 and 8

        Parameters
        ----------
        band4: QgsRasterLayer
        band8: QgsRasterLayer

        Returns
        -------

        """
        entries = []
        ras4 = QgsRasterCalculatorEntry()
        ras4.ref = 'ras@4'
        ras4.raster = band4
        ras4.bandNumber = 1
        entries.append(ras4)

        ras8 = QgsRasterCalculatorEntry()
        ras8.ref = 'ras@8'
        ras8.raster = band8
        ras8.bandNumber = 1
        entries.append(ras8)

        if self.dlg.RBNdviIndex.isChecked():
            calc = QgsRasterCalculator('(ras@8 - ras@4) / (ras@4+ras@8)*100',
                                       self.path + "raster_output.tif", 'GTiff',
                                       band4.extent(), band4.width(), band4.height(),
                                       entries)
            calc.processCalculation()
        elif self.dlg.RBMsavi2Index.isChecked():
            calc = QgsRasterCalculator('(2 * ras@8 + 1 - sqrt((2 * ras@8 + 1) ^ 2 - 8 * (ras@8 - ras@4))) / 2*100',
                                       self.path + "raster_output.tif", 'GTiff',
                                       band4.extent(), band4.width(), band4.height(),
                                       entries)
            calc.processCalculation()

    def update_texts(self):
        """Updates the labels telling the distribution of the index. Currently
        fixed for 5 different values and interpolates between them."""
        self.x_values = []
        ds = gdal.Open(self.path + "raster_output.tif")
        rarray = np.array(ds.GetRasterBand(1).ReadAsArray())
        rarray = rarray[~np.isnan(rarray)]
        rarray = rarray[0.01 < rarray]
        min_value = round(float(rarray.min()))
        max_value = round(float(rarray.max()))
        interval = (max_value - min_value) / 5
        field_areal = self.parent.db.execute_and_return("""
        select st_area(polygon::geography)/10000 
        FROM fields
        Where field_name='{f_n}'""".format(f_n=self.dlg.CBFieldList.currentText()))[0][0]
        c1 = rarray[(min_value <= rarray) & (rarray < min_value + interval)].size
        areal = round(field_areal* c1/rarray.size, 2)
        text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(v=min_value, mi=min_value,
                                                   ma=round(float(min_value + interval)), ar=areal)
        self.dlg.LVal_1.setText(text)
        self.x_values.append(min_value)
        c2 = rarray[(min_value + 1 * interval <= rarray) &
                    (rarray < min_value + 2 * interval)].size
        areal = round(field_areal * c2 / rarray.size, 2)
        text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(v=round(float(min_value + interval * 1.5)),
                                                  mi=round(float(min_value + interval * 1)),
                                                  ma=round(float(min_value + interval * 2)),
                                                  ar=areal)
        self.dlg.LVal_2.setText(text)
        self.x_values.append(round(float(min_value + interval * 1.5)))
        c3 = rarray[(min_value + 2 * interval <= rarray) &
                    (rarray < min_value + 3 * interval)].size
        areal = round(field_areal * c3 / rarray.size, 2)
        text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(v=round(float(min_value + interval * 2.5)),
                                                  mi=round(float(min_value + interval * 2)),
                                                  ma=round(float(min_value + interval * 3)),
                                                  ar=areal)
        self.dlg.LVal_3.setText(text)
        self.x_values.append(round(float(min_value + interval * 2.5)))
        c4 = rarray[(min_value + 3 * interval <= rarray) &
                    (rarray < min_value + 4 * interval)].size
        areal = round(field_areal * c4 / rarray.size, 2)
        text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(v=round(float(min_value + interval * 3.5)),
                                                  mi=round(float(min_value + interval * 3)),
                                                  ma=round(float(min_value + interval * 4)),
                                                  ar=areal)
        self.dlg.LVal_4.setText(text)
        self.x_values.append(round(float(min_value + interval * 3.5)))
        c5 = rarray[(min_value + 4 * interval <= rarray) &
                    (rarray < max_value)].size
        areal = round(field_areal * c5 / rarray.size, 2)
        text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(v=max_value,
                                                  mi=round(float(min_value + interval * 4)),
                                                  ma=max_value,
                                                  ar=areal)
        self.dlg.LVal_5.setText(text)
        self.x_values.append(max_value)
        self.rarray = rarray

    def update_graph(self):
        """Updates the graph according to index values and the set fertilizer
        distribution."""
        fig, ax = plt.subplots()
        if self.canvas is not None:
            self.graph_area.removeWidget(self.canvas)
        self.y_values = []
        self.y_values.append(float(self.dlg.LEVal_1.text()))
        self.y_values.append(float(self.dlg.LEVal_2.text()))
        self.y_values.append(float(self.dlg.LEVal_3.text()))
        self.y_values.append(float(self.dlg.LEVal_4.text()))
        self.y_values.append(float(self.dlg.LEVal_5.text()))
        ax.plot(self.x_values, self.y_values)
        self.canvas = FigureCanvas(fig)
        self.graph_area.addWidget(self.canvas)
        self.canvas.draw()

    def update_field_list(self):
        """Populates the field list (with parent.populate.reload_fields) and
        enables the selection of the zip file."""
        self.parent.populate.reload_fields(self.dlg.CBFieldList)
        self.dlg.PBSelectZipFile.setEnabled(True)

    def generate_guide_file(self):
        """Generates the guide file, if CheckBPlanned.isChecked then add_to_db
        is called. Finalising with calling on the cleanup function."""
        path = self.path[:self.path.index('tmp_files123')]
        file_name = path + 'guide_file_{f}_{g}.shp'.format(
                      f=self.dlg.CBFieldList.currentText(),
                      g=datetime.date(datetime.today()).isoformat())
        if os.path.isfile(file_name):
            msgBox = QMessageBox()
            msgBox.setText(self.tr('You have all ready created a guide file for this field today, do you want to replace it?'))
            msgBox.addButton(QPushButton(self.tr('Yes')), QMessageBox.YesRole)
            msgBox.addButton(QPushButton(self.tr('No')), QMessageBox.NoRole)
            res = msgBox.exec_()
            if res == 1:
                return
            try:
                for ending in ['dbf', 'prj', 'shp', 'shx']:
                    os.remove(file_name[:-3] + ending)
            except PermissionError:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('The file could not automaticlly be removed, please try to do it manually and create the guide file again'))
                return
        params = {'INPUT': self.path + "raster_output.tif", 'BAND': 1,
                  'OUTPUT': file_name,
                  'FIELD': 'raster_value'}
        alg_name = 'gdal:polygonize'
        processing.run(alg_name, params)
        vl = QgsVectorLayer(file_name, 'ferti_layert', 'ogr')
        vl.startEditing()
        ferti_field = QgsField('Fertilizin', QVariant.Int)
        vl.dataProvider().addAttributes([ferti_field])
        vl.updateFields()
        idx = vl.dataProvider().fieldNameIndex('Fertilizin')

        for f in vl.getFeatures():
            val = f.attributes()[0]
            if type(val) is not int:
                break
            ferti = int(np.interp(val, self.x_values, self.y_values))
            vl.changeAttributeValue(f.id(), idx, ferti)
        vl.commitChanges()
        del vl
        self.file_name = file_name
        if self.dlg.CheckBPlanned.isChecked():
            self.add_to_db()
        self.cleanup()

    def cleanup(self):
        """Removes the temporary folder (tmp_files123) from the path and
        disable some buttons."""
        shutil.rmtree(self.path)
        self.dlg.PBUpdateGraph.setEnabled(False)
        self.dlg.PBGenerateGuideFile.setEnabled(False)
        self.dlg.CWPlannedDate.setEnabled(False)

    def add_to_db(self):
        """Adds the guide file to the database with the expected date of usage.
        """
        s_date = self.dlg.CWPlannedDate.selectedDate().toString("yyyy-MM-dd")
        if s_date == datetime.date(datetime.today()).isoformat():
            msgBox = QMessageBox()
            msgBox.setText(self.tr('Are you planning to use it today?'))
            msgBox.addButton(QPushButton(self.tr('Yes')), QMessageBox.YesRole)
            msgBox.addButton(QPushButton(self.tr('No')), QMessageBox.NoRole)
            res = msgBox.exec_()
            if res == 1:
                return
        tbl = check_text(self.file_name[self.path.index('tmp_files123')+11:-4] + '_' + s_date)
        if self.parent.db.check_table_exists(tbl, 'ferti'):
            return
        ish = InputShpHandler(self.parent, schema='ferti', spec_columns=[])
        ish.tbl_name = tbl
        ish.col_names = ['raster_value', 'Fertilizin']
        ish.col_types = [1, 1]
        ish.file_name_with_path = self.file_name
        ish.ISD.EPSG.setText('4326')
        ish.field = self.dlg.CBFieldList.currentText()
        ish.params_to_evaluate = ['Fertilizin']
        res = ish.import_data('debug', date_dict={'simple_date': s_date})
