from ..import_data.handle_input_shp_data import InputShpHandler
from ..import_data.handle_text_data import InputTextHandler
from ..import_data.handle_raster import ImportRaster
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate


class SaveSpraying:
    def __init__(self, parent):
        """A class for storing spraying data

        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        self.tr = parent.tr
        self.parent = parent

    def set_widget_connections(self):
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBSpAddFile.clicked.connect(self.run_file_import)
        self.parent.dock_widget.PBSpSaveManual.clicked.connect(self.save_manual_data)

    def run_file_import(self):
        """The function loads the correct import dialog for files"""
        columns = [self.tr('Variety'), self.tr('Rate'), self.tr('Depth')]
        if self.dw.CBSpFileType.currentText() == self.tr('Text file (.csv; .txt)'):
            add_f = InputTextHandler(self.parent, 'spray', columns=columns)
            add_f.run()
        elif self.dw.CBSpFileType.currentText() == self.tr('Databasefile (.db)'):
            QMessageBox.information(None, "Error:", self.tr(
                'Support for databasefiles are not implemented 100% yet'))
            return
            self.IH = dbFileHandler(self.iface, self.dock_widget)
            self.IH.start_up()
        elif self.dw.CBSpFileType.currentText() == self.tr('Shape file (.shp)'):
            shp_file = InputShpHandler(self.parent, 'spraying', columns)
            shp_file.run()
        elif self.dw.CBFFileType.currentText() == self.tr('Georeferenced Raster (.tif; .geotif)'):
            if self.check_input(variety_check=False):
                ir = ImportRaster(self.parent, self.dw.DESpraying, self.dw.CBSpField, 'spray')
                ir.run()

    def save_manual_data(self):
        """Saves the manual data."""
        if self.check_input():
            field = self.dw.CBSpField.currentText()
            crop = self.dw.CBSpCrop.currentText()
            date_ = self.dw.DESpraying.text()
            varerity = self.dw.LESpVarerity.text()
            rate = self.dw.LESpRate.text()
            wind_speed = self.dw.LESpWindSpeed.text()
            wind_dir = self.dw.LESpWindDir.text()
            other = self.dw.LESpOther.toPlainText()
            if rate == '':
                rate = 'Null'
            if wind_speed == '':
                wind_speed = 'Null'
            if wind_dir == '':
                wind_dir = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into spray.manual(field, crop, date_, variety, rate, wind_speed, wind_dir, other, table_) 
            VALUES ('{field}', '{crop}', '{date_}','{varerity}','{rate}','{wind_speed}','{wind_dir}','{other}', 'None')
            """.format(field=field, crop=crop, date_=date_, varerity=varerity, rate=rate, wind_speed=wind_speed,
                       wind_dir=wind_dir, other=other)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBSpField.setCurrentIndex(0)
        self.dw.CBSpCrop.setCurrentIndex(0)
        self.dw.DESpraying.setDate(QDate.fromString('2000-01-01', 'yyyy-MM-dd'))
        self.dw.LESpVarerity.setText('')
        self.dw.LESpRate.setText('')
        self.dw.LESpWindSpeed.setText('')
        self.dw.LESpWindDir.setText('')
        self.dw.LESpOther.setPlainText('')

    def check_input(self, variety_check=True):
        """Some simple checks that ensure that the basic data is filled in.

        Parameters
        ----------
        variety_check: bool

        Returns
        -------
        bool
        """
        if self.dw.CBSpField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.CBSpCrop.currentText() == self.tr('--- Select crop ---'):
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a crop'))
            return False
        if self.dw.DESpraying.text() == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'), self.tr('In order to save the data you must select a date'))
            return False
        if variety_check and self.dw.LESpVarerity.text == '':
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('A variety  has to be set in order to save the data'))
            return False
        return True
