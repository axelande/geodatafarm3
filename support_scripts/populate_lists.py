from qgis.core import QgsProject, QgsVectorLayer, QgsApplication
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from PyQt5.QtWidgets import QAction, QMessageBox, QApplication, QListWidgetItem


class Populate:
    def __init__(self, parent):
        self.plugin_dir = parent.plugin_dir
        self.dw = parent.dock_widget
        self.db = parent.db
        self.items_in_table = [[None, ''], [None, ''], [None, ''], [None, ''], [None, ''], [None, ''], [None, '']]
        self.tables_in_db = [0, 0, 0, 0, 0, 0, 0]
        self.fields = ['--- Select field ---']
        self.crops = ['--- Select crop ---']
        self.reload_all()
        self.update_table_list()

    def refresh(self, db):
        self.db = db

    def get_items_in_table(self):
        return self.items_in_table

    def reload_all(self):
        self.reload_fields()
        self.reload_crops()

    def reload_fields(self):
        cmdboxes = [[self.dw.CBPField, 'planting'],
                    [self.dw.CBFField, 'fertilising'],
                    [self.dw.CBSpField, 'spraying'],
                    [self.dw.CBCField, 'cultivating'],
                    [self.dw.CBHvField, 'harvest'],
                    [self.dw.CBPloField, 'plowing'],
                    [self.dw.CBHwField, 'harrowing'],
                    [self.dw.CBIField, 'irrigation'],
                    [self.dw.CBSoField, 'soil']]
        fields_ = self.db.execute_and_return("select field_name from fields order by field_name")
        fields = []
        for field in fields_:
            fields.append(field[0])
        for i, (lw, name_type) in enumerate(cmdboxes):
            if len(self.fields) > 1:
                lw.clear()
            for name in fields:
                lw.addItem(str(name))
        self.fields = ['--- Select field ---']
        self.fields.extend(fields)

    def reload_crops(self):
        cmdboxes = [[self.dw.CBPCrop, 'planting'],
                    [self.dw.CBFCrop, 'fertilising'],
                    [self.dw.CBSpCrop, 'spraying'],
                    [self.dw.CBCCrop, 'cultivating'],
                    [self.dw.CBHvCrop, 'harvest']]
        crops_ = self.db.execute_and_return("select crop_name from crops order by crop_name")
        crops = []
        for crop in crops_:
            crops.append(crop[0])
        for i, (lw, name) in enumerate(cmdboxes):
            if len(self.crops) > 1:
                lw.clear()
            for name in crops:
                lw.addItem(str(name))
        self.crops = ['--- Select Crop ---']
        self.crops.extend(crops)

    def update_table_list(self):
        """Update the list of tables in the docket widget"""
        lw_list = [[self.dw.LWPlantingTable, 'plant'],
                   [self.dw.LWHarvestTable, 'harvest'],
                   [self.dw.LWSoilTable, 'soil'],
                   [self.dw.LWSprayingTable, 'spray'],
                   [self.dw.LWFertiTable, 'ferti'],
                   [self.dw.LWOtherTable, 'other'],
                   [self.dw.LWWeatherTable, 'weather']]
        for i, (lw, schema) in enumerate(lw_list):
            table_names = self.db.get_tables_in_db(schema)
            if self.tables_in_db[i] != 0:
                model = lw.model()
                for item in self.items_in_table[i][0]:
                    q_index = lw.indexFromItem(item)
                    model.removeRow(q_index.row())
            self.tables_in_db[i] = 0
            for name in table_names:
                if name[0] in ["spatial_ref_sys", "pointcloud_formats",
                               "temp_polygon"]:
                    continue
                item_name = str(name[0])
                _name = QApplication.translate("qadashboard", item_name, None)
                item = QListWidgetItem(_name, lw)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.tables_in_db[i] += 1
            self.items_in_table[i][0] = lw.findItems('', QtCore.Qt.MatchContains)
            self.items_in_table[i][1] = schema
        lw = self.dw.LWCrops
        model = lw.model()
        counted = lw.count()
        for item in range(counted):
            q_index = lw.indexFromItem(item)
            model.removeRow(q_index.row())
        crops = self.db.get_distinct('crops', 'crop_name', 'public')
        for crop_name in crops:
            _name = QApplication.translate("qadashboard", crop_name[0], None)
            item = QListWidgetItem(_name, self.dw.LWCrops)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
        fields = self.db.get_distinct('fields', 'field_name', 'public')
        lw = self.dw.LWFields
        lw.clear()
        for field_name in fields:
            _name = QApplication.translate("qadashboard", field_name[0], None)
            item = QListWidgetItem(_name, self.dw.LWFields)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)

        crops = self.db.get_distinct('crops', 'crop_name', 'public')
        lw = self.dw.LWCrops
        lw.clear()
        for crop_name in crops:
            _name = QApplication.translate("qadashboard", crop_name[0], None)
            item = QListWidgetItem(_name, self.dw.LWCrops)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked)
