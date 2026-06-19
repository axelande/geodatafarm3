from typing import Self
from ..import_data.handle_text_data import InputTextHandler
from ..import_data.handle_raster import ImportRaster
from ..import_data.handle_input_shp_data import InputShpHandler
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate
from ..support_scripts.__init__ import TR
from ..support_scripts.notifier import report_success, report_warning, report_error, report_info


class SaveSoil:
    def __init__(self: Self, parent) -> None:
        """A class for storing spraying data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SaveSoil')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self: Self) -> None:
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBSoAddFile.clicked.connect(self.run_file_import)
        self.parent.dock_widget.PBSoSaveManual.clicked.connect(self.save_manual_data)

    def run_file_import(self):
        """The function loads the correct import dialog for files"""
        columns = [self.tr('Clay'), self.tr('Humus'), self.tr('pH'), self.tr('rx')]
        if self.dw.CBSoFileType.currentText() == self.tr('Text file (.csv; .txt)'):
            add_f = InputTextHandler(self.parent, 'soil', columns=columns)
            add_f.run()
        elif self.dw.CBSoFileType.currentText() == self.tr('Databasefile (.db)'):
            report_info(self.tr(
                'Support for databasefiles are not implemented 100% yet'))
            return
        elif self.dw.CBSoFileType.currentText() == self.tr('Shape file (.shp)'):
            shp_file = InputShpHandler(self.parent, 'soil', columns)
            shp_file.run()
        elif self.dw.CBFFileType.currentText() == self.tr('Georeferenced Raster (.tif; .geotif)'):
            ir = ImportRaster(self.parent, self.dw.DESoil, self.dw.CBSoField, 'soil')
            ir.run()

    def save_manual_data(self):
        """Saves the manual data."""
        if self.check_input():
            field = self.dw.CBSoField.currentText()
            date_ = self.dw.DESoil.selectedDate().toString("yyyy-MM-dd")
            clay = self.dw.LESoClay.text()
            humus = self.dw.LESoHumus.text()
            ph = self.dw.LESoPh.text()
            rx = self.dw.LESoRx.text()
            other = self.dw.LESoOther.toPlainText()
            clay = clay or None
            humus = humus or None
            ph = ph or None
            rx = rx or None
            other = other or None
            sql = ("INSERT INTO soil.manual"
                   " (field, date_, clay, humus, ph, rx, other, table_)"
                   " VALUES (%s, %s, %s, %s, %s, %s, %s, 'None')")
            try:
                self.parent.db.execute_sql(sql, params=(
                    field, date_, clay, humus, ph, rx, other))
                report_success(self.tr('The data was stored correctly'))
            except Exception as e:
                report_error(self.tr(f'Following error occurred: {e}'), detail=str(e))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBSoField.setCurrentIndex(0)
        self.dw.LESoClay.setText('')
        self.dw.LESoHumus.setText('')
        self.dw.LESoPh.setText('')
        self.dw.LESoRx.setText('')
        self.dw.LESoOther.setPlainText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBSoField.currentText() == self.tr('--- Select field ---'):
            report_warning(self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.DESoil.selectedDate().toString("yyyy-MM-dd") == '2000-01-01':
            report_warning(self.tr('In order to save the data you must select a date'))
            return False
        return True
