from typing import TYPE_CHECKING, Never, Self
if TYPE_CHECKING:
    import matplotlib.figure
    import pyproj.crs.crs
    import shapely.geometry.polygon
import os
import xml.etree.ElementTree as ET

import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pyproj
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication
from psycopg2 import IntegrityError, InternalError
from qgis.core import QgsTask
from shapely import wkt
from shapely.ops import transform
from shapely.geometry import Polygon, Point

from ..support_scripts.pyagriculture.agriculture import PyAgriculture
from ..widgets.find_iso_fields import FindIsoFieldWidget

class FindIsoField:
    def __init__(self: Self, parent, test_path:str = '') -> None:
        self.parent = parent
        self.fifw = FindIsoFieldWidget()
        self.connect()
        self.current_polygon = ''
        self.fields = {}
        self.path = test_path
        self.zoom_level = 17

    def connect(self: Self) -> None:
        """Connects the UI elements to their respective functions."""
        self.fifw.PBAddFolder.clicked.connect(self.open_input_folder)
        self.fifw.LWFields.itemClicked.connect(self.on_item_clicked)
        self.fifw.PBSaveField.clicked.connect(self.save_field)
        self.fifw.PBGetAdditionalData.clicked.connect(self.find_from_tasks)

    def disconnect(self: Self) -> None:
        self.fifw.PBAddFolder.clicked.disconnect()
        self.fifw.LWFields.itemClicked.disconnect()
        self.fifw.PBSaveField.clicked.disconnect(self.save_field)
        self.fifw.PBGetAdditionalData.clicked.connect(self.find_from_tasks)

    def run(self):
        """Shows the widget and executes it if not in test mode."""
        self.fifw.show()
        if not self.parent.test_mode:
            self.fifw.exec_()

    def open_input_folder(self: Self) -> None:
        """Opens a dialog and lets the user select the folder where Taskdata are stored."""
        if self.parent.test_mode:
            path = self.path
        else:
            path = QtWidgets.QFileDialog.getOpenFileName(None, self.parent.tr("Open a taskdata"), '',
                                                              "Taskdata (TASKDATA.xml taskdata.xml)")[0]
        if path != '':
            self._populate_field_table(path)

    def _populate_field_table(self: Self, file_path: str) -> bool|None:
        """Populates the field table with data from the provided file path."""
        self.path = file_path
        self.fifw.LSelectedFolder.setText(file_path)
        self.fifw.PBGetAdditionalData.setEnabled(True)
        root = self._get_xml_root(file_path)
        data = self._extract_coordinates(root)
        if len(data) == 0:
            if not self.parent.test_mode:
                QMessageBox.information(None, self.parent.tr('Warning'),
                                            self.parent.tr('No partfields contour was found in the taskdata.xml'))
            return False
        wkt_polygons = [(field_name, polygon.wkt) for field_name, polygon in data]
        self.fifw.LWFields.clear()
        for name, wkt in wkt_polygons:
            self.fields[name] = wkt
            self.fifw.LWFields.addItem(name)

    def _get_xml_root(self: Self, file_path: str) -> ET.Element:
        """Parses the XML file and returns the root element."""
        tree = ET.parse(file_path)
        root = tree.getroot()
        return root

    def _extract_coordinates(self: Self, root: ET.Element) -> list[list[str]|Never]:
        """Extracts coordinates from the XML root and returns them as a list of field names and polygons."""
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

    def find_from_tasks(self: Self) -> None:
        """Finds additional data from Pyagriculture tasks"""
        self.py_agri = PyAgriculture(os.path.dirname(self.path))
        if self.parent.test_mode is False:
            task = QgsTask.fromFunction('Decode binary data', self.py_agri.gather_data, 
                                        most_important=None,
                                        on_finished=self.populate_field_list2)
            self.parent.tsk_mngr.addTask(task)
        else:
            self.py_agri.gather_data(qtask='debug', most_important=None)
            self.populate_field_list2()

    def populate_field_list2(self: Self, res: None=None, 
                             values: None=None) -> None:
        """Populates the field list based on the pyagri tasks."""
        self.fifw.LWFields.clear()
        for i, task in enumerate(self.py_agri.tasks):
            task['geometry'] = task.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
            gdf = gpd.GeoDataFrame(task, geometry='geometry')
            gdf.set_crs(epsg=4326, inplace=True)
            convex_hull = gdf.unary_union.convex_hull
            self.fields[f'Task {i}'] = convex_hull.wkt
            self.fifw.LWFields.addItem(f'Task {i}')

    def on_item_clicked(self: Self, item: QListWidgetItem) -> None:
        """Handles the event when an item in the field list is clicked."""
        item_name = item.text()
        if self.current_polygon != '':
            self.save_updated_polygon()
        if item_name != '':
            self.load_wkt(self.fields[item_name])
            self.current_polygon = self.fields[item_name]

    def _set_new_crs(self: Self, 
                     polygon: "shapely.geometry.polygon.Polygon", 
                     source_proj: "pyproj.crs.crs.CRS" = pyproj.CRS('EPSG:4326'), 
                     target_proj: "pyproj.crs.crs.CRS" = pyproj.CRS('EPSG:3857')
                     ) -> "shapely.geometry.polygon.Polygon":
        """Transforms the polygon to a new coordinate reference system."""
        project = pyproj.Transformer.from_crs(source_proj, target_proj, always_xy=True).transform
        transformed_polygon = transform(project, polygon)
        return transformed_polygon

    def _plot_polygon_on_map(self: Self, 
                             polygon: "shapely.geometry.polygon.Polygon"
                             ) -> "matplotlib.figure.Figure":
        """Plots the polygon on a map with interactivity for zoom and node editing."""
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
        ax.set_ylim(miny - (maxy - miny) * padding)
        ax.set_axis_off()
        fig.canvas.mpl_connect('scroll_event', self.zoom)
        self.draggable_points = []
        for x, y in polygon.exterior.coords:
            point, = ax.plot(x, y, 'ro', picker=5)
            self.draggable_points.append(point)
        fig.canvas.mpl_connect('pick_event', self.on_pick)
        fig.canvas.mpl_connect('motion_notify_event', self.on_motion)
        return fig

    def zoom(self, event):
        """Handles zooming in and out on the map."""
        ax = event.inaxes
        if ax is None:
            return
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        x_range = (x_max - x_min) * 0.1
        y_range = (y_max - y_min) * 0.1
        if event.button == 'up':
            ax.set_xlim([x_min + x_range, x_max - x_range])
            ax.set_ylim([y_min + y_range, y_max - y_range])
        elif event.button == 'down':
            ax.set_xlim([x_min - x_range, x_max + x_range])
            ax.set_ylim([y_min - y_range, y_max + y_range])
        ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=self.zoom_level)
        ax.figure.canvas.draw()

    def on_pick(self, event):
        """Handles the event when a point on the map is picked for dragging."""
        self.dragging_point = event.artist
        self.dragging_point.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        self.canvas.mpl_connect('button_release_event', self.on_release)

    def on_motion(self, event):
        """Handles the motion event for dragging points on the map."""
        if not hasattr(self, 'dragging_point'):
            return
        if self.dragging_point is None:
            return
        if event.inaxes is None or event.inaxes != self.dragging_point.axes:
            return
        self.dragging_point.set_xdata(event.xdata)
        self.dragging_point.set_ydata(event.ydata)
        self.canvas.restore_region(self.background)
        self.dragging_point.axes.draw_artist(self.dragging_point)
        self.canvas.blit(self.dragging_point.axes.bbox)
        new_coords = [(point.get_xdata()[0], point.get_ydata()[0]) for point in self.draggable_points]
        self.polygon_patch.set_xy(new_coords)
        self.canvas.draw()

    def on_release(self, event):
        """Handles the event when a dragged point is released."""
        if not hasattr(self, 'dragging_point'):
            return
        self.dragging_point.set_animated(False)
        self.dragging_point = None
        self.canvas.draw()

    def load_wkt(self: Self, polygon_wkt: str) -> None:
        """Loads a polygon from WKT and plots it on the map."""
        polygon = wkt.loads(polygon_wkt)
        fig = self._plot_polygon_on_map(polygon)
        self.canvas = FigureCanvas(fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = self.fifw.WShowField.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout()
            self.fifw.WShowField.setLayout(layout)
        else:
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)
        layout.addWidget(self.canvas)

    def save_updated_polygon(self: Self) -> None:
        """Saves the updated polygon coordinates."""
        new_coords = [(point.get_xdata()[0], point.get_ydata()[0]) for point in self.draggable_points]
        new_polygon = Polygon(new_coords)
        for key, value in self.fields.items():
            if value == self.current_polygon:
                new_wkt = self._set_new_crs(new_polygon, source_proj = pyproj.CRS('EPSG:3857'), 
                                                          target_proj = pyproj.CRS('EPSG:4326'))
                self.fields[key] = new_wkt.wkt
                break
        self.current_polygon = new_wkt.wkt

    def save_field(self: Self) -> None:
        """Saves the current field to the database."""
        self.save_updated_polygon()
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
