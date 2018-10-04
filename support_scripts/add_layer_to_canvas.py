from qgis.core import QgsProject
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QListWidgetItem
from ..support_scripts.create_layer import CreateLayer
from ..widgets.add_to_canvas import AddToCanvas


class AddLayerToCanvas:
    def __init__(self, parent):
        self.parent = parent
        self.dlg = AddToCanvas()
        self.populate_widget()
        self.parameters = {}

    def run(self):
        self.dlg.show()
        self.dlg.PBAddData.clicked.connect(self.add_selected)
        self.dlg.exec_()

    def get_tables(self):
        self.parent.items_in_table = self.parent.populate.get_items_in_table()
        parameters = {}
        ins = -1
        for list_widget, schema, lw in self.parent.items_in_table:
            tables = []
            for item in list_widget:
                if item.checkState() == 2:
                    tables.append(str(item.text()))
            temp_d = self.parent.db.get_indexes(', '.join("'" + str(e) + "'" for e in tables)[1:-1], schema)
            for key in temp_d.keys():
                if temp_d[key]['index_col'] == 'field_row_id':
                    continue
                ins += 1
                parameters[ins] = temp_d[key]
        return parameters

    def populate_widget(self):
        # TODO: If only one attribute add directly to canvas.
        self.dlg.LWAttributes.clear()
        self.parameters = self.get_tables()
        for nr in range(len(self.parameters)):
            target_field = self.parameters[nr]['index_col']
            tbl_name = self.parameters[nr]['tbl_name']
            item_name = tbl_name + '_' + target_field
            _name = QApplication.translate("qadashboard", item_name, None)
            item = QListWidgetItem(_name, self.dlg.LWAttributes)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)

    def add_selected(self):
        lw = self.dlg.LWAttributes.findItems('', QtCore.Qt.MatchContains)
        self.parameters = self.get_tables()
        for i, item in enumerate(lw):
            if item.checkState() == 2:
                target_field = self.parameters[i]['index_col']
                tbl_name = self.parameters[i]['tbl_name']
                if self.parameters[i]['schema'] == 'harvest':
                    layer = self.parent.db.addPostGISLayer(tbl_name.lower(),
                                                    geom_col='pos', schema='harvest',
                                                    extra_name='harvest')
                else:
                    layer = self.parent.db.addPostGISLayer(tbl_name.lower(), 'polygon', self.parameters[i]['schema'],
                                                    str(target_field.lower()))
                create_layer = CreateLayer(self.parent.db)
                create_layer.create_layer_style(layer, target_field, tbl_name.lower(), self.parameters[i]['schema'])
                QgsProject.instance().addMapLayer(layer)
        self.dlg.PBAddData.disconnect()
        self.dlg.done(0)
