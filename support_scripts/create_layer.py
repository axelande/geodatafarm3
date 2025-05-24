from typing import TYPE_CHECKING, Self
if TYPE_CHECKING:
    import geodatafarm.database_scripts.db
    import pytest_qgis.qgis_interface
    import qgis._core
from qgis.core import QgsSymbol, Qgis, QgsMarkerSymbol, QgsRendererRange,\
    QgsLineSymbol, QgsFillSymbol, QgsGraduatedSymbolRenderer, \
    QgsProject, QgsRendererCategory, QgsCategorizedSymbolRenderer, \
    QgsTextFormat, QgsPalLayerSettings, QgsTextBufferSettings, \
    QgsVectorLayerSimpleLabeling, QgsRasterLayer, QgsCoordinateReferenceSystem, \
    QgsRectangle
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QMessageBox
import numpy as np
import matplotlib.pyplot as plt
from ..support_scripts import isint
from ..support_scripts.RG import rg
__author__ = 'Axel'


def set_label(layer: "qgis._core.QgsVectorLayer", 
              field_label: str) -> None:
    """Function that sets the label to a field value. Inspiration found at:
    https://gis.stackexchange.com/questions/277106/loading-labels-from-python-script-in-qgis

    Parameters
    ----------
    layer: QgsVectorLayer
        valid qgis layer.
    field_label: str
        The label of the field

    """
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()

    text_format.setFont(QFont("Arial", 12))
    text_format.setSize(12)

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(0.10)
    buffer_settings.setColor(QColor("black"))

    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)
    layer_settings.fieldName = field_label
    # layer_settings.placement = 4

    layer_settings.enabled = True

    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)
    layer.triggerRepaint()


def set_zoom(iface: "pytest_qgis.qgis_interface.QgisInterface", 
             extra_extent: int) -> None:
    """Sets the zoom level to include all layers (excluding tiles layer) with some extra extent

    Parameters
    ----------
    iface: QGIS interface
        The QGIS iface module.
    extra_extent: float
        How much extra space around the layers eg. 1.1 is 10% extra
    """
    zoom_extent = QgsRectangle()
    for layer in QgsProject.instance().mapLayers().values():
        if 'xyz&url' not in layer.source():
            zoom_extent.combineExtentWith(layer.extent())
    if zoom_extent.center().x() != 0.0:
        wgsCRS = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        QgsProject.instance().setCrs(wgsCRS)
        zoom_extent.scale(extra_extent)
        iface.mapCanvas().setExtent(zoom_extent)
        iface.mapCanvas().refresh()
        wgsCRS = QgsCoordinateReferenceSystem.fromEpsgId(3857)
        QgsProject.instance().setCrs(wgsCRS)


def add_background() -> None:
    """Check if there are no other tiles present on the canvas then
    adds a google satellite as a background map."""
    source_found = False
    for layer in QgsProject.instance().mapLayers().values():
        if 'xyz&url' in layer.source():
            source_found = True
    if not source_found:
        url_with_params = 'type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0'
        rlayer = QgsRasterLayer(url_with_params, 'Google satellite', 'wms')
        rlayer.isValid()
        QgsProject.instance().addMapLayer(rlayer)


def hist_edges_equal(x, nbin):
    """Histogram with equal number of points in each bin, inspired by:
     https://stackoverflow.com/questions/39418380/histogram-with-equal-number-of-points-in-each-bin

    Parameters
    ----------
    x: list
        list of all values to put in the histogram
    nbin: int
        Number of bins to use in the histogram

    Returns
    -------
    bins
        Returns the second parameter (bins) in plt.hist
    """
    npt = len(x)
    return np.interp(np.linspace(0, npt, nbin + 1),
                     np.arange(npt),
                     np.sort(x))


class CreateLayer:
    def __init__(self: Self, 
                 db: "geodatafarm.database_scripts.db.DB", 
                 dock_widget: None=None) -> None:
        """Creates a layer with color coded attributes"""
        self.db = db
        self.dock_widget = dock_widget

    def _apply_symbology_fixed_divisions(self, layer, field, tbl_name, schema,
                                         min_v, max_v, steps):
        """Finds the amount of levels that is necessary to describe the layer,
        a maximum of 20 different levels is set.

        Parameters
        ----------
        layer: QgsVectorLayer
        field: str
        tbl_name: str
        schema: str
        min_v: float
        max_v: float
        steps: int
        """
        str_values = False
        if min_v is not None and max_v is not None:
            distinct_values = list(np.arange(min_v, max_v, steps))
        elif not str_values:
            distinct = self.db.get_distinct(tbl_name, field, schema)
            if len(distinct) == 1:
                return
            distinct_values = []
            distinct_count = []
            for value, count in distinct:
                if value is None:
                    continue
                
                if isint(value):
                    value = int(float(value))
                distinct_values.append(value)
                distinct_count.append(count)
            if len(distinct_values) > 20:
                distinct_values.sort()
                temp_list = []
                for val in range(0, len(distinct_values), int(np.floor(len(distinct_values)/20))):
                    temp_list.append(distinct_values[val])
                if temp_list[-1] != distinct_values[-1]:
                    temp_list.append(distinct_values[-1])
                distinct_values = temp_list
        if isinstance(distinct_values[0], str):
            str_values = True
        colors = self._create_colors(len(distinct_values))
        if len(distinct_values) > 19 and not str_values:
            range_list = []
            for i in range(len(distinct_values) - 1):
                red, green, blue = colors[i]
                range_list.append(self._make_symbology(layer, distinct_values[i],
                                                     distinct_values[i + 1],
                                                     str(distinct_values[i]) + ' - ' + str(distinct_values[i + 1]),
                                                     QColor(int(red*255),int(green*255), int(blue*255), 128) ) )
            renderer = QgsGraduatedSymbolRenderer(field, range_list)
            renderer.setMode(QgsGraduatedSymbolRenderer.Custom )
        else:
            categories = []
            for i in range(len(distinct_values)):
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                red, green, blue = colors[i]
                symbol.setColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                symbol.symbolLayer(0).setStrokeColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                category = QgsRendererCategory(str(distinct_values[i]), symbol, str(distinct_values[i]))
                categories.append(category)
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            #renderer.setMode(QgsCategorizedSymbolRenderer.Custom)
        layer.setRenderer(renderer)

    def _make_symbology(self, layer, min , max, title, color):
        """Creates the symbols and sets the coloring of the layer

        Parameters
        ----------
        layer: QgsVectorLayer
        min: float
        max: float
        title: str
        color: QColor

        Returns
        -------
        QgsRendererRange
        """
        symbol = self._validated_default_symbol(layer.geometryType() )
        symbol.setColor(color)
        symbol.symbolLayer(0).setStrokeColor(color)
        range = QgsRendererRange(min, max, symbol, title)
        return range

    def _create_colors(self, number_of_items):
        """Returning a list of lists with RGB code, where the size of the list
         is equals the number_of_items

         Parameters
         ----------
         number_of_items: int

         Returns
         -------
         list
            list with rgb colors"""
        colors = []
        for i in range(number_of_items):
            value = float(i) / float(number_of_items)
            colors.append(rg(value))
        return colors

    def _validated_default_symbol(self, geometry_type ):
        """Validates that the symbol is of the correct type, (point, line or
        polygon and then returning a Qgis type symbol)

        Parameters
        ----------
        Qgis.geometry

        Returns
        -------
        QgsSymbol
        """
        symbol = QgsSymbol.defaultSymbol(geometry_type)
        if symbol is None:
            if geometry_type == Qgis.Point:
                symbol = QgsMarkerSymbol()
            elif geometry_type == Qgis.Line:
                symbol = QgsLineSymbol()
            elif geometry_type == Qgis.Polygon:
                symbol = QgsFillSymbol()
        return symbol

    def equal_count(self, layer, data_values_list, field, steps=10,
                    min_value=None, max_value=None):
        """

        Parameters
        ----------
        layer
        data_values_list
        field
        steps
        min_value
        max_value

        Returns
        -------

        """
        if min_value is not None:
            values = []
            for value in data_values_list:
                if value >= min_value:
                    values.append(value)
            data_values_list = values
        if max_value is not None:
            values = []
            for value in data_values_list:
                if value <= max_value:
                    values.append(value)
            data_values_list = values
        count_0 = data_values_list.count(0)
        if count_0 > 1:
            def remove_values_from_list(the_list, val):
                return [value for value in the_list if value != val]
            data_values_list = remove_values_from_list(data_values_list, 0)
            data_values_list.insert(0, 0)
        n, bins, patches = plt.hist(data_values_list,
                                    hist_edges_equal(data_values_list, steps))
        colors = self._create_colors(steps)
        range_list = []
        for i in range(steps):
            red, green, blue = colors[i]
            range_list.append(
                self._make_symbology(layer, bins[i],
                                     bins[i + 1],
                                     str(bins[i]) + ' - ' + str(
                                         bins[i + 1]),
                                     QColor(int(red * 255),
                                            int(green * 255),
                                            int(blue * 255), 128)))
        renderer = QgsGraduatedSymbolRenderer(field, range_list)
        renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
        layer.setRenderer(renderer)
        return layer

    def create_layer_style(self, layer, target_field, tbl_name, schema, min=None, max=None, steps=20):
        """Create the layer and adds the layer to the canvas

        Parameters
        ----------
        layer: QgsVectorLayer
        target_field: str
        tbl_name: str
        schema: str
        min: float, optional
        max: float, optional
        steps: int, optional default 20
        """
        if layer.isValid():
            self._apply_symbology_fixed_divisions(layer, target_field, tbl_name, schema, min, max, steps)
            QgsProject.instance().addMapLayers([layer])

    def repaint_layer(self):
        """Applies the new min and max and repaints the layer with new colors"""
        cb = self.dock_widget.mMapLayerComboBox
        layer = cb.currentLayer()
        if layer.renderer().type() == 'graduatedSymbol':
            field = layer.renderer().classAttribute()
            min_user_val = float(self.dock_widget.LEMinColor.text())
            max_user_val = float(self.dock_widget.LEMaxColor.text())
            max_nbr_user_val = float(self.dock_widget.LEMaxNbrColor.text())
            v2_step = int((max_user_val - min_user_val) / max_nbr_user_val)
            self._apply_symbology_fixed_divisions(layer, field, None, None,
                                                  min_user_val, max_user_val,
                                                  v2_step)
            layer.triggerRepaint()
        else:
            QMessageBox.information(None, self.tr("Error:"),
                                    self.tr('Only ranged layers on the map can be altered here.'))
