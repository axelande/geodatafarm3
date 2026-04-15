from typing import TYPE_CHECKING, Self
import matplotlib
matplotlib.use('Agg')
if TYPE_CHECKING:
    import matplotlib.figure
    import shapely.geometry.polygon
import os
import math

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from shapely.geometry import Polygon
from shapely import wkt
import pyproj
from shapely.ops import transform

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QListWidgetItem, QApplication, QSizePolicy, QVBoxLayout, QFileDialog

from ..widgets.find_shape_fields import FindShapeFieldWidget
from ..support_scripts.qt_data import _check_state, _item_flag

class FindShapeField:
    def __init__(self: Self, parent, test_path: str = '') -> None:
        self.parent = parent
        self.fsfw = FindShapeFieldWidget()
        self.connect()
        self.fields = {}
        self.current_polygon = ''
        self.path = test_path
        self.zoom_level = 17
        self.gdf = None
        self.gdf_crs = None

    def connect(self: Self) -> None:
        self.fsfw.PBAddShapeFile.clicked.connect(self.open_shapefile)
        self.fsfw.CBFieldNames.currentIndexChanged.connect(self.populate_field_list)
        self.fsfw.LWFields.itemClicked.connect(self.on_item_clicked)
        self.fsfw.PBSaveField.clicked.connect(self.save_field)
    
    def run(self):
        """Shows the widget and executes it if not in test mode."""
        self.fsfw.show()
        if not self.parent.test_mode:
            self.fsfw.exec()


    def open_shapefile(self: Self) -> None:
        if self.parent.test_mode:
            path = self.path
        else:
            path, _ = QFileDialog.getOpenFileName(None, self.parent.tr("Open a shapefile"), '',
                                                            "Shapefile (*.shp)")
        if path:
            self.path = path
            self.gdf = gpd.read_file(path)
            # remember the source CRS for geometries so WKT transformations use it
            try:
                self.gdf_crs = self.gdf.crs
            except Exception:
                self.gdf_crs = None
            self.fsfw.CBFieldNames.clear()
            geom_col = None
            try:
                geom_col = self.gdf.geometry.name
            except Exception:
                geom_col = 'geometry'
            for col in self.gdf.columns:
                if col != geom_col:
                    self.fsfw.CBFieldNames.addItem(col)
            for i in range(self.fsfw.CBFieldNames.count()):
                if self.parent.tr("name") in self.fsfw.CBFieldNames.itemText(i).lower():
                    self.fsfw.CBFieldNames.setCurrentIndex(i)
                    break
            if self.fsfw.CBFieldNames.count() > 0:
                self.populate_field_list()

    def populate_field_list(self: Self) -> None:
        self.fsfw.LWFields.clear()
        if self.gdf is None:
            return
        field_name_col = self.fsfw.CBFieldNames.currentText()
        if not field_name_col:
            return
        self.fields.clear()
        for idx, row in self.gdf.iterrows():
            name = str(row[field_name_col])
            geom = row.geometry
            if geom is not None and not geom.is_empty:
                self.fields[name] = geom.wkt
                self.fsfw.LWFields.addItem(name)

    def on_item_clicked(self: Self, item: QListWidgetItem) -> None:
        item_name = item.text()
        if item_name in self.fields:
            self.fsfw.LEFieldName.setText(item_name)
            self.load_wkt(self.fields[item_name])
            self.current_polygon = self.fields[item_name]

    def _set_new_crs(self: Self, polygon: "shapely.geometry.polygon.Polygon",
                     source_proj: str = None,
                     target_proj: str = 'EPSG:3857') -> "shapely.geometry.polygon.Polygon":
        # If source projection not provided, try to use the shapefile CRS
        if source_proj is None:
            try:
                if self.gdf_crs is not None:
                    source_proj = pyproj.CRS(self.gdf_crs).to_string()
                else:
                    source_proj = 'EPSG:4326'
            except Exception:
                source_proj = 'EPSG:4326'
        project = pyproj.Transformer.from_crs(source_proj, target_proj, always_xy=True).transform
        return transform(project, polygon)

    def _plot_polygon_on_map(self: Self, polygon: "shapely.geometry.polygon.Polygon") -> "matplotlib.figure.Figure":
        try:
            if polygon.is_empty:
                fig, ax = plt.subplots(figsize=(12, 9))
                ax.text(0.5, 0.5, 'No data points were found', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=15)
                ax.set_axis_off()
                return fig

            polygon = self._set_new_crs(polygon)

            # If it's a MultiPolygon, pick the largest part for preview
            if getattr(polygon, 'geom_type', '') == 'MultiPolygon':
                if len(polygon.geoms) > 0:
                    polygon = max(polygon.geoms, key=lambda g: g.area)

            # Ensure we have a polygon-like geometry (fallback to convex hull)
            if not hasattr(polygon, 'exterior'):
                polygon = polygon.convex_hull

            minx, miny, maxx, maxy = polygon.bounds

            # Validate bounds
            if not all(math.isfinite(v) for v in (minx, miny, maxx, maxy)):
                fig, ax = plt.subplots(figsize=(12, 9))
                ax.text(0.5, 0.5, 'Invalid polygon bounds', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=15)
                ax.set_axis_off()
                return fig

            # Guard degenerate bounds (zero width/height)
            dx = maxx - minx
            dy = maxy - miny
            if dx == 0:
                minx -= 0.5
                maxx += 0.5
                dx = maxx - minx
            if dy == 0:
                miny -= 0.5
                maxy += 0.5
                dy = maxy - miny

            fig, ax = plt.subplots(figsize=(12, 9))
            x, y = polygon.exterior.xy
            patch_collection = ax.fill(x, y, edgecolor='m', facecolor='none')
            if patch_collection:
                self.polygon_patch = patch_collection[0]
            if not self.parent.test_mode:
                ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=self.zoom_level)
            padding = 0.15
            ax.set_xlim(minx - dx * padding, maxx + dx * padding)
            ax.set_ylim(miny - dy * padding, maxy + dy * padding)
            ax.set_axis_off()
            return fig
        except Exception as e:
            fig, ax = plt.subplots(figsize=(12, 9))
            ax.text(0.5, 0.5, f'Error plotting polygon: {e}', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=12)
            ax.set_axis_off()
            return fig

    def load_wkt(self: Self, polygon_wkt: str) -> None:
        polygon = wkt.loads(polygon_wkt)
        fig = self._plot_polygon_on_map(polygon)
        self.canvas = FigureCanvas(fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = self.fsfw.WShowField.layout()
        if layout is None:
            layout = QVBoxLayout()
            self.fsfw.WShowField.setLayout(layout)
        else:
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        layout.addWidget(self.canvas)

    def save_field(self: Self) -> None:
        name = self.fsfw.LEFieldName.text()
        if name == '' or self.current_polygon == '':
            return False
        # Determine source CRS of loaded shapefile so we insert geometry correctly
        source_srid = 4326
        try:
            if hasattr(self, 'gdf_crs') and self.gdf_crs is not None:
                try:
                    crs_obj = pyproj.CRS(self.gdf_crs)
                    epsg = crs_obj.to_epsg()
                    if epsg is not None:
                        source_srid = int(epsg)
                    else:
                        # try to parse common 'EPSG:xxxx' string
                        s = str(self.gdf_crs)
                        if 'EPSG' in s:
                            import re
                            m = re.search(r"(\d{4,6})", s)
                            if m:
                                source_srid = int(m.group(1))
                except Exception:
                    source_srid = 4326
        except Exception:
            source_srid = 4326

        # Build SQL to ensure polygon stored in 4326 in DB
        if source_srid != 4326:
            sql = ("INSERT INTO fields (field_name, polygon)"
                   " VALUES (%s, st_transform(st_geomfromtext(%s, %s), 4326))")
            params = (name, self.current_polygon, source_srid)
        else:
            sql = ("INSERT INTO fields (field_name, polygon)"
                   " VALUES (%s, st_geomfromtext(%s, 4326))")
            params = (name, self.current_polygon)
        try:
            res = self.parent.db.execute_sql(sql, params=params, return_failure=True)
        except Exception as e:
            if self.parent.test_mode:
                return False
            else:
                QMessageBox.information(None, self.parent.tr('Error:'), str(e))
                return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.parent.dock_widget.LWFields)
        item.setFlags(item.flags() | _item_flag('ItemIsUserCheckable'))
        item.setCheckState(_check_state('Unchecked'))
