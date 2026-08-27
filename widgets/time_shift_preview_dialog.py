from typing import Self

from qgis.core import (QgsFeature, QgsField, QgsGeometry, QgsPointXY,
                       QgsVectorLayer, QgsLineSymbol, QgsMarkerSymbol,
                       QgsGraduatedSymbolRenderer, QgsRendererRange,
                       QgsRectangle)
from qgis.PyQt.QtCore import QVariant, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
                                 QDoubleSpinBox, QHBoxLayout)
from qgis.gui import QgsMapCanvas, QgsMapToolPan
from ..support_scripts.time_shift import TimeShiftMatcher

COLORS = ['#006837', '#1a9850', '#66bd63', '#d9ef8b',
          '#fee08b', '#fdae61', '#d73027']
REDRAW_DELAY_MS = 150


class TimeShiftPreviewDialog(QDialog):
    def __init__(self: Self, rows: list[list[str]], source_indexes: list[int|None],
                 latitude_index: int, longitude_index: int,
                 yield_index: int|None = None,
                 field_wkt: str|None = None, field_name: str = '', parent=None,
                 timestamps: list|None = None, date_index: int = 0,
                 delay_seconds: float = 0.0, strategy: str = 'nearest',
                 tolerance_seconds: float = 1.0) -> None:
        super().__init__(parent)
        self.setWindowTitle('Time shift preview map')
        self.resize(900, 650)
        self.rows = rows
        self.timestamps = timestamps
        self.date_index = date_index
        self.latitude_index = latitude_index
        self.longitude_index = longitude_index
        self.yield_index = yield_index
        self.field_wkt = field_wkt
        self.field_name = field_name
        self.strategy = strategy
        self.tolerance_seconds = tolerance_seconds
        # Coordinates and harvest values never change with the delay, only the
        # row they are read from does, so parse the text once and reuse it.
        self.geometries = []
        for index, row in enumerate(rows):
            point = self._point(row, latitude_index, longitude_index)
            if point is not None:
                self.geometries.append((index, QgsGeometry.fromPointXY(point)))
        self.values = None if yield_index is None else [
            self._number(row[yield_index]) if yield_index < len(row) else None
            for row in rows]
        self.matcher = None
        self.matcher_source = None
        self.applied_delay = delay_seconds
        self.value_range = []
        self.canvas = QgsMapCanvas(self)
        self.canvas.setCanvasColor(QColor('white'))
        self.pan_tool = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.pan_tool)
        self.legend = QLabel()
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(-86400, 86400)
        self.delay_spin.setDecimals(3)
        self.delay_spin.setSingleStep(1)
        self.delay_spin.setSuffix(' s')
        self.delay_spin.setValue(delay_seconds)
        self.layers = self._create_layers(field_wkt)
        self._populate_layers(source_indexes)
        self.canvas.setLayers(self.layers)
        self.canvas.refresh()
        extent = self._full_extent()
        if extent is not None:
            self.canvas.setExtent(extent)
            self.canvas.zoomByFactor(1.15)
        self._update_legend()
        # Typing in the spin box or holding its arrows fires several changes per
        # second, only the last one is worth a redraw.
        self.redraw_timer = QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(REDRAW_DELAY_MS)
        self.redraw_timer.timeout.connect(
            lambda: self._delay_changed(self.delay_spin.value()))
        self.delay_spin.valueChanged.connect(lambda _: self.redraw_timer.start())
        if hasattr(QDialogButtonBox, 'Close'):
            close_button = QDialogButtonBox.Close
        else:
            close_button = QDialogButtonBox.StandardButton.Close
        buttons = QDialogButtonBox(close_button)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Delay:'))
        controls.addWidget(self.delay_spin)
        controls.addStretch()
        layout.addLayout(controls)
        layout.addWidget(self.legend)
        layout.addWidget(self.canvas)
        layout.addWidget(buttons)

    def _delay_changed(self, delay_seconds: float) -> None:
        if self.timestamps is None or delay_seconds == self.applied_delay:
            return
        if self.matcher is None or self.matcher_source is not self.timestamps:
            self.matcher = TimeShiftMatcher(self.timestamps)
            self.matcher_source = self.timestamps
        self.applied_delay = delay_seconds
        self._populate_layers(self.matcher.source_indexes(
            delay_seconds, self.strategy, self.tolerance_seconds))
        self.canvas.refresh()
        self._update_legend()

    def _full_extent(self) -> QgsRectangle|None:
        boundary_extent = self.layers[0].extent() if self.field_wkt else None
        if boundary_extent is not None and not boundary_extent.isEmpty():
            return QgsRectangle(boundary_extent)
        point_extents = [layer.extent() for layer in self._point_layers()
                         if not layer.extent().isEmpty()]
        if not point_extents:
            return None
        extent = QgsRectangle(point_extents[0])
        for point_extent in point_extents[1:]:
            extent.combineExtentWith(point_extent)
        return None if extent.isEmpty() else extent

    def _point_layers(self) -> list:
        """Draw order, topmost first. A row carrying a value always wins over a
        row that carries none - a sparse export logs both at the same spot, and
        the value is what actually reaches the database."""
        return [self.target_layer, self.zero_layer, self.unmatched_layer,
                self.blank_layer]

    def _update_legend(self) -> None:
        value_text = (f'Harvest range: {min(self.value_range):.1f} - '
                      f'{max(self.value_range):.1f} | ' if self.value_range else '')
        self.legend.setText(
            f'Field: {self.field_name} | Delay: {self.delay_spin.value():.3f} s | '
            f'Points: {self.target_layer.featureCount() + self.zero_layer.featureCount()} | '
            f'{value_text}'
            f'Zero: {self.zero_layer.featureCount()} | '
            f'Outside the time window: {self.unmatched_layer.featureCount()} | '
            f'No value, will not be imported: {self.blank_layer.featureCount()}\n'
            'Green to red: harvest value | Blue: zero | Red: no measurement within '
            'the max difference | Small grey: the matched row has an empty value '
            'column, so the import drops it | Drag to pan')

    @staticmethod
    def _point(row: list[str], latitude_index: int, longitude_index: int):
        try:
            latitude = float(row[latitude_index].strip().strip('"').replace(',', '.'))
            longitude = float(row[longitude_index].strip().strip('"').replace(',', '.'))
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return None
            return QgsPointXY(longitude, latitude)
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _number(value: str):
        try:
            cleaned = value.strip().strip('"').replace(' ', '').replace(' ', '')
            return float(cleaned.replace(',', '.'))
        except (AttributeError, TypeError, ValueError):
            return None

    def _create_layers(self, field_wkt) -> list:
        """Build the empty layers once, every delay change only refills them."""
        self.target_layer = QgsVectorLayer('Point?crs=EPSG:4326', 'Shifted values', 'memory')
        self.zero_layer = QgsVectorLayer('Point?crs=EPSG:4326', 'Zero harvest', 'memory')
        self.unmatched_layer = QgsVectorLayer('Point?crs=EPSG:4326', 'No matching value', 'memory')
        self.blank_layer = QgsVectorLayer('Point?crs=EPSG:4326', 'Blank value', 'memory')
        if self.values is not None:
            for layer in (self.target_layer, self.zero_layer):
                layer.dataProvider().addAttributes([QgsField('harvest', QVariant.Double)])
                layer.updateFields()
        self.unmatched_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple(
            {'color': '#d7191c', 'size': '4', 'outline_color': '#7f1012'}))
        # Kept small and pale: these rows hold nothing and never reach the
        # database, they are drawn only to show where they sit.
        self.blank_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple(
            {'color': '#d0d0d0', 'size': '2.5', 'outline_color': '#a0a0a0'}))
        self.zero_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple(
            {'color': '#3182bd', 'size': '4', 'outline_color': '#173f5f'}))
        result = self._point_layers()
        if field_wkt:
            result.insert(0, self._create_boundary_layer(field_wkt))
        return result

    @staticmethod
    def _create_boundary_layer(field_wkt: str):
        boundary = QgsVectorLayer('LineString?crs=EPSG:4326', 'Field boundary', 'memory')
        field_geometry = QgsGeometry.fromWkt(field_wkt)
        rings = []
        if field_geometry.isMultipart():
            for polygon in field_geometry.asMultiPolygon():
                rings.extend(polygon)
        else:
            rings = field_geometry.asPolygon()
        boundary_features = []
        for ring in rings:
            if len(ring) > 1:
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPolylineXY(ring))
                boundary_features.append(feature)
        boundary.dataProvider().addFeatures(boundary_features)
        boundary.updateExtents()
        boundary.renderer().setSymbol(QgsLineSymbol.createSimple({
            'color': '#4d8c3a', 'width': '0.8'}))
        return boundary

    def _populate_layers(self, source_indexes: list[int|None]) -> None:
        target_features, zero_features = [], []
        unmatched_features, blank_features = [], []
        target_fields = self.target_layer.fields()
        zero_fields = self.zero_layer.fields()
        values = []
        for index, geometry in self.geometries:
            source_index = source_indexes[index]
            if source_index is None:
                unmatched_features.append(self._feature(geometry))
                continue
            if self.values is None:
                target_features.append(self._feature(geometry))
                continue
            value = self.values[source_index]
            if value == 0:
                zero_features.append(self._feature(geometry, zero_fields, 0.0))
            elif value is None:
                # A row was found, its value column just holds nothing usable.
                blank_features.append(self._feature(geometry))
            else:
                target_features.append(self._feature(geometry, target_fields, value))
                values.append(value)
        for layer, features in ((self.target_layer, target_features),
                                (self.zero_layer, zero_features),
                                (self.unmatched_layer, unmatched_features),
                                (self.blank_layer, blank_features)):
            provider = layer.dataProvider()
            if layer.featureCount():
                provider.truncate()
            provider.addFeatures(features)
            layer.updateExtents()
            layer.triggerRepaint()
        self.value_range = values
        self._apply_target_renderer(values)

    @staticmethod
    def _feature(geometry, fields=None, value=None) -> QgsFeature:
        feature = QgsFeature() if fields is None else QgsFeature(fields)
        feature.setGeometry(geometry)
        if fields is not None:
            feature.setAttribute('harvest', value)
        return feature

    def _apply_target_renderer(self, values: list) -> None:
        if not values:
            self.target_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple(
                {'color': '#2b83ba', 'size': '3.5', 'outline_color': '#123b55'}))
            return
        minimum, maximum = min(values), max(values)
        if minimum == maximum:
            maximum = minimum + 1
        ranges = []
        step = (maximum - minimum) / len(COLORS)
        for index, color in enumerate(COLORS):
            lower = minimum + index * step
            upper = maximum if index == len(COLORS) - 1 else minimum + (index + 1) * step
            symbol = QgsMarkerSymbol.createSimple({
                'color': color, 'size': '4', 'outline_color': '#303030'})
            ranges.append(QgsRendererRange(lower, upper, symbol,
                                           f'{lower:.1f} - {upper:.1f}'))
        self.target_layer.setRenderer(QgsGraduatedSymbolRenderer('harvest', ranges))
