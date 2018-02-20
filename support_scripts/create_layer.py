import RG
from qgis.core import QgsSymbolV2, QGis, QgsMarkerSymbolV2, QgsRendererRangeV2,\
    QgsLineSymbolV2, QgsFillSymbolV2, QgsGraduatedSymbolRendererV2, \
    QgsMapLayerRegistry, QgsRendererCategoryV2, QgsCategorizedSymbolRendererV2
from PyQt5.QtGui import QColor
import numpy as np
__author__ = 'Axel'


class CreateLayer:
    def __init__(self, db, dock_widget=None):
        """Creates a layer with color coded attributes"""
        self.DB = db
        self.dock_widget = dock_widget

    def _apply_symbology_fixed_divisions(self, layer, field, tbl_name, schema,
                                         min_v, max_v, steps):
        """Finds the amount of levels that is necessary to describe the layer,
        a maximum of 20 different levels is set"""
        if min_v is not None and max_v is not None:
            distinct_values = list(np.arange(min_v, max_v, steps))
        else:
            distinct = self.DB.get_distinct(tbl_name, field, schema)
            distinct_values = []
            distinct_count = []
            for value, count in distinct:
                distinct_values.append(value)
                distinct_count.append(count)
            if len(distinct_values) > 20:
                distinct_values.sort()
                temp_list = []
                for val in range(0, len(distinct_values), int(round(len(distinct_values)/20))):
                    temp_list.append(distinct_values[val])
                distinct_values = temp_list

        colors = self._create_colors(len(distinct_values))
        try:
            range_list = []
            for i in range(len(distinct_values) - 1):
                red, green, blue = colors[i]
                range_list.append(self._make_symbology(layer, distinct_values[i],
                                                     distinct_values[i + 1],
                                                     str(distinct_values[i]) + ' - ' + str(distinct_values[i + 1]),
                                                     QColor(int(red*255),int(green*255), int(blue*255), 128) ) )
            renderer = QgsGraduatedSymbolRendererV2(field, range_list)
            renderer.setMode(QgsGraduatedSymbolRendererV2.Custom )
        except TypeError:
            categories = []
            for i in range(len(distinct_values)):
                symbol = QgsSymbolV2.defaultSymbol(layer.geometryType())
                red, green, blue = colors[i]
                symbol.setColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                symbol.symbolLayer(0).setOutlineColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                category = QgsRendererCategoryV2(str(distinct_values[i]), symbol, str(distinct_values[i]))
                categories.append(category)
            renderer = QgsCategorizedSymbolRendererV2(field, categories)
            #renderer.setMode(QgsCategorizedSymbolRendererV2.Custom)
        layer.setRendererV2(renderer)

    def _make_symbology(self, layer, min , max, title, color):
        """Creates the symbols and sets the coloring of the layer"""
        symbol = self._validated_default_symbol(layer.geometryType() )
        symbol.setColor(color)
        symbol.symbolLayer(0).setOutlineColor(color)
        range = QgsRendererRangeV2(min, max, symbol, title)
        return range

    def _create_colors(self, number_of_items):
        """Returning a list of lists with RGB code, where the size of the list
         is equals the number_of_items"""
        colors = []
        for i in range(number_of_items):
            value = float(i) / float(number_of_items)
            colors.append(RG.rg(value))
        return colors

    def _validated_default_symbol(self, geometryType ):
        """Validates that the symbol is of the correct type, (point, line or
        polygon and then returning a Qgis type symbol)"""
        symbol = QgsSymbolV2.defaultSymbol( geometryType )
        if symbol is None:
            if geometryType == QGis.Point:
                symbol = QgsMarkerSymbolV2()
            elif geometryType == QGis.Line:
                symbol =  QgsLineSymbolV2()
            elif geometryType == QGis.Polygon:
                symbol = QgsFillSymbolV2()
        return symbol

    def create_layer_style(self, layer, target_field, tbl_name, schema, min=None, max=None, steps=None):
        """Create the layer and adds the layer to the canvas"""
        if layer.isValid():
            self._apply_symbology_fixed_divisions(layer, target_field, tbl_name, schema, min, max, steps)
            QgsMapLayerRegistry.instance().addMapLayers([layer])

    def repaint_layer(self):
        cb = self.dock_widget.mMapLayerComboBox
        layer = cb.currentLayer()
        field = layer.rendererV2().classAttribute()
        min_user_val = float(self.dock_widget.LEMinColor.text())
        max_user_val = float(self.dock_widget.LEMaxColor.text())
        max_nbr_user_val = float(self.dock_widget.LEMaxNbrColor.text())
        v2_step = int((max_user_val - min_user_val) / max_nbr_user_val)
        self._apply_symbology_fixed_divisions(layer, field, None, None,
                                              min_user_val, max_user_val,
                                              v2_step)
        layer.triggerRepaint()