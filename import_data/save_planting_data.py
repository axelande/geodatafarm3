from typing import Self
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate

from ..import_data.handle_text_data import InputTextHandler
from ..import_data.handle_raster import ImportRaster
from ..import_data.handle_input_shp_data import InputShpHandler
from ..support_scripts.__init__ import TR
from ..import_data.handle_iso11783 import Iso11783


class SavePlanting:
    def __init__(self: Self, parent) -> None:
        """A class for storing plant data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SavePlanting')
        self.tr = translate.tr
        self.parent = parent
        self.importer = None

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBPAddFile.clicked.connect(self.run_file_import)
        self.parent.dock_widget.PBPSaveManual.clicked.connect(self.save_manual_data)

    def run_file_import(self: Self) -> None:
        """The function loads the correct import dialog for files"""
        columns = [self.tr('Variety')]
        if self.dw.CBPFileType.currentText() == self.tr('Text file (.csv; .txt)'):
            self.importer = InputTextHandler(self.parent, 'plant', columns=columns)
            self.importer.run()

        elif self.dw.CBPFileType.currentText() == self.tr('Iso Bin XML files (.xml+.bin)'):
            self.importer = Iso11783(self.parent, 'plant')
            self.importer.run()

        elif self.dw.CBPFileType.currentText() == self.tr('Databasefile (.db)'):
            QMessageBox.information(None, "Error:", self.tr(
                'Support for databasefiles are not implemented 100% yet'))
            return
        elif self.dw.CBPFileType.currentText() == self.tr('Shape file (.shp)'):
            self.importer = InputShpHandler(self.parent, 'planting', columns)
            self.importer.run()
        elif self.dw.CBFFileType.currentText() == self.tr('Georeferenced Raster (.tif; .geotif)'):
            self.importer = ImportRaster(self.parent, self.dw.DEPlanting, self.dw.CBPField, 'plant')
            self.importer.run()

    def save_manual_data(self):
        """Saves the manual data"""
        if self.check_input():
            field = self.dw.CBPField.currentText()
            crop = self.dw.CBPCrop.currentText()
            date_ = self.dw.DEPlanting.selectedDate().toString("yyyy-MM-dd")
            varerity  = self.dw.LEPVarerity.text()
            spacing = self.dw.LEPSpacing.text()
            seed_rate = self.dw.LEPSeedRate.text()
            saw_depth = self.dw.LEPSawDepth.text()
            other = self.dw.LEPOther.toPlainText()
            if spacing == '':
                spacing = 'Null'
            if seed_rate == '':
                seed_rate = 'Null'
            if saw_depth == '':
                saw_depth = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into plant.manual(field, crop, date_, variety, spacing, seed_rate, saw_depth, other, table_) 
            VALUES ('{field}', '{crop}', '{date_}','{varerity}','{spacing}','{seed_rate}','{saw_depth}','{other}', 'None')
            """.format(field=field, crop=crop, date_=date_, varerity=varerity, spacing=spacing, seed_rate=seed_rate,
                       saw_depth=saw_depth, other=other)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
                self.dw.CBPField.setCurrentIndex(0)
                self.dw.CBPCrop.setCurrentIndex(0)
                self.dw.LEPVarerity.setText('')
                self.dw.LEPSpacing.setText('')
                self.dw.LEPSeedRate.setText('')
                self.dw.LEPSawDepth.setText('')
                self.dw.LEPOther.setPlainText('')
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBPField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.CBPCrop.currentText() == self.tr('--- Select crop ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a crop'))
            return False
        if self.dw.DEPlanting.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        if self.dw.LEPVarerity.text == '':
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('A variety  has to be set in order to save the data'))
            return False
        return True
