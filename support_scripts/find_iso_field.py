from typing import TYPE_CHECKING, Never, Self
import os
import xml.etree.ElementTree as ET  # nosec B405

import matplotlib
matplotlib.use('Agg')
if TYPE_CHECKING:
    import matplotlib.figure
    import pyproj.crs.crs
    import shapely.geometry.polygon
import contextily as ctx
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import pyproj
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMessageBox, QListWidgetItem, QApplication, QSizePolicy, QVBoxLayout, QFileDialog, QLabel
from qgis.PyQt.QtGui import QMovie, QColor
from psycopg2 import IntegrityError
from qgis.core import QgsTask
from shapely import wkt
from shapely.ops import transform
from shapely.geometry import Point, Polygon

from ..support_scripts.pyagriculture.agriculture import PyAgriculture
from ..widgets.find_iso_fields import FindIsoFieldWidget
from .notifier import report_warning, report_error
from .notifier import log as gdf_log
from ..support_scripts.qt_data import _check_state, _item_flag


def get_auto_zoom_level(minx, miny, maxx, maxy, max_zoom=17, min_zoom=10):
    """Estimate a suitable zoom level for the given bounds in meters (EPSG:3857)."""
    width = abs(maxx - minx)
    # These thresholds are tuned for Web Mercator (meters)
    if width < 100:         # < 100 m
        return max_zoom
    elif width < 1000:      # < 1 km
        return max_zoom - 2
    elif width < 10000:     # < 10 km
        return max_zoom - 4
    elif width < 100000:    # < 100 km
        return max_zoom - 6
    else:
        return min_zoom


def remove_invalid_points(gdf):
    """Removes rows with invalid latitude and longitude values from the GeoDataFrame."""
    # Define valid ranges for latitude and longitude
    valid_lat_range = (-90, 90)
    valid_lon_range = (-180, 180)

    # Filter out rows with invalid latitude and longitude values
    valid_gdf = gdf[
        (gdf['latitude'].between(*valid_lat_range)) &
        (gdf['longitude'].between(*valid_lon_range)) &
        ~((gdf['latitude'] == 0) & (gdf['longitude'] == 0))
    ]

    return valid_gdf

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
            self.fifw.exec()

    def open_input_folder(self: Self) -> None:
        """Opens a dialog and lets the user select the folder where Taskdata are stored."""
        if self.parent.test_mode:
            path = self.path
        else:
            path = QFileDialog.getOpenFileName(None, self.parent.tr("Open a taskdata"), '',
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
                report_warning(self.parent.tr('No partfields contour was found in the taskdata.xml'))
            return False
        wkt_polygons = [(field_name, polygon.wkt) for field_name, polygon in data]
        self.fifw.LWFields.clear()
        existing_fields = self._existing_fields()
        for name, wkt_str in wkt_polygons:
            self.fields[name] = wkt_str
            self._add_field_list_item(name, wkt_str, existing_fields)

    def _existing_fields(self: Self) -> "list[tuple[str, shapely.geometry.polygon.Polygon]]":
        """Returns (name, polygon) for every field already saved in the database."""
        rows = self.parent.db.execute_and_return("SELECT field_name, ST_AsText(polygon) FROM fields")
        if not isinstance(rows, (list, tuple)):
            return []
        existing = []
        for name, wkt_str in rows:
            if not wkt_str:
                continue
            try:
                existing.append((name, wkt.loads(wkt_str)))
            except Exception:
                gdf_log.warning(
                    f"Skipping field '{name}': stored polygon is not valid WKT ({wkt_str!r}).")
                continue
        return existing

    def _matching_existing_field(self: Self, candidate_wkt: str,
                                 existing_fields: "list[tuple[str, shapely.geometry.polygon.Polygon]]",
                                 min_overlap: float=0.5) -> str|None:
        """Returns the name of an already-saved field whose polygon substantially
        overlaps the candidate (by area), regardless of what either is named, or
        None if there isn't one."""
        try:
            candidate = wkt.loads(candidate_wkt)
        except Exception:
            return None
        if candidate.area == 0:
            return None
        for name, polygon in existing_fields:
            if not candidate.intersects(polygon):
                continue
            if candidate.intersection(polygon).area / candidate.area >= min_overlap:
                return name
        return None

    def _add_field_list_item(self: Self, name: str, wkt_str: str,
                             existing_fields: "list[tuple[str, shapely.geometry.polygon.Polygon]]") -> None:
        """Adds a field to LWFields, greying it out and flagging it with a
        tooltip if it substantially overlaps a field that's already saved."""
        item = QListWidgetItem(name)
        match = self._matching_existing_field(wkt_str, existing_fields)
        if match is not None:
            item.setForeground(QColor('gray'))
            item.setToolTip(self.parent.tr('This overlaps the already-added field "{name}"').format(name=match))
        self.fifw.LWFields.addItem(item)

    def _get_xml_root(self: Self, file_path: str) -> ET.Element:
        """Parses the XML file and returns the root element.

        Handles both ISO 11783-10 layouts: a single self-contained
        TASKDATA.xml, and a "split" dataset where TASKDATA.xml is just an
        index of ``<XFR A="PFD00000" .../>`` references to separate
        per-type files (PFD00000.XML, TSK00000.XML, ...) sitting alongside
        it - some FMIS/terminal software (e.g. Topcon) exports this way.
        In the split case the actual partfield boundary lives in the
        referenced PFD file, invisible to a caller that only looks at what
        was picked - so this transparently merges each referenced file's
        elements into a single synthetic root, keeping every other method
        that searches the returned root (e.g. _extract_coordinates's
        ``root.findall('.//PFD')``) unaware anything special happened."""
        tree = ET.parse(file_path)  # nosec B314 - user-chosen local ISO 11783 XML
        root = tree.getroot()
        xfr_refs = root.findall('XFR')
        if not xfr_refs:
            return root
        directory = os.path.dirname(file_path)
        merged = ET.Element(root.tag, root.attrib)
        for child in root:
            if child.tag != 'XFR':
                merged.append(child)
        for xfr in xfr_refs:
            ref_path = self._resolve_split_file(directory, xfr.get('A'))
            if ref_path is None:
                continue
            try:
                ref_root = ET.parse(ref_path).getroot()  # nosec B314 - same trusted local dataset
            except ET.ParseError:
                continue
            for child in ref_root:
                merged.append(child)
        return merged

    @staticmethod
    def _resolve_split_file(directory: str, ref_name: str|None) -> str|None:
        """Finds the file an ``<XFR A="...">`` reference points to, next to
        the taskdata file - case-insensitively, since ``.XML``/``.xml``
        both appear in the wild across different exporters."""
        if not ref_name:
            return None
        for ext in ('.XML', '.xml'):
            candidate = os.path.join(directory, ref_name + ext)
            if os.path.isfile(candidate):
                return candidate
        return None

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
        self.show_loading_animation() # <-- Show spinner before starting task
        #self.parent.tsk_mngr.addTask(self.loading_tsk)
        if self.parent.test_mode is False:
            task = QgsTask.fromFunction('Decode binary data', self.py_agri.gather_data, 
                                        most_importants=[],
                                        on_finished=self.populate_field_list2)
            self.parent.tsk_mngr.addTask(task)
        else:
            self.py_agri.gather_data(qtask='debug', most_importants=[])
            self.populate_field_list2()

    def clear_layout(self):
        """Remove all widgets from a given layout."""
        layout = self.fifw.WShowField.layout()
        # Stop *and* tear down the loading animation if present. On Windows,
        # QMovie keeps its backing img/loading.gif open at the OS level
        # until the QMovie object itself is destroyed - stop() alone only
        # pauses playback, it doesn't release that file lock. Left alive,
        # that lock persists for the rest of the QGIS session (every
        # completed "Find ISO field" search leaks one), which is why
        # `pb_tool deploy` fails to overwrite img/loading.gif with a
        # PermissionError until QGIS is fully restarted.
        if hasattr(self, "loading_label"):
            self.loading_label.setMovie(None)
        if hasattr(self, "movie"):
            self.movie.stop()
            self.movie.deleteLater()
            del self.movie
        if hasattr(self, "loading_label") and self.loading_label in [layout.itemAt(i).widget() for i in range(layout.count())]:
            layout.removeWidget(self.loading_label)
            self.loading_label.deleteLater()
            del self.loading_label
        if layout is not None:
            for i in reversed(range(layout.count())):
                widget = layout.itemAt(i).widget()
                if widget is not None:
                    widget.setParent(None)

    def show_loading_animation(self: Self) -> None:
        """Show a spinning/loading animation in the canvas area."""
        layout = self.fifw.WShowField.layout()
        if layout is None:
            layout = QVBoxLayout()
            self.fifw.WShowField.setLayout(layout)
        else:
            self.clear_layout()
        # Create and add the loading animation
        print('run')
        self.loading_label = QLabel()
        gif_path = os.path.join(os.path.dirname(__file__),"..", "img", "loading.gif")
        if not os.path.exists(gif_path):
            self.loading_label.setText("Loading...")
        else:
            self.movie = QMovie(gif_path)
            self.loading_label.setMovie(self.movie)
            self.movie.start()
        layout.addWidget(self.loading_label)
        
    def populate_field_list2(self: Self, res: None=None, values: None=None) -> None:
        """Populates the field list based on the pyagri tasks."""
        self.clear_layout()
        self.fifw.LWFields.clear()
        existing_fields = self._existing_fields()
        for i, task in enumerate(self.py_agri.tasks):
            if 'longitude' not in task.columns:
                try:
                    extent = task.total_bounds
                    convex_hull = Polygon([
                        (extent[0], extent[1]),
                        (extent[0], extent[3]),
                        (extent[2], extent[3]),
                        (extent[2], extent[1]),
                        (extent[0], extent[1])
                    ])
                except Exception:  # nosec B112
                    continue
            else:
                task['geometry'] = task.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
                gdf = gpd.GeoDataFrame(task, geometry='geometry')
                gdf.set_crs(epsg=4326, inplace=True)
                gdf = remove_invalid_points(gdf)
                convex_hull = gdf.union_all().convex_hull

            # Only create a new polygon if there are at least 3 points left
            if len(convex_hull.exterior.coords) < 3:
                continue  # Not enough points for a valid polygon

            name = task.attrs.get('task_name', f'Task {i}')
            self.fields[name] = convex_hull.wkt
            self._add_field_list_item(name, convex_hull.wkt, existing_fields)

    def on_item_clicked(self: Self, item: QListWidgetItem) -> None:
        """Handles the event when an item in the field list is clicked."""
        item_name = item.text()
        self.show_loading_animation()
        if self.current_polygon != '':
            self.save_updated_polygon()
        if item_name != '':
            self.load_wkt(polygon_wkt=self.fields[item_name])
            #tsk = QgsTask.fromFunction('Load polygon', self.load_wkt,
            #                            polygon_wkt=self.fields[item_name],
            #                            on_finished=None)
            #self.parent.tsk_mngr.addTask(tsk)
            self.current_polygon = self.fields[item_name]
            self.fifw.LEFieldName.setText(item_name)

    def _set_new_crs(self: Self, 
                     polygon: "shapely.geometry.polygon.Polygon", 
                     source_proj: "pyproj.crs.crs.CRS" = pyproj.CRS('EPSG:4326'), 
                     target_proj: "pyproj.crs.crs.CRS" = pyproj.CRS('EPSG:3857')
                     ) -> "shapely.geometry.polygon.Polygon":
        """Transforms the polygon to a new coordinate reference system."""
        project = pyproj.Transformer.from_crs(source_proj, target_proj, always_xy=True).transform
        transformed_polygon = transform(project, polygon)
        return transformed_polygon

    def _plot_polygon_on_map(self: Self, polygon: "shapely.geometry.polygon.Polygon") -> "matplotlib.figure.Figure":
        """Plots the polygon or point on a map with interactivity for zoom and node editing."""
        if polygon.is_empty:
            fig, ax = plt.subplots(figsize=(12, 9))
            ax.text(0.5, 0.5, 'No data points were found', horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=15)
            ax.set_axis_off()
            return fig

        # Handle Polygon geometry as before
        polygon = self._set_new_crs(polygon)
        minx, miny, maxx, maxy = polygon.bounds

        # Calculate zoom level automatically
        zoom = get_auto_zoom_level(minx, miny, maxx, maxy, max_zoom=17, min_zoom=10)

        fig, ax = plt.subplots(figsize=(12, 9))
        patch_collection = ax.fill(*polygon.exterior.xy, edgecolor='m', facecolor='none')
        if patch_collection:
            self.polygon_patch = patch_collection[0]

        # Add the basemap with the calculated zoom
        if not self.parent.test_mode:
            ctx.add_basemap(ax, source=ctx.providers.Esri.WorldImagery, zoom=zoom)

        # Set the axis limits with padding
        padding = 0.15
        ax.set_xlim(minx - (maxx - minx) * padding, maxx + (maxx - minx) * padding)
        ax.set_ylim(miny - (maxy - miny) * padding)
        ax.set_axis_off()

        # Add interactivity
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
        if event.button == 'up':  # Zoom in
            ax.set_xlim([x_min + x_range, x_max - x_range])
            ax.set_ylim([y_min + y_range, y_max - y_range])
        elif event.button == 'down':  # Zoom out
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
        if self.dragging_point is not None:
            self.dragging_point.set_animated(False)
        self.dragging_point = None
        self.canvas.draw()

    def load_wkt(self: Self, polygon_wkt: str) -> None:
        """Loads a polygon from WKT and plots it on the map."""
        polygon = wkt.loads(polygon_wkt)
        self.clear_layout()
        fig = self._plot_polygon_on_map(polygon)
        self.canvas = FigureCanvas(fig)  # Link the figure to the FigureCanvas
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Add the canvas to the layout
        layout = self.fifw.WShowField.layout()
        if layout is None:
            layout = QVBoxLayout()
            self.fifw.WShowField.setLayout(layout)
        else:
            # Clear the existing layout
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
                new_wkt = self._set_new_crs(new_polygon, source_proj=pyproj.CRS('EPSG:3857'), target_proj=pyproj.CRS('EPSG:4326'))
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
        sql = ("INSERT INTO fields (field_name, polygon)"
               " VALUES (%s, st_geomfromtext(%s, 4326))")
        res = self.parent.db.execute_sql(
            sql, params=(name, self.current_polygon), return_failure=True)
        if not res[0]:
            if self.parent.test_mode:
                return False
            elif res[1] is IntegrityError:
                report_warning(self.parent.tr('Field name already exist, please select a new name'))
                return False
            else:
                report_error(str(res[2]), detail=str(res[2]))
                return False
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.parent.dock_widget.LWFields)
        item.setFlags(item.flags() | _item_flag('ItemIsUserCheckable'))
        item.setCheckState(_check_state('Unchecked'))
        return True
