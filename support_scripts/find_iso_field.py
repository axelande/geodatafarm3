import os
import sys
import xml.etree.ElementTree as ET

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pyproj
from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication
from psycopg2 import IntegrityError, InternalError
from shapely import wkt
from shapely.ops import transform
from shapely.geometry import Polygon

from ..widgets.find_iso_fields import FindIsoFieldWidget


class FindIsoField:
    def __init__(self, parent) -> None:
        self.parent = parent
        self.fifw = FindIsoFieldWidget()
        self.connect()
        self.current_polygon = ''
        self.fields = {}

    def connect(self):
        self.fifw.PBAddFolder.clicked.connect(self.open_input_folder)
        self.fifw.LWFields.itemClicked.connect(self.on_item_clicked)
        self.fifw.PBSaveField.clicked.connect(self.save_field)

    def run(self):
        self.fifw.show()
        if not self.parent.test_mode:
            self.fifw.exec_()

    def open_input_folder(self):
        """Opens a dialog and let the user select the folder where Taskdata are stored."""
        if self.parent.test_mode:
            path = './tests/test_data/TASKDATA3/'
        else:
            path = QtWidgets.QFileDialog.get(None, self.parent.tr("Open a taskdata"), '',
                                                              "Taskdata (TASKDATA.xml taskdata.xml)")[0]
        if path != '':
            self._populate_field_table(path)

    def _populate_field_table(self, file_path):
        root = self._get_xml_root(file_path)
        data = self._extract_coordinates(root)
        if len(data):
            QMessageBox.information(None, self.tr('Failure:'),
                                        self.tr('No partfields contour was found in the taskdata.xml'))
            return
        wkt_polygons = [(field_name, polygon.wkt) for field_name, polygon in data]
        self.fifw.LWFields.clear()
        for name, wkt in wkt_polygons:
            self.fields[name] = wkt
            self.fifw.LWFields.addItem(name)

    def _get_xml_root(self, file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        return root

    def _extract_coordinates(self, root):
        data = []
        for pfd in root.findall('.//PFD'):
            field_name = pfd.get('C')
            points = []
            for pnt in pfd.findall('.//PLN//LSG//PNT'):
                lat = float(pnt.get('C'))
                lon = float(pnt.get('D'))
                points.append((lon, lat))  # Note: WKT uses (lon, lat) format
            if points:
                data.append([field_name, Polygon(points)])
        return data

    def on_item_clicked(self, item):
        item_name = item.text()
        if item_name != '':
            self.load_wkt(self.fields[item_name])
            self.current_polygon = self.fields[item_name]


    def _transform_polygon_to_3857(self, polygon):
        # Define the source and target CRS
        source_proj = pyproj.CRS('EPSG:4326')
        target_proj = pyproj.CRS('EPSG:3857')

        # Define the transformation function
        project = pyproj.Transformer.from_crs(source_proj, target_proj, always_xy=True).transform

        # Transform the polygon
        transformed_polygon = transform(project, polygon)
        return transformed_polygon

    def _plot_polygon_on_map(self, polygon):
        polygon = self._transform_polygon_to_3857(polygon)
        # Calculate the bounding box of the polygon
        minx, miny, maxx, maxy = polygon.bounds

        # Create the map with the bounding box as the extent
        fig, ax = plt.subplots(figsize=(12, 9))
        gdf = gpd.GeoDataFrame({'geometry': [polygon]}, crs='EPSG:3857')
        
        # Plot the polygon
        gdf.plot(ax=ax, edgecolor='m', facecolor='none')

        # Add OpenStreetMap basemap
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom=12)

        # Set the extent to the bounding box with some padding
        padding = 0.15  # Adjust padding as needed
        ax.set_xlim(minx - (maxx - minx) * padding, maxx + (maxx - minx) * padding)
        ax.set_ylim(miny - (maxy - miny) * padding, maxy + (maxy - miny) * padding)
        ax.set_axis_off()
        return fig

    def load_wkt(self, polygon_wkt):
        polygon = wkt.loads(polygon_wkt)

        # Create the plot
        fig = self._plot_polygon_on_map(polygon)

        # Set up the FigureCanvas
        self.canvas = FigureCanvas(fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        # Check if the layout exists and remove the old canvas if it does
        layout = self.fifw.WShowField.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
            self.fifw.WShowField.setLayout(layout)
        else:
            # Remove the old canvas
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)

        # Add the new canvas to the layout
        layout.addWidget(self.canvas)

    def save_field(self):
        name = self.fifw.LEFieldName.text()
        if name == '':
            return False
        if self.current_polygon == '':
            return False
        sql = f"""Insert into fields (field_name, polygon) 
        VALUES ('{name}', st_geomfromtext('{self.current_polygon}', 4326))"""
        try:
            res = self.parent.db.execute_sql(sql, return_failure=True)
        except IntegrityError:
            if self.parent.test_mode:
                return False
            else:  
                QMessageBox.information(None, self.tr('Error:'),
                                        self.tr('Field name already exist, please select a new name'))
                return
        except InternalError as e:
            QMessageBox.information(None, self.tr('Error:'),
                                    str(e))
            return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.parent.dock_widget.LWFields)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)
