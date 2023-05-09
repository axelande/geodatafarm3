from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QDate
from ..import_data.handle_text_data import InputTextHandler
from ..import_data.handle_raster import ImportRaster
from ..import_data.handle_input_shp_data import InputShpHandler
from ..support_scripts.__init__ import TR
from ..support_scripts.init_checks import check_if_pyagri_is_built

if check_if_pyagri_is_built():
    from ..import_data.handle_iso11783 import Iso11783
else:
    class Iso11783:
        def __init__(self, a, b):
            pass

        def run(self):
            QMessageBox.information(None, 'ERROR',
                                    """During the first startup this program there are some third party packages that is required to be installed, 
GeoDataFarm tried to install them automatic but failed. You can try to manually install the two packages with "pip install cython"
(If you are using Windows you need to run it from the OSGeo4W shell) 
If can't get the plugin to work, don't hesitate to send an e-mail to geodatafarm@gmail.com and tell which os you are using and QGIS version.""")


class SaveFertilizing:
    def __init__(self, parent):
        """
        A class for storing plant data
        Parameters
        ----------
        parent: GeoDataFarm
        """
        self.dw = parent.dock_widget
        translate = TR('SaveFertilizing')
        self.tr = translate.tr
        self.parent = parent

    def set_widget_connections(self):
        """A simple function that sets the buttons on the planting tab"""
        self.parent.dock_widget.PBFAddFile.clicked.connect(self.run_file_import)
        self.parent.dock_widget.PBFSaveManual.clicked.connect(self.save_manual_data)

    def run_file_import(self):
        """The function loads the correct import dialog for files"""
        columns = [self.tr('Variety'), self.tr('Rate'), self.tr('Depth')]
        if self.dw.CBFFileType.currentText() == self.tr('Text file (.csv; .txt)'):
            add_f = InputTextHandler(self.parent, 'ferti', columns=columns)
            add_f.run()
        elif self.dw.CBPFileType.currentText() == self.tr('Iso Bin XML files (.xml+.bin)'):
            add_f = Iso11783(self.parent, 'ferti')
            add_f.run()
        elif self.dw.CBFFileType.currentText() == self.tr('Georeferenced Raster (.tif; .geotif)'):
            ir = ImportRaster(self.parent, self.dw.DEFertilizing, self.dw.CBFField, 'ferti')
            ir.run()
        elif self.dw.CBFFileType.currentText() == self.tr('Databasefile (.db)'):
            QMessageBox.information(None, "Error:", self.tr(
                'Support for databasefiles are not implemented 100% yet'))
            return
            self.IH = dbFileHandler(self.iface, self.dock_widget)
            self.IH.start_up()
        elif self.dw.CBFFileType.currentText() == self.tr('Shape file (.shp)'):
            shp_file = InputShpHandler(self.parent, 'ferti', columns)
            shp_file.run()

    def save_manual_data(self):
        """Saves the manual data."""
        if self.check_input():
            field = self.dw.CBFField.currentText()
            crop = self.dw.CBFCrop.currentText()
            date_ = self.dw.DEFertilizing.text()
            varerity = self.dw.LEFVarerity.text()
            rate = self.dw.LEFSeedRate.text()
            saw_depth = self.dw.LEFSawDepth.text()
            other = self.dw.LEFOther.toPlainText()
            if rate == '':
                rate = 'Null'
            if saw_depth == '':
                saw_depth = 'Null'
            if other == '':
                other = 'Null'
            sql = """Insert into ferti.manual(field, crop, date_, variety, rate, saw_depth, other, table_) 
            VALUES ('{field}', '{crop}', '{date_}','{varerity}','{rate}','{saw_depth}','{other}', 'None')
            """.format(field=field, crop=crop, date_=date_, varerity=varerity, rate=rate, saw_depth=saw_depth, other=other)
            try:
                self.parent.db.execute_sql(sql)
                QMessageBox.information(None, self.tr('Success'), self.tr('The data was stored correctly'))
            except Exception as e:
                QMessageBox.information(None, self.tr('Error'),
                                        self.tr('Following error occurred: {m}'.format(m=e)))
        self.reset_widget()

    def reset_widget(self):
        """Resets the widget to the default values"""
        self.dw.CBFField.setCurrentIndex(0)
        self.dw.CBFCrop.setCurrentIndex(0)
        self.dw.DEFertilizing.setDate(QDate.fromString('2000-01-01', 'yyyy-MM-dd'))
        self.dw.LEFVarerity.setText('')
        self.dw.LEFSeedRate.setText('')
        self.dw.LEFSawDepth.setText('')
        self.dw.LEFOther.setPlainText('')

    def check_input(self):
        """Some simple checks that ensure that the basic data is filled in.

        Returns
        -------
        bool
        """
        if self.dw.CBFField.currentText() == self.tr('--- Select field ---'):
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('In order to save the data you must select a field'))
            return False
        if self.dw.CBFCrop.currentText() == self.tr('--- Select crop ---'):
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('In order to save the data you must select a crop'))
            return False
        if self.dw.DEFertilizing.text() == '2000-01-01':
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('In order to save the data you must select a date'))
            return False
        if self.dw.LEFVarerity.text == '':
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('A variety  has to be set in order to save the data'))
            return False
        return True
