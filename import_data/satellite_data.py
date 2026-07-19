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
from qgis.PyQt.QtWidgets import (QMessageBox, QVBoxLayout, QGridLayout,
                                 QPushButton, QLabel, QLineEdit)
from qgis.PyQt.QtCore import QVariant, QSettings, Qt, QPointF
from qgis.PyQt.QtGui import (QPixmap, QPainter, QPen, QColor, QPolygonF,
                             QImage)
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsGeometry,
                       QgsFeature,QgsProcessingFeedback, QgsRasterBandStats,
                       QgsExpression, QgsField)
from qgis.analysis import QgsRasterCalculatorEntry, QgsRasterCalculator, QgsZonalStatistics
import sys
sys.path.append('C:\\OSGeo4W\\apps\\qgis\\python\\plugins\\')
import processing
from qgis.core import QgsProcessingException
from ..support_scripts import check_text, TR, isfloat
from ..support_scripts.notifier import report_warning, report_error, report_success
from ..support_scripts.cdse_client import CDSEClient, CDSEError
from ..support_scripts.RG import rg
from ..import_data.handle_input_shp_data import InputShpHandler

# Where the per-user Copernicus OAuth credentials are stored in QSettings.
CDSE_ID_KEY = "geodatafarm/cdse_client_id"
CDSE_SECRET_KEY = "geodatafarm/cdse_client_secret"  # pragma: allowlist secret  # nosec B105
# URL where users create an OAuth client to obtain their id/secret.
CDSE_DASHBOARD_URL = "https://shapps.dataspace.copernicus.eu/dashboard/"
# Extra context (in metres) captured around the field in the true-colour
# preview, so the surroundings are visible and not just the field itself.
PREVIEW_BUFFER_M = 300


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
        self.rarray_2d = None
        self.classes = []
        self.rate_edits = []
        self._last_num_classes = None
        self.graph_area = QVBoxLayout(self.dlg.QWGraphArea)
        self.class_grid = QGridLayout(self.dlg.QWValueMapping)
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
        self.dlg.PBUpdateClasses.clicked.connect(self._apply_classification)
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

    def _field_geometry(self, buffer_m=0):
        """Reads the selected field from the database.

        Parameters
        ----------
        buffer_m: float
            If non-zero, the field polygon is expanded outward by this many
            metres (via ``st_buffer`` on the geography) before its geometry
            and bbox are returned, e.g. to capture context around the field
            for the true-colour preview.

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
        if buffer_m:
            row = self.parent.db.execute_and_return(
                "SELECT st_asgeojson(buf), st_xmin(buf), st_ymin(buf),"
                " st_xmax(buf), st_ymax(buf) FROM (SELECT"
                " st_buffer(polygon::geography, %s)::geometry AS buf"
                " FROM fields WHERE field_name = %s) t",
                params=(buffer_m, field_name))[0]
        else:
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
        if not self._apply_classification():
            self.cleanup()
            return
        self.dlg.PBUpdateGraph.setEnabled(True)
        self.dlg.PBUpdateClasses.setEnabled(True)
        self.dlg.PBGenShp.setEnabled(True)
        self.dlg.PBGenIso.setEnabled(True)
        # True-colour preview alongside the index (best-effort), padded with
        # extra context around the field and outlined with the field
        # boundary so the buffer zone stays distinguishable from the field.
        preview_field = self._field_geometry(PREVIEW_BUFFER_M)
        if preview_field is not None:
            p_geometry, p_bbox, p_width, p_height = preview_field
            self._update_preview(client, p_geometry, geometry, p_bbox, date,
                                 p_width, p_height)

    def _update_preview(self, client, geometry, field_geometry, bbox, date,
                        width, height):
        """Fetch a true-colour composite covering ``geometry`` (the field
        buffered by :data:`PREVIEW_BUFFER_M`), draw the actual field boundary
        (``field_geometry``) on top so it stays distinguishable from the
        surrounding buffer zone, and show it next to the index. Failures are
        silently ignored — the index already succeeded."""
        try:
            png = client.get_truecolor(geometry, date, width, height)
        except CDSEError:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(png):
            return
        self._draw_field_outline(pixmap, field_geometry, bbox)
        try:
            aspect = Qt.AspectRatioMode.KeepAspectRatio
            smooth = Qt.TransformationMode.SmoothTransformation
        except AttributeError:
            aspect = getattr(Qt, 'KeepAspectRatio')
            smooth = getattr(Qt, 'SmoothTransformation')
        self.dlg.LSatPreview.setPixmap(pixmap.scaled(300, 300, aspect, smooth))

    def _draw_field_outline(self, pixmap, field_geometry, bbox):
        """Draws ``field_geometry`` (a GeoJSON Polygon/MultiPolygon in
        EPSG:4326) as a red line on top of ``pixmap``, mapping its
        coordinates into pixel space via ``bbox`` (the ``[min_lon, min_lat,
        max_lon, max_lat]`` extent the pixmap covers)."""
        min_lon, min_lat, max_lon, max_lat = bbox
        lon_span = max_lon - min_lon
        lat_span = max_lat - min_lat
        if lon_span <= 0 or lat_span <= 0:
            return
        w, h = pixmap.width(), pixmap.height()

        def to_px(lon, lat):
            x = (lon - min_lon) / lon_span * w
            y = (max_lat - lat) / lat_span * h
            return QPointF(x, y)

        if field_geometry['type'] == 'Polygon':
            polygons = [field_geometry['coordinates']]
        elif field_geometry['type'] == 'MultiPolygon':
            polygons = field_geometry['coordinates']
        else:
            return
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        try:
            for polygon in polygons:
                for ring in polygon:
                    painter.drawPolyline(
                        QPolygonF([to_px(lon, lat) for lon, lat in ring]))
        finally:
            painter.end()

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

    def _class_color(self, i, num_classes):
        """Maps class index ``i`` (of ``num_classes``) to an ``(r, g, b)``
        tuple in 0..1 via the shared red-to-green colormap (``rg()``), low
        index=red (stressed), high index=green (healthy). Clamped/rounded
        defensively before calling ``rg()`` (see support_scripts/RG.py)."""
        frac = round(max(0.0, min(1.0, float(i) / float(num_classes))), 2)
        return tuple(rg(frac))

    def _classify_index(self):
        """Reads ``raster_output.tif`` and splits its valid pixels into
        ``SBNumClasses`` classes across ``LEClassMin``/``LEClassMax`` (blank
        = auto, taken from the raster's own min/max), building
        ``self.classes`` (one dict per class: lo/hi/anchor/text/area/color)
        and ``self.x_values``. The two extreme classes absorb any pixels
        outside a user-narrowed min/max so no pixels are silently dropped.

        Returns
        -------
        bool
            False (after a warning) if the input is invalid or the raster
            has no usable data.
        """
        num_classes = self.dlg.SBNumClasses.value()
        min_text = self.dlg.LEClassMin.text().strip()
        max_text = self.dlg.LEClassMax.text().strip()
        if min_text and not isfloat(min_text):
            report_warning(self.tr('The minimum value must be a number.'))
            return False
        if max_text and not isfloat(max_text):
            report_warning(self.tr('The maximum value must be a number.'))
            return False
        ds = gdal.Open(self.path + "raster_output.tif")
        rarray_2d = np.array(ds.GetRasterBand(1).ReadAsArray())
        rarray = rarray_2d[~np.isnan(rarray_2d) & (rarray_2d > 0.01)]
        if rarray.size == 0:
            report_warning(self.tr(
                'There is no data in that file, is the day cloud free?'))
            return False
        min_value = round(float(min_text)) if min_text else round(float(rarray.min()))
        max_value = round(float(max_text)) if max_text else round(float(rarray.max()))
        if max_value <= min_value:
            report_warning(self.tr(
                'The maximum value must be greater than the minimum value.'))
            return False
        field_areal = self.parent.db.execute_and_return(
            "SELECT st_area(polygon::geography)/10000 FROM fields WHERE field_name = %s",
            params=(self.dlg.CBFieldList.currentText(),))[0][0]
        interval = (max_value - min_value) / num_classes
        classes = []
        x_values = []
        for i in range(num_classes):
            lo = min_value + i * interval
            hi = max_value if i == num_classes - 1 else min_value + (i + 1) * interval
            if i == 0:
                # Absorbs values below min_value too, so a user-narrowed
                # range never silently drops pixels from the area stats.
                mask = rarray < hi
                anchor = min_value
            elif i == num_classes - 1:
                mask = rarray >= lo
                anchor = max_value
            else:
                mask = (rarray >= lo) & (rarray < hi)
                anchor = min_value + interval * (i + 0.5)
            area = round(field_areal * mask.sum() / rarray.size, 2)
            text = '{v}% [{mi}-{ma}] ({ar} ha)'.format(
                v=round(anchor), mi=round(lo), ma=round(hi), ar=area)
            classes.append({'lo': lo, 'hi': hi, 'anchor': anchor,
                           'text': text, 'area': area,
                           'color': self._class_color(i, num_classes)})
            x_values.append(round(anchor))
        self.classes = classes
        self.x_values = x_values
        self.rarray = rarray
        self.rarray_2d = rarray_2d
        return True

    def _rebuild_value_grid(self):
        """Rebuilds the 'Index value mapping' rows (label, color swatch,
        rate box) from ``self.classes``. Previously typed rates are
        preserved when the class count hasn't changed since the last
        classification; otherwise a sensible default rate sequence is
        reseeded."""
        old_rates = [le.text() for le in self.rate_edits]
        reuse_rates = (self._last_num_classes == len(self.classes)
                      and len(old_rates) == len(self.classes))
        if not reuse_rates:
            old_rates = [str(int(round(v))) for v in
                        np.linspace(200, 100, len(self.classes))]
        while self.class_grid.count():
            item = self.class_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.rate_edits = []
        for i, cls in enumerate(self.classes):
            self.class_grid.addWidget(QLabel(cls['text']), i, 0)
            red, green, blue = cls['color']
            swatch = QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                'background-color: rgb({r},{g},{b}); '
                'border:1px solid palette(mid);'.format(
                    r=int(red * 255), g=int(green * 255), b=int(blue * 255)))
            self.class_grid.addWidget(swatch, i, 1)
            rate_edit = QLineEdit(old_rates[i])
            rate_edit.setMaximumWidth(120)
            self.class_grid.addWidget(rate_edit, i, 2)
            self.rate_edits.append(rate_edit)
        self._last_num_classes = len(self.classes)

    def _render_index_image(self):
        """Renders ``raster_output.tif`` as a classified thematic map
        (colored per ``self.classes``, transparent outside the field) and
        shows it in the second preview label, next to the true-colour one."""
        arr = self.rarray_2d
        valid = ~np.isnan(arr) & (arr > 0.01)
        h, w = arr.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        for i, cls in enumerate(self.classes):
            if i == 0:
                mask = valid & (arr < cls['hi'])
            elif i == len(self.classes) - 1:
                mask = valid & (arr >= cls['lo'])
            else:
                mask = valid & (arr >= cls['lo']) & (arr < cls['hi'])
            red, green, blue = cls['color']
            rgba[mask] = (int(red * 255), int(green * 255), int(blue * 255), 255)
        rgba = np.ascontiguousarray(rgba)
        try:
            img_format = QImage.Format.Format_RGBA8888
        except AttributeError:
            img_format = getattr(QImage, 'Format_RGBA8888')
        # .copy() decouples the QImage from the numpy buffer's lifetime.
        qimg = QImage(rgba.data, w, h, w * 4, img_format).copy()
        pixmap = QPixmap.fromImage(qimg)
        try:
            aspect = Qt.AspectRatioMode.KeepAspectRatio
            smooth = Qt.TransformationMode.SmoothTransformation
        except AttributeError:
            aspect = getattr(Qt, 'KeepAspectRatio')
            smooth = getattr(Qt, 'SmoothTransformation')
        self.dlg.LClassPreview.setPixmap(pixmap.scaled(300, 300, aspect, smooth))

    def _apply_classification(self):
        """Reclassifies the already-downloaded index raster into the
        current number of classes/range (no new Copernicus request),
        rebuilds the value-mapping table, the classified-map preview and
        the rate graph.

        Returns
        -------
        bool
            True on success. Failures are reported via ``report_warning``
            and leave whatever was previously on screen untouched (the
            caller decides whether that also means calling ``cleanup()``).
        """
        if not os.path.isfile(self.path + "raster_output.tif"):
            report_warning(self.tr('Please fetch and process an image first.'))
            return False
        if not self._classify_index():
            return False
        self._rebuild_value_grid()
        self._render_index_image()
        self.update_graph()
        return True

    def update_graph(self):
        """Updates the graph according to index values and the set fertilizer
        distribution."""
        fig, ax = plt.subplots()
        if self.canvas is not None:
            self.graph_area.removeWidget(self.canvas)
        self.y_values = [float(le.text()) for le in self.rate_edits]
        ax.plot(self.x_values, self.y_values)
        ax.set_xlabel(self.tr('Index value (%)'))
        ax.set_ylabel(self.tr('Application rate'))
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
        self.dlg.PBUpdateClasses.setEnabled(False)
        self.dlg.PBGenShp.setEnabled(False)
        self.dlg.PBGenIso.setEnabled(False)
