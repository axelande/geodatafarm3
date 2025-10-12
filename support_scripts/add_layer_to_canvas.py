from qgis.core import QgsProject
from PyQt5 import QtCore
from qgis.PyQt.QtWidgets import QApplication, QListWidgetItem
from ..support_scripts.create_layer import CreateLayer, add_background
from ..widgets.add_to_canvas import AddToCanvas


class AddLayerToCanvas:
    """A class that adds layers to the canvas"""
    def __init__(self, parent):
        """The function adds AddToCanvas class on self.dlg
        The function populate_widget is run with this function.

        Parameters
        ----------
        parent: object
            The GeoDataFarm parent class
        """
        self.parent = parent
        self.dlg = AddToCanvas()

        self.parameters = {}
        self.items_in_table = []

    def run(self):
        """Displays the widget and connects the button"""
        self.get_tables()
        add_background()
        if len(self.parameters) == 1:
            self.add_2_canvas(self.parameters[0])
        else:
            self.populate_widget()
            self.dlg.show()
            self.dlg.PBAddData.clicked.connect(self.add_selected)
            self.dlg.exec()

    def get_tables(self):
        """Fills the dict 'parameters' with an int as key and a dict as the value
        The value dict has following args: index_col, schema, and tbl_name"""
        self.items_in_table = self.parent.populate.get_items_in_table()
        self.parameters = {}
        ins = -1
        for list_widget, schema, lw in self.items_in_table:
            tables = []
            for item in list_widget:
                if item.checkState() == 2:
                    tables.append(str(item.text()))
            temp_d = self.parent.db.get_indexes(', '.join("'" + str(e) + "'" for e in tables)[1:-1], schema)
            for key in temp_d.keys():
                if temp_d[key]['index_col'] == 'field_row_id':
                    continue
                ins += 1
                self.parameters[ins] = temp_d[key]

    def add_2_canvas(self, data):
        """Adds the parameter to the canvas

        Parameters
        ----------
        data: dict
            A dict containing index_col, tbl_name, schema
        """
        target_field = data['index_col']
        tbl_name = data['tbl_name']
        schema = data['schema']
        if schema == 'harvest':
            layer = self.parent.db.add_postgis_layer(tbl_name.lower(),
                                                   geom_col='pos', schema='harvest',
                                                   extra_name='harvest')
        else:
            layer = self.parent.db.add_postgis_layer(tbl_name.lower(), 'polygon', schema,
                                                   str(target_field.lower()))
        create_layer = CreateLayer(self.parent.db)
        create_layer.create_layer_style(layer, target_field, tbl_name.lower(), schema)
        QgsProject.instance().addMapLayer(layer)

    def populate_widget(self):
        """For all selected data sets in the GeoDataFarm widget adds all column names
        to a ListWidget except if there is only one, then it is directly added to the
        canvas."""
        self.dlg.LWAttributes.clear()
        for nr in range(len(self.parameters)):
            target_field = self.parameters[nr]['index_col']
            tbl_name = self.parameters[nr]['tbl_name']
            item_name = tbl_name + '_' + target_field
            _name = QApplication.translate("qadashboard", item_name, None)
            item = QListWidgetItem(_name, self.dlg.LWAttributes)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)

    def add_selected(self):
        """All checked items in the ListWidget is added to the canvas. Afterwards the button
        becomes disconnected and this widget closes"""
        lw = self.dlg.LWAttributes.findItems('', QtCore.Qt.MatchContains)
        if len(self.parameters) == 0:
            self.get_tables()
        for i, item in enumerate(lw):
            if item.checkState() == 2:
                self.add_2_canvas(self.parameters[i])
        self.dlg.PBAddData.disconnect()
        self.dlg.done(0)
