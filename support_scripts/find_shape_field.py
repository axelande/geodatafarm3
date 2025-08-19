from typing import TYPE_CHECKING, Self
import matplotlib
matplotlib.use('Agg')
if TYPE_CHECKING:
    import matplotlib.figure
    import shapely.geometry.polygon
import os

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from shapely.geometry import Polygon
from shapely import wkt
import pyproj
from shapely.ops import transform

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication

from ..widgets.find_shape_fields import FindShapeFieldWidget

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

    def connect(self: Self) -> None:
        self.fsfw.PBAddShapeFile.clicked.connect(self.open_shapefile)
        self.fsfw.CBFieldNames.currentIndexChanged.connect(self.populate_field_list)
        self.fsfw.LWFields.itemClicked.connect(self.on_item_clicked)
        self.fsfw.PBSaveField.clicked.connect(self.save_field)
    
    def run(self):
        """Shows the widget and executes it if not in test mode."""
        self.fsfw.show()
        if not self.parent.test_mode:
            self.fsfw.exec_()


    def open_shapefile(self: Self) -> None:
        if self.parent.test_mode:
            path = self.path
        else:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(None, self.parent.tr("Open a shapefile"), '',
                                                            "Shapefile (*.shp)")
        if path:
            self.path = path
            self.gdf = gpd.read_file(path)
            self.fsfw.CBFieldNames.clear()
            for col in self.gdf.columns:
                if self.gdf[col].dtype == object:
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
                     source_proj: str = 'EPSG:4326', 
                     target_proj: str = 'EPSG:3857') -> "shapely.geometry.polygon.Polygon":
        project = pyproj.Transformer.from_crs(source_proj, target_proj, always_xy=True).transform
        return transform(project, polygon)

    def _plot_polygon_on_map(self: Self, polygon: "shapely.geometry.polygon.Polygon") -> "matplotlib.figure.Figure":
        if polygon.is_empty:
            fig, ax = plt.subplots(figsize=(12, 9))
            ax.text(0.5, 0.5, 'No data points were found', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=15)
            ax.set_axis_off()
            return fig
        polygon = self._set_new_crs(polygon)
        minx, miny, maxx, maxy = polygon.bounds
        fig, ax = plt.subplots(figsize=(12, 9))
        patch_collection = ax.fill(*polygon.exterior.xy, edgecolor='m', facecolor='none')
        if patch_collection:
            self.polygon_patch = patch_collection[0]
        if not self.parent.test_mode:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=self.zoom_level)
        padding = 0.15
        ax.set_xlim(minx - (maxx - minx) * padding, maxx + (maxx - minx) * padding)
        ax.set_ylim(miny - (maxy - miny) * padding, maxy + (maxy - miny) * padding)
        ax.set_axis_off()
        return fig

    def load_wkt(self: Self, polygon_wkt: str) -> None:
        polygon = wkt.loads(polygon_wkt)
        fig = self._plot_polygon_on_map(polygon)
        self.canvas = FigureCanvas(fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = self.fsfw.WShowField.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
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
        sql = f"""Insert into fields (field_name, polygon) 
        VALUES ('{name}', st_geomfromtext('{self.current_polygon}', 4326))"""
        try:
            res = self.parent.db.execute_sql(sql, return_failure=True)
        except Exception as e:
            if self.parent.test_mode:
                return False
            else:
                QMessageBox.information(None, self.parent.tr('Error:'), str(e))
                return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.parent.dock_widget.LWFields)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)