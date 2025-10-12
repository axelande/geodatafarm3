from typing import TYPE_CHECKING, Self
if TYPE_CHECKING:
    import PyQt5.QtWidgets
from qgis.core import QgsProject, QgsVectorLayer, QgsApplication
from PyQt5 import QtCore, QtGui
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QApplication, QListWidgetItem
from ..support_scripts.__init__ import TR


class Populate:
    """A class to set/reload list widgets and comboBoxes"""
    def __init__(self: Self, parent) -> None:
        """Starts/resets the class and all its objects,
        calls: - reload_fields,
               - reload_crops,
               - update_table_list
        Parameters
        ----------
        parent: GeoDataFarm class
        """
        self.plugin_dir = parent.plugin_dir
        self.dw = parent.dock_widget
        self.db = parent.db
        translate = TR('Populate')
        self.tr = translate.tr
        self.items_in_table = [[None, '', None], [None, '', None], [None, '', None], [None, '', None],
                               [None, '', None], [None, '', None], [None, '', None]]
        self.tables_in_db = [0, 0, 0, 0, 0, 0, 0]
        self.fields = [self.tr('--- Select field ---')]
        self.crops = [self.tr('--- Select crop ---')]
        self.lw_list = [[self.dw.LWPlantingTable, 'plant'],
                   [self.dw.LWHarvestTable, 'harvest'],
                   [self.dw.LWSprayingTable, 'spray'],
                   [self.dw.LWFertiTable, 'ferti'],
                   [self.dw.LWSoilTable, 'soil'],
                   [self.dw.LWOtherTable, 'other'],
                   [self.dw.LWWeatherTable, 'weather']]
        self.reload_fields()
        self.reload_crops()
        #self.update_table_list()

    def get_items_in_table(self):
        """Returns the list of list 'items in table'
        Returns
        -------
        list"""
        return self.items_in_table

    def get_lw_list(self: Self) -> list[list[str]]:
        """ Function returns the list of lists with [[ListWidget, 'name']]
        Returns
        -------
        list
        """
        return self.lw_list

    def reload_fields(self: Self, cmd_box: "PyQt5.QtWidgets.QComboBox|None|None"=None) -> None:
        """Reloads all field comboBoxes in the GeoDataFarm widget
        Parameters
        ----------
        cmd_box: QtComboBox, optional
            a comboBox to fill with the field names (used in text_data_handler)"""
        if cmd_box is None:
            cmd_box = [self.dw.CBPField,
                       self.dw.CBFField,
                       self.dw.CBSpField,
                       self.dw.CBOField,
                       self.dw.CBHvField,
                       self.dw.CBPloField,
                       self.dw.CBHwField,
                       self.dw.CBIField,
                       self.dw.CBSoField]
            fields = self.db.get_distinct('fields', 'field_name', 'public')
            lw = self.dw.LWFields
            lw.clear()
            for box in cmd_box:
                box.clear()
            for field_name in fields:
                _na = QApplication.translate("qadashboard", field_name[0], None)
                item = QListWidgetItem(_na, self.dw.LWFields)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
        else:
            cmd_box = [cmd_box]
        fields_ = self.db.execute_and_return("select field_name from fields order by field_name")
        fields = []
        for field in fields_:
            fields.append(field[0])
        for i, lw in enumerate(cmd_box):
            if len(self.fields) > 1:
                lw.clear()
            lw.addItem(self.tr('--- Select field ---'))
            for name in fields:
                lw.addItem(str(name))
        self.fields = [self.tr('--- Select field ---')]
        self.fields.extend(fields)

    def reload_crops(self: Self, cmd_box: "PyQt5.QtWidgets.QComboBox|None|None"=None) -> None:
        """Reloads all crops comboBoxes in the GeoDataFarm widget
        Parameters
        ----------
        cmd_box: QtComboBox, optional
            a comboBox to fill with the crop names (used in text_data_handler)"""
        if cmd_box is None:
            cmd_box = [self.dw.CBPCrop,
                       self.dw.CBFCrop,
                       self.dw.CBSpCrop,
                       self.dw.CBOCrop,
                       self.dw.CBHvCrop]
            crops = self.db.get_distinct('crops', 'crop_name', 'public')
            lw = self.dw.LWCrops
            lw.clear()
            for box in cmd_box:
                box.clear()
            for crop_name in crops:
                _nam = QApplication.translate("qadashboard", crop_name[0], None)
                item = QListWidgetItem(_nam, self.dw.LWCrops)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
        else:
            cmd_box = [cmd_box]
        crops_ = self.db.execute_and_return("select crop_name from crops order by crop_name")
        crops = []
        for crop in crops_:
            crops.append(crop[0])
        for i, lw in enumerate(cmd_box):
            if len(self.crops) > 1:
                lw.clear()
            lw.addItem(self.tr('--- Select crop ---'))
            for name in crops:
                lw.addItem(str(name))
        self.crops = [self.tr('--- Select crop ---')]
        self.crops.extend(crops)

    def update_table_list(self: Self) -> None:
        """Update the list of tables in the docket widget"""
        for i, (lw, schema) in enumerate(self.lw_list):
            table_names = self.db.get_tables_in_db(schema)
            # If already added, starts with cleaning the lw
            if self.tables_in_db[i] != 0:
                lw.clear()
            self.tables_in_db[i] = 0
            for name in table_names:
                if name in ["spatial_ref_sys", "pointcloud_formats",
                               "temp_polygon", "manual", "plowing_manual", "harrowing_manual"]:
                    continue
                if self.dw.RBSpecificYear.isChecked():
                    year = self.dw.DEYear.text()
                    if schema != 'soil' and year not in name:
                        continue
                _name = QApplication.translate("qadashboard", name, None)
                item = QListWidgetItem(_name, lw)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.tables_in_db[i] += 1
            self.items_in_table[i][0] = lw.findItems('', QtCore.Qt.MatchContains)
            self.items_in_table[i][1] = schema
            self.items_in_table[i][2] = lw
