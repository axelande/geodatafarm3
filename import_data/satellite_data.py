try:
    from typing import Self
except ImportError:
    Self = None
import webbrowser
import os
import json
import math
import shutil
import tempfile
import numpy as np
from osgeo import gdal, ogr
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
from qgis.PyQt.QtWidgets import QMessageBox, QVBoxLayout, QPushButton
from qgis.PyQt.QtCore import QVariant, QSettings, Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsGeometry,
                       QgsFeature,QgsProcessingFeedback, QgsRasterBandStats,
                       QgsExpression, QgsField)
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator, QgsZonalStatistics
import sys
sys.path.append('C:\\OSGeo4W\\apps\\qgis\\python\\plugins\\')
import processing
from qgis.core import QgsProcessingException
from ..support_scripts import check_text, TR
from ..support_scripts.notifier import report_warning, report_error, report_success
from ..support_scripts.cdse_client import CDSEClient, CDSEError
from ..import_data.handle_input_shp_data import InputShpHandler

# Where the per-user Copernicus OAuth credentials are stored in QSettings.
CDSE_ID_KEY = "geodatafarm/cdse_client_id"
CDSE_SECRET_KEY = "geodatafarm/cdse_client_secret"  # pragma: allowlist secret
# URL where users create an OAuth client to obtain their id/secret.
CDSE_DASHBOARD_URL = "https://shapps.dataspace.copernicus.eu/dashboard/"


class SatelliteData:
    def __init__(self: Self, parent) -> None:
        self.parent = parent
        self.dlg = parent.dock_widget
        translate = TR('SatelliteData')
        self.tr = translate.tr
        self.path = ''
        self.canvas = None
        self.y_values = []
        self.x_values = []
        self.rarray = []
        self.graph_area = QVBoxLayout(self.dlg.QWGraphArea)
        self.connect_buttons = False
        self.qsettings = QSettings()
        self.client = None
        # Scenes returned by the last catalog search; index matches CBImageDate.
        self.features = []

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the satellite tab"""
        if self.connect_buttons:
            return
        self.dlg.PBListCropstat.clicked.connect(
            lambda: webbrowser.open('http://www.cropsat.se'))
        self.dlg.PBListCopernicus.clicked.connect(
            lambda: webbrowser.open(CDSE_DASHBOARD_URL))
        self.dlg.PBListGeoDataFarm.clicked.connect(
            lambda: webbrowser.open('http://www.geodatafarm.com/satellite/'))
        self.dlg.PBSaveCdseCreds.clicked.connect(self.save_credentials)
        self.dlg.PBSearchImages.clicked.connect(self.search_images)
        self.dlg.PBFetchImage.clicked.connect(self.fetch_and_process)
        self.dlg.PBUpdateFieldList.clicked.connect(self.update_field_list)
        self.dlg.PBGenShp.clicked.connect(lambda: self.generate_guide('shp'))
        self.dlg.PBGenIso.clicked.connect(lambda: self.generate_guide('iso'))
        self.dlg.PBUpdateGraph.clicked.connect(self.update_graph)
        # Pre-fill the saved Copernicus credentials, if any.
        self.dlg.LECdseClientId.setText(
            self.qsettings.value(CDSE_ID_KEY, '') or '')
        self.dlg.LECdseClientSecret.setText(
            self.qsettings.value(CDSE_SECRET_KEY, '') or '')
        self.connect_buttons = True

    def save_credentials(self):
        """Stores the Copernicus OAuth client id/secret in QSettings so the
        user only has to enter them once, and (re)creates the API client."""
        client_id = self.dlg.LECdseClientId.text().strip()
        client_secret = self.dlg.LECdseClientSecret.text().strip()
        if not client_id or not client_secret:
            report_warning(self.tr(
                'Please enter both the Copernicus client id and client '
                'secret. You can create them in the Copernicus dashboard '
                '(see the link above).'))
            return
        self.qsettings.setValue(CDSE_ID_KEY, client_id)
        self.qsettings.setValue(CDSE_SECRET_KEY, client_secret)
        self.client = CDSEClient(client_id, client_secret)
        report_success(self.tr('Copernicus credentials saved.'))

    def _ensure_client(self):
        """Returns a ready CDSEClient or None (after warning) if no
        credentials are available."""
        if self.client is not None:
            return self.client
        client_id = (self.dlg.LECdseClientId.text().strip()
                     or self.qsettings.value(CDSE_ID_KEY, '') or '')
        client_secret = (self.dlg.LECdseClientSecret.text().strip()
                         or self.qsettings.value(CDSE_SECRET_KEY, '') or '')
        if not client_id or not client_secret:
            report_warning(self.tr(
                'No Copernicus credentials found. Please enter your client '
                'id and secret and press "Save credentials".'))
            return None
        self.client = CDSEClient(client_id, client_secret)
        return self.client

    def _field_geometry(self):
        """Reads the selected field from the database.

        Returns
        -------
        tuple or None
            ``(geojson_geometry, bbox, width_px, height_px)`` where bbox is
            ``[min_lon, min_lat, max_lon, max_lat]`` and the pixel dimensions
            target a ~10 m Sentinel-2 resolution. Returns None (after warning)
            if no field is selected.
        """
        field_name = self.dlg.CBFieldList.currentText()
        if not field_name:
            report_warning(self.tr('Please select a field first.'))
            return None
        row = self.parent.db.execute_and_return(
            "SELECT st_asgeojson(polygon), st_xmin(polygon), st_ymin(polygon),"
            " st_xmax(polygon), st_ymax(polygon) FROM fields"
            " WHERE field_name = %s", params=(field_name,))[0]
        geometry = json.loads(row[0])
        min_lon, min_lat, max_lon, max_lat = (float(row[1]), float(row[2]),
                                              float(row[3]), float(row[4]))
        bbox = [min_lon, min_lat, max_lon, max_lat]
        # Convert the degree extent to metres to target a 10 m pixel size.
        mid_lat = math.radians((min_lat + max_lat) / 2)
        width_m = (max_lon - min_lon) * 111320 * math.cos(mid_lat)
        height_m = (max_lat - min_lat) * 111320
        width = min(2500, max(1, round(width_m / 10)))
        height = min(2500, max(1, round(height_m / 10)))
        return geometry, bbox, width, height

    def search_images(self):
        """Searches the Copernicus catalog for Sentinel-2 scenes covering the
        selected field within the chosen date range and lists them (with cloud
        cover) in the date combo box."""
        client = self._ensure_client()
        if client is None:
            return
        field = self._field_geometry()
        if field is None:
            return
        _geometry, bbox, _w, _h = field
        date_from = self.dlg.DECdseFrom.date().toString("yyyy-MM-dd")
        date_to = self.dlg.DECdseTo.date().toString("yyyy-MM-dd")
        if date_from > date_to:
            report_warning(self.tr(
                'The "to date" must be the same or later than the "from '
                'date".'))
            return
        max_cloud = self.dlg.SBMaxCloud.value()
        try:
            self.features = client.search_images(bbox, date_from, date_to,
                                                 max_cloud)
        except CDSEError as e:
            report_error(str(e))
            return
        self.dlg.CBImageDate.clear()
        if not self.features:
            self.dlg.PBFetchImage.setEnabled(False)
            report_warning(self.tr(
                'No Sentinel-2 images were found for that field, date range '
                'and cloud limit.'))
            return
        for feat in self.features:
            self.dlg.CBImageDate.addItem(
                '{d} ({c:.0f}% cloud)'.format(d=feat['date'], c=feat['cloud']))
        self.dlg.PBFetchImage.setEnabled(True)
        report_success(self.tr(
            'Found {n} image(s). Pick a date and press "Fetch & '
            'process".').format(n=len(self.features)))

    def fetch_and_process(self):
        """Downloads band 4 and band 8 for the selected scene from Copernicus,
        runs the base index calculation and updates the texts and graph."""
        idx = self.dlg.CBImageDate.currentIndex()
        if idx < 0 or idx >= len(self.features):
            report_warning(self.tr('Please search for and select an image '
                                   'date first.'))
            return
        client = self._ensure_client()
        if client is None:
            return
        field = self._field_geometry()
        if field is None:
            return
        geometry, _bbox, width, height = field
        date = self.features[idx]['date']
        base = QgsProject.instance().homePath() or os.path.expanduser('~')
        self.path = os.path.join(base, 'tmp_files123') + os.sep
        os.makedirs(self.path, exist_ok=True)
        try:
            band4 = self._download_band(client, geometry, date, 'B04',
                                        width, height, 'band4')
            band8 = self._download_band(client, geometry, date, 'B08',
                                        width, height, 'band8')
        except CDSEError as e:
            report_error(str(e))
            self.cleanup()
            return
        if not band4.isValid() or not band8.isValid():
            report_error(self.tr(
                'The downloaded Copernicus image could not be read.'))
            self.cleanup()
            return
        self.do_base_calculation(band4, band8)
        if not self.update_texts():
            self.cleanup()
            return
        self.dlg.PBUpdateGraph.setEnabled(True)
        self.dlg.PBGenShp.setEnabled(True)
        self.dlg.PBGenIso.setEnabled(True)
        self.update_graph()
        # True-color preview alongside the index (best-effort).
        self._update_preview(client, geometry, date, width, height)

    def _update_preview(self, client, geometry, date, width, height):
        """Fetch a true-color composite for the scene and show it next to the
        index. Failures are silently ignored — the index already succeeded."""
        try:
            png = client.get_truecolor(geometry, date, width, height)
        except CDSEError:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(png):
            return
        try:
            aspect = Qt.AspectRatioMode.KeepAspectRatio
            smooth = Qt.TransformationMode.SmoothTransformation
        except AttributeError:
            aspect = Qt.KeepAspectRatio
            smooth = Qt.SmoothTransformation
        self.dlg.LSatPreview.setPixmap(pixmap.scaled(300, 300, aspect, smooth))

    def generate_guide(self, fmt):
        """Hand the current index raster and the index->rate mapping over to the
        Guide-file tab, in 'Use satellite data' mode, for the chosen format
        ('shp' or 'iso')."""
        if not self.x_values:
            report_warning(self.tr('Please fetch and process an image first.'))
            return
        # Refresh the rate mapping from the value boxes (they may have changed).
        try:
            self.update_graph()
        except ValueError:
            report_warning(self.tr('Please enter a number in every rate box.'))
            return
        raster_src = self.path + 'raster_output.tif'
        if not os.path.isfile(raster_src):
            report_warning(self.tr('The processed image is missing, please '
                                   'fetch it again.'))
            return
        guide = getattr(self.parent, 'guide', None)
        if guide is None:
            report_error(self.tr('The guide-file tab is not ready yet.'))
            return
        # Copy the raster to a stable temp file so the guide tab owns its own
        # copy, independent of this tab's temporary folder.
        tmp = tempfile.NamedTemporaryFile(prefix='gdf_sat_', suffix='.tif',
                                          delete=False)
        tmp.close()
        shutil.copy(raster_src, tmp.name)
        field = self.dlg.CBFieldList.currentText()
        index_name = 'NDVI' if self.dlg.RBNdviIndex.isChecked() else 'MSAVI2'
        guide.arm_satellite(fmt, tmp.name, self.x_values, self.y_values,
                            field, index_name)

    def _download_band(self, client, geometry, date, band, width, height,
                       name):
        """Downloads a single band to a GeoTIFF and returns it as a layer.

        Parameters
        ----------
        client: CDSEClient
        geometry: dict
            GeoJSON field geometry (EPSG:4326).
        date: str
            Acquisition date, ``YYYY-MM-DD``.
        band: str
            Sentinel-2 band name, e.g. ``'B04'``.
        width, height: int
            Output size in pixels.
        name: str
            Local name/filename stem for the layer.

        Returns
        -------
        QgsRasterLayer
        """
        content = client.get_band(geometry, date, band, width, height)
        file_path = self.path + name + '.tif'
        with open(file_path, 'wb') as fh:
            fh.write(content)
        return QgsRasterLayer(file_path, name)

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
        if len(rarray) == 0:
            report_warning(self.tr(
                'There is no data in that file, is the day cloud free?'))
            return False
        min_value = round(float(rarray.min()))
        max_value = round(float(rarray.max()))
        interval = (max_value - min_value) / 5
        field_areal = self.parent.db.execute_and_return(
            "SELECT st_area(polygon::geography)/10000 FROM fields WHERE field_name = %s",
            params=(self.dlg.CBFieldList.currentText(),))[0][0]
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
        return True

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
        enables searching for satellite images."""
        self.parent.populate.reload_fields(self.dlg.CBFieldList)
        self.dlg.PBSearchImages.setEnabled(True)

    def cleanup(self):
        """Removes the temporary folder (tmp_files123) from the path and
        disables the generate buttons. Called on error paths."""
        if self.path and os.path.isdir(self.path):
            shutil.rmtree(self.path, ignore_errors=True)
        self.dlg.PBUpdateGraph.setEnabled(False)
        self.dlg.PBGenShp.setEnabled(False)
        self.dlg.PBGenIso.setEnabled(False)
